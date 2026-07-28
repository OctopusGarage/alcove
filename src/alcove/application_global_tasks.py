from __future__ import annotations

from typing import Any

from alcove.application_global_planner_payloads import _GlobalPlannerPayloadSupport
from alcove.tasks import AddTaskRequest


class _GlobalTaskCapabilities(_GlobalPlannerPayloadSupport):
    """Task payload implementation for the global planner capability group."""

    def task_add_payload(self, request: AddTaskRequest) -> dict[str, Any]:
        task = self._tasks_module().task_add(request)
        return self._planner_item_write_payload(
            status="added",
            field="task",
            item=task,
            action="task.add",
            target=task.id,
            activity_summary=f"Added task: {task.title}",
            activity_metadata={"id": task.id, "priority": task.priority},
        )

    def task_list_payload(self, status: str = "pending") -> dict[str, Any]:
        return self._planner_list_payload("tasks", self._tasks_module().task_list(status))

    def task_edit_payload(
        self,
        task_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        due: str | None = None,
    ) -> dict[str, Any]:
        task = self._tasks_module().task_edit(
            task_id,
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            due=due,
        )
        return self._planner_item_write_payload(
            status="updated",
            field="task",
            item=task,
            action="task.edit",
            target=task.id,
            activity_summary=f"Edited task: {task.title}",
            activity_metadata={"id": task.id},
        )

    def task_complete_payload(self, task_id: str) -> dict[str, Any]:
        task = self._tasks_module().task_complete(task_id)
        return self._planner_item_write_payload(
            status="completed",
            field="task",
            item=task,
            action="task.complete",
            target=task.id,
            activity_summary=f"Completed task: {task.title}",
            activity_metadata={"id": task.id},
        )

    def task_cancel_payload(self, task_id: str) -> dict[str, Any]:
        task = self._tasks_module().task_cancel(task_id)
        return self._planner_item_write_payload(
            status="cancelled",
            field="task",
            item=task,
            action="task.cancel",
            target=task.id,
            activity_summary=f"Cancelled task: {task.title}",
            activity_metadata={"id": task.id},
        )

    def task_digest_payload(
        self,
        *,
        period: str = "weekly",
        today: str = "",
        notify: bool = False,
    ) -> dict[str, Any]:
        payload = self._tasks_module().task_digest(
            period=period,
            today=today or None,
            notify=notify,
        )
        self._record_planner_action(
            action="task.digest",
            summary=f"Built task digest: {period}",
            metadata={"period": period, "notified": bool(notify)},
            visible=False,
        )
        return self.runtime.scope_payload(payload)
