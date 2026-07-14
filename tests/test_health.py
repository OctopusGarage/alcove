from __future__ import annotations

import json
import shutil

import yaml

from alcove.agent_workspaces import AgentWorkspacesModule
from alcove.cli import main
from alcove.health import HealthModule
from alcove.health_registry import HomeHealthCheck, home_health_checks, required_home_path_names
from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.mounts import AddMountRequest, MountsModule
from alcove.pins import AddPinRequest, PinsModule
from alcove.prompts import AddPromptRequest, PromptsModule
from alcove.tasks import AddIdeaRequest, AddRoutineRequest, AddTaskRequest, TasksModule
from alcove.workspace import Workspace


def test_home_health_registry_lists_each_check_once():
    names = [check.name for check in home_health_checks()]

    assert len(names) == len(set(names))
    assert names[:5] == ["registered_kbs", "workspaces", "pins", "prompts", "prompt_quality"]
    assert {"tasks", "mounts", "connectors", "dashboard", "usage"}.issubset(names)
    assert required_home_path_names() == (
        "pins",
        "prompts",
        "tasks",
        "projects",
        "mounts",
        "connectors",
        "knowledge_bases",
    )


def test_health_checks_agent_workspace_registries(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    module = AgentWorkspacesModule(home)
    module.init("family", context="Family workspace")
    module.init("stale", path=str(tmp_path / "missing-workspace"))
    shutil.rmtree(tmp_path / "missing-workspace")

    report = HealthModule(home=home).check()

    assert report["status"] == "warnings"
    assert report["counts"]["workspaces"] == 2
    assert report["counts"]["workspace_paths_existing"] == 1
    assert report["counts"]["workspace_agent_configs"] == 1
    assert any(
        issue["module"] == "workspaces" and issue["kind"] == "missing_workspace_path"
        for issue in report["issues"]
    )


def test_health_home_checks_are_isolated(monkeypatch, tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    def broken_check(*_args):
        raise RuntimeError("adapter exploded")

    monkeypatch.setattr(
        "alcove.health.home_health_checks",
        lambda: [HomeHealthCheck("broken_adapter", broken_check)],
    )

    report = HealthModule(home=home).check()

    assert report["status"] == "issues"
    assert any(
        issue["module"] == "broken_adapter"
        and issue["kind"] == "health_check_failed"
        and "adapter exploded" in issue["message"]
        for issue in report["issues"]
    )


def test_health_detects_stale_global_indexes_and_fix_rebuilds(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(AddPinRequest(title="OKF Reference", content="Use local evidence."))
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Review Prompt",
            content=(
                "Use this before shipping a change that needs evidence review.\n\n"
                "Inspect local evidence, relevant tests, and the change summary before judging. "
                "Report only concrete correctness or validation gaps, then recommend the "
                "smallest fix.\n\n"
                "Output findings, risks, and verification notes. Do not invent issues or "
                "hide assumptions.\n\n"
                "Verify the final judgment against the evidence you inspected."
            ),
            description="Review local evidence before shipping.",
            tags=["review"],
            use_cases=["Health test prompt"],
            kind="eval_prompt",
            domain="testing",
            outputs=["findings"],
        )
    )
    HealthModule(home=home).check(fix=True)

    pin_index = home.paths().pins / "index.json"
    payload = json.loads(pin_index.read_text(encoding="utf-8"))
    payload["pins"] = []
    pin_index.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    stale = HealthModule(home=home).check()

    assert stale["status"] == "warnings"
    assert any(issue["kind"] == "index_count_mismatch" for issue in stale["issues"])

    fixed = HealthModule(home=home).check(fix=True)

    assert fixed["status"] == "ok"
    assert any(action["module"] == "pins" for action in fixed["actions"])
    repaired = json.loads(pin_index.read_text(encoding="utf-8"))
    assert repaired["count"] == 1
    assert len(repaired["pins"]) == 1


def test_health_includes_prompt_quality_audit(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Tiny Prompt",
            content="Do it.",
            tags=["tiny"],
            use_cases=[],
        )
    )

    report = HealthModule(home=home).check()

    assert report["status"] == "warnings"
    assert report["counts"]["prompt_ready_prompts"] == 0
    assert report["counts"]["prompt_quality_issues"] > 0
    assert any(issue["kind"] == "prompt_short_content" for issue in report["issues"])


