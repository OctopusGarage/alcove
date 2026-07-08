from __future__ import annotations

from collections.abc import Iterator

from alcove.pins import PinsModule
from alcove.runtime import AlcoveRuntime
from alcove.search_query import SearchQueryPlan
from alcove.search_rows import SearchRow, SearchRowBuilder
from alcove.tasks import TasksModule


class GlobalHomeSearchAdapter:
    def __init__(self, runtime: AlcoveRuntime, rows: SearchRowBuilder) -> None:
        self.runtime = runtime
        self.rows = rows

    def pin_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        if not plan.allows_type("Pin"):
            return
        pins = PinsModule(self.runtime.workspace, home=self.runtime.home).list(status="")
        for pin in pins:
            row = self.rows.pin_item(pin)
            if plan.matches_row(row):
                yield row

    def task_rows(self, plan: SearchQueryPlan) -> Iterator[SearchRow]:
        tasks = TasksModule(self.runtime.workspace, home=self.runtime.home)
        if plan.allows_type("Idea"):
            idea_status = plan.status or "active"
            for idea in tasks.idea_list(status=idea_status):
                row = self.rows.idea_item(idea)
                if plan.matches_row(row):
                    yield row
        if plan.allows_type("Task"):
            task_status = plan.status or "pending"
            for task in tasks.task_list(status=task_status):
                row = self.rows.task_record(task)
                if plan.matches_row(row):
                    yield row
