from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from alcove.markdown import RESERVED_FILENAMES, MarkdownDoc, MarkdownRepository, normalize_slug
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


@dataclass(frozen=True)
class AddEntityRequest:
    topic: str
    name: str
    kind: str
    summary: str
    tags: list[str] = field(default_factory=list)


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
            MarkdownDoc(
                frontmatter={
                    "type": "Question",
                    "question": request.question,
                    "domain": domain,
                    "topic": topic,
                    "tags": tags,
                    "created_at": now_iso(),
                },
                body=f"# {request.question}\n\n{request.answer}\n",
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
            MarkdownDoc(
                frontmatter={
                    "type": "Entity",
                    "title": request.name,
                    "kind": kind,
                    "domain": domain,
                    "topic": topic,
                    "tags": tags,
                    "created_at": now_iso(),
                },
                body=f"# {request.name}\n\n{request.summary}\n",
            ),
        )
        self._ensure_indexes(domain, topic, tags)
        self.rebuild_indexes()
        return KnowledgeDocResult(path=path)

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
        frontmatter = {
            "type": "Source",
            "title": request.title,
            "platform": platform,
            "resource": request.resource,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "created_at": now_iso(),
        }
        if request.published_date:
            frontmatter["published_date"] = request.published_date
        if request.legacy_path:
            frontmatter["legacy_path"] = request.legacy_path
        return self.repository.write_doc(
            path,
            MarkdownDoc(frontmatter=frontmatter, body=f"# {request.title}\n\n{request.summary}\n"),
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
                doc.frontmatter.get("source_refs") or doc.frontmatter.get("source"),
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
            }
            frontmatter.pop("source", None)
            if legacy_paths:
                frontmatter["legacy_paths"] = legacy_paths
            return self.repository.write_doc(
                path,
                MarkdownDoc(frontmatter=frontmatter, body=doc.body),
            )

        frontmatter = {
            "type": "Knowledge Concept",
            "title": request.title,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "source_refs": [source_ref],
            "created_at": now_iso(),
        }
        if request.legacy_path:
            frontmatter["legacy_paths"] = [request.legacy_path]
        return self.repository.write_doc(
            path,
            MarkdownDoc(frontmatter=frontmatter, body=f"# {request.title}\n\n{request.summary}\n"),
        )

    def _concept_path(self, directory: Path, title: str, domain: str, topic: str) -> Path:
        slug = normalize_slug(title)
        candidate = directory / f"{slug}.md"
        if candidate.name not in RESERVED_FILENAMES:
            return candidate
        if directory.exists():
            for path in sorted(directory.glob(f"{slug}-*.md"), key=lambda item: item.name):
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

    def _append_unique_source_ref(self, current: object, value: str) -> list[str]:
        values: list[str] = []
        for item in self._as_list(current):
            normalized = self._normalize_source_ref(item)
            if normalized not in values:
                values.append(normalized)
        normalized_value = self._normalize_source_ref(value)
        if normalized_value not in values:
            values.append(normalized_value)
        return values

    def _normalize_source_ref(self, value: str) -> str:
        ref = str(value or "").strip()
        if not ref:
            return ref
        return ref if ref.startswith("/") else f"/{ref}"

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
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if value:
            return [str(value)]
        return []

    def _ensure_indexes(self, domain: str, topic: str, tags: list[str]) -> None:
        self._write_index_doc(
            self.knowledge_root / "domains" / f"{domain}.md",
            {
                "type": "Domain",
                "title": self.taxonomy.get("domains", {}).get(domain, {}).get("title", domain),
                "domain": domain,
            },
            f"# {domain}\n",
        )
        self._write_index_doc(
            self.knowledge_root / "topics" / domain / f"{topic}.md",
            {
                "type": "Topic",
                "title": topic,
                "domain": domain,
                "topic": topic,
            },
            f"# {topic}\n",
        )
        for tag in tags:
            self._write_index_doc(
                self.knowledge_root / "tags" / f"{tag}.md",
                {
                    "type": "Tag",
                    "title": tag,
                    "tag": tag,
                },
                f"# {tag}\n",
            )

    def _write_index_doc(self, path: Path, frontmatter: dict, body: str) -> None:
        if path.exists():
            return
        frontmatter = {**frontmatter, "created_at": now_iso()}
        self.repository.write_doc(path, MarkdownDoc(frontmatter=frontmatter, body=body))

    def rebuild_indexes(self) -> Path:
        docs = self.repository.list_docs(self.knowledge_root)
        lines = ["# Knowledge Index", ""]
        for doc in docs:
            if doc.path is None:
                continue
            title = (
                doc.frontmatter.get("title")
                or doc.frontmatter.get("question")
                or doc.path.stem
            )
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
