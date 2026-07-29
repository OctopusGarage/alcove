from alcove.mcp_pin_requests import pin_add_request, pin_update_request


def test_mcp_pin_add_request_normalizes_list_defaults():
    request = pin_add_request(title="MCP Pin")

    assert request.title == "MCP Pin"
    assert request.tags == []
    assert request.source_refs == []
    assert request.resources == []


def test_mcp_pin_update_request_preserves_omitted_optional_lists():
    request = pin_update_request(pin_id="mcp-pin", content="Updated content")

    assert request.pin_id == "mcp-pin"
    assert request.content == "Updated content"
    assert request.tags is None
    assert request.source_refs is None
    assert request.resources is None
