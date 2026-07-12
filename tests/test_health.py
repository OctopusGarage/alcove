from __future__ import annotations

import json

from alcove.cli import main
from alcove.health import HealthModule
from alcove.home import AlcoveHome
from alcove.markdown import MarkdownDoc, MarkdownRepository
from alcove.mounts import AddMountRequest, MountsModule
from alcove.pins import AddPinRequest, PinsModule
from alcove.prompts import AddPromptRequest, PromptsModule
from alcove.workspace import Workspace


def test_health_detects_stale_global_indexes_and_fix_rebuilds(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    PinsModule(home=home).add(AddPinRequest(title="OKF Reference", content="Use local evidence."))
    PromptsModule(home=home).save(
        AddPromptRequest(title="Review Prompt", content="Review the local evidence.")
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
