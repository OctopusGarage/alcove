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
            MarkdownDoc(
                frontmatter={
                    "type": "Question",
                    "question": request.question,
                    "domain": domain,
                    "topic": topic,
                    "tags": tags,
                    "source_refs": self._normalize_refs(request.source_refs),
                    "status": "active",
                    "created_at": now_iso(),
                },
                body=(
                    f"# 问题\n\n{request.question}\n\n"
                    f"# 稳定答案\n\n{request.answer}\n\n"
                    f"# 相关来源\n\n"
                    + "\n".join(f"- [{ref}]({ref})" for ref in self._normalize_refs(request.source_refs))
                    + "\n"
                ),
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
                    "source_refs": self._normalize_refs(request.source_refs),
                    "status": "active",
                    "created_at": now_iso(),
                },
                body=(
                    f"# 对象\n\n{request.name}\n\n"
                    f"# 定位\n\n{request.summary}\n\n"
                    f"# 适用场景\n\n{request.use_cases}\n\n"
                    f"# 待验证问题\n\n{request.open_questions}\n\n"
                    f"# 相关来源\n\n"
                    + "\n".join(f"- [{ref}]({ref})" for ref in self._normalize_refs(request.source_refs))
                    + "\n"
                ),
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
        frontmatter = {
            "type": "Knowledge Concept",
            "title": request.title,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "source_refs": self._normalize_refs(request.source_refs),
            "legacy_paths": request.legacy_paths,
            "status": request.status,
            "created_at": now_iso(),
        }
        if request.confidence is not None:
            frontmatter["confidence"] = round(float(request.confidence), 2)
        if request.last_verified:
            frontmatter["last_verified"] = request.last_verified
        self.repository.write_doc(
            path,
            MarkdownDoc(
                frontmatter=frontmatter,
                body=self._concept_body(request.title, request.summary, None, self._normalize_refs(request.source_refs), request.legacy_paths),
            ),
        )
        self._ensure_indexes(domain, topic, tags)
        self.rebuild_indexes()
        return KnowledgeDocResult(path=path)

    def promote_source(self, source: str | Path, topic: str = "", summary: str = "") -> KnowledgeDocResult:
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
            summary=summary or self._source_summary(doc.body) or str(doc.frontmatter.get("description") or ""),
            tags=self._as_list(doc.frontmatter.get("tags")),
            source_refs=[source_ref],
            legacy_paths=self._as_list(doc.frontmatter.get("legacy_path")),
            confidence=float(doc.frontmatter["confidence"]) if "confidence" in doc.frontmatter else None,
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
        frontmatter = {
            "type": "Source",
            "title": request.title,
            "platform": platform,
            "resource": request.resource,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "status": request.status,
            "created_at": now_iso(),
        }
        if request.confidence is not None:
            frontmatter["confidence"] = round(float(request.confidence), 2)
        if request.supersedes:
            frontmatter["supersedes"] = request.supersedes
        if request.superseded_by:
            frontmatter["superseded_by"] = request.superseded_by
        if request.last_verified:
            frontmatter["last_verified"] = request.last_verified
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

        frontmatter = {
            "type": "Knowledge Concept",
            "title": request.title,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "source_refs": [source_ref],
            "status": request.status,
            "created_at": now_iso(),
        }
        if request.confidence is not None:
            frontmatter["confidence"] = round(float(request.confidence), 2)
        if request.supersedes:
            frontmatter["supersedes"] = request.supersedes
        if request.superseded_by:
            frontmatter["superseded_by"] = request.superseded_by
        if request.last_verified:
            frontmatter["last_verified"] = request.last_verified
        if request.legacy_path:
            frontmatter["legacy_paths"] = [request.legacy_path]
        return self.repository.write_doc(
            path,
            MarkdownDoc(
                frontmatter=frontmatter,
                body=self._concept_body(
                    request.title,
                    request.summary,
                    request.human_notes,
                    [source_ref],
                    [request.legacy_path] if request.legacy_path else [],
                ),
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

    def _normalize_refs(self, refs: list[str]) -> list[str]:
        values: list[str] = []
        for ref in refs:
            normalized = self._normalize_source_ref(ref)
            if normalized and normalized not in values:
                values.append(normalized)
        return values

    def _concept_body(
        self,
        title: str,
        summary: str,
        human_notes: dict[str, object] | None,
        source_refs: list[str],
        legacy_paths: list[str],
    ) -> str:
        notes = self._format_human_notes(human_notes)
        source_lines = "\n".join(f"- [{ref}]({ref})" for ref in source_refs)
        legacy_lines = "\n".join(f"- `{path}`" for path in legacy_paths if path)
        return (
            f"# {title}\n\n"
            f"## 摘要\n\n{summary}\n\n"
            f"## 要点\n\n{summary}\n\n"
            f"{notes}"
            f"## 关系\n\n{source_lines}\n\n"
            f"## 来源\n\n{legacy_lines}\n"
        )

    def _format_human_notes(self, human_notes: dict[str, object] | None) -> str:
        if not human_notes:
            return ""
        sections: list[str] = []
        selected = human_notes.get("selected_takeaways") or []
        if isinstance(selected, str):
            selected = [selected]
        selected_lines = "\n".join(f"- {item}" for item in selected if str(item).strip())
        if selected_lines:
            sections.append(f"### 选择的推荐项\n\n{selected_lines}")
        labels = {
            "why": "为什么值得收录",
            "connection": "和我有关的连接",
            "action": "下一步行动",
            "personal_note": "个人看法",
        }
        for key, label in labels.items():
            value = str(human_notes.get(key) or "").strip()
            if value:
                sections.append(f"### {label}\n\n{value}")
        if not sections:
            return ""
        return "## 我的判断\n\n" + "\n\n".join(sections) + "\n\n"

    def _source_summary(self, body: str) -> str:
        lines = [line.strip() for line in body.splitlines() if line.strip() and not line.startswith("#")]
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
        doc_path = self._index_doc_path(path, frontmatter)
        if doc_path.exists():
            return
        frontmatter = {**frontmatter, "created_at": now_iso()}
        self.repository.write_doc(doc_path, MarkdownDoc(frontmatter=frontmatter, body=body))

    def _index_doc_path(self, path: Path, frontmatter: dict) -> Path:
        if path.name not in RESERVED_FILENAMES:
            return path
        if path.parent.exists():
            for existing_path in sorted(path.parent.glob(f"{path.stem}-*.md")):
                doc = self.repository.read_doc(existing_path)
                if self._same_index_doc(doc.frontmatter, frontmatter):
                    return existing_path
        return self.repository.unique_path(path.parent, path.stem)

    def _same_index_doc(self, current: dict, desired: dict) -> bool:
        if current.get("type") != desired.get("type"):
            return False
        if desired.get("type") == "Domain":
            return current.get("domain") == desired.get("domain")
        if desired.get("type") == "Topic":
            return (
                current.get("domain") == desired.get("domain")
                and current.get("topic") == desired.get("topic")
            )
        if desired.get("type") == "Tag":
            return current.get("tag") == desired.get("tag")
        return False

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
