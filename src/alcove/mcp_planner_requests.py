from __future__ import annotations

from typing import Any

from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest


def idea_add_request(
    *,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
) -> AddIdeaRequest:
    """Build the planner idea write request shared by MCP adapter surfaces."""
    return AddIdeaRequest(
        title=title,
        notes=notes,
        tags=tags or [],
    )


def task_add_request(
    *,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    due: str = "",
) -> AddTaskRequest:
    """Build the planner task write request shared by MCP adapter surfaces."""
    return AddTaskRequest(
        title=title,
        notes=notes,
        tags=tags or [],
        priority=priority,
        due=due,
    )


def routine_add_request(
    *,
    title: str,
    notes: str = "",
    tags: list[str] | None = None,
    priority: str = "medium",
    every_days: int = 1,
    next_due: str = "",
    schedule: dict[str, Any] | None = None,
) -> AddRoutineRequest:
    """Build the planner routine write request shared by MCP adapter surfaces."""
    return AddRoutineRequest(
        title=title,
        notes=notes,
        tags=tags or [],
        priority=priority,
        every_days=every_days,
        next_due=next_due,
        schedule=schedule or {},
    )
