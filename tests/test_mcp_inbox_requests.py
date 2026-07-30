from alcove.mcp_inbox_requests import inbox_note_request


def test_mcp_inbox_note_request_normalizes_list_defaults():
    request = inbox_note_request(
        name="web/example",
        topic="agent-engineering/agent-harness",
        summary="Useful summary.",
    )

    assert request.name == "web/example"
    assert request.topic == "agent-engineering/agent-harness"
    assert request.summary == "Useful summary."
    assert request.tags == []
    assert request.selected_takeaways == []
    assert request.why == ""
    assert request.connection == ""
    assert request.action == ""
    assert request.personal_note == ""
    assert request.no_auto_tags is False
    assert request.supersede_similar is False


def test_mcp_inbox_note_request_preserves_supplied_values():
    request = inbox_note_request(
        name="web/example",
        topic="agent-engineering/agent-harness",
        summary="Useful summary.",
        tags=["mcp", "inbox"],
        selected_takeaways=["Keep the adapter thin."],
        why="Reduces request drift.",
        connection="Matches MCP helper modules.",
        action="Add helper tests.",
        personal_note="Local architecture slice.",
        no_auto_tags=True,
        supersede_similar=True,
    )

    assert request.tags == ["mcp", "inbox"]
    assert request.selected_takeaways == ["Keep the adapter thin."]
    assert request.why == "Reduces request drift."
    assert request.connection == "Matches MCP helper modules."
    assert request.action == "Add helper tests."
    assert request.personal_note == "Local architecture slice."
    assert request.no_auto_tags is True
    assert request.supersede_similar is True