def test_health_checks_registered_kb_okf_validation(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    workspace = Workspace.init(tmp_path / "kb")
    home.register_knowledge_base("research_notes", workspace.root)
    broken = workspace.paths().knowledge / "broken.md"
    broken.write_text("# Missing frontmatter\n", encoding="utf-8")

    report = HealthModule(home=home).check()

    assert report["status"] == "issues"
    assert report["counts"]["registered_kbs"] == 1
    assert any(issue["module"] == "managed_kb" for issue in report["issues"])
    assert any(issue["kind"] == "missing_okf_type" for issue in report["issues"])


def test_health_dedupes_workspace_and_registered_kb_issues(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    workspace = Workspace.init(tmp_path / "kb")
    home.register_knowledge_base("research_notes", workspace.root)
    broken = workspace.paths().knowledge / "broken.md"
    broken.write_text("# Missing frontmatter\n", encoding="utf-8")

    report = HealthModule(home=home, workspace=workspace).check()

    matching = [
        issue
        for issue in report["issues"]
        if issue["kind"] == "missing_okf_type" and issue["path"].endswith("broken.md")
    ]
    assert len(matching) == 1


def test_health_flags_invalid_governed_okf_schema(tmp_path):
    workspace = Workspace.init(tmp_path / "kb")
    MarkdownRepository().write_doc(
        workspace.paths().knowledge / "sources" / "web" / "bad.md",
        MarkdownDoc(
            frontmatter={
                "type": "Source",
                "schema": "wrong/schema",
                "title": "Bad Schema",
                "platform": "web",
                "resource": "https://example.test",
                "domain": "default",
                "topic": "default",
                "tags": [],
                "status": "active",
                "created_at": "2026-07-11T00:00:00+08:00",
            },
            body="# Bad Schema\n",
        ),
    )

    report = HealthModule(workspace=workspace).check()

    assert report["status"] == "warnings"
    assert any(issue["kind"] == "invalid_okf_schema" for issue in report["issues"])


def test_health_flags_invalid_mount_okf_schema(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    source = tmp_path / "source-docs"
    source.mkdir()
    (source / "note.md").write_text("# Agent Notes\n\nMount search needle.", encoding="utf-8")
    mounts = MountsModule(home=home)
    mount = mounts.add(AddMountRequest(path=str(source), name="Source Docs"))
    mounts.scan(mount.id)

    repo = MarkdownRepository()
    mount_index_path = home.paths().mounts / "okf" / mount.id / "index.md"
    mount_index = repo.read_doc(mount_index_path)
    repo.write_doc(
        mount_index_path,
        MarkdownDoc(
            frontmatter={**mount_index.frontmatter, "schema": "wrong/schema"},
            body=mount_index.body,
        ),
    )
    item_path = next((home.paths().mounts / "okf" / mount.id / "items").glob("*.md"))
    item = repo.read_doc(item_path)
    repo.write_doc(
        item_path,
        MarkdownDoc(
            frontmatter={**item.frontmatter, "schema": "wrong/schema"},
            body=item.body,
        ),
    )

    report = HealthModule(home=home).check()

    assert report["status"] == "warnings"
    invalid_paths = {
        issue["path"]
        for issue in report["issues"]
        if issue["module"] == "mounts" and issue["kind"] == "invalid_okf_schema"
    }
    assert str(mount_index_path) in invalid_paths
    assert str(item_path) in invalid_paths


def test_health_flags_invalid_mount_index_policy(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    source = tmp_path / "source"
    source.mkdir()
    mounts = MountsModule(home=home)
    mount = mounts.add(AddMountRequest(path=str(source), name="Source Docs"))
    mounts_path = home.paths().mounts / "mounts.json"
    data = json.loads(mounts_path.read_text(encoding="utf-8"))
    data["mounts"][0]["index_policy"] = {"profile": "unknown-profile"}
    mounts_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    report = HealthModule(home=home).check()

    assert any(
        issue["module"] == "mounts"
        and issue["kind"] == "invalid_mount_index_policy"
        and issue["path"].endswith("mounts.json")
        and mount.id in issue["message"]
        for issue in report["issues"]
    )


def test_health_fix_repairs_missing_governed_okf_schema(tmp_path):
    workspace = Workspace.init(tmp_path / "kb")
    path = workspace.paths().knowledge / "concepts" / "agent" / "okf" / "schema.md"
    MarkdownRepository().write_doc(
        path,
        MarkdownDoc(
            frontmatter={
                "type": "Knowledge Concept",
                "title": "Schema",
                "domain": "agent",
                "topic": "okf",
                "tags": [],
                "source_refs": [],
                "status": "active",
                "created_at": "2026-07-11T00:00:00+08:00",
            },
            body="# Schema\n",
        ),
    )

    before = HealthModule(workspace=workspace).check()
    fixed = HealthModule(workspace=workspace).check(fix=True)
    repaired = MarkdownRepository().read_doc(path)

    assert any(issue["kind"] == "missing_okf_schema" for issue in before["issues"])
    assert fixed["status"] == "ok"
    assert fixed["actions"] == [
        {
            "module": "managed_kb",
            "action": "repaired_missing_okf_schema",
            "path": str(workspace.root),
            "count": "1",
        }
    ]
    assert repaired.frontmatter["schema"] == "alcove/knowledge-concept/v1"


def test_cli_health_outputs_json_and_uses_fix(tmp_path, capsys):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(AddPinRequest(title="Pinned Thing", content="content"))

    code = main(["health", "--home", str(home.root), "--fix", "--json"])
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert payload["status"] == "ok"
    assert payload["home"] == str(home.root)
    assert payload["counts"]["pins"] == 1
    assert any(action["module"] == "okf_catalog" for action in payload["actions"])


def test_health_checks_operational_module_data(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    (home.root / "dashboard").mkdir()
    (home.root / "dashboard" / "snapshot.json").write_text("{}", encoding="utf-8")
    (home.root / "publishers" / "definitions").mkdir(parents=True)
    (home.root / "publishers" / "definitions" / "broken.yml").write_text(
        "targets: [", encoding="utf-8"
    )
    (home.root / "radars" / "definitions").mkdir(parents=True)
    (home.root / "radars" / "definitions" / "broken.yml").write_text("sources: [", encoding="utf-8")
    (home.root / "watchers" / "sources").mkdir(parents=True)
    (home.root / "watchers" / "sources" / "broken.yml").write_text("url: [", encoding="utf-8")
    (home.root / "blog-monitor" / "sources").mkdir(parents=True)
    (home.root / "blog-monitor" / "sources" / "broken.yml").write_text("url: [", encoding="utf-8")
    (home.root / "automations" / "jobs").mkdir(parents=True)
    (home.root / "automations" / "jobs" / "broken.yml").write_text("cmd: [", encoding="utf-8")
    (home.paths().stats / "summary.json").write_text("{", encoding="utf-8")

    report = HealthModule(home=home).check()

    assert report["status"] == "issues"
    kinds = {issue["kind"] for issue in report["issues"]}
    assert "invalid_dashboard_snapshot" in kinds
    assert "invalid_yaml" in kinds
    assert "invalid_json" in kinds
    assert report["counts"]["publisher_definitions"] == 1
    assert report["counts"]["radar_definitions"] == 1
    assert report["counts"]["watch_sources"] == 1
    assert report["counts"]["blog_sources"] == 1
    assert report["counts"]["automation_jobs"] == 1


def test_health_flags_active_planner_fixture_records(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    tasks = TasksModule(home=home)
    fixture_task = tasks.task_add(
        AddTaskRequest(title="MCP Task", notes="Expose task tools.", tags=["mcp"])
    )
    fixture_idea = tasks.idea_add(AddIdeaRequest(title="test idea"))
    fixture_routine = tasks.routine_add(
        AddRoutineRequest(title="MCP Routine", tags=["mcp"], next_due="2026-07-10")
    )
    cancelled = tasks.task_add(AddTaskRequest(title="Smoke Task", tags=["smoke"]))
    tasks.task_cancel(cancelled.id)
    archived = tasks.idea_add(AddIdeaRequest(title="smoke idea"))
    tasks.idea_archive(archived.id)

    report = HealthModule(home=home).check()

    assert report["status"] == "warnings"
    assert report["counts"]["planner_fixture_records"] == 3
    messages = {
        issue["message"] for issue in report["issues"] if issue["kind"] == "active_fixture_record"
    }
    assert any(fixture_task.id in message for message in messages)
    assert any(fixture_idea.id in message for message in messages)
    assert any(fixture_routine.id in message for message in messages)
    assert not any(cancelled.id in message for message in messages)
    assert not any(archived.id in message for message in messages)

    fixture_report = HealthModule(home=home).check(fixture_context=True)

    assert fixture_report["counts"]["planner_fixture_records"] == 3
    assert fixture_report["counts"]["planner_fixture_context"] == 1
    assert not [
        issue for issue in fixture_report["issues"] if issue["kind"] == "active_fixture_record"
    ]


def test_health_checks_connector_source_registry_status(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    source_path = home.paths().connectors / "github-stars" / "sources" / "kingson.yml"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        yaml.safe_dump(
            {
                "schema": "alcove/connector-source/v1",
                "connector": "github-stars",
                "id": "kingson",
                "source": "https://github.com/Kingson4Wu?tab=stars",
                "refresh": {
                    "status": "error",
                    "last_checked_at": "2026-07-12T00:00:00+00:00",
                    "ttl_hours": 24,
                    "item_count": 0,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    report = HealthModule(home=home).check()

    assert report["status"] == "warnings"
    assert report["counts"]["connector_sources"] == 1
    assert any(issue["kind"] == "connector_source_error" for issue in report["issues"])


def test_health_deep_rebuilds_mounts_dashboard_usage_and_catalog(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    source = tmp_path / "source-docs"
    source.mkdir()
    (source / "note.md").write_text("# Deep Note\n\nDeep health needle.", encoding="utf-8")
    MountsModule(home=home).add(AddMountRequest(path=str(source), name="Source Docs"))

    report = HealthModule(home=home).check(fix=True, deep=True)

    assert report["status"] == "ok"
    action_modules = {action["module"] for action in report["actions"]}
    assert {"mounts", "dashboard", "usage", "okf_catalog"} <= action_modules
    assert (home.paths().mounts / "indexes" / "source-docs.json").is_file()
    assert (home.root / "dashboard" / "snapshot.json").is_file()
    assert (home.paths().stats / "summary.json").is_file()


def test_cli_health_deep_accepts_refresh_stale_connector_flag(tmp_path, capsys):
    home = AlcoveHome.init(tmp_path / "home")
    sources_root = home.paths().connectors / "chrome-bookmarks" / "sources"
    sources_root.mkdir(parents=True)
    (sources_root / "default.yml").write_text(
        yaml.safe_dump(
            {
                "schema": "alcove/connector-source/v1",
                "id": "default",
                "connector": "chrome-bookmarks",
                "source": "Chrome Bookmarks: Default",
                "source_file": str(tmp_path / "missing-bookmarks.json"),
                "refresh": {
                    "status": "stale",
                    "last_checked_at": "2020-01-01T00:00:00+00:00",
                    "ttl_hours": 1,
                    "item_count": 0,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    code = main(
        [
            "health",
            "--home",
            str(home.root),
            "--fix",
            "--deep",
            "--refresh-stale-connectors",
            "--json",
        ]
    )
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert any(action["module"] == "connectors" for action in payload["actions"])
    assert payload["counts"]["connector_sources"] == 1
