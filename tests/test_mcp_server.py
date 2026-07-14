from __future__ import annotations

import asyncio
import json

from alcove.connectors.github_stars import GitHubStarsConnector, GitHubStarsImportRequest
from alcove.home import AlcoveHome
from alcove.knowledge import AddConceptRequest, KnowledgeModule, NoteSourceRequest
from alcove.markdown import MarkdownRepository
from alcove.mcp_direct_tools import direct_tool_runtime
from alcove.mcp_registrar import McpToolRegistrar
from alcove.mcp_server import (
    command_hints_tool,
    create_mcp_server,
    gardener_tool,
    get_topic_tool,
    idea_archive_tool,
    idea_edit_tool,
    idea_promote_routine_tool,
    idea_promote_tool,
    inbox_peek_tool,
    link_source_tool,
    mount_list_tool,
    note_source_tool,
    okf_catalog_build_tool,
    revise_knowledge_tool,
    pin_add_tool,
    pin_get_tool,
    pin_rebuild_index_tool,
    pin_render_html_tool,
    pin_search_tool,
    pin_update_tool,
    project_add_tool,
    project_find_tool,
    prompt_get_tool,
    prompt_rebuild_index_tool,
    prompt_save_tool,
    routine_add_tool,
    routine_archive_tool,
    routine_list_tool,
    routine_materialize_due_tool,
    routine_pause_tool,
    routine_resume_tool,
    search_tool,
    task_add_tool,
    task_digest_tool,
    task_edit_tool,
    task_list_tool,
)
from alcove.mounts import AddMountRequest, MountsModule
from alcove.tasks import AddIdeaRequest, TasksModule
from alcove.usage import UsageRecorder
from alcove.workspace import Workspace


class _FakeMcp:
    def __init__(self, name: str = "alcove") -> None:
        self.name = name
        self.registered: list[str] = []

    def tool(self, fn):
        self.registered.append(fn.__name__)
        return fn


def test_mcp_registrar_owns_toolset_filter_and_context():
    registrar = McpToolRegistrar.create(
        _FakeMcp,
        default_workspace="/tmp/workspace",
        default_home="/tmp/home",
        toolset="lite",
    )

    def alcove_search():
        return {}

    def alcove_inbox_peek():
        return {}

    assert registrar.mcp.name == "alcove-lite"
    assert registrar.context.default_workspace == "/tmp/workspace"
    assert registrar.context.default_home == "/tmp/home"
    assert registrar.tool(alcove_search) is alcove_search
    assert registrar.tool(alcove_inbox_peek) is alcove_inbox_peek
    assert registrar.mcp.registered == ["alcove_search"]


