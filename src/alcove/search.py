from __future__ import annotations

from dataclasses import dataclass

from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.okf import is_infrastructure_doc, value_list
from alcove.runtime import AlcoveRuntime
from alcove.search_rows import SearchRowBuilder
from alcove.search_sources import SearchSourceAggregator
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


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


class SearchModule:
    def __init__(
        self,
        workspace: Workspace | None = None,
        repo: MarkdownRepository | None = None,
        home: AlcoveHome | None = None,
    ) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.workspace = self.runtime.workspace
        self.home = self.runtime.home
        self.paths = self.workspace.paths() if self.workspace is not None else None
        self.knowledge_root = self.runtime.knowledge_root
        self.repo = repo or MarkdownRepository()
        self.taxonomy = load_taxonomy(self.runtime.taxonomy_root)
        self.pins_root = self.runtime.pins_root
        self.tasks_root = self.runtime.tasks_root
        self.mounts_root = self.runtime.mounts_root
        self.connectors_root = self.runtime.connectors_root
        self.rows = SearchRowBuilder(self.knowledge_root)

    def search(self, request: SearchRequest) -> list[dict]:
        return SearchSourceAggregator(self.runtime, self.repo, self.taxonomy).search(request)

    def tags(self) -> list[dict]:
        counts: dict[str, int] = {}
        for doc in self._docs():
            for tag in self._tags(doc.frontmatter.get("tags")):
                counts[tag] = counts.get(tag, 0) + 1
        return [
            {"tag": tag, "count": count}
            for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
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

    def _row(self, doc: MarkdownDoc) -> dict:
        return self.rows.knowledge_doc(doc)

    def _normalized_tags(self, value: object) -> list[str]:
        return [normalize_tag(tag, self.taxonomy) for tag in self._tags(value)]

    def _tags(self, value: object) -> list[str]:
        return value_list(value)

    def _docs(self) -> list[MarkdownDoc]:
        if self.knowledge_root is None:
            return []
        return [
            doc
            for doc in self.repo.list_docs(self.knowledge_root)
            if doc.path is not None and not self._is_infrastructure_doc(doc)
        ]

    def _is_infrastructure_doc(self, doc: MarkdownDoc) -> bool:
        return is_infrastructure_doc(doc)
