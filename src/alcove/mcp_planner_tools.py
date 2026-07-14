from __future__ import annotations

from typing import Any

from alcove.mcp_context import McpInvocationContext
from alcove.mcp_registrar import McpToolRegistrar
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest


def register_mcp_planner_tools(
    registrar: McpToolRegistrar,
    context: McpInvocationContext,
) -> None:
    tool = registrar.tool

    @tool
    def alcove_task_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        due: str = "",
    ) -> dict[str, Any]:
        """Create a personal task through the governed planner write path."""
        return context.scoped_app(workspace, home).global_home.task_add_payload(
            AddTaskRequest(
                title=title,
                notes=notes,
                tags=tags or [],
                priority=priority,
                due=due,
            )
        )

    @tool
    def alcove_task_list(
        workspace: str = "",
        status: str = "pending",
        home: str = "",
    ) -> dict[str, Any]:
        """List personal tasks."""
        return context.scoped_app(workspace, home).global_home.task_list_payload(status)

    @tool
    def alcove_task_edit(
        task_id: str,
        workspace: str = "",
        home: str = "",
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
        priority: str | None = None,
        due: str | None = None,
    ) -> dict[str, Any]:
        """Edit a personal task through the governed planner write path."""
        return context.scoped_app(workspace, home).global_home.task_edit_payload(
            task_id,
            title=title,
            notes=notes,
            tags=tags,
            priority=priority,
            due=due,
        )

    @tool
    def alcove_task_complete(
        task_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Complete a task."""
        return context.scoped_app(workspace, home).global_home.task_complete_payload(task_id)

    @tool
    def alcove_task_cancel(
        task_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Cancel a task."""
        return context.scoped_app(workspace, home).global_home.task_cancel_payload(task_id)

    @tool
    def alcove_idea_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Add a low-friction idea through the governed planner write path."""
        return context.scoped_app(workspace, home).global_home.idea_add_payload(
            AddIdeaRequest(title=title, notes=notes, tags=tags or [])
        )

    @tool
    def alcove_idea_list(
        workspace: str = "",
        home: str = "",
        status: str = "active",
    ) -> dict[str, Any]:
        """List low-friction ideas."""
        return context.scoped_app(workspace, home).global_home.idea_list_payload(status)

    @tool
    def alcove_idea_promote(
        idea_id: str,
        workspace: str = "",
        home: str = "",
        priority: str = "medium",
        due: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        """Promote an idea into a concrete task."""
        return context.scoped_app(workspace, home).global_home.idea_promote_payload(
            idea_id=idea_id,
            priority=priority,
            due=due,
            notes=notes,
        )

    @tool
    def alcove_idea_edit(
        idea_id: str,
        workspace: str = "",
        home: str = "",
        title: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Edit a low-friction idea through the governed planner write path."""
        return context.scoped_app(workspace, home).global_home.idea_edit_payload(
            idea_id,
            title=title,
            notes=notes,
            tags=tags,
        )

    @tool
    def alcove_idea_archive(
        idea_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Archive a low-friction idea."""
        return context.scoped_app(workspace, home).global_home.idea_archive_payload(idea_id)

    @tool
    def alcove_idea_promote_routine(
        idea_id: str,
        workspace: str = "",
        home: str = "",
        priority: str = "medium",
        next_due: str = "",
        notes: str = "",
        schedule: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Promote an idea into a recurring task template."""
        return context.scoped_app(workspace, home).global_home.idea_promote_routine_payload(
            idea_id=idea_id,
            priority=priority,
            next_due=next_due,
            notes=notes,
            schedule=schedule or {},
        )

    @tool
    def alcove_routine_add(
        title: str,
        workspace: str = "",
        home: str = "",
        notes: str = "",
        tags: list[str] | None = None,
        priority: str = "medium",
        every_days: int = 1,
        next_due: str = "",
        schedule: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create a recurring task template."""
        return context.scoped_app(workspace, home).global_home.routine_add_payload(
            AddRoutineRequest(
                title=title,
                notes=notes,
                tags=tags or [],
                priority=priority,
                every_days=every_days,
                next_due=next_due,
                schedule=schedule or {},
            )
        )

    @tool
    def alcove_routine_list(
        workspace: str = "",
        status: str = "active",
        home: str = "",
    ) -> dict[str, Any]:
        """List recurring task templates."""
        return context.scoped_app(workspace, home).global_home.routine_list_payload(status)

    @tool
    def alcove_routine_materialize_due(
        workspace: str = "",
        today: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Create tasks for due recurring templates."""
        return context.scoped_app(workspace, home).global_home.routine_materialize_due_payload(
            today
        )

    @tool
    def alcove_routine_pause(
        routine_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Pause a recurring task template."""
        return context.scoped_app(workspace, home).global_home.routine_pause_payload(routine_id)

    @tool
    def alcove_routine_resume(
        routine_id: str,
        workspace: str = "",
        home: str = "",
        today: str = "",
    ) -> dict[str, Any]:
        """Resume a recurring task template."""
        return context.scoped_app(workspace, home).global_home.routine_resume_payload(
            routine_id,
            today=today,
        )

    @tool
    def alcove_routine_archive(
        routine_id: str,
        workspace: str = "",
        home: str = "",
    ) -> dict[str, Any]:
        """Archive a recurring task template."""
        return context.scoped_app(workspace, home).global_home.routine_archive_payload(routine_id)

    @tool
    def alcove_task_digest(
        workspace: str = "",
        home: str = "",
        period: str = "weekly",
        today: str = "",
        notify: bool = False,
    ) -> dict[str, Any]:
        """Build a planner digest, optionally notifying through configured credentials."""
        return context.scoped_app(workspace, home).global_home.task_digest_payload(
            period=period,
            today=today,
            notify=notify,
        )
