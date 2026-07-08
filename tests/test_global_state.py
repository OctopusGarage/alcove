from __future__ import annotations

import json

from alcove.connectors.apple_notes import AppleNotesConnector, AppleNotesImportRequest
from alcove.home import AlcoveHome
from alcove.markdown import MarkdownRepository
from alcove.mounts import AddMountRequest, MountsModule
from alcove.pins import AddPinRequest, PinsModule
from alcove.tasks import AddTaskRequest, TasksModule


def test_pins_use_alcove_home_not_managed_kb_workspace(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    kb_root = tmp_path / "kb"
    kb_root.mkdir()

    result = PinsModule(home=home).add(AddPinRequest(title="Global Pin"))

    assert result.path == home.paths().pins / "global-pin.md"
    assert not (kb_root / "pins" / "global-pin.md").exists()
    assert MarkdownRepository().read_doc(result.path).frontmatter["type"] == "Pin"


def test_tasks_use_alcove_home_not_managed_kb_workspace(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")

    task = TasksModule(home=home).task_add(AddTaskRequest(title="Global Task"))

    assert task.id == "global-task"
    assert (home.paths().tasks / "tasks.json").is_file()


def test_mounts_use_global_index_per_mount(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    source = tmp_path / "source"
    source.mkdir()
    (source / "note.md").write_text("# Mounted Note\n\nneedle", encoding="utf-8")
    module = MountsModule(home=home)

    mount = module.add(AddMountRequest(path=str(source), name="Source Docs"))
    report = module.scan(mount.id)

    assert (home.paths().mounts / "mounts.json").is_file()
    assert (home.paths().mount_indexes / "source-docs.json").is_file()
    assert report["scanned"] == 1


def test_connectors_use_global_home_index(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    export_dir = tmp_path / "apple-export"
    note_dir = export_dir / "notes" / "note-1"
    note_dir.mkdir(parents=True)
    (note_dir / "note.json").write_text(
        json.dumps(
            {
                "id": "note-1",
                "title": "Global Apple Note",
                "plaintext": "connector needle",
            }
        ),
        encoding="utf-8",
    )

    result = AppleNotesConnector(home=home).import_export(
        AppleNotesImportRequest(export_dir=str(export_dir))
    )

    assert result["index_path"] == str(home.paths().connectors / "apple-notes" / "index.json")
