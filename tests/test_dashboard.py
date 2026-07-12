from __future__ import annotations

import hashlib
import json

from alcove.connectors.apple_notes import (
    AppleNotesConnector,
    AppleNotesImportRequest,
    write_apple_notes_export_tree,
)
from alcove.connectors.chrome_bookmarks import (
    ChromeBookmarksConnector,
    ChromeBookmarksImportRequest,
)
from alcove.connectors.github_stars import GitHubStarsConnector, GitHubStarsImportRequest
from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.mounts import AddMountRequest, MountsModule
from alcove.pins_import import PinsMarkdownImportModule
from alcove.pins import AddPinRequest, PinsModule
from alcove.projects import AddProjectRequest, ProjectsModule
from alcove.prompts import AddPromptRequest, PromptsModule
from alcove.tasks import AddRoutineRequest, AddTaskRequest, TasksModule
from alcove.usage import UsageRecorder
from alcove.workspace import Workspace


def test_dashboard_snapshot_counts_global_modules(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(
        AddPinRequest(
            title="Reference Pin",
            summary="Keep for lookup.",
            content="Useful reference content.",
            kind="regular",
        )
    )
    PinsModule(home=home).add(
        AddPinRequest(
            title="Future Pin",
            summary="Try later.",
            content="Worth practicing.",
            kind="todo",
        )
    )
    TasksModule(home=home).task_add(
        AddTaskRequest(title="Review dashboard", notes="Check local UI.", tags=["ui"])
    )
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Review Prompt",
            description="Review prompt description.",
            content="Look for regressions and missing tests.",
            use_cases=["code review"],
            tags=["review"],
        )
    )
    ProjectsModule(home=home).add(
        AddProjectRequest(alias="alcove", path=str(tmp_path), note="Local-first PKM project.")
    )

    snapshot = DashboardModule(home=home).snapshot()

    assert snapshot["snapshot_version"] == 1
    assert snapshot["home"].startswith("Alcove Home · ")
    assert str(tmp_path) not in snapshot["home"]
    assert snapshot["summary"]["counts"]["pins"] == 2
    assert snapshot["summary"]["counts"]["pending_tasks"] == 1
    assert snapshot["summary"]["counts"]["direct_pending_tasks"] == 1
    assert snapshot["summary"]["counts"]["routine_due_tasks"] == 0
    assert snapshot["summary"]["counts"]["prompts"] == 1
    assert snapshot["summary"]["counts"]["projects"] == 1
    assert snapshot["summary"]["counts"]["knowledge_items"] == 0
    assert snapshot["ideas"] == []
    assert snapshot["routines"] == []
    assert snapshot["modules"][0]["id"] == "pins"
    assert snapshot["modules"][0]["metric"] == 2
    assert snapshot["modules"][0]["detail"] == (
        "2 total pins / 0 theme pins (0 regular themes / 0 TODO themes)"
    )
    assert any(module["id"] == "library" for module in snapshot["modules"])
    prompt_row = next(row for row in snapshot["search_index"] if row["type"] == "prompt")
    project_row = next(row for row in snapshot["search_index"] if row["type"] == "project")
    assert prompt_row["href"] == "/library"
    assert "Look for regressions and missing tests." in prompt_row["text"]
    assert "code review" in prompt_row["text"]
    assert project_row["href"] == "/library"
    assert "Local-first PKM project." in project_row["text"]
    assert snapshot["projects"][0]["path_label"] == tmp_path.name
    assert snapshot["projects"][0]["target_label"] == f"alcove ({tmp_path.name})"
    assert snapshot["projects"][0]["command_hint"] == "alcove project get alcove --json"
    assert "detail_path" not in snapshot["projects"][0]
    assert "Local-first PKM project." in project_row["text"]
    assert "alcove project get alcove --json" not in project_row["text"]
    assert str(tmp_path) not in project_row["text"]
    activity_details = {row["detail"] for row in snapshot["activity"]}
    assert "tasks: Review dashboard" in activity_details
    assert "alcove" in activity_details
    assert "search_index" in snapshot


