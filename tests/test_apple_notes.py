from __future__ import annotations

import json
from pathlib import Path

from alcove.connectors.apple_notes import AppleNotesConnector, AppleNotesImportRequest
from alcove.search import SearchModule, SearchRequest
from alcove.workspace import Workspace


def test_apple_notes_import_indexes_stable_export_notes(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_dir = _write_export(
        tmp_path / "apple-notes-export",
        [
            {
                "id": "x-coredata://note-1",
                "title": "Knowledge Garden",
                "account": "iCloud",
                "folder_path": "iCloud/Ideas",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Use stable exports as an external source index.",
                "body_html": "<div>Use stable exports as an external source index.</div>",
            }
        ],
    )

    result = AppleNotesConnector(workspace).import_export(
        AppleNotesImportRequest(export_dir=str(export_dir), tags=["apple-notes"])
    )

    assert result["scanned"] == 1
    assert result["index_path"].endswith(".alcove/connectors/apple-notes/index.json")
    assert result["items"][0]["note_id"] == "x-coredata://note-1"
    assert result["items"][0]["title"] == "Knowledge Garden"
    assert result["items"][0]["folder_path"] == "iCloud/Ideas"
    assert result["items"][0]["tags"] == ["apple-notes"]


def test_search_includes_imported_apple_notes(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_dir = _write_export(
        tmp_path / "apple-notes-export",
        [
            {
                "id": "x-coredata://note-2",
                "title": "Pinned Context",
                "account": "iCloud",
                "folder_path": "iCloud/Reference",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Apple Notes search needle for Alcove.",
                "body_html": "<div>Apple Notes search needle for Alcove.</div>",
            }
        ],
    )
    AppleNotesConnector(workspace).import_export(
        AppleNotesImportRequest(export_dir=str(export_dir), tags=["reference"])
    )

    rows = SearchModule(workspace).search(SearchRequest(query="search needle"))

    assert len(rows) == 1
    assert {
        "root": "connectors",
        "type": "Apple Note",
        "title": "Pinned Context",
        "topic": "iCloud/Reference",
        "tags": ["reference"],
        "status": "active",
    }.items() <= rows[0].items()
    assert rows[0]["resource"].endswith("notes/x-coredata%3A%2F%2Fnote-2/note.json")


def _write_export(root: Path, notes: list[dict]) -> Path:
    notes_root = root / "notes"
    notes_root.mkdir(parents=True)
    manifest_notes = []
    for note in notes:
        dir_name = _encoded_note_id(note["id"])
        note_dir = notes_root / dir_name
        note_dir.mkdir()
        (note_dir / "note.json").write_text(
            json.dumps(note, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        (note_dir / "note.md").write_text(
            f"# {note['title']}\n\n{note['plaintext']}\n",
            encoding="utf-8",
        )
        manifest_notes.append(
            {
                "id": note["id"],
                "title": note["title"],
                "account": note["account"],
                "folder_path": note["folder_path"],
                "updated_at": note["updated_at"],
                "dir_name": dir_name,
            }
        )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "note_count": len(notes),
                "note_ids": [note["id"] for note in notes],
                "notes": manifest_notes,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return root


def _encoded_note_id(note_id: str) -> str:
    from urllib.parse import quote

    return quote(note_id, safe="")
