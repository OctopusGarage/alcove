from __future__ import annotations

import yaml

from alcove.home import AlcoveHome


def test_home_init_creates_global_state_directories(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    assert home.root == tmp_path / "home"
    assert (home.root / "config.yml").is_file()
    assert home.paths().pins == home.root / "pins"
    assert home.paths().tasks == home.root / "tasks"
    assert home.paths().mounts == home.root / "mounts"
    assert home.paths().mount_indexes == home.root / "mounts" / "indexes"
    assert home.paths().connectors == home.root / "connectors"
    assert home.paths().knowledge_bases == home.root / "knowledge-bases"

    config = yaml.safe_load((home.root / "config.yml").read_text())
    assert config["version"] == 1
    assert config["home"] == {"name": "alcove"}


def test_home_default_honors_alcove_home_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("ALCOVE_HOME", str(tmp_path / "custom-home"))

    home = AlcoveHome.init()

    assert home.root == tmp_path / "custom-home"


def test_home_registers_and_lists_managed_knowledge_bases(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb_root = tmp_path / "social_media_posts"
    kb_root.mkdir()

    record = home.register_knowledge_base("social_media_posts", kb_root)
    records = home.list_knowledge_bases()
    loaded = home.get_knowledge_base("social_media_posts")

    assert record.name == "social_media_posts"
    assert record.path == kb_root.resolve()
    assert loaded == record
    assert records == [record]
    assert (
        (home.paths().knowledge_bases / "social_media_posts.yml")
        .read_text()
        .startswith("version: 1\n")
    )
