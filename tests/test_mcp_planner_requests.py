from alcove.mcp_planner_requests import routine_add_request, task_add_request


def test_mcp_task_add_request_preserves_task_fields() -> None:
    request = task_add_request(
        title="Review release notes",
        notes="Check the MCP-facing task payload.",
        tags=["release", "mcp"],
        priority="high",
        due="2026-08-01",
    )

    assert request.title == "Review release notes"
    assert request.notes == "Check the MCP-facing task payload."
    assert request.tags == ["release", "mcp"]
    assert request.priority == "high"
    assert request.due == "2026-08-01"


def test_mcp_task_add_request_defaults_optional_fields() -> None:
    request = task_add_request(title="Draft task")

    assert request.notes == ""
    assert request.tags == []
    assert request.priority == "medium"
    assert request.due == ""


def test_mcp_routine_add_request_preserves_routine_fields() -> None:
    schedule = {"kind": "weekly", "days": ["mon"]}
    request = routine_add_request(
        title="Review planner",
        notes="Inspect recurring work.",
        tags=["routine"],
        priority="low",
        every_days=7,
        next_due="2026-08-03",
        schedule=schedule,
    )

    assert request.title == "Review planner"
    assert request.notes == "Inspect recurring work."
    assert request.tags == ["routine"]
    assert request.priority == "low"
    assert request.every_days == 7
    assert request.next_due == "2026-08-03"
    assert request.schedule == schedule


def test_mcp_routine_add_request_defaults_optional_fields() -> None:
    request = routine_add_request(title="Draft routine")

    assert request.notes == ""
    assert request.tags == []
    assert request.priority == "medium"
    assert request.every_days == 1
    assert request.next_due == ""
    assert request.schedule == {}
