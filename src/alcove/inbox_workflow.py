from __future__ import annotations

from pathlib import Path
import shutil

from alcove.inbox_models import InboxNoteRequest, InboxPost, InboxProcessResult
from alcove.knowledge import KnowledgeModule
from alcove.knowledge import NoteSourceRequest
from alcove.markdown import normalize_slug
from alcove.workspace import Workspace


class InboxPromotionWorkflow:
    def __init__(self, workspace: Workspace, knowledge: KnowledgeModule) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.knowledge = knowledge

    def note(self, post: InboxPost, request: InboxNoteRequest) -> InboxProcessResult:
        archive_path = self._archive_post(post, request.topic)
        archive_reference = self._legacy_path(archive_path)
        tags = self._resolve_tags(
            post,
            request.topic,
            request.tags,
            request.no_auto_tags,
        )
        confidence = self._score_confidence(post)
        supersedes = self._similar_sources_to_supersede(
            post,
            request.topic,
            request.summary,
            confidence["confidence"],
            request.supersede_similar,
        )
        try:
            result = self.knowledge.note_source(
                NoteSourceRequest(
                    platform=post.platform,
                    title=post.title or post.name,
                    topic=request.topic,
                    resource=post.source or archive_reference,
                    summary=request.summary,
                    tags=tags,
                    published_date=post.date,
                    legacy_path=archive_reference,
                    create_concept=True,
                    human_notes=self._human_notes(request),
                    confidence=confidence["confidence"],
                    status="active",
                    supersedes=supersedes,
                    last_verified=post.date,
                )
            )
        except Exception:
            self._rollback_archive(post, archive_path)
            raise
        superseded = self._mark_superseded(result.source_path, supersedes)
        return InboxProcessResult(
            archive_path,
            result.source_path,
            result.concept_path,
            tags=tags,
            confidence=confidence,
            superseded=superseded,
        )

    def archive(
        self,
        post: InboxPost,
        topic: str,
        summary: str = "",
        tags: list[str] | None = None,
        no_auto_tags: bool = False,
        supersede_similar: bool = False,
    ) -> InboxProcessResult:
        archive_path = self._archive_post(post, topic)
        archive_reference = self._legacy_path(archive_path)
        resolved_tags = tags or self._resolve_tags(post, topic, [], no_auto_tags)
        confidence = self._score_confidence(post)
        supersedes = self._similar_sources_to_supersede(
            post,
            topic,
            summary or post.content[:500],
            confidence["confidence"],
            supersede_similar,
        )
        try:
            result = self.knowledge.note_source(
                NoteSourceRequest(
                    platform=post.platform,
                    title=post.title or post.name,
                    topic=topic,
                    resource=post.source or archive_reference,
                    summary=summary or post.content,
                    tags=resolved_tags,
                    published_date=post.date,
                    legacy_path=archive_reference,
                    create_concept=False,
                    confidence=confidence["confidence"],
                    status="active",
                    supersedes=supersedes,
                    last_verified=post.date,
                )
            )
        except Exception:
            self._rollback_archive(post, archive_path)
            raise
        superseded = self._mark_superseded(result.source_path, supersedes)
        return InboxProcessResult(
            archive_path,
            result.source_path,
            result.concept_path,
            tags=resolved_tags,
            confidence=confidence,
            superseded=superseded,
        )

    def _archive_post(self, post: InboxPost, topic: str) -> Path:
        topic_dir = self.paths.archive / self._archive_topic_slug(topic)
        topic_dir.mkdir(parents=True, exist_ok=True)
        dest = self._unique_folder_path(topic_dir / f"[{post.platform}] {post.name}")
        shutil.move(str(post.path), str(dest))
        return dest

    def _unique_folder_path(self, path: Path) -> Path:
        dest = path
        counter = 2
        original = path
        while dest.exists():
            dest = Path(f"{original}-{counter}")
            counter += 1
        return dest

    def _rollback_archive(self, post: InboxPost, archive_path: Path) -> None:
        if not archive_path.exists() or post.path.exists():
            return
        post.path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(archive_path), str(post.path))

    def _archive_topic_slug(self, topic: str) -> str:
        return normalize_slug(topic.rsplit("/", 1)[-1])

    def _legacy_path(self, path: Path) -> str:
        try:
            return path.relative_to(self.paths.root).as_posix()
        except ValueError:
            return str(path)

    def _resolve_tags(
        self,
        post: InboxPost,
        topic: str,
        tags: list[str],
        no_auto_tags: bool,
    ) -> list[str]:
        if tags:
            return tags
        if no_auto_tags:
            return []
        from alcove.classify import ClassifyModule

        return ClassifyModule(self.workspace).suggest_tags(post, topic)

    def _score_confidence(self, post: InboxPost) -> dict:
        from alcove.lifecycle import score_confidence

        score = score_confidence(post)
        return {
            "confidence": score.confidence,
            "signals": score.signals,
            "details": score.details,
        }

    def _similar_sources_to_supersede(
        self,
        post: InboxPost,
        topic: str,
        summary: str,
        confidence: float,
        enabled: bool,
    ) -> list[str]:
        if not enabled:
            return []
        from alcove.lifecycle import LifecycleModule

        similar = LifecycleModule(self.workspace).find_similar_sources(
            topic,
            post.title,
            summary or post.content[:500],
        )
        return [item.rel for item in similar if item.confidence < confidence]

    def _mark_superseded(self, source_path: Path, supersedes: list[str]) -> list[str]:
        if not supersedes:
            return []
        from alcove.lifecycle import LifecycleModule

        source_ref = source_path.relative_to(self.paths.knowledge).as_posix()
        return LifecycleModule(self.workspace).mark_superseded(supersedes, source_ref)

    def _human_notes(self, request: InboxNoteRequest) -> dict[str, object]:
        notes: dict[str, object] = {}
        if request.selected_takeaways:
            notes["selected_takeaways"] = request.selected_takeaways
        for key in ("why", "connection", "action", "personal_note"):
            value = getattr(request, key)
            if value:
                notes[key] = value
        return notes
