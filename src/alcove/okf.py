from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re

from alcove.markdown import RESERVED_FILENAMES, MarkdownDoc, MarkdownRepository


INFRASTRUCTURE_TYPES = {"Domain", "Index", "Log", "Tag", "Topic"}
OKF_SCHEMA_BY_TYPE = {
    "Source": "alcove/source/v1",
    "Knowledge Concept": "alcove/knowledge-concept/v1",
    "Question": "alcove/question/v1",
    "Entity": "alcove/entity/v1",
}
OKF_REQUIRED_FIELDS = {
    "Source": (
        "type",
        "schema",
        "title",
        "platform",
        "resource",
        "domain",
        "topic",
        "tags",
        "status",
        "created_at",
    ),
    "Knowledge Concept": (
        "type",
        "schema",
        "title",
        "domain",
        "topic",
        "tags",
        "source_refs",
        "status",
        "created_at",
    ),
    "Question": (
        "type",
        "schema",
        "question",
        "domain",
        "topic",
        "tags",
        "source_refs",
        "status",
        "created_at",
    ),
    "Entity": (
        "type",
        "schema",
        "title",
        "kind",
        "domain",
        "topic",
        "tags",
        "source_refs",
        "status",
        "created_at",
    ),
}


def okf_schema_for(doc_type: str) -> str:
    return OKF_SCHEMA_BY_TYPE.get(doc_type, "")


def require_okf_frontmatter(frontmatter: dict) -> None:
    doc_type = str(frontmatter.get("type") or "")
    required = OKF_REQUIRED_FIELDS.get(doc_type)
    if required is None:
        raise ValueError(f"Unsupported OKF document type: {doc_type or '<missing>'}")
    missing = [field for field in required if field not in frontmatter]
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"{doc_type} frontmatter missing required fields: {joined}")


def string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def object_list(value: object) -> list[dict]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def value_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item]
    if value:
        return [str(value)]
    return []


def frontmatter_date(frontmatter: dict) -> str:
    value = (
        frontmatter.get("date")
        or frontmatter.get("published_date")
        or frontmatter.get("created_at")
        or frontmatter.get("updated_at")
        or frontmatter.get("date_added")
        or frontmatter.get("date_modified")
        or frontmatter.get("timestamp")
        or ""
    )
    if isinstance(value, date):
        return value.isoformat()
    return str(value)[:10]


def frontmatter_confidence(frontmatter: dict) -> float:
    try:
        return float(frontmatter.get("confidence", 0.5))
    except (TypeError, ValueError):
        return 0.5


def normalize_source_ref(value: str) -> str:
    ref = str(value or "").strip()
    if not ref:
        return ref
    return ref if ref.startswith("/") else f"/{ref}"


def normalize_source_refs(refs: list[str]) -> list[str]:
    values: list[str] = []
    for ref in refs:
        normalized = normalize_source_ref(ref)
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def append_unique_source_ref(current: object, value: str) -> list[str]:
    values: list[str] = []
    for item in value_list(current):
        normalized = normalize_source_ref(item)
        if normalized not in values:
            values.append(normalized)
    normalized_value = normalize_source_ref(value)
    if normalized_value not in values:
        values.append(normalized_value)
    return values


def is_infrastructure_doc(doc: MarkdownDoc) -> bool:
    return str(doc.frontmatter.get("type") or "") in INFRASTRUCTURE_TYPES


def require_doc_path(doc: MarkdownDoc, label: str = "Document") -> Path:
    if doc.path is None:
        raise ValueError(f"{label} has no path")
    return doc.path


def relative_doc_path(doc: MarkdownDoc, root: Path | None) -> str:
    path = require_doc_path(doc)
    if root is None:
        return path.as_posix()
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def doc_title(doc: MarkdownDoc) -> str:
    path = require_doc_path(doc)
    return str(doc.frontmatter.get("title") or doc.frontmatter.get("question") or path.stem)


