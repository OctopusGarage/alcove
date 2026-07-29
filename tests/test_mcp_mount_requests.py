from alcove.mcp_mount_requests import mount_add_request, mount_index_policy_request


def test_mcp_mount_add_request_preserves_mount_fields() -> None:
    request = mount_add_request(
        path="/tmp/source-docs",
        name="Source Docs",
        mount_type="git-repo-local",
        tags=["docs", "agent"],
        profile="docs",
        include=["**/*.md"],
        exclude=["drafts/**"],
        max_file_size_kb=512,
    )

    assert request.path == "/tmp/source-docs"
    assert request.name == "Source Docs"
    assert request.mount_type == "git-repo-local"
    assert request.tags == ["docs", "agent"]
    assert request.index_policy.profile == "docs"
    assert request.index_policy.include == ["**/*.md"]
    assert request.index_policy.exclude == ["drafts/**"]
    assert request.index_policy.max_file_size_kb == 512


def test_mcp_mount_add_request_defaults_adapter_values() -> None:
    request = mount_add_request(path="/tmp/source-docs")

    assert request.name == ""
    assert request.mount_type == "local-folder"
    assert request.tags == []
    assert request.index_policy.profile == "raw"
    assert request.index_policy.include == []
    assert request.index_policy.exclude == []
    assert request.index_policy.max_file_size_kb == 976


def test_mcp_mount_index_policy_request_preserves_policy_fields() -> None:
    policy = mount_index_policy_request(
        profile="docs",
        include=["**/*.md"],
        exclude=["archive/**"],
        max_file_size_kb=256,
    )

    assert policy.profile == "docs"
    assert policy.include == ["**/*.md"]
    assert policy.exclude == ["archive/**"]
    assert policy.max_file_size_kb == 256


def test_mcp_mount_index_policy_request_defaults_adapter_values() -> None:
    policy = mount_index_policy_request()

    assert policy.profile == "raw"
    assert policy.include == []
    assert policy.exclude == []
    assert policy.max_file_size_kb == 976
