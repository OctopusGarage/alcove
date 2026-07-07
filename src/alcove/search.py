from __future__ import annotations

from dataclasses import dataclass

from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.taxonomy import load_taxonomy, normalize_tag, normalize_topic, split_domain_topic
from alcove.workspace import Workspace


@dataclass(frozen=True)
class SearchRequest:
    query: str
    type_filter: str | None = None
    tag: str | None = None
    topic: str | None = None
    limit: int = 20


class SearchModule:
    def __init__(self, workspace: Workspace, repo: MarkdownRepository | None = None) -> None:
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

        for doc in self.repo.list_docs(self.knowledge_root, type_filter=request.type_filter):
            if doc.path is None:
                continue
            if not self._matches_filters(doc, tag_filter, topic_filter):
                continue
            if query and query not in self._search_text(doc):
                continue

            rows.append(self._row(doc))
            if len(rows) >= limit:
                break

        return rows

    def _matches_filters(
        self,
        doc: MarkdownDoc,
        tag_filter: str | None,
        topic_filter: str | None,
    ) -> bool:
        frontmatter = doc.frontmatter
        if (
            tag_filter is not None
            and tag_filter not in self._normalized_tags(frontmatter.get("tags"))
        ):
            return False
        if topic_filter is not None and frontmatter.get("topic") != topic_filter:
            return False
        return True

    def _search_text(self, doc: MarkdownDoc) -> str:
        title = str(doc.frontmatter.get("title") or "")
        return f"{title}\n{doc.body}".casefold()

    def _row(self, doc: MarkdownDoc) -> dict:
        frontmatter = doc.frontmatter
        assert doc.path is not None
        return {
            "root": "knowledge",
            "type": frontmatter.get("type"),
            "title": frontmatter.get("title") or doc.path.stem,
            "topic": frontmatter.get("topic"),
            "tags": self._tags(frontmatter.get("tags")),
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

    def _normalize_topic_filter(self, topic: str | None) -> str | None:
        if topic is None:
            return None
        if "/" in topic:
            return split_domain_topic(topic, self.taxonomy)[1]
        return normalize_topic(topic, self.taxonomy)

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
