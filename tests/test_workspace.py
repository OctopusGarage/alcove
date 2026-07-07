from pathlib import Path

import yaml

from alcove.workspace import Workspace


def test_workspace_init_creates_expected_directories(tmp_path):
    workspace = Workspace.init(tmp_path)

    assert workspace.root == tmp_path
    assert (tmp_path / ".alcove" / "config.yml").is_file()
    assert (tmp_path / "knowledge").is_dir()
    assert (tmp_path / "inbox").is_dir()
    assert (tmp_path / "archive").is_dir()
    assert (tmp_path / "pins").is_dir()
    assert (tmp_path / "tasks").is_dir()
    assert (tmp_path / "mounts").is_dir()
    assert (tmp_path / "todo").is_dir()

    config = yaml.safe_load((tmp_path / ".alcove" / "config.yml").read_text())
    assert config["version"] == 1
    assert config["workspace"] == {"name": tmp_path.name}


def test_workspace_discover_walks_up_from_child(tmp_path):
    Workspace.init(tmp_path)
    child = tmp_path / "a" / "b"
    child.mkdir(parents=True)

    discovered = Workspace.discover(child)

    assert discovered.root == tmp_path


def test_workspace_status_reports_initialized_paths(tmp_path):
    workspace = Workspace.init(tmp_path)
    status = workspace.status()

    assert status["initialized"] is True
    assert status["root"] == str(tmp_path)
    assert status["paths"]["knowledge"] == str(tmp_path / "knowledge")
