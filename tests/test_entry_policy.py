from __future__ import annotations

from alcove.entry_policy import default_toolset_for_entry, entry_mode_policy
from alcove.mcp_toolsets import mcp_tool_inventory, resolve_mcp_toolset


def test_entry_policy_centralizes_default_toolsets() -> None:
    assert default_toolset_for_entry("hub") == "full"
    assert default_toolset_for_entry("global") == "lite"
    assert default_toolset_for_entry("managed-kb") == "kb"
    assert default_toolset_for_entry("service") == "none"


def test_mcp_toolset_aliases_follow_entry_policy() -> None:
    assert resolve_mcp_toolset("hub")[0] == "full"
    assert resolve_mcp_toolset("global-lite")[0] == "lite"
    assert resolve_mcp_toolset("knowledge-base")[0] == "kb"


def test_mcp_toolsets_resolve_from_inventory() -> None:
    inventory = mcp_tool_inventory()
    known_tools = {tool for tools in inventory.values() for tool in tools}
    lite_tools = resolve_mcp_toolset("lite")[1]
    kb_tools = resolve_mcp_toolset("kb")[1]

    assert lite_tools <= known_tools
    assert kb_tools <= known_tools
    assert set(inventory["guidance"]) | set(inventory["search"]) <= lite_tools
    assert set(inventory["inbox"]) | set(inventory["knowledge"]) <= kb_tools
    assert set(inventory["external_indexes"]).isdisjoint(lite_tools)
    assert set(inventory["external_indexes"]).isdisjoint(kb_tools)


def test_entry_policy_documents_read_write_scope() -> None:
    policy = entry_mode_policy("global")

    assert policy.as_dict() == {
        "mode": "global",
        "default_toolset": "lite",
        "read_scope": "home-wide",
        "write_scope": "lightweight governed memory writes only",
        "description": "Small MCP surface for unrelated projects.",
    }
