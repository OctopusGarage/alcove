from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from alcove.markdown import MarkdownDoc
from alcove.okf import frontmatter_confidence, frontmatter_date, value_list
from alcove.taxonomy import normalize_tag, normalize_topic, split_domain_topic


@dataclass(frozen=True)
class TopicFilter:
    topic: str
    domain: str | None = None


@dataclass(frozen=True)
class SearchQueryPlan:
    query: str
    type_filter: str | None
    tag_filter: str | None
    topic_filter: TopicFilter | None
    platform: str | None
    date_from: str | None
    date_to: str | None
    min_confidence: float | None
    status: str | None
    limit: int
    taxonomy: dict[str, Any]

    @classmethod
    def from_request(cls, request: Any, taxonomy: dict[str, Any]) -> "SearchQueryPlan":
        return cls(
            query=str(request.query or "").casefold(),
            type_filter=request.type_filter,
            tag_filter=cls._normalize_tag_filter(request.tag, taxonomy),
            topic_filter=cls._normalize_topic_filter(request.topic, taxonomy),
            platform=request.platform,
            date_from=request.date_from,
            date_to=request.date_to,
            min_confidence=request.min_confidence,
            status=request.status,
            limit=max(int(request.limit), 0),
            taxonomy=taxonomy,
        )

    def allows_type(self, *types: str) -> bool:
        return self.type_filter is None or self.type_filter in set(types)

    def matches_doc(self, doc: MarkdownDoc) -> bool:
        frontmatter = doc.frontmatter
        if self.type_filter and str(frontmatter.get("type") or "") != self.type_filter:
            return False
        if self.tag_filter is not None and self.tag_filter not in self._normalized_tags(
            frontmatter.get("tags")
        ):
            return False
        if self.topic_filter is not None:
            topic = str(frontmatter.get("topic") or "")
            domain = str(frontmatter.get("domain") or "")
            if topic != self.topic_filter.topic and self.topic_filter.topic not in topic:
                return False
            if self.topic_filter.domain is not None and domain != self.topic_filter.domain:
                return False
        if (
            self.platform
            and str(frontmatter.get("platform") or "").casefold() != self.platform.casefold()
        ):
            return False
        if (
            self.status
            and str(frontmatter.get("status") or "active").casefold() != self.status.casefold()
        ):
            return False
        if (
            self.min_confidence is not None
            and frontmatter_confidence(frontmatter) < self.min_confidence
        ):
            return False
        return self._matches_date(frontmatter_date(frontmatter))

    def matches_row(self, row: Mapping[str, Any]) -> bool:
        if self.type_filter and str(row.get("type") or "") != self.type_filter:
            return False
        if self.tag_filter is not None and self.tag_filter not in self._normalized_tags(
            row.get("tags")
        ):
            return False
        if self.platform and str(row.get("platform") or "").casefold() != self.platform.casefold():
            return False
        if self.topic_filter is not None:
            row_topic = str(row.get("topic") or "").casefold()
            if self.topic_filter.topic.casefold() not in row_topic:
                return False
        if self.status and str(row.get("status") or "").casefold() != self.status.casefold():
            return False
        return self._matches_date(str(row.get("date") or ""))

    def matches_text(self, row: Mapping[str, Any]) -> bool:
        return not self.query or self.query in self.row_search_text(row)

    def row_search_text(self, row: Mapping[str, Any]) -> str:
        return f"{row.get('title') or ''}\n{row.get('notes') or ''}".casefold()

    def _matches_date(self, row_date: str) -> bool:
        if self.date_from or self.date_to:
            if not row_date:
                return False
        if self.date_from and row_date < self.date_from:
            return False
        if self.date_to and row_date > self.date_to:
            return False
        return True

    def _normalized_tags(self, value: object) -> list[str]:
        return [normalize_tag(tag, self.taxonomy) for tag in value_list(value)]

    @staticmethod
    def _normalize_tag_filter(tag: str | None, taxonomy: dict[str, Any]) -> str | None:
        if tag is None:
            return None
        return normalize_tag(tag, taxonomy)

    @staticmethod
    def _normalize_topic_filter(topic: str | None, taxonomy: dict[str, Any]) -> TopicFilter | None:
        if topic is None:
            return None
        if "/" in topic:
            domain, topic_slug = split_domain_topic(topic, taxonomy)
            return TopicFilter(topic=topic_slug, domain=domain)
        return TopicFilter(topic=normalize_topic(topic, taxonomy))
