from alcove.mcp_project_requests import project_add_request


def test_mcp_project_add_request_preserves_project_fields() -> None:
    request = project_add_request(
        alias="alcove",
        path="/tmp/alcove",
        note="Knowledge manager.",
    )

    assert request.alias == "alcove"
    assert request.path == "/tmp/alcove"
    assert request.note == "Knowledge manager."


def test_mcp_project_add_request_defaults_note_to_empty_string() -> None:
    request = project_add_request(alias="alcove", path="/tmp/alcove")

    assert request.note == ""
