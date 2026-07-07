from pathlib import Path

import yaml
import pytest

from alcove.errors import WorkspaceInitializationError, WorkspaceNotFoundError
from alcove.workspace import DATA_DIRS, Workspace


def test_workspace_init_creates_expected_directories(tmp_path):
    workspace = Workspace.init(tmp_path)

    assert workspace.root == tmp_path
    assert (tmp_path / ".alcove" / "config.yml").is_file()
    assert (tmp_path / ".alcove" / "connectors").is_dir()
    assert (tmp_path / ".alcove" / "logs").is_dir()
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
    assert config["paths"] == {name: name for name in DATA_DIRS}


def test_workspace_discover_walks_up_from_child(tmp_path):
    Workspace.init(tmp_path)
    child = tmp_path / "a" / "b"
    child.mkdir(parents=True)

    discovered = Workspace.discover(child)

    assert discovered.root == tmp_path


def test_workspace_discover_raises_when_no_workspace_exists(tmp_path):
    with pytest.raises(WorkspaceNotFoundError, match="No Alcove workspace found"):
        Workspace.discover(tmp_path)


def test_workspace_status_reports_initialized_paths(tmp_path):
    workspace = Workspace.init(tmp_path)
    status = workspace.status()

    assert status["initialized"] is True
    assert status["root"] == str(tmp_path)
    assert status["paths"]["knowledge"] == str(tmp_path / "knowledge")


def test_workspace_init_existing_file_raises_alcove_error(tmp_path):
    target = tmp_path / "not-a-directory"
    target.write_text("content")

    with pytest.raises(WorkspaceInitializationError, match="Could not initialize"):
        Workspace.init(target)


def test_workspace_paths_honor_configured_paths(tmp_path):
    Workspace.init(tmp_path)
    config_path = tmp_path / ".alcove" / "config.yml"
    config = yaml.safe_load(config_path.read_text())
    config["paths"]["knowledge"] = "vault/knowledge"
    config["paths"]["todo"] = "next-actions"
    config_path.write_text(yaml.safe_dump(config, sort_keys=False))

    workspace = Workspace.discover(tmp_path)
    paths = workspace.paths()
    status = workspace.status()

    assert paths.knowledge == tmp_path / "vault" / "knowledge"
    assert paths.todo == tmp_path / "next-actions"
    assert status["paths"]["knowledge"] == str(tmp_path / "vault" / "knowledge")
    assert status["paths"]["todo"] == str(tmp_path / "next-actions")
