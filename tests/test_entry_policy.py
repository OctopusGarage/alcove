from __future__ import annotations

from alcove.entry_policy import default_toolset_for_entry, entry_mode_policy
from alcove.mcp_toolsets import resolve_mcp_toolset


def test_entry_policy_centralizes_default_toolsets() -> None:
    assert default_toolset_for_entry("hub") == "full"
    assert default_toolset_for_entry("global") == "lite"
    assert default_toolset_for_entry("managed-kb") == "kb"
    assert default_toolset_for_entry("service") == "none"


def test_mcp_toolset_aliases_follow_entry_policy() -> None:
    assert resolve_mcp_toolset("hub")[0] == "full"
    assert resolve_mcp_toolset("global-lite")[0] == "lite"
    assert resolve_mcp_toolset("knowledge-base")[0] == "kb"


def test_entry_policy_documents_read_write_scope() -> None:
    policy = entry_mode_policy("global")

    assert policy.as_dict() == {
        "mode": "global",
        "default_toolset": "lite",
        "read_scope": "home-wide",
        "write_scope": "lightweight governed memory writes only",
        "description": "Small MCP surface for unrelated projects.",
    }
