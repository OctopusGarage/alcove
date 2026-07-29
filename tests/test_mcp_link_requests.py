from alcove.mcp_link_requests import link_source_request


def test_link_source_request_preserves_adapter_values() -> None:
    request = link_source_request(
        item_path="connectors/github-stars#octocat/hello",
        topic="engineering/testing",
        summary="Useful example",
        create_concept=True,
    )

    assert request.item_path == "connectors/github-stars#octocat/hello"
    assert request.topic == "engineering/testing"
    assert request.summary == "Useful example"
    assert request.create_concept is True


def test_link_source_request_uses_mcp_defaults() -> None:
    request = link_source_request(
        item_path="mounts/repos#README.md",
        topic="engineering/architecture",
    )

    assert request.summary == ""
    assert request.create_concept is False
