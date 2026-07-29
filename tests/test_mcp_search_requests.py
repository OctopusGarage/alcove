from alcove.mcp_search_requests import search_request


def test_mcp_search_request_preserves_search_fields() -> None:
    request = search_request(
        query="agent memory",
        type_filter="Source",
        tag="mcp",
        topic="agent-engineering/agent-harness",
        platform="web",
        date_from="2026-07-01",
        date_to="2026-07-29",
        min_confidence=0.75,
        status="active",
        limit=7,
    )

    assert request.query == "agent memory"
    assert request.type_filter == "Source"
    assert request.tag == "mcp"
    assert request.topic == "agent-engineering/agent-harness"
    assert request.platform == "web"
    assert request.date_from == "2026-07-01"
    assert request.date_to == "2026-07-29"
    assert request.min_confidence == 0.75
    assert request.status == "active"
    assert request.limit == 7


def test_mcp_search_request_defaults_to_broad_candidate_search() -> None:
    request = search_request()

    assert request.query == ""
    assert request.type_filter is None
    assert request.tag is None
    assert request.topic is None
    assert request.platform is None
    assert request.date_from is None
    assert request.date_to is None
    assert request.min_confidence is None
    assert request.status is None
    assert request.limit == 20
