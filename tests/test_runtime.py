from __future__ import annotations

from alcove.home import AlcoveHome
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


def test_runtime_resolves_registered_kb_from_home(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    workspace = Workspace.init(tmp_path / "kb")
    home.register_knowledge_base("research_notes", workspace.root)

    runtime = AlcoveRuntime.resolve(home=home, kb="research_notes")

    assert runtime.home == home
    assert runtime.workspace == workspace
    assert runtime.knowledge_root == workspace.paths().knowledge


def test_runtime_discovers_current_workspace_when_required(tmp_path, monkeypatch):
    workspace = Workspace.init(tmp_path / "kb")
    nested = workspace.root / "inbox" / "web"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    runtime = AlcoveRuntime.resolve(require_workspace=True)

    assert runtime.workspace == workspace
