from alcove.mcp_knowledge_requests import note_source_request, revise_knowledge_request


def test_mcp_note_source_request_preserves_okf_fields() -> None:
    request = note_source_request(
        platform="web",
        title="MCP Knowledge",
        topic="agent-engineering/agent-harness",
        resource="https://example.test/mcp",
        summary="MCP summary.",
        tags=["mcp", "okf"],
        published_date="2026-07-29",
        create_concept=False,
    )

    assert request.platform == "web"
    assert request.title == "MCP Knowledge"
    assert request.topic == "agent-engineering/agent-harness"
    assert request.resource == "https://example.test/mcp"
    assert request.summary == "MCP summary."
    assert request.tags == ["mcp", "okf"]
    assert request.published_date == "2026-07-29"
    assert request.create_concept is False


def test_mcp_note_source_request_defaults_to_empty_adapter_values() -> None:
    request = note_source_request(
        platform="chat",
        title="Defaulted Source",
        topic="agent-engineering/agent-harness",
    )

    assert request.resource == ""
    assert request.summary == ""
    assert request.tags == []
    assert request.published_date is None
    assert request.create_concept is True


def test_mcp_revise_knowledge_request_preserves_okf_fields() -> None:
    request = revise_knowledge_request(
        path="concepts/agent-engineering/agent-harness/mcp.md",
        summary="New summary.",
        answer="New answer.",
        append="Appendix.",
        tags=["managed-kb"],
        source_refs=["sources/web/agent-engineering/example.md"],
        reason="Follow-up",
        status="active",
    )

    assert request.path == "concepts/agent-engineering/agent-harness/mcp.md"
    assert request.summary == "New summary."
    assert request.answer == "New answer."
    assert request.append == "Appendix."
    assert request.tags == ["managed-kb"]
    assert request.source_refs == ["sources/web/agent-engineering/example.md"]
    assert request.reason == "Follow-up"
    assert request.status == "active"


def test_mcp_revise_knowledge_request_defaults_to_empty_adapter_values() -> None:
    request = revise_knowledge_request(path="concepts/example.md")

    assert request.summary == ""
    assert request.answer == ""
    assert request.append == ""
    assert request.tags == []
    assert request.source_refs == []
    assert request.reason == ""
    assert request.status == ""