@dataclass(frozen=True)
class OkfIndexWriter:
    root: Path
    taxonomy: dict
    repository: MarkdownRepository
    now: str

    def ensure_indexes(self, domain: str, topic: str, tags: list[str]) -> None:
        self._write_index_doc(
            self.root / "domains" / f"{domain}.md",
            {
                "type": "Domain",
                "title": self.taxonomy.get("domains", {}).get(domain, {}).get("title", domain),
                "domain": domain,
            },
            f"# {domain}\n",
        )
        self._write_index_doc(
            self.root / "topics" / domain / f"{topic}.md",
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
                self.root / "tags" / f"{tag}.md",
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
        self.repository.write_doc(
            doc_path,
            MarkdownDoc(frontmatter={**frontmatter, "created_at": self.now}, body=body),
        )

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
            return current.get("domain") == desired.get("domain") and current.get(
                "topic"
            ) == desired.get("topic")
        if desired.get("type") == "Tag":
            return current.get("tag") == desired.get("tag")
        return False


class OkfDocumentFactory:
    def __init__(self, now: str) -> None:
        self.now = now

    def source_doc(
        self,
        *,
        title: str,
        platform: str,
        resource: str,
        domain: str,
        topic: str,
        tags: list[str],
        status: str,
        summary: str,
        source_excerpt: str = "",
        confidence: float | None = None,
        supersedes: list[str] | None = None,
        superseded_by: str = "",
        last_verified: str | None = None,
        published_date: str | None = None,
        legacy_path: str | None = None,
    ) -> MarkdownDoc:
        frontmatter = {
            "type": "Source",
            "schema": okf_schema_for("Source"),
            "title": title,
            "platform": platform,
            "resource": resource,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "status": status,
            "created_at": self.now,
        }
        self._optional_lifecycle(
            frontmatter,
            confidence=confidence,
            supersedes=supersedes or [],
            superseded_by=superseded_by,
            last_verified=last_verified,
        )
        if published_date:
            frontmatter["published_date"] = published_date
        if legacy_path:
            frontmatter["legacy_path"] = legacy_path
        require_okf_frontmatter(frontmatter)
        excerpt = f"\n\n## 原文摘录\n\n{source_excerpt}\n" if source_excerpt else ""
        provenance = f"\n\n## 来源\n\n- `{legacy_path}`\n" if legacy_path else ""
        return MarkdownDoc(
            frontmatter=frontmatter,
            body=f"# {title}\n\n{summary}{excerpt}{provenance}\n",
        )

    def concept_doc(
        self,
        *,
        title: str,
        domain: str,
        topic: str,
        tags: list[str],
        source_refs: list[str],
        status: str,
        summary: str,
        human_notes: dict[str, object] | None = None,
        legacy_paths: list[str] | None = None,
        confidence: float | None = None,
        supersedes: list[str] | None = None,
        superseded_by: str = "",
        last_verified: str | None = None,
    ) -> MarkdownDoc:
        frontmatter = {
            "type": "Knowledge Concept",
            "schema": okf_schema_for("Knowledge Concept"),
            "title": title,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "source_refs": source_refs,
            "status": status,
            "created_at": self.now,
        }
        if legacy_paths:
            frontmatter["legacy_paths"] = legacy_paths
        self._optional_lifecycle(
            frontmatter,
            confidence=confidence,
            supersedes=supersedes or [],
            superseded_by=superseded_by,
            last_verified=last_verified,
        )
        require_okf_frontmatter(frontmatter)
        return MarkdownDoc(
            frontmatter=frontmatter,
            body=self.concept_body(
                title,
                summary,
                human_notes,
                source_refs,
                legacy_paths or [],
            ),
        )

    def question_doc(
        self,
        *,
        question: str,
        answer: str,
        domain: str,
        topic: str,
        tags: list[str],
        source_refs: list[str],
    ) -> MarkdownDoc:
        frontmatter = {
            "type": "Question",
            "schema": okf_schema_for("Question"),
            "question": question,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "source_refs": source_refs,
            "status": "active",
            "created_at": self.now,
        }
        require_okf_frontmatter(frontmatter)
        return MarkdownDoc(
            frontmatter=frontmatter,
            body=(
                f"# 问题\n\n{question}\n\n"
                f"# 稳定答案\n\n{answer}\n\n"
                f"# 相关来源\n\n" + "\n".join(f"- [{ref}]({ref})" for ref in source_refs) + "\n"
            ),
        )

    def entity_doc(
        self,
        *,
        name: str,
        kind: str,
        summary: str,
        domain: str,
        topic: str,
        tags: list[str],
        use_cases: str,
        open_questions: str,
        source_refs: list[str],
    ) -> MarkdownDoc:
        frontmatter = {
            "type": "Entity",
            "schema": okf_schema_for("Entity"),
            "title": name,
            "kind": kind,
            "domain": domain,
            "topic": topic,
            "tags": tags,
            "source_refs": source_refs,
            "status": "active",
            "created_at": self.now,
        }
        require_okf_frontmatter(frontmatter)
        return MarkdownDoc(
            frontmatter=frontmatter,
            body=(
                f"# 对象\n\n{name}\n\n"
                f"# 定位\n\n{summary}\n\n"
                f"# 适用场景\n\n{use_cases}\n\n"
                f"# 待验证问题\n\n{open_questions}\n\n"
                f"# 相关来源\n\n" + "\n".join(f"- [{ref}]({ref})" for ref in source_refs) + "\n"
            ),
        )

    def concept_body(
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
        sections = [f"# {title}", f"## 摘要\n\n{summary}"]
        key_points = self._summary_key_points(summary)
        if key_points:
            sections.append("## 要点\n\n" + "\n".join(key_points))
        if notes:
            sections.append(notes.rstrip())
        if source_lines:
            sections.append(f"## 关系\n\n{source_lines}")
        if legacy_lines:
            sections.append(f"## 来源\n\n{legacy_lines}")
        return "\n\n".join(sections).rstrip() + "\n"

    def _summary_key_points(self, summary: str) -> list[str]:
        points: list[str] = []
        for line in summary.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^([-*]|\d+[.)])\s+", stripped):
                text = re.sub(r"^([-*]|\d+[.)])\s+", "", stripped).strip()
                if text:
                    points.append(f"- {text}")
        if len(points) == 1 and points[0].removeprefix("- ").strip() == summary.strip():
            return []
        return points

    def _optional_lifecycle(
        self,
        frontmatter: dict,
        *,
        confidence: float | None,
        supersedes: list[str],
        superseded_by: str,
        last_verified: str | None,
    ) -> None:
        if confidence is not None:
            frontmatter["confidence"] = round(float(confidence), 2)
        if supersedes:
            frontmatter["supersedes"] = supersedes
        if superseded_by:
            frontmatter["superseded_by"] = superseded_by
        if last_verified:
            frontmatter["last_verified"] = last_verified

    def _format_human_notes(self, human_notes: dict[str, object] | None) -> str:
        if not human_notes:
            return ""
        sections: list[str] = []
        raw_selected = human_notes.get("selected_takeaways") or []
        selected: list[object]
        if isinstance(raw_selected, str):
            selected = [raw_selected]
        elif isinstance(raw_selected, list):
            selected = raw_selected
        else:
            selected = []
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
