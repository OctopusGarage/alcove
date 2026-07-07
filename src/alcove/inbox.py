from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil

from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.markdown import normalize_slug
from alcove.workspace import Workspace


PLATFORM_READ_ORDER = {
    "wechat": ("article.md", "post.md", "ocr-merge.txt"),
    "xhs": ("summary.md", "ocr-merge.txt", "post.md"),
    "x": ("post.md", "ocr-merge.txt", "summary.md"),
    "web": ("article.md", "summary.md", "post.md"),
    "fallback": ("post.md", "summary.md", "article.md", "ocr-merge.txt"),
}


@dataclass(frozen=True)
class InboxPost:
    name: str
    path: Path
    platform: str
    title: str
    source: str | None
    date: str | None
    content: str
    content_source: str


@dataclass(frozen=True)
class InboxNoteRequest:
    name: str
    topic: str
    summary: str
    tags: list[str] = field(default_factory=list)
    selected_takeaways: list[str] = field(default_factory=list)
    why: str = ""
    connection: str = ""
    action: str = ""
    personal_note: str = ""
    no_auto_tags: bool = False
    supersede_similar: bool = False


@dataclass(frozen=True)
class InboxProcessResult:
    archive_path: Path
    source_path: Path
    concept_path: Path | None
    tags: list[str] = field(default_factory=list)
    confidence: dict | None = None
    superseded: list[str] = field(default_factory=list)


class InboxModule:
    def __init__(self, workspace: Workspace, knowledge: KnowledgeModule | None = None) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.knowledge = knowledge or KnowledgeModule(workspace)

    def peek(self) -> InboxPost | None:
        entries = self._entries()
        if not entries:
            return None
        return self._read_path(entries[0])

    def read(self, name: str) -> InboxPost:
        return self._read_path(self._find_entry(name))

    def note(self, request: InboxNoteRequest) -> InboxProcessResult:
        post = self.read(request.name)
        archive_path = self._archive_post(post, request.topic)
        archive_reference = self._legacy_path(archive_path)
        tags = self._resolve_tags(post, request.topic, request.tags, request.no_auto_tags)
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
        name: str,
        topic: str,
        summary: str = "",
        tags: list[str] | None = None,
        no_auto_tags: bool = False,
        supersede_similar: bool = False,
    ) -> InboxProcessResult:
        post = self.read(name)
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

    def todo(self, name: str, reason: str = "") -> Path:
        post = self.read(name)
        dest = self._unique_folder_path(self.paths.todo / post.name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(post.path), str(dest))
        if reason:
            (dest / "todo.md").write_text(f"# 待处理\n\n{reason}\n", encoding="utf-8")
        return dest

    def delete(self, name: str, confirm: bool = False) -> dict:
        post = self.read(name)
        if not confirm:
            return {"status": "preview", "path": str(post.path), "confirm_required": True}
        shutil.rmtree(post.path)
        return {"status": "deleted", "path": str(post.path)}

    def _entries(self) -> list[Path]:
        entries: list[Path] = []
        if not self.paths.inbox.exists():
            return entries
        for platform_dir in sorted(self.paths.inbox.iterdir(), key=lambda p: p.name):
            if not platform_dir.is_dir():
                continue
            for item in platform_dir.iterdir():
                if item.is_dir():
                    entries.append(item)
        return sorted(entries, key=lambda p: self._sort_key(p.name))

    def _sort_key(self, name: str) -> tuple[str, str]:
        match = re.match(r"^(\d{8})(?!\d)", name)
        return (match.group(1) if match else "99999999", name)

    def _find_entry(self, name: str) -> Path:
        platform, item_name = self._parse_identifier(name)
        if platform is not None:
            entry = self.paths.inbox / platform / item_name
            if entry.is_dir():
                return entry
            raise FileNotFoundError(f"Inbox item not found: {name}")

        matches = [entry for entry in self._entries() if entry.name == item_name]
        if not matches:
            raise FileNotFoundError(f"Inbox item not found: {name}")
        if len(matches) > 1:
            identifiers = ", ".join(f"{entry.parent.name}/{entry.name}" for entry in matches)
            raise ValueError(
                f"Ambiguous inbox item {name!r}; use platform/name. Matches: {identifiers}"
            )
        return matches[0]

    def _parse_identifier(self, name: str) -> tuple[str | None, str]:
        identifier = str(name)
        if Path(identifier).is_absolute():
            raise ValueError(f"Invalid inbox identifier {name!r}")

        parts = identifier.split("/")
        if len(parts) == 1:
            item_name = parts[0]
            if self._invalid_identifier_component(item_name):
                raise ValueError(f"Invalid inbox identifier {name!r}")
            return None, item_name

        if len(parts) != 2:
            raise ValueError(f"Invalid inbox identifier {name!r}")

        platform, item_name = parts
        if self._invalid_identifier_component(platform) or self._invalid_identifier_component(
            item_name
        ):
            raise ValueError(f"Invalid inbox identifier {name!r}")
        return platform, item_name

    def _invalid_identifier_component(self, value: str) -> bool:
        return value in {"", ".", ".."} or "/" in value

    def _read_path(self, path: Path) -> InboxPost:
        platform = path.parent.name
        candidates = PLATFORM_READ_ORDER.get(platform, PLATFORM_READ_ORDER["fallback"])
        content_path = next((path / name for name in candidates if (path / name).is_file()), None)
        if content_path is None:
            raise FileNotFoundError(f"No readable content file found in {path}")
        content = content_path.read_text(encoding="utf-8")
        title = self._first_heading(content) or path.name
        source = self._extract_source(content)
        date = self._date_from_name(path.name)
        return InboxPost(path.name, path, platform, title, source, date, content, content_path.name)

    def _first_heading(self, content: str) -> str:
        for line in content.splitlines():
            if line.startswith("# "):
                return line[2:].strip()
        return ""

    def _extract_source(self, content: str) -> str | None:
        for line in content.splitlines():
            stripped = line.strip()
            match = re.search(r"(?:Source URL:|来源[:：])\s*(\S+)", stripped)
            if match:
                return match.group(1).strip()
        match = re.search(r"https?://\S+", content)
        return match.group(0) if match else None

    def _date_from_name(self, name: str) -> str | None:
        match = re.match(r"^(\d{4})(\d{2})(\d{2})(?!\d)", name)
        if not match:
            return None
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

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
