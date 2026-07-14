from __future__ import annotations

from dataclasses import asdict
from typing import Any

from alcove.application_base import _Capability
from alcove.tasks import AddRoutineRequest, TasksModule


class _GlobalRoutineCapabilities(_Capability):
    """Routine payload implementation for the global planner capability group."""

    def routine_add_payload(self, request: AddRoutineRequest) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_add(request)
        self._record_action(
            area="task",
            action="routine.add",
            summary=f"Added routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "added", "routine": asdict(routine)},
                area="task",
                action="routine.add",
                target=routine.id,
                source_of_truth="tasks",
            )
        )

    def routine_list_payload(self, status: str = "active") -> dict[str, Any]:
        routines = [
            asdict(routine)
            for routine in TasksModule(self.runtime.workspace, home=self.runtime.home).routine_list(
                status
            )
        ]
        return self.runtime.scope_payload({"count": len(routines), "routines": routines})

    def routine_materialize_due_payload(self, today: str = "") -> dict[str, Any]:
        created = TasksModule(
            self.runtime.workspace,
            home=self.runtime.home,
        ).routine_materialize_due(today=today or None)
        self._record_action(
            area="task",
            action="routine.materialize_due",
            summary="Materialized due routines",
            metrics={"created": len(created)},
            metadata={"today": today},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "materialized", "created": [asdict(task) for task in created]},
                area="task",
                action="routine.materialize_due",
                target=today or "due",
                source_of_truth="tasks",
            )
        )

    def routine_edit_payload(
        self,
        routine_id: str,
        *,
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        schedule: dict[str, Any] | None = None,
        next_due: str | None = None,
    ) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_edit(
            routine_id,
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            schedule=schedule,
            next_due=next_due,
        )
        self._record_action(
            area="task",
            action="routine.edit",
            summary=f"Edited routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "updated", "routine": asdict(routine)},
                area="task",
                action="routine.edit",
                target=routine.id,
                source_of_truth="tasks",
            )
        )

    def routine_pause_payload(self, routine_id: str) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_pause(
            routine_id
        )
        self._record_action(
            area="task",
            action="routine.pause",
            summary=f"Paused routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "paused", "routine": asdict(routine)},
                area="task",
                action="routine.pause",
                target=routine.id,
                source_of_truth="tasks",
            )
        )

    def routine_resume_payload(self, routine_id: str, today: str = "") -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_resume(
            routine_id,
            today=today or None,
        )
        self._record_action(
            area="task",
            action="routine.resume",
            summary=f"Resumed routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "active", "routine": asdict(routine)},
                area="task",
                action="routine.resume",
                target=routine.id,
                source_of_truth="tasks",
            )
        )

    def routine_archive_payload(self, routine_id: str) -> dict[str, Any]:
        routine = TasksModule(self.runtime.workspace, home=self.runtime.home).routine_archive(
            routine_id
        )
        self._record_action(
            area="task",
            action="routine.archive",
            summary=f"Archived routine: {routine.title}",
            metadata={"id": routine.id},
        )
        return self.runtime.scope_payload(
            self._governed_write(
                {"status": "archived", "routine": asdict(routine)},
                area="task",
                action="routine.archive",
                target=routine.id,
                source_of_truth="tasks",
            )
        )