def test_mcp_direct_tool_runtime_uses_server_context_defaults(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    home = AlcoveHome.init(tmp_path / "home")

    runtime = direct_tool_runtime(
        default_workspace=str(workspace.root),
        default_home=str(home.root),
    )

    assert runtime.app().runtime.workspace.root == workspace.root
    assert runtime.app().runtime.home.root == home.root
    assert runtime.managed_app().runtime.workspace.root == workspace.root


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

    assert "workspace" not in payload
    assert "_diagnostic" not in payload
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


def test_mcp_search_records_privacy_safe_usage(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    task_add_tool("", home=str(home.root), title="MCP Usage Needle", notes="Searchable MCP usage.")

    payload = search_tool("", home=str(home.root), query="mcp usage")
    events = (home.paths().logs / "usage.jsonl").read_text(encoding="utf-8")
    summary = UsageRecorder(home).summary()

    assert payload["count"] == 1
    assert payload["results"][0]["title"] == "MCP Usage Needle"
    assert summary["search"]["surfaces"] == {"mcp": 1}
    assert "mcp usage" not in events


def test_mcp_project_and_prompt_tools_use_global_home(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    project_root = tmp_path / "alcove"
    project_root.mkdir()

    project_payload = project_add_tool(
        "",
        home=str(home.root),
        alias="alcove",
        path=str(project_root),
        note="Knowledge manager.",
    )
    find_payload = project_find_tool("", home=str(home.root), keyword="knowledge")
    prompt_payload = prompt_save_tool(
        "",
        home=str(home.root),
        title="Review Lens",
        content="Check regressions and missing tests.",
        tags=["review"],
        force=True,
    )
    get_payload = prompt_get_tool("", home=str(home.root), prompt_id="review-lens")
    index_payload = prompt_rebuild_index_tool("", home=str(home.root))
    search_payload = search_tool("", home=str(home.root), query="regressions")

    assert project_payload["project"]["alias"] == "alcove"
    assert find_payload["projects"][0]["path"] == str(project_root.resolve())
    assert prompt_payload["prompt"]["id"] == "review-lens"
    assert get_payload["prompt"]["content"] == "Check regressions and missing tests."
    assert index_payload["status"] == "rebuilt"
    assert index_payload["count"] == 1
    assert {row["root"] for row in search_payload["results"]} >= {"prompts"}


def test_mcp_okf_catalog_build_tool_uses_global_home(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    payload = okf_catalog_build_tool("", home=str(home.root))

    assert payload["home"] == str(home.root)
    assert payload["status"] == "built"
    assert "search-map.md" in payload["files"]
    assert (home.root / "okf" / "index.md").is_file()


def test_mcp_okf_catalog_build_tool_accepts_all_status(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    payload = okf_catalog_build_tool("", home=str(home.root), include_all_status=True)

    assert payload["include_all_status"] is True


def test_mcp_command_hints_exposes_cli_only_workflows(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    payload = command_hints_tool(home=str(home.root))

    workflow_ids = {workflow["id"] for workflow in payload["workflows"]}
    assert {"workspace_okf", "blog_monitor", "radars", "dashboard", "publishers"} <= workflow_ids
    assert payload["status"] == "ok"
    assert payload["home"].endswith("/home")
    assert all(workflow["surface"] == "cli" for workflow in payload["workflows"])

    blog = next(workflow for workflow in payload["workflows"] if workflow["id"] == "blog_monitor")
    assert any("alcove blog check" in command for command in blog["commands"])
    workspace_okf = next(
        workflow for workflow in payload["workflows"] if workflow["id"] == "workspace_okf"
    )
    assert any("workspace okf init" in command for command in workspace_okf["commands"])


def test_mcp_command_hints_can_filter_by_workflow(tmp_path):
    payload = command_hints_tool(home=str(tmp_path / "home"), workflow="radar")

    assert [workflow["id"] for workflow in payload["workflows"]] == ["radars"]
    assert any("alcove radar run" in command for command in payload["workflows"][0]["commands"])


def test_mcp_server_registers_v1_tools(tmp_path):
    Workspace.init(tmp_path)
    mcp = create_mcp_server(str(tmp_path))

    tools = asyncio.run(mcp.list_tools())

    assert {tool.name for tool in tools} >= {
        "alcove_command_hints",
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
        "alcove_knowledge_revise",
        "alcove_knowledge_delete",
        "alcove_knowledge_promote",
        "alcove_knowledge_refresh",
        "alcove_knowledge_topics",
        "alcove_pin_add",
        "alcove_pin_list",
        "alcove_pin_get",
        "alcove_pin_search",
        "alcove_pin_update",
        "alcove_pin_rebuild_index",
        "alcove_pin_render_html",
        "alcove_pin_archive",
        "alcove_project_add",
        "alcove_project_get",
        "alcove_project_find",
        "alcove_project_list",
        "alcove_project_remove",
        "alcove_project_roots_set",
        "alcove_prompt_save",
        "alcove_prompt_propose",
        "alcove_prompt_proposal",
        "alcove_prompt_search",
        "alcove_prompt_recommend",
        "alcove_prompt_compose",
        "alcove_prompt_audit",
        "alcove_prompt_get",
        "alcove_prompt_archive",
        "alcove_prompt_tags",
        "alcove_prompt_rebuild_index",
        "alcove_okf_catalog_build",
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
        "alcove_mount_update_policy",
        "alcove_mount_scan",
        "alcove_connector_fetch",
        "alcove_connector_status",
        "alcove_connector_refresh",
        "alcove_connector_apple_notes_index",
        "alcove_connector_apple_notes_import_local",
        "alcove_connector_github_stars_index",
        "alcove_connector_github_stars_import_url",
        "alcove_connector_chrome_bookmarks_index",
        "alcove_connector_chrome_bookmarks_import_local",
        "alcove_gardener",
        "alcove_doctor",
        "alcove_validate",
        "alcove_export_global",
        "alcove_export_kb",
        "alcove_export_all",
    }


def test_mcp_server_lite_toolset_keeps_global_common_tools_small(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    mcp = create_mcp_server(default_home=str(home.root), toolset="lite")

    tools = {tool.name for tool in asyncio.run(mcp.list_tools())}

    assert "alcove_search" in tools
    assert "alcove_command_hints" in tools
    assert "alcove_pin_add" in tools
    assert "alcove_task_add" in tools
    assert "alcove_prompt_save" in tools
    assert "alcove_prompt_propose" in tools
    assert "alcove_prompt_proposal" in tools
    assert "alcove_inbox_manual_add" in tools
    assert "alcove_connector_github_stars_import_url" not in tools
    assert "alcove_mount_scan" not in tools
    assert "alcove_export_all" not in tools
    assert len(tools) <= 27


def test_mcp_server_kb_toolset_keeps_kb_workflow_without_admin_tools(tmp_path):
    Workspace.init(tmp_path)
    mcp = create_mcp_server(default_workspace=str(tmp_path), toolset="kb")

    tools = {tool.name for tool in asyncio.run(mcp.list_tools())}

    assert "alcove_inbox_peek" in tools
    assert "alcove_command_hints" in tools
    assert "alcove_inbox_note" in tools
    assert "alcove_knowledge_revise" in tools
    assert "alcove_knowledge_delete" in tools
    assert "alcove_validate" in tools
    assert "alcove_connector_chrome_bookmarks_import_local" not in tools
    assert "alcove_export_all" not in tools
    assert "alcove_gardener" not in tools


def test_mcp_tool_descriptions_encode_read_write_operating_model(tmp_path):
    Workspace.init(tmp_path)
    mcp = create_mcp_server(str(tmp_path))

    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

    assert "candidate Alcove records" in tools["alcove_search"].description
    assert "leads, not final truth" in tools["alcove_search"].description
    assert "local files before answering" in tools["alcove_search"].description
    assert "governed OKF write path" in tools["alcove_knowledge_revise"].description
    assert "soft-delete" in tools["alcove_knowledge_delete"].description
    assert "governed global write path" in tools["alcove_pin_update"].description
    assert "proposal" in tools["alcove_prompt_save"].description
    assert "deduplicate" in tools["alcove_prompt_propose"].description
    assert "derived global OKF catalog" in tools["alcove_okf_catalog_build"].description
    assert "AI-led reads" in tools["alcove_okf_catalog_build"].description
    assert "governed planner write path" in tools["alcove_task_add"].description
    assert "Lazy-fetch detail" in tools["alcove_connector_fetch"].description
    assert "before final synthesis" in tools["alcove_connector_fetch"].description


def test_mcp_knowledge_revise_tool_updates_existing_note(tmp_path):
    workspace = Workspace.init(tmp_path)
    KnowledgeModule(workspace).add_concept(
        AddConceptRequest(
            topic="agent-engineering/agent-harness",
            title="MCP Revision",
            summary="Old MCP summary.",
            tags=["mcp"],
        )
    )

    payload = revise_knowledge_tool(
        str(workspace.root),
        path="concepts/agent-engineering/agent-harness/mcp-revision.md",
        summary="New MCP summary.",
        append="MCP 调用补充的讨论记录。",
        tags=["managed-kb"],
        source_refs=["sources/chat/agent-engineering/mcp-discussion.md"],
        reason="MCP discussion",
    )

    doc = MarkdownRepository().read_doc(
        workspace.paths().knowledge
        / "concepts"
        / "agent-engineering"
        / "agent-harness"
        / "mcp-revision.md"
    )
    assert payload["status"] == "revised"
    assert doc.frontmatter["tags"] == ["mcp", "managed-kb"]
    assert "MCP 调用补充的讨论记录。" in doc.body


def test_mcp_server_default_home_routes_global_tools(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    mcp = create_mcp_server(default_home=str(home.root))

    add_result = asyncio.run(mcp.call_tool("alcove_task_add", {"title": "Default Home MCP Task"}))
    project_result = asyncio.run(
        mcp.call_tool(
            "alcove_project_add",
            {"alias": "alcove", "path": str(tmp_path), "note": "Default project."},
        )
    )
    proposal_result = asyncio.run(
        mcp.call_tool(
            "alcove_prompt_propose",
            {
                "title": "Default Prompt",
                "content": (
                    "Review the default home workflow for regression risk, missing "
                    "tests, incomplete evidence, and unclear user-facing behavior. "
                    "Return findings, risks, and verification notes."
                ),
                "tags": ["review"],
            },
        )
    )
    prompt_result = asyncio.run(
        mcp.call_tool(
            "alcove_prompt_save",
            {
                "proposal_id": proposal_result.structured_content["id"],
            },
        )
    )
    compose_result = asyncio.run(
        mcp.call_tool("alcove_prompt_compose", {"scenario": "regression review"})
    )
    audit_result = asyncio.run(mcp.call_tool("alcove_prompt_audit", {}))
    list_result = asyncio.run(mcp.call_tool("alcove_task_list", {}))

    assert add_result.structured_content["home"] == str(home.root)
    assert add_result.structured_content["task"]["id"] == "default-home-mcp-task"
    assert project_result.structured_content["project"]["alias"] == "alcove"
    assert proposal_result.structured_content["action"] in {
        "create_new",
        "create_new_after_review",
    }
    assert prompt_result.structured_content["prompt"]["id"] == "default-prompt"
    assert compose_result.structured_content["sources"][0]["title"] == "Default Prompt"
    assert "Review the default home workflow" in compose_result.structured_content["prompt"]
    assert audit_result.structured_content["counts"]["prompts"] == 1
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
        summary="Pinned from MCP.",
        content="Keep a reusable MCP pin visible.",
        kind="regular",
        tags=["mcp"],
        priority="high",
        source_refs=["sources/web/demo.md"],
        resources=["https://example.test/mcp-pin"],
    )
    update_payload = pin_update_tool(
        str(tmp_path),
        pin_id="mcp-pin",
        kind="todo",
        content="Try the MCP pin workflow again.",
        tags=["mcp", "practice"],
    )
    get_payload = pin_get_tool(str(tmp_path), pin_id="mcp-pin")
    search_payload = pin_search_tool(str(tmp_path), query="workflow", kind="todo")
    index_payload = pin_rebuild_index_tool(str(tmp_path))
    html_payload = pin_render_html_tool(str(tmp_path))

    assert payload["workspace"] == str(tmp_path.resolve())
    assert payload["status"] == "pinned"
    assert payload["pin"]["id"] == "mcp-pin"
    assert payload["pin"]["kind"] == "regular"
    assert payload["pin"]["source_refs"] == ["/sources/web/demo.md"]
    assert payload["pin"]["resources"] == ["https://example.test/mcp-pin"]
    assert update_payload["pin"]["kind"] == "todo"
    assert get_payload["pin"]["tags"] == ["mcp", "practice"]
    assert search_payload["count"] == 1
    assert index_payload["status"] == "rebuilt"
    assert html_payload["path"].endswith("pins/board.html")


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


def test_mcp_full_planner_lifecycle_tools(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    sent: list[str] = []

    def fake_send(*, home, text):
        sent.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("alcove.tasks.send_telegram_message", fake_send)

    task_payload = task_add_tool("", home=str(home.root), title="MCP Edit Me")
    edited_task = task_edit_tool(
        "",
        home=str(home.root),
        task_id=task_payload["task"]["id"],
        title="MCP Edited Task",
        priority="high",
    )
    TasksModule(home=home).idea_add(AddIdeaRequest(title="MCP Routine Idea"))
    TasksModule(home=home).idea_add(AddIdeaRequest(title="MCP Archive Idea"))
    edited_idea = idea_edit_tool(
        "",
        home=str(home.root),
        idea_id="mcp-routine-idea",
        title="MCP Routine Plan",
    )
    promoted = idea_promote_routine_tool(
        "",
        home=str(home.root),
        idea_id=edited_idea["idea"]["id"],
        next_due="2026-07-12",
        schedule={"frequency": "weekly", "interval": 1, "weekdays": ["sun"]},
    )
    paused = routine_pause_tool("", home=str(home.root), routine_id=promoted["routine"]["id"])
    resumed = routine_resume_tool(
        "",
        home=str(home.root),
        routine_id=promoted["routine"]["id"],
        today="2026-07-12",
    )
    digest = task_digest_tool("", home=str(home.root), today="2026-07-12", notify=True)
    archived = routine_archive_tool("", home=str(home.root), routine_id=promoted["routine"]["id"])
    archived_idea = idea_archive_tool("", home=str(home.root), idea_id="mcp-archive-idea")

    assert edited_task["task"]["title"] == "MCP Edited Task"
    assert promoted["routine"]["schedule"]["weekdays"] == ["sun"]
    assert paused["routine"]["status"] == "paused"
    assert resumed["routine"]["status"] == "active"
    assert digest["status"] == "sent"
    assert "MCP Edited Task" in sent[0]
    assert archived["routine"]["status"] == "archived"
    assert archived_idea["idea"]["status"] == "archived"


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
