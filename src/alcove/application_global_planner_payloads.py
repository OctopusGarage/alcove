from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from alcove.application_base import _Capability
from alcove.tasks import TasksModule


class _GlobalPlannerPayloadSupport(_Capability):
    """Shared payload support for global task, idea, and routine capabilities."""

    def _tasks_module(self) -> TasksModule:
        return TasksModule(self.runtime.workspace, home=self.runtime.home)

    def _planner_item(self, item: Any) -> dict[str, Any]:
        return asdict(item)

    def _planner_items(self, items: Sequence[Any]) -> list[dict[str, Any]]:
        return [self._planner_item(item) for item in items]

    def _planner_list_payload(self, field: str, items: Sequence[Any]) -> dict[str, Any]:
        rows = self._planner_items(items)
        return self.runtime.scope_payload({"count": len(rows), field: rows})

    def _record_planner_action(
        self,
        *,
        action: str,
        summary: str,
        metrics: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        visible: bool = True,
    ) -> None:
        self._record_action(
            area="task",
            action=action,
            summary=summary,
            metrics=metrics,
            metadata=metadata,
            visible=visible,
        )

    def _planner_write_payload(
        self,
        payload: dict[str, Any],
        *,
        action: str,
        target: str,
        activity_summary: str = "",
        activity_metrics: dict[str, Any] | None = None,
        activity_metadata: dict[str, Any] | None = None,
        activity_visible: bool = True,
    ) -> dict[str, Any]:
        if activity_summary:
            self._record_planner_action(
                action=action,
                summary=activity_summary,
                metrics=activity_metrics,
                metadata=activity_metadata,
                visible=activity_visible,
            )
        return self.runtime.scope_payload(
            self._governed_write(
                payload,
                area="task",
                action=action,
                target=target,
                source_of_truth="tasks",
            )
        )

    def _planner_item_write_payload(
        self,
        *,
        status: str,
        field: str,
        item: Any,
        action: str,
        target: str,
        activity_summary: str = "",
        activity_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._planner_write_payload(
            {"status": status, field: self._planner_item(item)},
            action=action,
            target=target,
            activity_summary=activity_summary,
            activity_metadata=activity_metadata,
        )
