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
from alcove.workspace import Workspace


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
        rows.sort(key=self._sort_key)
        return rows[: plan.limit]

    def _sort_key(self, row: SearchRow) -> tuple[int, int, str, str]:
        return (
            self._status_rank(str(row.get("status") or "active")),
            self._information_rank(row),
            str(row.get("date") or ""),
            str(row.get("title") or "").casefold(),
        )

    def _information_rank(self, row: SearchRow) -> int:
        quality = row.get("information_quality")
        if isinstance(quality, dict) and quality.get("status") not in {"", None, "ok"}:
            return 1
        return 0

    def _status_rank(self, status: str) -> int:
        return {
            "active": 0,
            "fresh": 0,
            "pending": 1,
            "needs-review": 2,
            "todo": 2,
            "superseded": 3,
            "archived": 4,
            "cancelled": 4,
            "done": 4,
        }.get(status.casefold(), 1)

    def _iter_rows(
        self,
        request: Any,
        plan: SearchQueryPlan,
    ) -> Iterator[SearchRow]:
        yield from self._knowledge_rows(request, plan)
        yield from self._registered_kb_rows(request, plan)
        yield from self._pin_rows(plan)
        yield from self._project_rows(plan)
        yield from self._prompt_rows(plan)
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

    def _registered_kb_rows(
        self,
        request: Any,
        plan: SearchQueryPlan,
    ) -> Iterator[SearchRow]:
        if self.runtime.home is None or self.runtime.workspace is not None:
            return
        for record in self.runtime.home.list_knowledge_bases():
            knowledge_root = Workspace.discover(record.path).paths().knowledge
            rows = SearchRowBuilder(knowledge_root)
            for doc in self.repo.list_docs(knowledge_root, type_filter=request.type_filter):
                if doc.path is None:
                    continue
                if request.type_filter is None and is_infrastructure_doc(doc):
                    continue
                if not plan.matches_doc(doc):
                    continue
                row = rows.knowledge_doc(doc)
                row["kb"] = record.name
                row["path"] = f"knowledge-bases/{record.name}/{row['path']}"
                yield row

    def _pin_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        yield from GlobalHomeSearchAdapter(self.runtime, self.rows).pin_rows(plan)

    def _task_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        yield from GlobalHomeSearchAdapter(self.runtime, self.rows).task_rows(plan)

    def _project_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        yield from GlobalHomeSearchAdapter(self.runtime, self.rows).project_rows(plan)

    def _prompt_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        yield from GlobalHomeSearchAdapter(self.runtime, self.rows).prompt_rows(plan)

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
