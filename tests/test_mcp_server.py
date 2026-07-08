from __future__ import annotations

import asyncio
import json

from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.mcp_server import (
    create_mcp_server,
    gardener_tool,
    get_topic_tool,
    idea_promote_tool,
    inbox_peek_tool,
    mount_list_tool,
    note_source_tool,
    pin_add_tool,
    routine_add_tool,
    routine_list_tool,
    routine_materialize_due_tool,
    search_tool,
    task_add_tool,
    task_list_tool,
)
from alcove.mounts import AddMountRequest, MountsModule
from alcove.tasks import AddIdeaRequest, TasksModule
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


def test_mcp_server_registers_v1_tools(tmp_path):
    Workspace.init(tmp_path)
    mcp = create_mcp_server(str(tmp_path))

    tools = asyncio.run(mcp.list_tools())

    assert {tool.name for tool in tools} >= {
        "alcove_search",
        "alcove_inbox_peek",
        "alcove_note_source",
        "alcove_get_topic",
        "alcove_pin_add",
        "alcove_task_add",
        "alcove_task_list",
        "alcove_idea_promote",
        "alcove_routine_add",
        "alcove_routine_list",
        "alcove_routine_materialize_due",
        "alcove_mount_list",
        "alcove_gardener",
    }


def test_mcp_note_source_tool_records_source_and_concept(tmp_path):
    Workspace.init(tmp_path)

    payload = note_source_tool(
        str(tmp_path),
        platform="web",
        title="MCP Note Source",
        topic="agent-engineering/agent-harness",
        resource="https://example.test/source",
        summary="MCP can write a source.",
        tags=["mcp"],
        published_date="2026-07-08",
    )

    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["status"] == "noted"
    assert payload["source_path"].endswith("mcp-note-source.md")
    assert payload["concept_path"].endswith("mcp-note-source.md")
    json.dumps(payload, ensure_ascii=False)


def test_mcp_pin_add_tool_creates_pin(tmp_path):
    Workspace.init(tmp_path)

    payload = pin_add_tool(
        str(tmp_path),
        title="MCP Pin",
        description="Pinned from MCP.",
        tags=["mcp"],
        priority="high",
        source_refs=["sources/web/demo.md"],
    )

    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["status"] == "pinned"
    assert payload["pin"]["id"] == "mcp-pin"
    assert payload["pin"]["source_refs"] == ["/sources/web/demo.md"]


def test_mcp_task_add_and_list_tools_use_task_store(tmp_path):
    Workspace.init(tmp_path)

    add_payload = task_add_tool(
        str(tmp_path),
        title="MCP Task",
        notes="Expose task tools.",
        tags=["mcp"],
        priority="high",
        due="2026-07-09",
    )
    list_payload = task_list_tool(str(tmp_path), status="pending")

    assert add_payload["status"] == "added"
    assert add_payload["task"]["id"] == "mcp-task"
    assert list_payload["count"] == 1
    assert list_payload["tasks"][0]["title"] == "MCP Task"


def test_mcp_idea_promote_tool_creates_task(tmp_path):
    workspace = Workspace.init(tmp_path)
    TasksModule(workspace).idea_add(
        AddIdeaRequest(
            title="MCP Idea",
            notes="Make this actionable.",
            tags=["mcp"],
        )
    )

    payload = idea_promote_tool(
        str(tmp_path),
        idea_id="mcp-idea",
        priority="high",
        due="2026-07-10",
        notes="Add checks.",
    )

    assert payload["status"] == "promoted"
    assert payload["idea"]["promoted_task_id"] == "mcp-idea"
    assert payload["task"]["due"] == "2026-07-10"


def test_mcp_routine_tools_materialize_due_tasks(tmp_path):
    Workspace.init(tmp_path)

    add_payload = routine_add_tool(
        str(tmp_path),
        title="MCP Routine",
        notes="Run on schedule.",
        tags=["mcp"],
        priority="high",
        every_days=7,
        next_due="2026-07-08",
    )
    list_payload = routine_list_tool(str(tmp_path))
    materialize_payload = routine_materialize_due_tool(
        str(tmp_path),
        today="2026-07-08",
    )

    assert add_payload["routine"]["id"] == "mcp-routine"
    assert list_payload["count"] == 1
    assert materialize_payload["created"][0]["title"] == "MCP Routine"
    assert materialize_payload["created"][0]["due"] == "2026-07-08"


def test_mcp_get_topic_tool_returns_topic_docs(tmp_path):
    workspace = Workspace.init(tmp_path)
    KnowledgeModule(workspace).note_source(
        NoteSourceRequest(
            platform="web",
            title="Topic Source",
            topic="agent-engineering/agent-harness",
            resource="https://example.test/topic",
            summary="Topic overview source.",
            tags=["mcp"],
        )
    )

    payload = get_topic_tool(str(tmp_path), topic="agent-engineering/agent-harness")

    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["topic"] == "agent-harness"
    assert payload["domain"] == "agent-engineering"
    assert payload["count"] >= 1
    assert any(row["title"] == "Topic Source" for row in payload["results"])


def test_mcp_gardener_tool_returns_health_report(tmp_path):
    Workspace.init(tmp_path)

    payload = gardener_tool(str(tmp_path))

    assert payload["workspace"] == str(tmp_path.resolve())
    assert "issues" in payload
    assert "actions" in payload
    json.dumps(payload, ensure_ascii=False)
