from __future__ import annotations

from alcove.cli import main
from alcove.home import AlcoveHome
from alcove.watchers import WatcherModule
from alcove.workspace import Workspace


def test_watcher_add_and_check_detects_file_url_changes(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    page.write_text("<html><title>First</title><body>v1</body></html>", encoding="utf-8")
    module = WatcherModule(home)

    added = module.add(title="Example Blog", url=page.as_uri(), kind="page", tags=["blog"])
    first = module.check(source_id=added["source"]["id"])
    page.write_text("<html><title>Second</title><body>v2</body></html>", encoding="utf-8")
    second = module.check(source_id=added["source"]["id"])

    assert added["source"]["id"] == "example-blog"
    assert first["sources"][0]["status"] == "initialized"
    assert second["changed"] == 1
    assert second["sources"][0]["status"] == "changed"
    assert (home.root / "watchers" / "events.jsonl").is_file()


def test_watcher_change_can_add_update_to_managed_kb_inbox(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    kb_root = tmp_path / "research_notes"
    Workspace.init(kb_root)
    home.register_knowledge_base("research_notes", kb_root)
    page = tmp_path / "blog.html"
    page.write_text("<html><title>First</title><body>v1</body></html>", encoding="utf-8")
    module = WatcherModule(home)
    added = module.add(
        title="Research Blog",
        url=page.as_uri(),
        kind="page",
        kb="research_notes",
        tags=["blog"],
    )
    module.check(source_id=added["source"]["id"])

    page.write_text("<html><title>Second</title><body>v2</body></html>", encoding="utf-8")
    result = module.check(source_id=added["source"]["id"])

    assert result["changed"] == 1
    inbox_items = sorted((kb_root / "inbox" / "manual").iterdir())
    assert len(inbox_items) == 1
    assert "Watcher update: Research Blog" in (inbox_items[0] / "note.md").read_text(
        encoding="utf-8"
    )


def test_cli_watch_add_list_and_check_file_url(tmp_path, capsys):
    home = tmp_path / ".alcove"
    page = tmp_path / "blog.html"
    page.write_text("<html><title>First</title><body>v1</body></html>", encoding="utf-8")

    add_code = main(
        [
            "watch",
            "add",
            "--home",
            str(home),
            "CLI Blog",
            page.as_uri(),
            "--tag",
            "blog",
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    list_code = main(["watch", "list", "--home", str(home), "--json"])
    list_output = capsys.readouterr()
    check_code = main(["watch", "check", "--home", str(home), "--json"])
    check_output = capsys.readouterr()

    assert add_code == 0
    assert '"id": "cli-blog"' in add_output.out
    assert list_code == 0
    assert '"count": 1' in list_output.out
    assert check_code == 0
    assert '"status": "initialized"' in check_output.out
