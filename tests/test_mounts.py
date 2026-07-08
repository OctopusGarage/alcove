from __future__ import annotations

from alcove.mounts import AddMountRequest, MountsModule
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def test_mount_add_and_list_persists_local_folder_mount(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source-docs"
    source.mkdir()

    mount = MountsModule(workspace).add(
        AddMountRequest(path=str(source), name="Source Docs", mount_type="local-folder")
    )
    mounts = MountsModule(workspace).list()

    assert mount.id == "source-docs"
    assert mount.name == "Source Docs"
    assert mount.type == "local-folder"
    assert mount.path == str(source.resolve())
    assert mounts == [mount]
    assert (workspace.paths().mounts / "mounts.json").is_file()


def test_mount_scan_indexes_text_files_without_copying_content(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source-docs"
    source.mkdir()
    (source / "note.md").write_text("# Agent Notes\n\nMount search needle.", encoding="utf-8")
    (source / "data.json").write_text('{"name":"ignored"}', encoding="utf-8")
    (source / "image.png").write_bytes(b"png")
    module = MountsModule(workspace)
    mount = module.add(AddMountRequest(path=str(source), mount_type="local-folder"))

    report = module.scan(mount.id)

    assert report["scanned"] == 1
    assert report["skipped"] == 2
    assert report["items"][0]["title"] == "Agent Notes"
    assert report["items"][0]["path"].endswith("note.md")
    assert not (workspace.paths().mounts / mount.id / "note.md").exists()


def test_mount_scan_reuses_unchanged_index_items(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source-docs"
    source.mkdir()
    note = source / "note.md"
    note.write_text("# Agent Notes\n\nMount search needle.", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(AddMountRequest(path=str(source), mount_type="local-folder"))

    first = module.scan(mount.id)
    second = module.scan(mount.id)
    note.write_text("# Agent Notes\n\nChanged needle.", encoding="utf-8")
    third = module.scan(mount.id)

    assert first["reused"] == 0
    assert second["scanned"] == 1
    assert second["reused"] == 1
    assert second["items"][0]["indexed_at"] == first["items"][0]["indexed_at"]
    assert third["scanned"] == 1
    assert third["reused"] == 0
    assert third["items"][0]["text"] == "# Agent Notes\n\nChanged needle."


def test_mount_scan_detects_local_git_repo(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".git").mkdir()
    (repo / "README.md").write_text("# Mounted Repo\n\nRepo search needle.", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(AddMountRequest(path=str(repo), mount_type="git-repo-local"))

    report = module.scan(mount.id)

    assert report["mount"]["type"] == "git-repo-local"
    assert report["scanned"] == 1
    assert report["items"][0]["title"] == "Mounted Repo"


def test_search_includes_mounted_items_after_scan(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source-docs"
    source.mkdir()
    (source / "note.md").write_text(
        "# Mounted Note\n\nHistorical archive needle.", encoding="utf-8"
    )
    module = MountsModule(workspace)
    module.add(AddMountRequest(path=str(source), name="Archive", tags=["history"]))
    module.scan()

    rows = SearchModule(workspace).search(SearchRequest(query="archive needle"))

    assert len(rows) == 1
    assert {
        "root": "mounts",
        "type": "Mounted Item",
        "title": "Mounted Note",
        "tags": ["history"],
        "status": "active",
    }.items() <= rows[0].items()
    assert rows[0]["path"].startswith("mounts/archive#")
