from __future__ import annotations

import json

from alcove.cli import main
from alcove.markdown import MarkdownRepository
from alcove.mounts import AddMountRequest, MountIndexPolicy, MountsModule
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
    assert report["items"][0]["relative_path"] == "note.md"
    assert "path" not in report["items"][0]
    assert "file_size" not in report["items"][0]
    assert "file_mtime_ns" not in report["items"][0]
    assert "diagnostics" not in report["items"][0]
    assert not (workspace.paths().mounts / mount.id / "note.md").exists()

    debug_report = module.scan(mount.id, include_diagnostics=True)
    assert debug_report["items"][0]["diagnostics"]["file_size"] > 0
    assert debug_report["items"][0]["diagnostics"]["file_mtime_ns"] > 0


def test_mount_scan_writes_okf_markdown_index_for_agent_search(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source-docs"
    source.mkdir()
    (source / "note.md").write_text("# Agent Notes\n\nMount search needle.", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(AddMountRequest(path=str(source), name="Source Docs", tags=["agent"]))

    module.scan(mount.id)

    repo = MarkdownRepository()
    mount_index = repo.read_doc(workspace.paths().mounts / "okf" / mount.id / "index.md")
    item_paths = sorted((workspace.paths().mounts / "okf" / mount.id / "items").glob("*.md"))
    item = repo.read_doc(item_paths[0])
    assert mount_index.frontmatter["type"] == "Mount Index"
    assert mount_index.frontmatter["schema"] == "okf/mount-index/v1"
    assert mount_index.frontmatter["mount_id"] == mount.id
    assert mount_index.frontmatter["item_count"] == 1
    assert item.frontmatter["type"] == "Mounted Item"
    assert item.frontmatter["schema"] == "okf/mounted-item/v1"
    assert item.frontmatter["relative_path"] == "note.md"
    assert "Mount search needle." in item.body


def test_mount_scan_removes_stale_okf_items_when_source_file_is_deleted(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source-docs"
    source.mkdir()
    note = source / "note.md"
    note.write_text("# Agent Notes\n\nMount search needle.", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(AddMountRequest(path=str(source), name="Source Docs"))
    module.scan(mount.id)
    item_dir = workspace.paths().mounts / "okf" / mount.id / "items"
    assert len(list(item_dir.glob("*.md"))) == 1

    note.unlink()
    report = module.scan(mount.id)

    assert report["scanned"] == 0
    assert list(item_dir.glob("*.md")) == []
    mount_index = MarkdownRepository().read_doc(
        workspace.paths().mounts / "okf" / mount.id / "index.md"
    )
    assert mount_index.frontmatter["item_count"] == 0


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


def test_mount_docs_profile_filters_generated_and_agent_markdown(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "superpowers" / "plans").mkdir(parents=True)
    (repo / "book" / "_build").mkdir(parents=True)
    (repo / ".agents" / "skills" / "demo").mkdir(parents=True)
    (repo / "src").mkdir(parents=True)
    (repo / "README.md").write_text("# Repo Readme\n\nUseful.", encoding="utf-8")
    (repo / "docs" / "guide.md").write_text("# Guide\n\nUseful docs.", encoding="utf-8")
    (repo / "docs" / "superpowers" / "plans" / "plan.md").write_text(
        "# Agent Plan",
        encoding="utf-8",
    )
    (repo / "book" / "_build" / "generated.md").write_text("# Generated", encoding="utf-8")
    (repo / ".agents" / "skills" / "demo" / "SKILL.md").write_text("# Skill", encoding="utf-8")
    (repo / "src" / "notes.md").write_text("# Source Adjacent", encoding="utf-8")
    (repo / "src" / "main.py").write_text("print('ignored')", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(
        AddMountRequest(
            path=str(repo),
            name="Repo",
            index_policy=MountIndexPolicy(profile="docs"),
        )
    )

    report = module.scan(mount.id, include_diagnostics=True)

    assert report["scanned"] == 2
    assert report["skipped"] == 5
    assert [item["relative_path"] for item in report["items"]] == [
        "README.md",
        "docs/guide.md",
    ]
    assert report["policy"]["profile"] == "docs"
    assert report["skip_reasons"]["excluded"] == 4
    assert report["skip_reasons"]["unsupported_extension"] == 1


def test_mount_scan_allows_custom_include_and_exclude_over_profile(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    repo = tmp_path / "repo"
    (repo / "content").mkdir(parents=True)
    (repo / "drafts").mkdir(parents=True)
    (repo / "content" / "post.md").write_text("# Post\n\nNeedle.", encoding="utf-8")
    (repo / "drafts" / "draft.md").write_text("# Draft\n\nNoisy.", encoding="utf-8")
    (repo / "README.md").write_text("# Readme\n\nNoisy.", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(
        AddMountRequest(
            path=str(repo),
            name="Site",
            index_policy=MountIndexPolicy(
                profile="site",
                include=["content/**/*.md", "README.md"],
                exclude=["README.md"],
            ),
        )
    )

    report = module.scan(mount.id)

    assert report["scanned"] == 1
    assert report["items"][0]["relative_path"] == "content/post.md"
    assert report["skip_reasons"]["not_included"] == 1
    assert report["skip_reasons"]["excluded"] == 1


def test_mount_update_policy_preserves_current_profile_when_only_excluding(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "drafts").mkdir(parents=True)
    (repo / "docs" / "guide.md").write_text("# Guide\n\nUseful docs.", encoding="utf-8")
    (repo / "drafts" / "draft.md").write_text("# Draft\n\nNoisy.", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(
        AddMountRequest(
            path=str(repo),
            name="Repo",
            index_policy=MountIndexPolicy(profile="docs"),
        )
    )

    updated = module.update_policy(mount.id, MountIndexPolicy(profile="", exclude=["drafts/**"]))
    report = module.scan(mount.id)

    assert updated.index_policy.profile == "docs"
    assert "docs/**" in updated.index_policy.include
    assert "drafts/**" in updated.index_policy.exclude
    assert report["policy"]["profile"] == "docs"
    assert report["scanned"] == 1
    assert report["skip_reasons"]["excluded"] == 1


def test_mount_scan_dry_run_reports_without_writing_indexes(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source-docs"
    source.mkdir()
    (source / "note.md").write_text("# Agent Notes\n\nMount search needle.", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(AddMountRequest(path=str(source), name="Source Docs"))

    report = module.scan(mount.id, dry_run=True)

    assert report["dry_run"] is True
    assert report["scanned"] == 1
    assert not (workspace.paths().mounts / "index.json").exists()
    assert not (workspace.paths().mounts / "okf" / mount.id / "index.md").exists()


def test_mount_okf_index_records_policy_for_agent_context(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "source-docs"
    source.mkdir()
    (source / "README.md").write_text("# Agent Notes\n\nMount search needle.", encoding="utf-8")
    module = MountsModule(workspace)
    mount = module.add(
        AddMountRequest(
            path=str(source),
            name="Source Docs",
            index_policy=MountIndexPolicy(profile="docs", exclude=["drafts/**"]),
        )
    )

    module.scan(mount.id)

    mount_index = MarkdownRepository().read_doc(
        workspace.paths().mounts / "okf" / mount.id / "index.md"
    )
    assert mount_index.frontmatter["index_policy"]["profile"] == "docs"
    assert "drafts/**" in mount_index.frontmatter["index_policy"]["exclude"]
    assert "- Profile: `docs`" in mount_index.body
    assert "`drafts/**`" in mount_index.body


def test_cli_mount_add_update_and_dry_run_scan_support_index_policy(tmp_path, capsys):
    workspace = Workspace.init(tmp_path / "workspace")
    source = tmp_path / "site"
    (source / "content").mkdir(parents=True)
    (source / "drafts").mkdir(parents=True)
    (source / "content" / "post.md").write_text("# Post\n\nNeedle.", encoding="utf-8")
    (source / "drafts" / "draft.md").write_text("# Draft\n\nNoisy.", encoding="utf-8")

    assert (
        main(
            [
                "mount",
                "--workspace",
                str(workspace.root),
                "add",
                str(source),
                "--name",
                "Site",
                "--profile",
                "site",
                "--json",
            ]
        )
        == 0
    )
    added = json.loads(capsys.readouterr().out)
    assert added["mount"]["index_policy"]["profile"] == "site"

    assert (
        main(
            [
                "mount",
                "--workspace",
                str(workspace.root),
                "update",
                "site",
                "--exclude",
                "drafts/**",
                "--json",
            ]
        )
        == 0
    )
    updated = json.loads(capsys.readouterr().out)
    assert updated["mount"]["index_policy"]["profile"] == "site"
    assert "drafts/**" in updated["mount"]["index_policy"]["exclude"]

    assert (
        main(
            [
                "mount",
                "--workspace",
                str(workspace.root),
                "scan",
                "site",
                "--dry-run",
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["dry_run"] is True
    assert report["scanned"] == 1
    assert report["skip_reasons"]["excluded"] == 1
    assert not (workspace.paths().mounts / "index.json").exists()


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
        "resource": "note.md",
        "tags": ["history"],
        "status": "active",
    }.items() <= rows[0].items()
    assert rows[0]["path"].startswith("mounts/archive#")
