from __future__ import annotations

import json

from alcove.cli import main
from alcove.home import AlcoveHome
from alcove.mounts import AddMountRequest, MountsModule
from alcove.okf_catalog import OkfCatalogModule
from alcove.paths import compact_user_path
from alcove.pins import AddPinRequest, PinsModule
from alcove.projects import AddProjectRequest, ProjectsModule
from alcove.prompts import AddPromptRequest, PromptsModule
from alcove.tasks import AddIdeaRequest, AddTaskRequest, TasksModule


def test_okf_catalog_builds_global_progressive_disclosure_entry(tmp_path):
    home = _home_with_global_memory(tmp_path)

    result = OkfCatalogModule(home).build()

    assert result["status"] == "built"
    assert result["root"] == compact_user_path(home.root / "okf")
    assert sorted(result["files"]) == [
        "external-indexes.md",
        "global-memory.md",
        "index.md",
        "log.md",
        "managed-kbs.md",
        "modules/connectors.md",
        "modules/mounts.md",
        "modules/pins.md",
        "modules/projects.md",
        "modules/prompts.md",
        "modules/tasks.md",
        "search-map.md",
    ]

    index = (home.root / "okf" / "index.md").read_text(encoding="utf-8")
    managed = (home.root / "okf" / "managed-kbs.md").read_text(encoding="utf-8")
    memory = (home.root / "okf" / "global-memory.md").read_text(encoding="utf-8")
    external = (home.root / "okf" / "external-indexes.md").read_text(encoding="utf-8")
    search_map = (home.root / "okf" / "search-map.md").read_text(encoding="utf-8")

    assert "Alcove Global OKF Catalog" in index
    assert "[Managed Knowledge Bases](managed-kbs.md)" in index
    assert "research_notes" in managed
    assert "../knowledge-bases/research_notes.yml" in managed
    assert "Reference Pin" in memory
    assert "Review Prompt" in memory
    assert "Investigate OKF" in memory
    assert "alcove-project" in memory
    assert "Archive Mount" in external
    assert "../mounts/okf/archive-mount/index.md" in external
    assert "github-stars" in external
    assert "../connectors/github-stars/okf/index.md" in external
    assert "Search returns candidates, not final answers." in search_map


def test_cli_okf_catalog_build_exposes_catalog_payload(tmp_path, capsys):
    home = _home_with_global_memory(tmp_path)

    code = main(["okf", "--home", str(home.root), "catalog", "build", "--json"])
    output = capsys.readouterr()

    payload = json.loads(output.out)
    assert code == 0
    assert payload["status"] == "built"
    assert payload["home"] == str(home.root)
    assert "search-map.md" in payload["files"]
    assert (home.root / "okf" / "index.md").is_file()


def _home_with_global_memory(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb_root = tmp_path / "research_notes"
    kb_root.mkdir()
    home.register_knowledge_base("research_notes", kb_root)

    PinsModule(home=home).add(
        AddPinRequest(
            title="Reference Pin",
            content="Stable repeated reference.",
            tags=["okf"],
        )
    )
    PromptsModule(home=home).save(
        AddPromptRequest(
            title="Review Prompt",
            content="Review with local evidence.",
            tags=["review"],
        )
    )
    tasks = TasksModule(home=home)
    tasks.task_add(AddTaskRequest(title="Investigate OKF", tags=["okf"]))
    tasks.idea_add(AddIdeaRequest(title="Try connector catalog", tags=["connector"]))
    project_root = tmp_path / "alcove-project"
    project_root.mkdir()
    ProjectsModule(home=home).add(
        AddProjectRequest(alias="alcove-project", path=str(project_root), note="Catalog test")
    )

    mount_source = tmp_path / "archive"
    mount_source.mkdir()
    (mount_source / "note.md").write_text("# Archive Note\n\nOKF archive needle.", encoding="utf-8")
    mounts = MountsModule(home=home)
    mount = mounts.add(
        AddMountRequest(path=str(mount_source), name="Archive Mount", tags=["archive"])
    )
    mounts.scan(mount.id)

    connector_dir = home.paths().connectors / "github-stars"
    okf_dir = connector_dir / "okf"
    okf_dir.mkdir(parents=True)
    (okf_dir / "index.md").write_text(
        "---\ntype: Connector Index\nschema: okf/connector-index/v1\n"
        "title: GitHub Stars\n---\n# GitHub Stars\n",
        encoding="utf-8",
    )
    (connector_dir / "index.json").write_text(
        json.dumps(
            {
                "connector": "github-stars",
                "source_id": "kingson4wu",
                "items": [{"title": "Codegraph", "relative_path": "codegraph"}],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return home
