from __future__ import annotations

from typing import Any

from alcove.application_global_planner_payloads import _GlobalPlannerPayloadSupport
from alcove.tasks import AddIdeaRequest


class _GlobalIdeaCapabilities(_GlobalPlannerPayloadSupport):
    """Idea payload implementation for the global planner capability group."""

    def idea_add_payload(self, request: AddIdeaRequest) -> dict[str, Any]:
        idea = self._tasks_module().idea_add(request)
        return self._planner_item_write_payload(
            status="added",
            field="idea",
            item=idea,
            action="idea.add",
            target=idea.id,
            activity_summary=f"Added idea: {idea.title}",
            activity_metadata={"id": idea.id},
        )

    def idea_list_payload(self, status: str = "active") -> dict[str, Any]:
        return self._planner_list_payload("ideas", self._tasks_module().idea_list(status))

    def idea_edit_payload(
        self,
        idea_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        idea = self._tasks_module().idea_edit(
            idea_id,
            title=title,
            notes=notes,
            tags=tags,
        )
        return self._planner_item_write_payload(
            status="updated",
            field="idea",
            item=idea,
            action="idea.edit",
            target=idea.id,
            activity_summary=f"Edited idea: {idea.title}",
            activity_metadata={"id": idea.id},
        )

    def idea_archive_payload(self, idea_id: str) -> dict[str, Any]:
        idea = self._tasks_module().idea_archive(idea_id)
        return self._planner_item_write_payload(
            status="archived",
            field="idea",
            item=idea,
            action="idea.archive",
            target=idea.id,
            activity_summary=f"Archived idea: {idea.title}",
            activity_metadata={"id": idea.id},
        )

    def idea_promote_payload(
        self,
        idea_id: str,
        priority: str = "medium",
        due: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        tasks = self._tasks_module()
        task = tasks.idea_promote_to_task(
            idea_id,
            priority=priority,
            due=due,
            notes=notes,
        )
        idea = next(
            item for item in tasks.idea_list(status="promoted") if item.promoted_task_id == task.id
        )
        return self._planner_write_payload(
            {
                "status": "promoted",
                "idea": self._planner_item(idea),
                "task": self._planner_item(task),
            },
            action="idea.promote",
            target=idea.id,
        )

    def idea_promote_routine_payload(
        self,
        idea_id: str,
        *,
        priority: str = "medium",
        next_due: str = "",
        notes: str = "",
        schedule: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        tasks = self._tasks_module()
        routine = tasks.idea_promote_to_routine(
            idea_id,
            priority=priority,
            next_due=next_due,
            notes=notes,
            schedule=schedule or {},
        )
        idea = next(
            item
            for item in tasks.idea_list(status="promoted")
            if item.promoted_routine_id == routine.id
        )
        return self._planner_write_payload(
            {
                "status": "promoted",
                "idea": self._planner_item(idea),
                "routine": self._planner_item(routine),
            },
            action="idea.promote_routine",
            target=idea.id,
            activity_summary=f"Promoted idea to routine: {routine.title}",
            activity_metadata={"idea_id": idea.id, "routine_id": routine.id},
        )
