from __future__ import annotations

import json

from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.mcp_server import inbox_peek_tool, mount_list_tool, search_tool
from alcove.mounts import AddMountRequest, MountsModule
from alcove.workspace import Workspace


def test_mcp_search_tool_returns_search_payload(tmp_path):
    workspace = Workspace.init(tmp_path)
    KnowledgeModule(workspace).note_source(
        NoteSourceRequest(
            platform="web",
            title="MCP Search Source",
            topic="agent-engineering/agent-harness",
            resource="https://example.test/mcp",
            summary="Searchable MCP summary.",
            tags=["mcp"],
        )
    )

    payload = search_tool(str(tmp_path), query="searchable", tag="mcp", type_filter="Source")

    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["count"] == 1
    assert payload["results"][0]["title"] == "MCP Search Source"
    json.dumps(payload, ensure_ascii=False)


def test_mcp_inbox_peek_tool_returns_oldest_inbox_item(tmp_path):
    Workspace.init(tmp_path)
    item = tmp_path / "inbox" / "web" / "20260708-mcp"
    item.mkdir(parents=True)
    (item / "article.md").write_text("# MCP Inbox\n\nBody", encoding="utf-8")

    payload = inbox_peek_tool(str(tmp_path))

    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["item"]["title"] == "MCP Inbox"
    assert payload["item"]["content_source"] == "article.md"


def test_mcp_mount_list_tool_returns_active_mounts(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source"
    source.mkdir()
    MountsModule(workspace).add(AddMountRequest(path=str(source), name="Source"))

    payload = mount_list_tool(str(workspace.root))

    assert payload["workspace"] == str(workspace.root)
    assert payload["count"] == 1
    assert payload["mounts"][0]["name"] == "Source"
