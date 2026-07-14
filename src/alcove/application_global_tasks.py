from __future__ import annotations

from dataclasses import asdict
from typing import Any

from alcove.application_base import _Capability
from alcove.tasks import AddTaskRequest, TasksModule


class _GlobalTaskCapabilities(_Capability):
    """Task payload implementation for the global planner capability group."""

    def task_add_payload(self, request: AddTaskRequest) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_add(request)
        self._record_action(
            area="task",
            action="task.add",
            summary=f"Added task: {task.title}",
            metadata={"id": task.id, "priority": task.priority},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "added", "task": asdict(task)},
                area="task",
                action="task.add",
                target=task.id,
                source_of_truth="tasks",
            )
        )

    def task_list_payload(self, status: str = "pending") -> dict[str, Any]:
        tasks = [
            asdict(task)
            for task in TasksModule(self.runtime.workspace, home=self.runtime.home).task_list(
                status
            )
        ]
        return self.runtime.scope_payload({"count": len(tasks), "tasks": tasks})

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
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_edit(
            task_id,
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            due=due,
        )
        self._record_action(
            area="task",
            action="task.edit",
            summary=f"Edited task: {task.title}",
            metadata={"id": task.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "updated", "task": asdict(task)},
                area="task",
                action="task.edit",
                target=task.id,
                source_of_truth="tasks",
            )
        )

    def task_complete_payload(self, task_id: str) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_complete(task_id)
        self._record_action(
            area="task",
            action="task.complete",
            summary=f"Completed task: {task.title}",
            metadata={"id": task.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "completed", "task": asdict(task)},
                area="task",
                action="task.complete",
                target=task.id,
                source_of_truth="tasks",
            )
        )

    def task_cancel_payload(self, task_id: str) -> dict[str, Any]:
        task = TasksModule(self.runtime.workspace, home=self.runtime.home).task_cancel(task_id)
        self._record_action(
            area="task",
            action="task.cancel",
            summary=f"Cancelled task: {task.title}",
            metadata={"id": task.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "cancelled", "task": asdict(task)},
                area="task",
                action="task.cancel",
                target=task.id,
                source_of_truth="tasks",
            )
        )

    def task_digest_payload(
        self,
        *,
        period: str = "weekly",
        today: str = "",
        notify: bool = False,
    ) -> dict[str, Any]:
        payload = TasksModule(self.runtime.workspace, home=self.runtime.home).task_digest(
            period=period,
            today=today or None,
            notify=notify,
        )
        self._record_action(
            area="task",
            action="task.digest",
            summary=f"Built task digest: {period}",
            metadata={"period": period, "notified": bool(notify)},
            visible=False,
        )
        return self.runtime.scope_payload(payload)
