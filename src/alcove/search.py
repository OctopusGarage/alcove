from __future__ import annotations

from dataclasses import dataclass

from alcove.markdown import MarkdownDoc, MarkdownRepository
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
        self.repo = repo or MarkdownRepository()

    def search(self, request: SearchRequest) -> list[dict]:
        rows: list[dict] = []
        limit = max(request.limit, 0)
        if limit == 0:
            return rows
        query = request.query.casefold()
        knowledge_root = self.workspace.paths().knowledge

        for doc in self.repo.list_docs(knowledge_root, type_filter=request.type_filter):
            if doc.path is None:
                continue
            if not self._matches_filters(doc, request):
                continue
            if query and query not in self._search_text(doc):
                continue

            rows.append(self._row(doc))
            if len(rows) >= limit:
                break

        return rows

    def _matches_filters(self, doc: MarkdownDoc, request: SearchRequest) -> bool:
        frontmatter = doc.frontmatter
        if request.tag is not None and request.tag not in self._tags(frontmatter.get("tags")):
            return False
        if request.topic is not None and frontmatter.get("topic") != request.topic:
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
            "path": doc.path,
        }

    def _tags(self, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if item]
        if value:
            return [str(value)]
        return []