def test_dashboard_search_index_deduplicates_pin_summary_content(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(
        AddPinRequest(
            title="Repeated Pin",
            summary="Keep this exact line.",
            content="Keep this exact line.\nUse the extra detail for search.",
            kind="regular",
        )
    )

    snapshot = DashboardModule(home=home).snapshot()

    row = next(row for row in snapshot["search_index"] if row["type"] == "pin")
    assert row["text"].count("Keep this exact line.") == 1
    assert "Use the extra detail for search." in row["text"]


def test_dashboard_module_owns_snapshot_view_model_shape(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(
        AddPinRequest(
            title="Projection Pin",
            summary="Projected into dashboard view model.",
            content="Dashboard projection content.",
            kind="regular",
        )
    )

    snapshot = DashboardModule(home=home).snapshot()

    assert snapshot["snapshot_version"] == 1
    assert snapshot["summary"]["counts"]["pins"] == 1
    assert snapshot["sources"]["connectors"] == snapshot["connectors"]
    assert snapshot["sources"]["mounts"] == snapshot["mounts"]
    assert any(row["title"] == "Projection Pin" for row in snapshot["search_index"])


def test_dashboard_marks_routine_generated_task_instances(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    tasks = TasksModule(home=home)
    routine = tasks.routine_add(
        AddRoutineRequest(
            title="Review weekly inbox",
            notes="Process pending captured posts.",
            every_days=7,
            next_due="2026-07-08",
        )
    )
    tasks.routine_materialize_due(today="2026-07-08")

    snapshot = DashboardModule(home=home).snapshot()
    pending = snapshot["tasks"]["pending"][0]
    search_row = next(row for row in snapshot["search_index"] if row["type"] == "task")

    assert pending["source_routine_id"] == routine.id
    assert pending["generated_from_routine"] is True
    assert pending["instance_due"] == "2026-07-08"
    assert pending["display_title"] == "Review weekly inbox (routine due)"
    assert pending["overdue"] is True
    assert pending["overdue_days"] > 0
    assert pending["due_state"] == "overdue"
    assert snapshot["summary"]["counts"]["direct_pending_tasks"] == 0
    assert snapshot["summary"]["counts"]["routine_due_tasks"] == 1
    planner = next(module for module in snapshot["modules"] if module["id"] == "planner")
    assert "0 direct pending / 1 routine due" in planner["detail"]
    assert search_row["title"] == "Review weekly inbox (routine due)"
    assert "generated_from_routine" in search_row["text"]
    assert routine.id in search_row["text"]
    assert "overdue" in search_row["text"]


def test_dashboard_build_writes_snapshot(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(
        AddPinRequest(
            title="Claude Code Workflow",
            summary="Commands and operating notes.",
            content="/plan, /compact, /fork.",
            kind="regular",
            tags=["agent-workflow"],
        )
    )
    PinsModule(home=home).add(
        AddPinRequest(
            title="Knowledge Dashboard",
            summary="Track search records and usage records.",
            content="Build a dashboard for user behavior and knowledge usage.",
            kind="todo",
            tags=["dashboard"],
        )
    )

    result = DashboardModule(home=home).build(build_frontend=False)
    snapshot = (home.root / "dashboard" / "snapshot.json").read_text(encoding="utf-8")

    assert result["status"] == "built"
    assert result["frontend_built"] is False
    assert result["frontend_mode"] == "static_snapshot"
    assert "static index.html" in result["frontend_note"]
    assert '"snapshot_version": 1' in snapshot
    assert "Claude Code Workflow" in snapshot


def test_dashboard_imports_regular_and_todo_text_files_as_markdown_pins(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    regular = tmp_path / "regular.txt"
    regular.write_text(
        "# 常用收藏\n\n## Claude / Codex\n\n### Claude Code\n\n- `/plan`\n- `/compact`\n",
        encoding="utf-8",
    )
    todo = tmp_path / "todo.txt"
    todo.write_text(
        "# Todo\n\n## 个人知识库\n\n- 数据看板搜索记录使用记录。\n- GitHub star 索引。\n",
        encoding="utf-8",
    )

    module = DashboardModule(home=home)
    result = module.import_pins(regular_file=regular, todo_file=todo)
    second = module.import_pins(regular_file=regular, todo_file=todo)
    pins = PinsModule(home=home).list(status="")
    snapshot = module.snapshot()

    assert result["regular"]["raw_lines"] == regular.read_text(encoding="utf-8").count("\n")
    assert result["todo"]["raw_lines"] == todo.read_text(encoding="utf-8").count("\n")
    assert result["regular"]["imported"] == 1
    assert result["todo"]["imported"] == 1
    assert result["regular"]["pins"][0]["title"] == "常用收藏"
    assert result["todo"]["pins"][0]["title"] == "Todo"
    assert (
        result["regular"]["archive"]["sha256"] == hashlib.sha256(regular.read_bytes()).hexdigest()
    )
    assert result["todo"]["archive"]["bytes"] == todo.stat().st_size
    assert second["archived_duplicates"] == 0
    assert {pin.kind for pin in pins} == {"regular", "todo"}
    assert all("source-markdown-pin" in pin.tags for pin in pins)
    assert all(not pin.resources for pin in pins)
    assert len(snapshot["pins"]["themes"]) == 2
    assert snapshot["pins"]["themes"][0]["content"] == regular.read_text(encoding="utf-8")
    assert snapshot["pins"]["themes"][1]["content"] == todo.read_text(encoding="utf-8")
    assert (
        snapshot["pins"]["themes"][0]["summary"]
        == "Claude / Codex · Claude Code; `/plan`; `/compact`"
    )


def test_pins_markdown_import_module_owns_regular_and_todo_import(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    regular = tmp_path / "regular.txt"
    regular.write_text("# 常用收藏\n\n- Agent CLI notes\n", encoding="utf-8")
    todo = tmp_path / "todo.txt"
    todo.write_text("# Todo\n\n- Build eval harness\n", encoding="utf-8")

    result = PinsMarkdownImportModule(home=home).import_pins(
        regular_file=regular,
        todo_file=todo,
    )

    pins = PinsModule(home=home).list(status="active")
    assert result["regular"]["pins"][0]["title"] == "常用收藏"
    assert result["todo"]["pins"][0]["title"] == "Todo"
    assert result["archived_duplicates"] == 0
    assert {pin.kind for pin in pins} == {"regular", "todo"}
    assert all("source-markdown-pin" in pin.tags for pin in pins)


def test_dashboard_activity_hides_internal_log_paths_and_build_events(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = DashboardModule(home=home)
    module.build(build_frontend=False)
    module._record_event(  # noqa: SLF001
        "dashboard.import_pins",
        "Imported regular/todo theme pin files",
        {"regular": {"imported": 1}, "todo": {"imported": 1}},
    )
    module._record_event(  # noqa: SLF001
        "dashboard.search",
        "Dashboard search used",
        {"query_length": 4},
        visible=False,
    )

    activity = module.snapshot()["activity"]

    assert any(row["name"] == "Imported regular/todo theme pin files" for row in activity)
    assert all(row.get("updated_at", "").endswith("+08:00") for row in activity)
    assert any(row.get("raw_updated_at", "").endswith("+00:00") for row in activity)
    assert all(row.get("name") != "Built Alcove dashboard" for row in activity)
    assert all("activity.jsonl" not in json.dumps(row) for row in activity)
    assert all(row.get("name") != "Pin theme updated" for row in activity)
    assert all(row.get("type") != "file_change" for row in activity)
    assert all("registry" not in row.get("name", "").casefold() for row in activity)
    assert all("index" not in row.get("name", "").casefold() for row in activity)
    assert all(row.get("detail") not in {"index", "regular", "todo"} for row in activity)


def test_dashboard_snapshot_includes_usage_summary_without_noisy_activity(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = DashboardModule(home=home)
    module._record_event(  # noqa: SLF001
        "dashboard.route",
        "Dashboard route viewed",
        {"route": "/knowledge"},
        visible=False,
    )
    module._record_event(  # noqa: SLF001
        "dashboard.search",
        "Dashboard search used",
        {"query_length": 11, "result_count": 0},
        visible=False,
    )
    module._record_event(  # noqa: SLF001
        "dashboard.result_open",
        "Dashboard search result opened",
        {"type": "pin", "href": "/pins", "title_length": 12},
        visible=False,
    )
    UsageRecorder(home).record_search(
        surface="cli",
        query="private dashboard query with sensitive suffix",
        result_count=2,
    )

    snapshot = module.snapshot()

    assert snapshot["summary"]["counts"]["usage_events"] == 4
    assert snapshot["usage"]["search"]["total"] == 2
    assert snapshot["usage"]["search"]["zero_result"] == 1
    assert snapshot["usage"]["search"]["surfaces"] == {"cli": 1, "dashboard": 1}
    assert snapshot["usage"]["dashboard"]["routes"] == {"/knowledge": 1}
    assert any(row["action"] == "dashboard.result_open" for row in snapshot["usage"]["recent"])
    assert "private dashboard query with sensitive suffix" not in json.dumps(
        snapshot["usage"], ensure_ascii=False
    )
    assert any(
        row.get("metrics", {}).get("query_preview")
        for row in snapshot["usage"]["recent"]
        if row["action"] == "search.run"
    )
    assert all(row.get("area") != "dashboard" for row in snapshot["activity"])


def test_dashboard_snapshot_includes_data_health_summary(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    (kb_root / "knowledge" / "sources" / "web").mkdir(parents=True)
    (kb_root / "knowledge" / "sources" / "web" / "source.md").write_text(
        "---\ntype: Source\ntitle: Health Source\n---\n# Health Source\n",
        encoding="utf-8",
    )
    home.register_knowledge_base("research_notes", kb_root)
    mounted = tmp_path / "mounted"
    mounted.mkdir()
    (mounted / "note.md").write_text("# Mounted Health\n", encoding="utf-8")
    mounts = MountsModule(home=home)
    mount = mounts.add(AddMountRequest(path=str(mounted), name="Mounted Health"))
    mounts.scan(mount.id)
    UsageRecorder(home).record_search(surface="cli", query="health secret", result_count=1)

    snapshot = DashboardModule(home=home).snapshot()

    assert snapshot["health"]["status"] == "ok"
    assert snapshot["health"]["totals"] == {
        "managed_kbs": 1,
        "managed_items": 1,
        "mounts": 1,
        "mount_items": 1,
        "connectors": 0,
        "connector_items": 0,
        "usage_events": 1,
    }
    assert snapshot["health"]["data_sources"][0]["kind"] == "managed-kb"
    assert snapshot["health"]["data_sources"][0]["name"] == "research_notes"
    assert snapshot["health"]["data_sources"][0]["item_count"] == 1
    assert snapshot["health"]["data_sources"][0]["status"] == "ok"
    assert (
        snapshot["health"]["data_sources"][0]["command_hint"]
        == "alcove validate --kb research_notes --json"
    )
    mount_row = next(row for row in snapshot["health"]["data_sources"] if row["kind"] == "mount")
    assert mount_row["command_hint"] == "alcove mount scan mounted-health --json"
    assert snapshot["health"]["stats"]["summary_exists"] is True
    assert snapshot["health"]["stats"]["daily_rollups"] >= 1
    assert str(tmp_path) not in json.dumps(snapshot["health"], ensure_ascii=False)
    assert "health secret" not in json.dumps(snapshot["health"], ensure_ascii=False)


def test_dashboard_uses_human_connector_source_labels(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    export_file = tmp_path / "bookmarks.json"
    export_file.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "children": [
                            {
                                "type": "url",
                                "name": "Dashboard Bookmark",
                                "url": "https://example.com/dashboard-bookmark",
                                "date_added": "13291532799000000",
                            }
                        ]
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    ChromeBookmarksConnector(home=home).import_export(
        ChromeBookmarksImportRequest(export_file=str(export_file), tags=["bookmarks"])
    )

    chrome_row = next(
        row
        for row in DashboardModule(home=home).snapshot()["connectors"]
        if row["connector"] == "chrome-bookmarks"
    )

    assert chrome_row["source"] == "Chrome Bookmarks"


def test_dashboard_knowledge_surface_includes_representative_external_items(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    (kb_root / "knowledge" / "sources" / "web").mkdir(parents=True)
    (kb_root / "knowledge" / "sources" / "web" / "source.md").write_text(
        "---\ntype: Source\ntitle: Dashboard Source\n---\n# Dashboard Source\n",
        encoding="utf-8",
    )
    (kb_root / "knowledge" / "index.md").write_text(
        "---\ntype: Index\ntitle: Knowledge Index\n---\n# Knowledge Index\n",
        encoding="utf-8",
    )
    (kb_root / "knowledge" / "domains").mkdir(parents=True)
    (kb_root / "knowledge" / "domains" / "agent-engineering.md").write_text(
        "---\ntype: Domain\ntitle: Agent Engineering\n---\n# Agent Engineering\n",
        encoding="utf-8",
    )
    home.register_knowledge_base("research_notes", kb_root)

    mounted = tmp_path / "mounted"
    mounted.mkdir()
    (mounted / "agent-notes.md").write_text(
        "# Agent Notes\n\nMounted dashboard needle.", encoding="utf-8"
    )
    mounts = MountsModule(home=home)
    mount = mounts.add(AddMountRequest(path=str(mounted), name="Research Mount"))
    mounts.scan(mount.id)

    export_file = tmp_path / "stars.json"
    export_file.write_text(
        json.dumps(
            [
                {
                    "full_name": "octopusgarage/alcove",
                    "html_url": "https://github.com/OctopusGarage/alcove",
                    "description": "Local-first knowledge core.",
                    "language": "Python",
                    "topics": ["pkm"],
                    "stargazers_count": 42,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    GitHubStarsConnector(home=home).import_export(
        GitHubStarsImportRequest(export_file=str(export_file), tags=["github-stars"])
    )
    apple_export = tmp_path / "apple-notes-export"
    write_apple_notes_export_tree(
        [
            {
                "id": "x-coredata://dashboard-note",
                "title": "Dashboard Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Ideas",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Apple Notes dashboard needle.",
                "body_html": "<div>Apple Notes dashboard needle.</div>",
            }
        ],
        apple_export,
    )
    AppleNotesConnector(home=home).import_export(
        AppleNotesImportRequest(export_dir=str(apple_export), tags=["apple-notes"])
    )

    snapshot = DashboardModule(home=home).snapshot()

    assert snapshot["knowledge"]["managed"][0]["name"] == "research_notes"
    assert snapshot["knowledge"]["managed"][0]["item_count"] == 1
    assert snapshot["knowledge"]["managed"][0]["display_limit"] == 5
    assert snapshot["knowledge"]["managed"][0]["omitted_item_count"] == 0
    assert snapshot["knowledge"]["managed"][0]["omitted_items"] == []
    assert snapshot["summary"]["counts"]["knowledge_items"] == 1
    knowledge_module = next(module for module in snapshot["modules"] if module["id"] == "knowledge")
    assert knowledge_module["title"] == "Knowledge"
    assert knowledge_module["metric"] == 4
    assert "1 managed note, 1 mounted file, 2 connector items" in knowledge_module["detail"]
    assert "1 managed KB, 1 mount, 2 connectors" in knowledge_module["detail"]
    assert snapshot["knowledge"]["managed"][0]["items"][0]["notes"] == "# Dashboard Source"
    assert snapshot["knowledge"]["managed"][0]["items"][0]["type"] == "Source"
    assert snapshot["knowledge"]["managed"][0]["items"][0]["okf_type"] == "Source"
    assert "status" in snapshot["knowledge"]["managed"][0]["items"][0]
    assert snapshot["knowledge"]["managed"][0]["items"][0]["confidence"] == 0.5
    assert snapshot["mounts"][0]["items"][0]["title"] == "Agent Notes"
    assert snapshot["sources"]["mounts"][0]["items"][0]["title"] == "Agent Notes"
    connector_item_titles = {
        item["title"] for row in snapshot["connectors"] for item in row["items"]
    }
    assert {"octopusgarage/alcove", "Dashboard Apple Note"}.issubset(connector_item_titles)
    apple_row = next(row for row in snapshot["connectors"] if row["connector"] == "apple-notes")
    assert apple_row["source"] == "Apple Notes"
    assert apple_row["item_count"] == 1
    assert apple_row["checked_at"]
    assert apple_row["items"][0]["path"] == ""
    assert apple_row["items"][0]["display_id"].startswith("apple-notes/")
    assert apple_row["items"][0]["display_label"] == "Dashboard Apple Note"
    assert apple_row["items"][0]["origin_label"] == "Apple Notes / iCloud/Ideas"
    assert apple_row["items"][0]["fetch_ref_available"] is True
    assert apple_row["items"][0]["fetch_command_pattern"] == (
        "alcove connector fetch <fetch_ref> --json"
    )
    assert "fetch_ref" not in apple_row["items"][0]
    assert "fetch_command" not in apple_row["items"][0]
    assert "debug" not in apple_row["items"][0]
    assert "fetch_id" not in json.dumps(snapshot["connectors"], ensure_ascii=False)
    assert apple_row["items"][0]["source"] == "Apple Notes"
    assert apple_row["items"][0]["resource"] == "Apple Notes"
    github_row = next(row for row in snapshot["connectors"] if row["connector"] == "github-stars")
    assert github_row["freshness_status"] == "fresh"
    assert github_row["ttl_hours"] == 24
    assert github_row["item_count"] == 1
    search_titles = {row["title"] for row in snapshot["search_index"]}
    assert {"research_notes", "Agent Notes", "octopusgarage/alcove"}.issubset(search_titles)
    assert "Dashboard Source" in search_titles
    assert "Knowledge Index" not in search_titles
    assert "Agent Engineering" not in search_titles
    assert str(tmp_path) not in json.dumps(snapshot["search_index"], ensure_ascii=False)
    assert str(tmp_path) not in json.dumps(snapshot, ensure_ascii=False)
    assert "index_path" not in json.dumps(snapshot["sources"]["connectors"], ensure_ascii=False)


def test_dashboard_omitted_knowledge_items_keep_type_path_and_search_hint(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    source_dir = kb_root / "knowledge" / "sources" / "web"
    source_dir.mkdir(parents=True)
    for index in range(7):
        (source_dir / f"source-{index}.md").write_text(
            "\n".join(
                [
                    "---",
                    "type: Source",
                    f"title: Dashboard Source {index}",
                    "topic: dashboard",
                    "---",
                    f"# Dashboard Source {index}",
                ]
            ),
            encoding="utf-8",
        )
    home.register_knowledge_base("research_notes", kb_root)

    managed = DashboardModule(home=home).snapshot()["knowledge"]["managed"][0]

    assert managed["display_limit"] == 5
    assert managed["omitted_item_count"] == 2
    assert managed["omitted_items"] == [
        {
            "title": "Dashboard Source 5",
            "type": "Source",
            "relative_path": "knowledge/sources/web/source-5.md",
            "search_hint": 'alcove search "Dashboard Source 5" --json',
        },
        {
            "title": "Dashboard Source 6",
            "type": "Source",
            "relative_path": "knowledge/sources/web/source-6.md",
            "search_hint": 'alcove search "Dashboard Source 6" --json',
        },
    ]
    assert len(managed["items"]) == 5
    assert "all_items" not in managed
    assert len(managed["search_items"]) == 7
    assert all(
        set(item) <= {"title", "type", "relative_path", "notes"} for item in managed["search_items"]
    )

    snapshot = DashboardModule(home=home).snapshot()
    indexed_titles = {
        row["title"] for row in snapshot["search_index"] if row["type"] == "knowledge-item"
    }
    assert "Dashboard Source 6" in indexed_titles


def test_dashboard_default_knowledge_view_hides_deleted_okf_records(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    source_dir = kb_root / "knowledge" / "sources" / "web"
    source_dir.mkdir(parents=True)
    (source_dir / "active.md").write_text(
        "---\ntype: Source\ntitle: Active Dashboard Source\nstatus: active\n---\n"
        "# Active Dashboard Source\n",
        encoding="utf-8",
    )
    (source_dir / "deleted.md").write_text(
        "---\ntype: Source\ntitle: Deleted Dashboard Source\nstatus: deleted\n---\n"
        "# Deleted Dashboard Source\n",
        encoding="utf-8",
    )
    home.register_knowledge_base("research_notes", kb_root)

    snapshot = DashboardModule(home=home).snapshot()
    managed = snapshot["knowledge"]["managed"][0]
    indexed_titles = {
        row["title"] for row in snapshot["search_index"] if row["type"] == "knowledge-item"
    }

    assert managed["item_count"] == 1
    assert managed["deleted_item_count"] == 1
    assert [item["title"] for item in managed["items"]] == ["Active Dashboard Source"]
    assert [item["title"] for item in managed["search_items"]] == ["Active Dashboard Source"]
    assert "Active Dashboard Source" in indexed_titles
    assert "Deleted Dashboard Source" not in indexed_titles


def test_dashboard_kb_excerpts_truncate_on_complete_lines(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    (kb_root / "knowledge" / "sources" / "web").mkdir(parents=True)
    long_lines = "\n".join(f"- Complete provenance line {index}" for index in range(80))
    (kb_root / "knowledge" / "sources" / "web" / "long.md").write_text(
        "---\ntype: Source\ntitle: Long Dashboard Source\n---\n"
        "# Long Dashboard Source\n\n"
        "## 来源\n\n"
        f"{long_lines}\n\n"
        "## Tail\n\n"
        "This should not be cut halfway.",
        encoding="utf-8",
    )
    home.register_knowledge_base("research_notes", kb_root)

    item = DashboardModule(home=home).snapshot()["knowledge"]["managed"][0]["items"][0]

    assert item["truncated"] is True
    assert item["notes"].splitlines()[-1].startswith("- Complete provenance line")
    assert not item["notes"].splitlines()[-1].endswith("provenance")
