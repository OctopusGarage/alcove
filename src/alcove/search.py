from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.taxonomy import (
    load_taxonomy,
    normalize_tag,
    normalize_topic,
    split_domain_topic,
)
from alcove.workspace import Workspace


INFRASTRUCTURE_TYPES = {"Domain", "Index", "Log", "Tag", "Topic"}


@dataclass(frozen=True)
class SearchRequest:
    query: str = ""
    type_filter: str | None = None
    tag: str | None = None
    topic: str | None = None
    platform: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    min_confidence: float | None = None
    status: str | None = None
    limit: int = 20


@dataclass(frozen=True)
class TopicFilter:
    topic: str
    domain: str | None = None


class SearchModule:
    def __init__(
        self, workspace: Workspace, repo: MarkdownRepository | None = None
    ) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.knowledge_root = self.paths.knowledge
        self.repo = repo or MarkdownRepository()
        self.taxonomy = load_taxonomy(self.knowledge_root)

    def search(self, request: SearchRequest) -> list[dict]:
        rows: list[dict] = []
        limit = max(request.limit, 0)
        if limit == 0:
            return rows
        query = request.query.casefold()
        tag_filter = self._normalize_tag_filter(request.tag)
        topic_filter = self._normalize_topic_filter(request.topic)

        for doc in self.repo.list_docs(
            self.knowledge_root, type_filter=request.type_filter
        ):
            if doc.path is None:
                continue
            if request.type_filter is None and self._is_infrastructure_doc(doc):
                continue
            if not self._matches_filters(doc, request, tag_filter, topic_filter):
                continue
            if query and query not in self._search_text(doc):
                continue

            rows.append(self._row(doc))
            if len(rows) >= limit:
                break

        return rows

    def tags(self) -> list[dict]:
        counts: dict[str, int] = {}
        for doc in self._docs():
            for tag in self._tags(doc.frontmatter.get("tags")):
                counts[tag] = counts.get(tag, 0) + 1
        return [
            {"tag": tag, "count": count}
            for tag, count in sorted(
                counts.items(), key=lambda item: (-item[1], item[0])
            )
        ]

    def tag_doctor(self) -> list[dict]:
        variants_by_canonical: dict[str, set[str]] = {}
        counts: dict[str, int] = {}
        for doc in self._docs():
            for tag in self._tags(doc.frontmatter.get("tags")):
                canonical = normalize_tag(tag, self.taxonomy)
                variants_by_canonical.setdefault(canonical, set()).add(tag)
                counts[canonical] = counts.get(canonical, 0) + 1
        return [
            {
                "canonical": canonical,
                "variants": sorted(variants),
                "count": counts[canonical],
            }
            for canonical, variants in sorted(variants_by_canonical.items())
            if len(variants) > 1
        ]

    def recent(self, limit: int = 20) -> list[dict]:
        rows = [self._row(doc) for doc in self._docs()]
        rows.sort(key=lambda row: row.get("date") or "", reverse=True)
        return rows[: max(limit, 0)]

    def _matches_filters(
        self,
        doc: MarkdownDoc,
        request: SearchRequest,
        tag_filter: str | None,
        topic_filter: TopicFilter | None,
    ) -> bool:
        frontmatter = doc.frontmatter
        if (
            tag_filter is not None
            and tag_filter not in self._normalized_tags(frontmatter.get("tags"))
        ):
            return False
        if topic_filter is not None:
            topic = str(frontmatter.get("topic") or "")
            domain = str(frontmatter.get("domain") or "")
            if topic != topic_filter.topic and topic_filter.topic not in topic:
                return False
            if topic_filter.domain is not None and domain != topic_filter.domain:
                return False
        if (
            request.platform
            and str(frontmatter.get("platform") or "").casefold()
            != request.platform.casefold()
        ):
            return False
        if (
            request.status
            and str(frontmatter.get("status") or "active").casefold()
            != request.status.casefold()
        ):
            return False
        if (
            request.min_confidence is not None
            and self._confidence(frontmatter) < request.min_confidence
        ):
            return False
        row_date = self._date(frontmatter)
        if request.date_from or request.date_to:
            if not row_date:
                return False
        if request.date_from and row_date < request.date_from:
            return False
        if request.date_to and row_date > request.date_to:
            return False
        return True

    def _search_text(self, doc: MarkdownDoc) -> str:
        title = str(doc.frontmatter.get("title") or "")
        return f"{title}\n{doc.body}".casefold()

    def _row(self, doc: MarkdownDoc) -> dict:
        frontmatter = doc.frontmatter
        assert doc.path is not None
        title = self._string_or_none(frontmatter.get("title")) or doc.path.stem
        return {
            "root": "knowledge",
            "type": self._string_or_none(frontmatter.get("type")),
            "title": title,
            "domain": self._string_or_none(frontmatter.get("domain")),
            "topic": self._string_or_none(frontmatter.get("topic")),
            "platform": self._string_or_none(frontmatter.get("platform")),
            "date": self._date(frontmatter),
            "tags": self._tags(frontmatter.get("tags")),
            "confidence": self._confidence(frontmatter),
            "status": self._string_or_none(frontmatter.get("status")) or "active",
            "resource": self._string_or_none(frontmatter.get("resource")),
            "path": self._relative_path(doc),
        }

    def _relative_path(self, doc: MarkdownDoc) -> str:
        assert doc.path is not None
        try:
            return doc.path.relative_to(self.knowledge_root).as_posix()
        except ValueError:
            return doc.path.as_posix()

    def _normalize_tag_filter(self, tag: str | None) -> str | None:
        if tag is None:
            return None
        return normalize_tag(tag, self.taxonomy)

    def _normalize_topic_filter(self, topic: str | None) -> TopicFilter | None:
        if topic is None:
            return None
        if "/" in topic:
            domain, topic_slug = split_domain_topic(topic, self.taxonomy)
            return TopicFilter(topic=topic_slug, domain=domain)
        return TopicFilter(topic=normalize_topic(topic, self.taxonomy))

    def _normalized_tags(self, value: object) -> list[str]:
        return [normalize_tag(tag, self.taxonomy) for tag in self._tags(value)]

    def _tags(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if value:
            return [str(value)]
        return []

    def _string_or_none(self, value: object) -> str | None:
        if value is None:
            return None
        return str(value)

    def _docs(self) -> list[MarkdownDoc]:
        return [
            doc
            for doc in self.repo.list_docs(self.knowledge_root)
            if doc.path is not None and not self._is_infrastructure_doc(doc)
        ]

    def _is_infrastructure_doc(self, doc: MarkdownDoc) -> bool:
        return str(doc.frontmatter.get("type") or "") in INFRASTRUCTURE_TYPES

    def _date(self, frontmatter: dict) -> str:
        value = (
            frontmatter.get("date")
            or frontmatter.get("published_date")
            or frontmatter.get("created_at")
            or frontmatter.get("timestamp")
            or ""
        )
        if isinstance(value, date):
            return value.isoformat()
        return str(value)[:10]

    def _confidence(self, frontmatter: dict) -> float:
        try:
            return float(frontmatter.get("confidence", 0.5))
        except (TypeError, ValueError):
            return 0.5
