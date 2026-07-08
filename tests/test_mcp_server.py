from __future__ import annotations

import asyncio
import json

from alcove.connectors.github_stars import GitHubStarsConnector, GitHubStarsImportRequest
from alcove.home import AlcoveHome
from alcove.knowledge import KnowledgeModule, NoteSourceRequest
from alcove.mcp_server import (
    create_mcp_server,
    gardener_tool,
    get_topic_tool,
    idea_promote_tool,
    inbox_peek_tool,
    link_source_tool,
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


def test_mcp_global_home_tools_do_not_require_workspace(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    pin_payload = pin_add_tool(
        "",
        home=str(home.root),
        title="Global MCP Pin",
        description="Global MCP pin needle.",
    )
    task_payload = task_add_tool(
        "",
        home=str(home.root),
        title="Global MCP Task",
        notes="Global MCP task needle.",
    )
    list_payload = task_list_tool("", home=str(home.root))
    search_payload = search_tool("", home=str(home.root), query="global mcp")

    assert pin_payload["home"] == str(home.root)
    assert pin_payload["pin"]["id"] == "global-mcp-pin"
    assert task_payload["task"]["id"] == "global-mcp-task"
    assert list_payload["tasks"][0]["title"] == "Global MCP Task"
    assert {row["root"] for row in search_payload["results"]} == {"pins", "tasks"}


def test_mcp_server_registers_v1_tools(tmp_path):
    Workspace.init(tmp_path)
    mcp = create_mcp_server(str(tmp_path))

    tools = asyncio.run(mcp.list_tools())

    assert {tool.name for tool in tools} >= {
        "alcove_search",
        "alcove_inbox_peek",
        "alcove_inbox_read",
        "alcove_inbox_manual_add",
        "alcove_inbox_archive",
        "alcove_inbox_note",
        "alcove_inbox_todo",
        "alcove_inbox_delete",
        "alcove_note_source",
        "alcove_get_topic",
        "alcove_knowledge_add_note",
        "alcove_knowledge_add_question",
        "alcove_knowledge_add_entity",
        "alcove_knowledge_promote",
        "alcove_knowledge_refresh",
        "alcove_knowledge_topics",
        "alcove_pin_add",
        "alcove_pin_list",
        "alcove_pin_archive",
        "alcove_task_add",
        "alcove_task_list",
        "alcove_task_complete",
        "alcove_task_cancel",
        "alcove_idea_add",
        "alcove_idea_list",
        "alcove_idea_promote",
        "alcove_routine_add",
        "alcove_routine_list",
        "alcove_routine_materialize_due",
        "alcove_link_source",
        "alcove_mount_list",
        "alcove_mount_add",
        "alcove_mount_scan",
        "alcove_connector_fetch",
        "alcove_connector_apple_notes_index",
        "alcove_connector_github_stars_index",
        "alcove_gardener",
        "alcove_doctor",
        "alcove_validate",
        "alcove_export_global",
        "alcove_export_kb",
        "alcove_export_all",
    }


def test_mcp_server_default_home_routes_global_tools(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    mcp = create_mcp_server(default_home=str(home.root))

    add_result = asyncio.run(mcp.call_tool("alcove_task_add", {"title": "Default Home MCP Task"}))
    list_result = asyncio.run(mcp.call_tool("alcove_task_list", {}))

    assert add_result.structured_content["home"] == str(home.root)
    assert add_result.structured_content["task"]["id"] == "default-home-mcp-task"
    assert list_result.structured_content["home"] == str(home.root)
    assert list_result.structured_content["tasks"][0]["title"] == "Default Home MCP Task"


def test_mcp_server_default_workspace_routes_managed_kb_tools(tmp_path):
    Workspace.init(tmp_path)
    item = tmp_path / "inbox" / "web" / "20260708-default-workspace"
    item.mkdir(parents=True)
    (item / "article.md").write_text("# Default Workspace\n\nBody", encoding="utf-8")
    mcp = create_mcp_server(default_workspace=str(tmp_path))

    result = asyncio.run(mcp.call_tool("alcove_inbox_peek", {}))

    assert result.structured_content["workspace"] == str(tmp_path.resolve())
    assert result.structured_content["item"]["title"] == "Default Workspace"


def test_mcp_server_exposes_inbox_manual_add_and_read(tmp_path):
    Workspace.init(tmp_path)
    mcp = create_mcp_server(default_workspace=str(tmp_path))

    add_result = asyncio.run(
        mcp.call_tool(
            "alcove_inbox_manual_add",
            {
                "title": "Manual MCP Thought",
                "content": "Copied through MCP.",
                "source": "chat://mcp",
            },
        )
    )
    read_result = asyncio.run(
        mcp.call_tool("alcove_inbox_read", {"name": add_result.structured_content["id"]})
    )

    assert add_result.structured_content["status"] == "added"
    assert read_result.structured_content["item"]["title"] == "Manual MCP Thought"
    assert read_result.structured_content["item"]["source"] == "chat://mcp"


def test_mcp_server_exposes_global_idea_and_task_state_tools(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    mcp = create_mcp_server(default_home=str(home.root))

    idea_result = asyncio.run(
        mcp.call_tool(
            "alcove_idea_add",
            {"title": "MCP Idea State", "notes": "Track it globally."},
        )
    )
    ideas_result = asyncio.run(mcp.call_tool("alcove_idea_list", {}))
    task_result = asyncio.run(mcp.call_tool("alcove_task_add", {"title": "MCP Task State"}))
    complete_result = asyncio.run(
        mcp.call_tool(
            "alcove_task_complete",
            {"task_id": task_result.structured_content["task"]["id"]},
        )
    )

    assert idea_result.structured_content["idea"]["id"] == "mcp-idea-state"
    assert ideas_result.structured_content["ideas"][0]["title"] == "MCP Idea State"
    assert complete_result.structured_content["task"]["status"] == "done"


def test_mcp_server_exposes_export_all(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb = Workspace.init(tmp_path / "kb")
    home.register_knowledge_base("demo", kb.root)
    concept = kb.paths().knowledge / "concepts" / "note.md"
    concept.parent.mkdir(parents=True)
    concept.write_text("demo", encoding="utf-8")
    mcp = create_mcp_server(default_home=str(home.root))

    result = asyncio.run(
        mcp.call_tool("alcove_export_all", {"output_dir": str(tmp_path / "backup")})
    )

    assert result.structured_content["type"] == "all"
    assert (tmp_path / "backup" / "global" / "knowledge-bases" / "demo.yml").is_file()
    assert (tmp_path / "backup" / "knowledge-bases" / "demo" / "knowledge").is_dir()


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


def test_mcp_link_source_tool_promotes_indexed_item(tmp_path):
    workspace = Workspace.init(tmp_path)
    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                    "description": "Personal knowledge management core.",
                    "language": "Python",
                    "topics": ["pkm"],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    GitHubStarsConnector(workspace).import_export(
        GitHubStarsImportRequest(export_file=str(export_file))
    )

    payload = link_source_tool(
        str(tmp_path),
        item_path="connectors/github-stars#octopusgarage/alcove",
        topic="ai-knowledge/knowledge-base",
        summary="Useful reference.",
    )

    assert payload["status"] == "linked"
    assert payload["source_path"].endswith("octopusgarage-alcove.md")


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
