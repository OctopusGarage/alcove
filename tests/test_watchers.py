from __future__ import annotations

from alcove.cli import main
from alcove.home import AlcoveHome
from alcove.watchers import WatcherModule
from alcove.workspace import Workspace
import pytest
import yaml


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


def test_watcher_stale_check_handles_legacy_naive_checked_at(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    page.write_text("<html><title>First</title><body>v1</body></html>", encoding="utf-8")
    module = WatcherModule(home)
    module.add(title="Legacy Blog", url=page.as_uri(), kind="page", ttl_hours=24)
    source_path = home.root / "watchers/sources/legacy-blog.yml"
    payload = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    payload["checked_at"] = "2026-07-12T08:00:00"
    source_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = module.check(stale_only=True, now="2026-07-12T09:00:00+00:00")

    assert result["checked"] == 1
    assert result["sources"][0] == {"id": "legacy-blog", "status": "skipped"}


def test_watcher_stale_check_handles_invalid_persisted_ttl_hours(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    page.write_text("<html><title>First</title><body>v1</body></html>", encoding="utf-8")
    module = WatcherModule(home)
    module.add(title="Malformed TTL Blog", url=page.as_uri(), kind="page", ttl_hours=24)
    source_path = home.root / "watchers/sources/malformed-ttl-blog.yml"
    payload = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    payload["ttl_hours"] = "hourly"
    payload["checked_at"] = "2026-07-12T08:00:00+00:00"
    source_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = module.check(stale_only=True, now="2026-07-12T09:00:00+00:00")

    assert result["checked"] == 1
    assert result["sources"][0]["status"] == "skipped"


def test_watcher_check_rejects_persisted_source_id_path_traversal(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    page.write_text("<html><title>First</title><body>v1</body></html>", encoding="utf-8")
    sources = home.root / "watchers" / "sources"
    sources.mkdir(parents=True)
    (sources / "bad.yml").write_text(
        yaml.safe_dump(
            {
                "id": "../../../escaped-watcher",
                "title": "Bad Watcher",
                "url": page.as_uri(),
                "kind": "page",
                "status": "active",
            }
        ),
        encoding="utf-8",
    )

    result = WatcherModule(home).check(now="2026-07-12T09:00:00+00:00")

    assert result["errors"] == 1
    assert result["sources"][0]["id"] == "bad"
    assert "Invalid watcher source id" in result["sources"][0]["error"]
    assert not (tmp_path / "escaped-watcher.yml").exists()


def test_watcher_check_rejects_source_file_symlink_without_overwriting_target(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    page.write_text("<html><title>First</title><body>v1</body></html>", encoding="utf-8")
    sources_root = home.root / "watchers" / "sources"
    sources_root.mkdir(parents=True)
    target = tmp_path / "do-not-clobber.yml"
    target.write_text(
        yaml.safe_dump(
            {
                "id": "linked-source",
                "title": "Linked Source",
                "url": page.as_uri(),
                "kind": "page",
                "status": "active",
            }
        ),
        encoding="utf-8",
    )
    (sources_root / "linked-source.yml").symlink_to(target)

    with pytest.raises(RuntimeError, match="Refusing to write watcher source through symlink"):
        WatcherModule(home).check(source_id="linked-source", now="2026-07-12T09:00:00+00:00")

    payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert "checked_at" not in payload
    assert "last_signature" not in payload


def test_cli_watcher_check_rejects_event_log_symlink_without_appending_to_target(
    tmp_path,
    capsys,
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    page.write_text("<html><title>First</title><body>v1</body></html>", encoding="utf-8")
    module = WatcherModule(home)
    added = module.add(title="Linked Event Blog", url=page.as_uri(), kind="page")
    module.check(source_id=added["source"]["id"])
    capsys.readouterr()
    target = tmp_path / "do-not-append.jsonl"
    target.write_text("sentinel\n", encoding="utf-8")
    (home.root / "watchers" / "events.jsonl").symlink_to(target)
    page.write_text("<html><title>Second</title><body>v2</body></html>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="Refusing to write watcher event through symlink"):
        main(
            [
                "watch",
                "check",
                "--home",
                str(home.root),
                added["source"]["id"],
                "--json",
            ]
        )

    assert target.read_text(encoding="utf-8") == "sentinel\n"


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
