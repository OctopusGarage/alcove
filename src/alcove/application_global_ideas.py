from __future__ import annotations

from dataclasses import asdict
from typing import Any

from alcove.application_base import _Capability
from alcove.tasks import AddIdeaRequest, TasksModule


class _GlobalIdeaCapabilities(_Capability):
    """Idea payload implementation for the global planner capability group."""

    def idea_add_payload(self, request: AddIdeaRequest) -> dict[str, Any]:
        idea = TasksModule(self.runtime.workspace, home=self.runtime.home).idea_add(request)
        self._record_action(
            area="task",
            action="idea.add",
            summary=f"Added idea: {idea.title}",
            metadata={"id": idea.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "added", "idea": asdict(idea)},
                area="task",
                action="idea.add",
                target=idea.id,
                source_of_truth="tasks",
            )
        )

    def idea_list_payload(self, status: str = "active") -> dict[str, Any]:
        ideas = [
            asdict(idea)
            for idea in TasksModule(self.runtime.workspace, home=self.runtime.home).idea_list(
                status
            )
        ]
        return self.runtime.scope_payload({"count": len(ideas), "ideas": ideas})

    def idea_edit_payload(
        self,
        idea_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        idea = TasksModule(self.runtime.workspace, home=self.runtime.home).idea_edit(
            idea_id,
            title=title,
            notes=notes,
            tags=tags,
        )
        self._record_action(
            area="task",
            action="idea.edit",
            summary=f"Edited idea: {idea.title}",
            metadata={"id": idea.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "updated", "idea": asdict(idea)},
                area="task",
                action="idea.edit",
                target=idea.id,
                source_of_truth="tasks",
            )
        )

    def idea_archive_payload(self, idea_id: str) -> dict[str, Any]:
        idea = TasksModule(self.runtime.workspace, home=self.runtime.home).idea_archive(idea_id)
        self._record_action(
            area="task",
            action="idea.archive",
            summary=f"Archived idea: {idea.title}",
            metadata={"id": idea.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "archived", "idea": asdict(idea)},
                area="task",
                action="idea.archive",
                target=idea.id,
                source_of_truth="tasks",
            )
        )

    def idea_promote_payload(
        self,
        idea_id: str,
        priority: str = "medium",
        due: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        tasks = TasksModule(self.runtime.workspace, home=self.runtime.home)
        task = tasks.idea_promote_to_task(
            idea_id,
            priority=priority,
            due=due,
            notes=notes,
        )
        idea = next(
            item for item in tasks.idea_list(status="promoted") if item.promoted_task_id == task.id
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {
                    "status": "promoted",
                    "idea": asdict(idea),
                    "task": asdict(task),
                },
                area="task",
                action="idea.promote",
                target=idea.id,
                source_of_truth="tasks",
            )
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
        tasks = TasksModule(self.runtime.workspace, home=self.runtime.home)
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
        self._record_action(
            area="task",
            action="idea.promote_routine",
            summary=f"Promoted idea to routine: {routine.title}",
            metadata={"idea_id": idea.id, "routine_id": routine.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "promoted", "idea": asdict(idea), "routine": asdict(routine)},
                area="task",
                action="idea.promote_routine",
                target=idea.id,
                source_of_truth="tasks",
            )
        )
