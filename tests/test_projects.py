from __future__ import annotations

from alcove.home import AlcoveHome
from alcove.projects import AddProjectRequest, ProjectsModule
from alcove.search import SearchModule, SearchRequest
import json


def test_project_add_get_find_list_and_remove_use_global_home(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    project_root = tmp_path / "work" / "alcove"
    project_root.mkdir(parents=True)
    module = ProjectsModule(home=home)

    added = module.add(
        AddProjectRequest(
            alias="alcove",
            path=str(project_root),
            note="Personal knowledge manager.",
        )
    )
    exact = module.get("alcove")
    found = module.find("knowledge")
    listed = module.list()
    removed = module.remove("alcove")

    assert added.alias == "alcove"
    assert added.path == project_root.resolve()
    assert exact.note == "Personal knowledge manager."
    assert [project.alias for project in found] == ["alcove"]
    assert listed[0].exists is True
    assert removed["status"] == "removed"
    assert module.list() == []


def test_project_find_scans_configured_roots(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    root = tmp_path / "programming"
    target = root / "forge-mcp-server"
    target.mkdir(parents=True)
    module = ProjectsModule(home=home)
    module.configure_roots([str(root)])

    matches = module.find("forge")

    assert matches[0].alias == "forge-mcp-server"
    assert matches[0].path == target.resolve()
    assert matches[0].source == "root-scan"


def test_project_registry_persists_user_paths_with_tilde(tmp_path, monkeypatch):
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    home = AlcoveHome.init(user_home / ".alcove")
    project_root = user_home / "projects" / "alcove"
    project_root.mkdir(parents=True)
    module = ProjectsModule(home=home)

    added = module.add(AddProjectRequest(alias="alcove", path=str(project_root)))
    module.configure_roots([str(user_home / "projects")])
    raw_config = json.loads((home.paths().projects / "projects.json").read_text(encoding="utf-8"))

    assert raw_config["projects"]["alcove"]["path"] == "~/projects/alcove"
    assert raw_config["roots"] == ["~/projects"]
    assert added.path == project_root.resolve()
    assert module.get("alcove").path == project_root.resolve()


def test_search_includes_registered_projects(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    project_root = tmp_path / "clipsmith"
    project_root.mkdir()
    ProjectsModule(home=home).add(
        AddProjectRequest(
            alias="clipsmith",
            path=str(project_root),
            note="Social post capture toolkit.",
        )
    )

    rows = SearchModule(home=home).search(SearchRequest(query="capture toolkit"))

    assert rows[0]["root"] == "projects"
    assert rows[0]["type"] == "Project"
    assert rows[0]["title"] == "clipsmith"
    assert rows[0]["resource"] == str(project_root.resolve())
