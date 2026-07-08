from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from alcove.markdown import RESERVED_FILENAMES, MarkdownDoc, MarkdownRepository, normalize_slug
from alcove.okf import (
    OkfDocumentFactory,
    OkfIndexWriter,
    append_unique_source_ref,
    normalize_source_ref,
    normalize_source_refs,
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
class KnowledgeDocResult:
    path: Path


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
