from alcove.mcp_knowledge_requests import (
    add_concept_request,
    add_entity_request,
    add_question_request,
    note_source_request,
    revise_knowledge_request,
)


def test_mcp_add_concept_request_preserves_okf_fields() -> None:
    request = add_concept_request(
        topic="agent-engineering/agent-harness",
        title="MCP Concept",
        summary="Concept summary.",
        tags=["mcp", "concept"],
    )

    assert request.topic == "agent-engineering/agent-harness"
    assert request.title == "MCP Concept"
    assert request.summary == "Concept summary."
    assert request.tags == ["mcp", "concept"]


def test_mcp_add_concept_request_defaults_to_empty_adapter_values() -> None:
    request = add_concept_request(
        topic="agent-engineering/agent-harness",
        title="Defaulted Concept",
    )

    assert request.summary == ""
    assert request.tags == []


def test_mcp_add_question_request_preserves_okf_fields() -> None:
    request = add_question_request(
        topic="agent-engineering/agent-harness",
        question="How should MCP adapters shape OKF requests?",
        answer="Through request helpers.",
        tags=["mcp", "question"],
        source_refs=["sources/web/agent-engineering/example.md"],
    )

    assert request.topic == "agent-engineering/agent-harness"
    assert request.question == "How should MCP adapters shape OKF requests?"
    assert request.answer == "Through request helpers."
    assert request.tags == ["mcp", "question"]
    assert request.source_refs == ["sources/web/agent-engineering/example.md"]


def test_mcp_add_question_request_defaults_to_empty_adapter_values() -> None:
    request = add_question_request(
        topic="agent-engineering/agent-harness",
        question="What defaults are used?",
    )

    assert request.answer == ""
    assert request.tags == []
    assert request.source_refs == []


def test_mcp_add_entity_request_preserves_okf_fields() -> None:
    request = add_entity_request(
        topic="agent-engineering/agent-harness",
        name="MCP Adapter",
        kind="system",
        summary="Routes tool calls.",
        use_cases="Governed writes.",
        open_questions="None.",
        tags=["mcp", "entity"],
        source_refs=["sources/web/agent-engineering/entity.md"],
    )

    assert request.topic == "agent-engineering/agent-harness"
    assert request.name == "MCP Adapter"
    assert request.kind == "system"
    assert request.summary == "Routes tool calls."
    assert request.use_cases == "Governed writes."
    assert request.open_questions == "None."
    assert request.tags == ["mcp", "entity"]
    assert request.source_refs == ["sources/web/agent-engineering/entity.md"]


def test_mcp_add_entity_request_defaults_to_empty_adapter_values() -> None:
    request = add_entity_request(
        topic="agent-engineering/agent-harness",
        name="Defaulted Entity",
    )

    assert request.kind == "object"
    assert request.summary == ""
    assert request.use_cases == ""
    assert request.open_questions == ""
    assert request.tags == []
    assert request.source_refs == []


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
