from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import re

from alcove.markdown import RESERVED_FILENAMES, MarkdownDoc, MarkdownRepository, normalize_slug
from alcove.okf import (
    OkfDocumentFactory,
    OkfIndexWriter,
    append_unique_source_ref,
    normalize_source_ref,
    normalize_source_refs,
    okf_schema_for,
    value_list,
)
from alcove.taxonomy import load_taxonomy, normalize_tag, split_domain_topic
from alcove.workspace import Workspace


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class NoteSourceRequest:
    platform: str
    title: str
    topic: str
    resource: str
    summary: str
    source_excerpt: str = ""
    tags: list[str] = field(default_factory=list)
    published_date: str | None = None
    legacy_path: str | None = None
    create_concept: bool = True
    human_notes: dict[str, object] | None = None
    confidence: float | None = None
    status: str = "active"
    supersedes: list[str] = field(default_factory=list)
    superseded_by: str = ""
    last_verified: str | None = None


@dataclass(frozen=True)
class NoteSourceResult:
    source_path: Path
    concept_path: Path | None


@dataclass(frozen=True)
class AddQuestionRequest:
    topic: str
    question: str
    answer: str
    tags: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AddEntityRequest:
    topic: str
    name: str
    kind: str
    summary: str
    tags: list[str] = field(default_factory=list)
    use_cases: str = ""
    open_questions: str = ""
    source_refs: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AddConceptRequest:
    topic: str
    title: str
    summary: str
    tags: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    legacy_paths: list[str] = field(default_factory=list)
    confidence: float | None = None
    status: str = "active"
    last_verified: str | None = None


@dataclass(frozen=True)
class ReviseKnowledgeRequest:
    path: str
    summary: str = ""
    answer: str = ""
    append: str = ""
    tags: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)
    reason: str = ""
    status: str = ""


@dataclass(frozen=True)
class KnowledgeDocResult:
    path: Path


@dataclass(frozen=True)
class DeleteKnowledgeResult:
    path: Path
    previous_status: str
    deleted_at: str


