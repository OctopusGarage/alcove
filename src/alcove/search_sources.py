from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from alcove.external_index import ExternalIndexStore
from alcove.markdown import MarkdownRepository
from alcove.okf import is_infrastructure_doc
from alcove.runtime import AlcoveRuntime
from alcove.search_global import GlobalHomeSearchAdapter
from alcove.search_query import SearchQueryPlan
from alcove.search_rows import SearchRow, SearchRowBuilder


class SearchSourceAggregator:
    def __init__(
        self,
        runtime: AlcoveRuntime,
        repo: MarkdownRepository,
        taxonomy: dict[str, Any],
    ) -> None:
        self.runtime = runtime
        self.repo = repo
        self.taxonomy = taxonomy
        self.knowledge_root = runtime.knowledge_root
        self.rows = SearchRowBuilder(self.knowledge_root)

    def search(self, request: Any) -> list[SearchRow]:
        rows: list[SearchRow] = []
        plan = SearchQueryPlan.from_request(request, self.taxonomy)
        if plan.limit == 0:
            return rows

        for row in self._iter_rows(request, plan):
            if not plan.matches_text(row):
                continue
            rows.append(row)
            if len(rows) >= plan.limit:
                break
        return rows

    def _iter_rows(
        self,
        request: Any,
        plan: SearchQueryPlan,
    ) -> Iterator[SearchRow]:
        yield from self._knowledge_rows(request, plan)
        yield from self._pin_rows(plan)
        yield from self._task_rows(plan)
        yield from self._mount_rows(plan)
        yield from self._connector_rows(plan)

    def _knowledge_rows(
        self,
        request: Any,
        plan: SearchQueryPlan,
    ) -> Iterator[SearchRow]:
        if self.knowledge_root is None:
            return
        for doc in self.repo.list_docs(self.knowledge_root, type_filter=request.type_filter):
            if doc.path is None:
                continue
            if request.type_filter is None and is_infrastructure_doc(doc):
                continue
            if not plan.matches_doc(doc):
                continue
            yield self.rows.knowledge_doc(doc)

    def _pin_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        yield from GlobalHomeSearchAdapter(self.runtime, self.rows).pin_rows(plan)

    def _task_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        yield from GlobalHomeSearchAdapter(self.runtime, self.rows).task_rows(plan)

    def _mount_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        if not plan.allows_type("Mounted Item"):
            return
        for dataset in ExternalIndexStore(self.runtime.mounts_root).mount_datasets():
            for item in dataset.items:
                row = self.rows.mount_item(item)
                if plan.matches_row(row):
                    yield row

    def _connector_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        for dataset in ExternalIndexStore(self.runtime.connectors_root).connector_datasets():
            for item in dataset.items:
                row = self.rows.connector_item(dataset.source_id, item)
                if plan.matches_row(row):
                    yield row
