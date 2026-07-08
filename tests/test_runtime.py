from __future__ import annotations

from alcove.home import AlcoveHome
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


def test_runtime_resolves_registered_kb_from_home(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    workspace = Workspace.init(tmp_path / "kb")
    home.register_knowledge_base("social_media_posts", workspace.root)

    runtime = AlcoveRuntime.resolve(home=home, kb="social_media_posts")

    assert runtime.home == home
    assert runtime.workspace == workspace
    assert runtime.knowledge_root == workspace.paths().knowledge