class KnowledgeModule:
    def __init__(
        self,
        workspace: Workspace,
        repository: MarkdownRepository | None = None,
    ) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.knowledge_root = self.paths.knowledge
        self.repository = repository or MarkdownRepository()
        self.taxonomy = load_taxonomy(self.knowledge_root)

    def note_source(self, request: NoteSourceRequest) -> NoteSourceResult:
        domain, topic = split_domain_topic(request.topic, self.taxonomy)
        tags = self._normalize_tags(request.tags)
        source_path = self._write_source(request, domain, topic, tags)
        concept_path = None
        if request.create_concept:
            concept_path = self._write_concept(request, domain, topic, tags, source_path)
        self._ensure_indexes(domain, topic, tags)
        self.rebuild_indexes()
        return NoteSourceResult(source_path=source_path, concept_path=concept_path)

    def add_question(self, request: AddQuestionRequest) -> KnowledgeDocResult:
        domain, topic = split_domain_topic(request.topic, self.taxonomy)
        tags = self._normalize_tags(request.tags)
        path = self.repository.unique_path(
            self.knowledge_root / "questions" / domain / topic,
            request.question,
        )
        self.repository.write_doc(
            path,
            self._docs().question_doc(
                question=request.question,
                answer=request.answer,
                domain=domain,
                topic=topic,
                tags=tags,
                source_refs=self._normalize_refs(request.source_refs),
            ),
        )
        self._ensure_indexes(domain, topic, tags)
        self.rebuild_indexes()
        return KnowledgeDocResult(path=path)

    def add_entity(self, request: AddEntityRequest) -> KnowledgeDocResult:
        domain, topic = split_domain_topic(request.topic, self.taxonomy)
        tags = self._normalize_tags(request.tags)
        kind = normalize_slug(request.kind)
        path = self.repository.unique_path(self.knowledge_root / "entities" / kind, request.name)
        self.repository.write_doc(
            path,
            self._docs().entity_doc(
                name=request.name,
                kind=kind,
                summary=request.summary,
                domain=domain,
                topic=topic,
                tags=tags,
                use_cases=request.use_cases,
                open_questions=request.open_questions,
                source_refs=self._normalize_refs(request.source_refs),
            ),
        )
        self._ensure_indexes(domain, topic, tags)
        self.rebuild_indexes()
        return KnowledgeDocResult(path=path)

    def add_concept(self, request: AddConceptRequest) -> KnowledgeDocResult:
        domain, topic = split_domain_topic(request.topic, self.taxonomy)
        tags = self._normalize_tags(request.tags)
        concept_dir = self.knowledge_root / "concepts" / domain / topic
        path = self._concept_path(concept_dir, request.title, domain, topic)
        self.repository.write_doc(
            path,
            self._docs().concept_doc(
                title=request.title,
                domain=domain,
                topic=topic,
                tags=tags,
                source_refs=self._normalize_refs(request.source_refs),
                status=request.status,
                summary=request.summary,
                legacy_paths=request.legacy_paths,
                confidence=request.confidence,
                last_verified=request.last_verified,
            ),
        )
        self._ensure_indexes(domain, topic, tags)
        self.rebuild_indexes()
        return KnowledgeDocResult(path=path)

    def revise(self, request: ReviseKnowledgeRequest) -> KnowledgeDocResult:
        path = self._knowledge_doc_path(request.path)
        doc = self.repository.read_doc(path)
        doc_type = str(doc.frontmatter.get("type") or "")
        if doc_type not in {"Knowledge Concept", "Source", "Question", "Entity"}:
            raise ValueError(f"Unsupported knowledge document type for revision: {doc_type}")

        tags = self._merge_unique(doc.frontmatter.get("tags"), self._normalize_tags(request.tags))
        source_refs = self._merge_unique(
            self._normalize_refs(self._as_list(doc.frontmatter.get("source_refs"))),
            self._normalize_refs(request.source_refs),
        )
        revised_at = now_iso()
        frontmatter = {
            **doc.frontmatter,
            "schema": str(doc.frontmatter.get("schema") or okf_schema_for(doc_type)),
            "tags": tags,
            "updated_at": revised_at,
            "revision_count": int(doc.frontmatter.get("revision_count") or 0) + 1,
        }
        if source_refs or "source_refs" in frontmatter:
            frontmatter["source_refs"] = source_refs
        if request.status:
            frontmatter["status"] = request.status
        revision = {
            "updated_at": revised_at,
            "reason": request.reason or "manual revision",
        }
        if request.summary:
            revision["summary_changed"] = True
        if request.answer:
            revision["answer_changed"] = True
        if request.append:
            revision["append"] = request.append[:240]
        frontmatter["revisions"] = [
            *self._revision_list(doc.frontmatter.get("revisions")),
            revision,
        ]

        body = doc.body
        if request.summary:
            body = self._replace_summary_section(doc_type, body, request.summary)
        if request.answer:
            body = self._replace_answer_section(body, request.answer)
        if request.append:
            body = self._append_revision_note(
                body,
                updated_at=revised_at,
                reason=request.reason or "manual revision",
                note=request.append,
            )

        self.repository.write_doc(path, MarkdownDoc(frontmatter=frontmatter, body=body))
        domain = str(frontmatter.get("domain") or "misc")
        topic = str(frontmatter.get("topic") or "general")
        self._ensure_indexes(domain, topic, tags)
        self.rebuild_indexes()
        return KnowledgeDocResult(path=path)

    def delete(self, path_value: str, *, confirm: bool = False, reason: str = "") -> dict:
        path = self._knowledge_doc_path(path_value)
        if not path.exists():
            raise ValueError(f"Knowledge document not found: {path_value}")
        doc = self.repository.read_doc(path)
        doc_type = str(doc.frontmatter.get("type") or "")
        if doc_type not in {"Source", "Knowledge Concept", "Question", "Entity"}:
            raise ValueError(f"Unsupported knowledge document type for delete: {doc_type}")
        previous_status = str(doc.frontmatter.get("status") or "active")
        preview = {
            "status": "preview",
            "path": str(path),
            "type": doc_type,
            "title": str(
                doc.frontmatter.get("title") or doc.frontmatter.get("question") or path.stem
            ),
            "previous_status": previous_status,
            "would_set_status": "deleted",
            "confirm_required": True,
        }
        if not confirm:
            return preview

        deleted_at = now_iso()
        frontmatter = {
            **doc.frontmatter,
            "schema": str(doc.frontmatter.get("schema") or okf_schema_for(doc_type)),
            "status": "deleted",
            "previous_status": previous_status,
            "deleted_at": deleted_at,
            "updated_at": deleted_at,
        }
        if reason:
            frontmatter["delete_reason"] = reason
        self.repository.write_doc(path, MarkdownDoc(frontmatter=frontmatter, body=doc.body))
        source_ref = f"/{path.relative_to(self.knowledge_root).as_posix()}"
        related_actions = self._delete_or_detach_source_ref(
            source_ref,
            deleted_at=deleted_at,
            reason=reason,
        )
        domain = str(frontmatter.get("domain") or "misc")
        topic = str(frontmatter.get("topic") or "general")
        tags = self._normalize_tags(self._as_list(frontmatter.get("tags")))
        self._ensure_indexes(domain, topic, tags)
        self.rebuild_indexes()
        return {
            **preview,
            "status": "deleted",
            "confirm_required": False,
            "deleted_at": deleted_at,
            "reason": reason,
            "related_actions": related_actions,
        }

    def promote_source(
        self, source: str | Path, topic: str = "", summary: str = ""
    ) -> KnowledgeDocResult:
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = self.knowledge_root / source_path
        doc = self.repository.read_doc(source_path)
        if doc.frontmatter.get("type") != "Source":
            raise ValueError(f"{source_path} is not a Source")
        source_ref = f"/{source_path.relative_to(self.knowledge_root).as_posix()}"
        request = AddConceptRequest(
            topic=topic or str(doc.frontmatter.get("topic") or "misc"),
            title=str(doc.frontmatter.get("title") or source_path.stem),
            summary=summary
            or self._source_summary(doc.body)
            or str(doc.frontmatter.get("description") or ""),
            tags=self._as_list(doc.frontmatter.get("tags")),
            source_refs=[source_ref],
            legacy_paths=self._as_list(doc.frontmatter.get("legacy_path")),
            confidence=float(doc.frontmatter["confidence"])
            if "confidence" in doc.frontmatter
            else None,
            status=str(doc.frontmatter.get("status") or "active"),
            last_verified=str(doc.frontmatter.get("last_verified") or ""),
        )
        return self.add_concept(request)

    def _write_source(
        self,
        request: NoteSourceRequest,
        domain: str,
        topic: str,
        tags: list[str],
    ) -> Path:
        platform = normalize_slug(request.platform)
        path = self.repository.unique_path(
            self.knowledge_root / "sources" / platform / domain,
            request.title,
        )
        return self.repository.write_doc(
            path,
            self._docs().source_doc(
                title=request.title,
                platform=platform,
                resource=request.resource,
                domain=domain,
                topic=topic,
                tags=tags,
                status=request.status,
                summary=request.summary,
                source_excerpt=request.source_excerpt,
                confidence=request.confidence,
                supersedes=request.supersedes,
                superseded_by=request.superseded_by,
                last_verified=request.last_verified,
                published_date=request.published_date,
                legacy_path=request.legacy_path,
            ),
        )

    def _write_concept(
        self,
        request: NoteSourceRequest,
        domain: str,
        topic: str,
        tags: list[str],
        source_path: Path,
    ) -> Path:
        concept_dir = self.knowledge_root / "concepts" / domain / topic
        path = self._concept_path(concept_dir, request.title, domain, topic)
        source_ref = f"/{source_path.relative_to(self.knowledge_root).as_posix()}"
        if path.exists():
            doc = self.repository.read_doc(path)
            source_refs = self._append_unique_source_ref(
                self._merge_unique(
                    doc.frontmatter.get("source_refs"),
                    self._as_list(doc.frontmatter.get("source")),
                ),
                source_ref,
            )
            legacy_paths = self._append_unique(
                doc.frontmatter.get("legacy_paths"),
                request.legacy_path,
            )
            frontmatter = {
                **doc.frontmatter,
                "type": "Knowledge Concept",
                "schema": str(doc.frontmatter.get("schema") or okf_schema_for("Knowledge Concept")),
                "title": request.title,
                "domain": domain,
                "topic": topic,
                "tags": self._merge_unique(doc.frontmatter.get("tags"), tags),
                "source_refs": source_refs,
                "status": request.status,
            }
            if request.confidence is not None:
                frontmatter["confidence"] = round(float(request.confidence), 2)
            if request.supersedes:
                frontmatter["supersedes"] = self._merge_unique(
                    doc.frontmatter.get("supersedes"),
                    request.supersedes,
                )
            if request.superseded_by:
                frontmatter["superseded_by"] = request.superseded_by
            if request.last_verified:
                frontmatter["last_verified"] = request.last_verified
            frontmatter.pop("source", None)
            if legacy_paths:
                frontmatter["legacy_paths"] = legacy_paths
            return self.repository.write_doc(
                path,
                MarkdownDoc(frontmatter=frontmatter, body=doc.body),
            )

        return self.repository.write_doc(
            path,
            self._docs().concept_doc(
                title=request.title,
                domain=domain,
                topic=topic,
                tags=tags,
                source_refs=[source_ref],
                status=request.status,
                summary=request.summary,
                human_notes=request.human_notes,
                legacy_paths=[request.legacy_path] if request.legacy_path else [],
                confidence=request.confidence,
                supersedes=request.supersedes,
                superseded_by=request.superseded_by,
                last_verified=request.last_verified,
            ),
        )

    def _concept_path(self, directory: Path, title: str, domain: str, topic: str) -> Path:
        slug = normalize_slug(title)
        candidate = directory / f"{slug}.md"
        if not candidate.exists() and candidate.name not in RESERVED_FILENAMES:
            return candidate
        if directory.exists():
            paths = [
                candidate,
                *sorted(directory.glob(f"{slug}-*.md"), key=lambda item: item.name),
            ]
            for path in paths:
                if not path.exists():
                    continue
                doc = self.repository.read_doc(path)
                if (
                    doc.frontmatter.get("type") == "Knowledge Concept"
                    and doc.frontmatter.get("title") == title
                    and doc.frontmatter.get("domain") == domain
                    and doc.frontmatter.get("topic") == topic
                ):
                    return path
        return self.repository.unique_path(directory, slug)

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _docs(self) -> OkfDocumentFactory:
        return OkfDocumentFactory(now_iso())

    def _append_unique_source_ref(self, current: object, value: str) -> list[str]:
        return append_unique_source_ref(current, value)

    def _normalize_source_ref(self, value: str) -> str:
        return normalize_source_ref(value)

    def _normalize_refs(self, refs: list[str]) -> list[str]:
        return normalize_source_refs(refs)

    def _knowledge_doc_path(self, value: str) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        return self.knowledge_root / path

    def _source_summary(self, body: str) -> str:
        lines = [
            line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#")
        ]
        return "\n".join(lines[:3])

    def _append_unique(self, current: object, value: str | None) -> list[str]:
        values = self._as_list(current)
        if value and value not in values:
            values.append(value)
        return values

    def _merge_unique(self, current: object, values: list[str]) -> list[str]:
        merged = self._as_list(current)
        for value in values:
            if value not in merged:
                merged.append(value)
        return merged

    def _as_list(self, value: object) -> list[str]:
        return value_list(value)

    def _revision_list(self, value: object) -> list[dict[str, object]]:
        if not isinstance(value, list):
            return []
        return [item for item in value if isinstance(item, dict)]

    def _replace_summary_section(self, doc_type: str, body: str, summary: str) -> str:
        if doc_type == "Knowledge Concept":
            replaced = self._replace_section(body, "## 摘要", summary)
            key_points = self._docs()._summary_key_points(summary)
            if "## 要点" in replaced:
                replacement = "\n".join(key_points) if key_points else ""
                return self._replace_section(replaced, "## 要点", replacement).replace(
                    "\n## 要点\n\n\n",
                    "\n",
                )
            if key_points:
                return self._insert_after_section(
                    replaced,
                    "## 摘要",
                    "## 要点\n\n" + "\n".join(key_points),
                )
            return replaced
        if doc_type == "Entity":
            return self._replace_section(body, "# 定位", summary)
        if doc_type == "Source":
            return self._replace_lead_after_title(body, summary)
        return body

    def _replace_answer_section(self, body: str, answer: str) -> str:
        return self._replace_section(body, "# 稳定答案", answer)

    def _replace_section(self, body: str, heading: str, content: str) -> str:
        pattern = rf"({re.escape(heading)}\n\n)(.*?)(?=\n[#]+ |\Z)"
        if re.search(pattern, body, flags=re.DOTALL):
            return re.sub(
                pattern,
                lambda match: f"{match.group(1)}{content.rstrip()}\n",
                body,
                count=1,
                flags=re.DOTALL,
            )
        return body.rstrip() + f"\n\n{heading}\n\n{content.rstrip()}\n"

    def _insert_after_section(self, body: str, heading: str, section: str) -> str:
        pattern = rf"({re.escape(heading)}\n\n.*?)(?=\n[#]+ |\Z)"
        if re.search(pattern, body, flags=re.DOTALL):
            return re.sub(
                pattern,
                lambda match: f"{match.group(1)}\n\n{section.rstrip()}\n",
                body,
                count=1,
                flags=re.DOTALL,
            )
        return body.rstrip() + f"\n\n{section.rstrip()}\n"

    def _replace_lead_after_title(self, body: str, summary: str) -> str:
        pattern = r"(# .+?\n\n)(.*?)(?=\n[#]+ |\Z)"
        if re.search(pattern, body, flags=re.DOTALL):
            return re.sub(
                pattern,
                lambda match: f"{match.group(1)}{summary.rstrip()}\n",
                body,
                count=1,
                flags=re.DOTALL,
            )
        return body.rstrip() + f"\n\n{summary.rstrip()}\n"

    def _append_revision_note(self, body: str, *, updated_at: str, reason: str, note: str) -> str:
        entry = f"### {updated_at} - {reason}\n\n{note.rstrip()}\n"
        if "## 修订记录" in body:
            return body.rstrip() + f"\n\n{entry}"
        return body.rstrip() + f"\n\n## 修订记录\n\n{entry}"

    def _delete_or_detach_source_ref(
        self,
        source_ref: str,
        *,
        deleted_at: str,
        reason: str,
    ) -> list[dict[str, str]]:
        actions: list[dict[str, str]] = []
        for doc in self.repository.list_docs(self.knowledge_root):
            if doc.path is None:
                continue
            doc_type = str(doc.frontmatter.get("type") or "")
            if doc_type not in {"Knowledge Concept", "Question", "Entity"}:
                continue
            refs = self._normalize_refs(self._as_list(doc.frontmatter.get("source_refs")))
            if source_ref not in refs:
                continue
            remaining_refs = [ref for ref in refs if ref != source_ref]
            previous_status = str(doc.frontmatter.get("status") or "active")
            frontmatter = {
                **doc.frontmatter,
                "schema": str(doc.frontmatter.get("schema") or okf_schema_for(doc_type)),
                "updated_at": deleted_at,
            }
            action = "detached_source_ref"
            if doc_type == "Knowledge Concept" and not remaining_refs:
                frontmatter.update(
                    {
                        "status": "deleted",
                        "previous_status": previous_status,
                        "deleted_at": deleted_at,
                    }
                )
                if reason:
                    frontmatter["delete_reason"] = reason
                action = "deleted_single_source_concept"
            else:
                frontmatter["source_refs"] = remaining_refs
            self.repository.write_doc(doc.path, MarkdownDoc(frontmatter=frontmatter, body=doc.body))
            actions.append(
                {
                    "action": action,
                    "path": str(doc.path),
                }
            )
        return actions

    def _ensure_indexes(self, domain: str, topic: str, tags: list[str]) -> None:
        OkfIndexWriter(
            root=self.knowledge_root,
            taxonomy=self.taxonomy,
            repository=self.repository,
            now=now_iso(),
        ).ensure_indexes(domain, topic, tags)

    def rebuild_indexes(self) -> Path:
        docs = self.repository.list_docs(self.knowledge_root)
        lines = ["# Knowledge Index", ""]
        for doc in docs:
            if doc.path is None:
                continue
            if str(doc.frontmatter.get("status") or "active").casefold() == "deleted":
                continue
            title = doc.frontmatter.get("title") or doc.frontmatter.get("question") or doc.path.stem
            doc_type = doc.frontmatter.get("type", "Document")
            rel_path = doc.path.relative_to(self.knowledge_root).as_posix()
            lines.append(f"- [{doc_type}] [{title}]({rel_path})")
        body = "\n".join(lines) + "\n"
        return self.repository.write_doc(
            self.knowledge_root / "index.md",
            MarkdownDoc(
                frontmatter={
                    "title": "Knowledge Index",
                    "updated_at": now_iso(),
                },
                body=body,
            ),
        )
