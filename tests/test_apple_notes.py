from __future__ import annotations

import json
from pathlib import Path

from alcove.connector_sources import ConnectorSourceRegistry
from alcove.connectors.fetch import ConnectorFetchModule
from alcove.connectors.apple_notes import (
    AppleNotesConnector,
    AppleNotesImportRequest,
    AppleNotesLocalImportRequest,
    write_apple_notes_export_tree,
)
from alcove.markdown import MarkdownRepository
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
        "resource": None,
        "tags": ["reference"],
        "status": "active",
    }.items() <= rows[0].items()
    assert rows[0]["path"] == "connectors/apple-notes#notes/x-coredata%3A%2F%2Fnote-2/note.json"
    assert rows[0]["display_id"] == "apple-notes/pinned-context"
    assert rows[0]["display_label"] == "Pinned Context"
    assert (
        rows[0]["fetch_ref"] == "connectors/apple-notes#notes/x-coredata%3A%2F%2Fnote-2/note.json"
    )
    assert (
        rows[0]["fetch_command"]
        == "alcove connector fetch connectors/apple-notes#notes/x-coredata%3A%2F%2Fnote-2/note.json --json"
    )
    assert rows[0]["information_quality"]["status"] == "ok"


def test_apple_notes_search_marks_identifier_heavy_notes_low_information(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_dir = _write_export(
        tmp_path / "apple-notes-export",
        [
            {
                "id": "x-coredata://weak-note",
                "title": "微信公众号",
                "account": "iCloud",
                "folder_path": "iCloud/Reference",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "微信公众号\nwxda7a1cb0644cb4cd\n1d21951cef2c3d0be0721de131166bec\n",
                "body_html": "<div>微信公众号</div>",
            }
        ],
    )
    AppleNotesConnector(workspace).import_export(
        AppleNotesImportRequest(export_dir=str(export_dir), tags=["reference"])
    )

    rows = SearchModule(workspace).search(SearchRequest(query="微信公众号"))

    assert len(rows) == 1
    assert rows[0]["information_quality"]["status"] == "low-information"
    assert "mostly identifiers" in rows[0]["information_quality"]["reason"]


def test_apple_notes_fetch_accepts_unique_display_alias(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_dir = _write_export(
        tmp_path / "apple-notes-export",
        [
            {
                "id": "x-coredata://note-alias",
                "title": "Pinned Context",
                "account": "iCloud",
                "folder_path": "iCloud/Reference",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Apple Notes alias fetch needle.",
                "body_html": "<div>Apple Notes alias fetch needle.</div>",
            }
        ],
    )
    AppleNotesConnector(workspace).import_export(
        AppleNotesImportRequest(export_dir=str(export_dir), tags=["reference"])
    )

    fetched = ConnectorFetchModule(workspace).fetch("apple-notes/pinned-context")

    assert fetched["status"] == "fetched"
    assert fetched["connector"] == "apple-notes"
    assert fetched["display_id"] == "apple-notes/pinned-context"
    assert fetched["display_label"] == "Pinned Context"
    assert (
        fetched["fetch_ref"]
        == "connectors/apple-notes#notes/x-coredata%3A%2F%2Fnote-alias/note.json"
    )
    assert fetched["item"]["title"] == "Pinned Context"
    assert fetched["detail"]["plaintext"] == "Apple Notes alias fetch needle."
    assert "path" not in fetched["item"]
    assert "path" not in fetched["detail"]


def test_apple_notes_fetch_rejects_ambiguous_display_alias(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_dir = _write_export(
        tmp_path / "apple-notes-export",
        [
            {
                "id": "x-coredata://note-one",
                "title": "Duplicate Title",
                "account": "iCloud",
                "folder_path": "iCloud/Reference",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "First note.",
            },
            {
                "id": "x-coredata://note-two",
                "title": "Duplicate Title",
                "account": "iCloud",
                "folder_path": "iCloud/Ideas",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:30:00Z",
                "plaintext": "Second note.",
            },
        ],
    )
    AppleNotesConnector(workspace).import_export(
        AppleNotesImportRequest(export_dir=str(export_dir))
    )

    try:
        ConnectorFetchModule(workspace).fetch("apple-notes/duplicate-title")
    except FileExistsError as exc:
        assert "ambiguous" in str(exc)
        assert "connectors/<connector-id>#<relative-path>" in str(exc)
    else:
        raise AssertionError("Expected duplicate Apple Notes display alias to be rejected")


def test_search_redacts_secret_like_apple_notes_by_default(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_dir = _write_export(
        tmp_path / "apple-notes-export",
        [
            {
                "id": "x-coredata://note-secret",
                "title": "apikey",
                "account": "iCloud",
                "folder_path": "iCloud/Sensitive",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "apikey = sk-real-looking-secret-1234567890\npassword: open-sesame",
                "body_html": "<div>secret</div>",
            }
        ],
    )
    AppleNotesConnector(workspace).import_export(
        AppleNotesImportRequest(export_dir=str(export_dir), tags=["apple-notes"])
    )

    rows = SearchModule(workspace).search(SearchRequest(query="apikey"))

    assert rows[0]["title"] == "apikey"
    assert rows[0]["redacted"] is True
    assert "sk-real-looking-secret" not in rows[0]["notes"]
    assert "open-sesame" not in rows[0]["notes"]
    assert rows[0]["notes"] == "[redacted: secret-like connector content]"


def test_apple_notes_import_reuses_unchanged_note_index_items(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_dir = _write_export(
        tmp_path / "apple-notes-export",
        [
            {
                "id": "x-coredata://note-reuse",
                "title": "Reusable Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Reference",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Reuse unchanged note index row.",
                "body_html": "<div>Reuse unchanged note index row.</div>",
            }
        ],
    )
    connector = AppleNotesConnector(workspace)
    connector.import_export(AppleNotesImportRequest(export_dir=str(export_dir), tags=["apple"]))
    index_path = workspace.paths().state / "connectors" / "apple-notes" / "index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    payload["items"][0]["indexed_at"] = "2026-01-01T00:00:00+00:00"
    index_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    result = connector.import_export(
        AppleNotesImportRequest(export_dir=str(export_dir), tags=["apple"])
    )

    assert result["reused"] == 1
    assert result["items"][0]["indexed_at"] == "2026-01-01T00:00:00+00:00"
    assert result["items"][0]["file_size"] > 0
    assert result["items"][0]["file_mtime_ns"] > 0


def test_apple_notes_import_writes_okf_markdown_connector_index(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    export_dir = _write_export(
        tmp_path / "apple-notes-export",
        [
            {
                "id": "x-coredata://note-okf",
                "title": "OKF Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Reference",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Apple Notes OKF connector needle.",
                "body_html": "<div>Apple Notes OKF connector needle.</div>",
            }
        ],
    )

    AppleNotesConnector(workspace).import_export(
        AppleNotesImportRequest(export_dir=str(export_dir), tags=["apple-notes"])
    )

    repo = MarkdownRepository()
    okf_root = workspace.paths().state / "connectors" / "apple-notes" / "okf"
    index = repo.read_doc(okf_root / "index.md")
    item_paths = sorted((okf_root / "items").glob("*.md"))
    item = repo.read_doc(item_paths[0])
    assert index.frontmatter["type"] == "Connector Index"
    assert index.frontmatter["schema"] == "okf/connector-index/v1"
    assert index.frontmatter["connector_id"] == "apple-notes"
    assert index.frontmatter["item_count"] == 1
    assert item.frontmatter["type"] == "Apple Note"
    assert item.frontmatter["schema"] == "okf/connector-item/v1"
    assert item.frontmatter["connector_id"] == "apple-notes"
    assert item.frontmatter["relative_path"].endswith("/note.json")
    assert "Apple Notes OKF connector needle." in item.body


def test_apple_notes_import_local_exports_indexes_and_registers_source(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    exporter = FakeAppleNotesExporter(
        [
            {
                "id": "x-coredata://note-local",
                "title": "Local Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Ideas",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Local Apple Notes connector needle.",
                "body_html": "<div>Local Apple Notes connector needle.</div>",
            }
        ]
    )

    result = AppleNotesConnector(workspace, exporter=exporter).import_local(
        AppleNotesLocalImportRequest(tags=["apple-notes"])
    )

    assert result["status"] == "imported"
    assert result["scanned"] == 1
    assert result["exported"] == 1
    assert result["item_count"] == 1
    assert result["summary"]["indexed_count"] == 1
    assert result["summary"]["exported_count"] == 1
    assert result["export_dir"].endswith(".alcove/connectors/apple-notes/exports/full")
    assert result["summary"] == {
        "added_count": 1,
        "updated_count": 0,
        "removed_count": 0,
        "exported_count": 1,
        "indexed_count": 1,
        "skipped_count": 0,
        "reused_count": 0,
    }
    rows = SearchModule(workspace).search(SearchRequest(query="connector needle"))
    assert rows[0]["title"] == "Local Apple Note"
    source = ConnectorSourceRegistry(workspace=workspace).get("apple-notes", "local")
    assert source["connector"] == "apple-notes"
    assert source["source"] == "Notes.app"
    assert source["refresh"]["status"] == "fresh"
    assert source["refresh"]["item_count"] == 1
    source_doc = MarkdownRepository().read_doc(
        workspace.paths().state / "connectors" / "apple-notes" / "okf" / "sources" / "local.md"
    )
    assert source_doc.frontmatter["type"] == "Connector Source"
    assert source_doc.frontmatter["schema"] == "okf/connector-source/v1"
    assert source_doc.frontmatter["source_id"] == "local"
    assert source_doc.frontmatter["item_count"] == 1


def test_apple_notes_refresh_registered_source_updates_export_and_index(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    exporter = FakeAppleNotesExporter(
        [
            {
                "id": "x-coredata://note-local",
                "title": "Local Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Ideas",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Before refresh.",
                "body_html": "<div>Before refresh.</div>",
            }
        ]
    )
    connector = AppleNotesConnector(workspace, exporter=exporter)
    connector.import_local(AppleNotesLocalImportRequest(tags=["apple-notes"]))
    exporter.notes = [
        {
            "id": "x-coredata://note-local",
            "title": "Local Apple Note",
            "account": "iCloud",
            "folder_path": "iCloud/Ideas",
            "created_at": "2026-07-07T08:00:00Z",
            "updated_at": "2026-07-09T09:00:00Z",
            "plaintext": "After refresh needle.",
            "body_html": "<div>After refresh needle.</div>",
        },
        {
            "id": "x-coredata://note-added",
            "title": "Added Apple Note",
            "account": "iCloud",
            "folder_path": "iCloud/Ideas",
            "created_at": "2026-07-09T08:00:00Z",
            "updated_at": "2026-07-09T09:00:00Z",
            "plaintext": "New note.",
            "body_html": "<div>New note.</div>",
        },
    ]

    result = connector.refresh_sources(source_id="local")

    assert result["refreshed"] == 1
    assert result["sources"][0]["id"] == "local"
    assert result["sources"][0]["diff"] == {
        "added": ["x-coredata://note-added"],
        "removed": [],
        "updated": ["x-coredata://note-local"],
        "unchanged": 0,
    }
    rows = SearchModule(workspace).search(SearchRequest(query="After refresh"))
    assert rows[0]["title"] == "Local Apple Note"


def test_apple_notes_refresh_removes_deleted_notes_from_export_and_index(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    exporter = FakeAppleNotesExporter(
        [
            {
                "id": "x-coredata://note-kept",
                "title": "Kept Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Ideas",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Kept note.",
                "body_html": "<div>Kept note.</div>",
            },
            {
                "id": "x-coredata://note-deleted",
                "title": "Deleted Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Ideas",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Deleted note needle.",
                "body_html": "<div>Deleted note needle.</div>",
            },
        ]
    )
    connector = AppleNotesConnector(workspace, exporter=exporter)
    connector.import_local(AppleNotesLocalImportRequest(tags=["apple-notes"]))
    export_dir = workspace.paths().state / "connectors" / "apple-notes" / "exports" / "full"
    deleted_dir = export_dir / "notes" / _encoded_note_id("x-coredata://note-deleted")
    assert deleted_dir.exists()
    exporter.notes = [
        {
            "id": "x-coredata://note-kept",
            "title": "Kept Apple Note",
            "account": "iCloud",
            "folder_path": "iCloud/Ideas",
            "created_at": "2026-07-07T08:00:00Z",
            "updated_at": "2026-07-08T09:00:00Z",
            "plaintext": "Kept note.",
            "body_html": "<div>Kept note.</div>",
        }
    ]

    result = connector.refresh_sources(source_id="local")

    assert result["sources"][0]["summary"]["removed_count"] == 1
    assert result["sources"][0]["diff"]["removed"] == ["x-coredata://note-deleted"]
    assert not deleted_dir.exists()
    index_path = workspace.paths().state / "connectors" / "apple-notes" / "index.json"
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    assert [item["note_id"] for item in payload["items"]] == ["x-coredata://note-kept"]
    assert SearchModule(workspace).search(SearchRequest(query="Deleted note needle")) == []
    okf_item_dir = workspace.paths().state / "connectors" / "apple-notes" / "okf" / "items"
    okf_items = [
        MarkdownRepository().read_doc(path)
        for path in sorted(okf_item_dir.glob("*.md"), key=lambda item: item.as_posix())
    ]
    assert [item.frontmatter["title"] for item in okf_items] == ["Kept Apple Note"]


def test_apple_notes_refresh_reports_reused_unchanged_index_items(tmp_path):
    workspace = Workspace.init(tmp_path / "workspace")
    exporter = FakeAppleNotesExporter(
        [
            {
                "id": "x-coredata://note-local",
                "title": "Local Apple Note",
                "account": "iCloud",
                "folder_path": "iCloud/Ideas",
                "created_at": "2026-07-07T08:00:00Z",
                "updated_at": "2026-07-08T09:00:00Z",
                "plaintext": "Stable note.",
                "body_html": "<div>Stable note.</div>",
            }
        ]
    )
    connector = AppleNotesConnector(workspace, exporter=exporter)
    connector.import_local(AppleNotesLocalImportRequest(tags=["apple-notes"]))

    result = connector.refresh_sources(source_id="local")

    assert result["sources"][0]["reused"] == 1


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


class FakeAppleNotesExporter:
    def __init__(self, notes: list[dict]) -> None:
        self.notes = notes

    def export_all(self, output_dir: Path) -> dict:
        return write_apple_notes_export_tree(self.notes, output_dir)
