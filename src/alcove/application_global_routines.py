from __future__ import annotations

from typing import Any

from alcove.application_global_planner_payloads import _GlobalPlannerPayloadSupport
from alcove.tasks import AddRoutineRequest


class _GlobalRoutineCapabilities(_GlobalPlannerPayloadSupport):
    """Routine payload implementation for the global planner capability group."""

    def routine_add_payload(self, request: AddRoutineRequest) -> dict[str, Any]:
        routine = self._tasks_module().routine_add(request)
        return self._planner_item_write_payload(
            status="added",
            field="routine",
            item=routine,
            action="routine.add",
            target=routine.id,
            activity_summary=f"Added routine: {routine.title}",
            activity_metadata={"id": routine.id},
        )

    def routine_list_payload(self, status: str = "active") -> dict[str, Any]:
        return self._planner_list_payload("routines", self._tasks_module().routine_list(status))

    def routine_materialize_due_payload(self, today: str = "") -> dict[str, Any]:
        created = self._tasks_module().routine_materialize_due(today=today or None)
        return self._planner_write_payload(
            {"status": "materialized", "created": self._planner_items(created)},
            action="routine.materialize_due",
            target=today or "due",
            activity_summary="Materialized due routines",
            activity_metrics={"created": len(created)},
            activity_metadata={"today": today},
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
        routine = self._tasks_module().routine_edit(
            routine_id,
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            schedule=schedule,
            next_due=next_due,
        )
        return self._planner_item_write_payload(
            status="updated",
            field="routine",
            item=routine,
            action="routine.edit",
            target=routine.id,
            activity_summary=f"Edited routine: {routine.title}",
            activity_metadata={"id": routine.id},
        )

    def routine_pause_payload(self, routine_id: str) -> dict[str, Any]:
        routine = self._tasks_module().routine_pause(routine_id)
        return self._planner_item_write_payload(
            status="paused",
            field="routine",
            item=routine,
            action="routine.pause",
            target=routine.id,
            activity_summary=f"Paused routine: {routine.title}",
            activity_metadata={"id": routine.id},
        )

    def routine_resume_payload(self, routine_id: str, today: str = "") -> dict[str, Any]:
        routine = self._tasks_module().routine_resume(routine_id, today=today or None)
        return self._planner_item_write_payload(
            status="active",
            field="routine",
            item=routine,
            action="routine.resume",
            target=routine.id,
            activity_summary=f"Resumed routine: {routine.title}",
            activity_metadata={"id": routine.id},
        )

    def routine_archive_payload(self, routine_id: str) -> dict[str, Any]:
        routine = self._tasks_module().routine_archive(routine_id)
        return self._planner_item_write_payload(
            status="archived",
            field="routine",
            item=routine,
            action="routine.archive",
            target=routine.id,
            activity_summary=f"Archived routine: {routine.title}",
            activity_metadata={"id": routine.id},
        )
