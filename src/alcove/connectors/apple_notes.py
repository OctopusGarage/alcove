from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import platform
from pathlib import Path
import shutil
import subprocess
from typing import Any, Protocol
from urllib.parse import quote

from alcove.connector_sources import ConnectorSourceRegistry, DEFAULT_TTL_HOURS
from alcove.errors import AlcoveError
from alcove.external_index import ExternalIndexItemFactory, ExternalIndexStore
from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace

from .okf_index import write_connector_okf_index, write_connector_okf_sources


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AppleNotesImportRequest:
    export_dir: str
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AppleNotesLocalImportRequest:
    export_dir: str = ""
    tags: list[str] = field(default_factory=list)
    source_id: str = "local"


class AppleNotesExporter(Protocol):
    def export_all(self, output_dir: Path) -> dict[str, Any]: ...


class LocalAppleNotesExporter:
    def export_all(self, output_dir: Path) -> dict[str, Any]:
        if platform.system() != "Darwin":
            raise AlcoveError("Apple Notes local export requires macOS.")
        response = self._run_jxa()
        if not response.get("ok"):
            raise AlcoveError(str(response.get("details") or response.get("error") or response))
        data = response.get("data") if isinstance(response.get("data"), dict) else {}
        notes = data.get("notes") if isinstance(data.get("notes"), list) else []
        return write_apple_notes_export_tree(
            [note for note in notes if isinstance(note, dict)],
            output_dir,
        )

    def _run_jxa(self) -> dict[str, Any]:
        script = """
function ok(data) {
  return { ok: true, action: "export-all-notes", mode: "execute", data };
}

function fail(error, details) {
  return { ok: false, action: "export-all-notes", error, details };
}

function scanFolderNotes(folder, accountName, parentPath, out) {
  const folderPath = parentPath ? `${parentPath}/${folder.name()}` : `${accountName}/${folder.name()}`;
  for (const note of folder.notes()) {
    out.push({ note, folderPath });
  }
  for (const child of folder.folders()) {
    scanFolderNotes(child, accountName, folderPath, out);
  }
}

function allNotes(app) {
  const out = [];
  for (const account of app.accounts()) {
    const accountName = account.name();
    for (const folder of account.folders()) {
      scanFolderNotes(folder, accountName, "", out);
    }
  }
  return out;
}

function isDeletedFolderPath(folderPath) {
  return String(folderPath || '').split('/').map((part) => part.trim()).includes('Recently Deleted');
}

function fullNoteRecord(note, folderPath) {
  const account = folderPath ? folderPath.split('/')[0] : null;
  return {
    id: note.id(),
    title: note.name(),
    account,
    folder_path: folderPath,
    created_at: note.creationDate(),
    updated_at: note.modificationDate(),
    plaintext: String(note.plaintext() || ''),
    body_html: String(note.body() || ''),
  };
}

function main() {
  try {
    const app = Application('Notes');
    const notes = allNotes(app)
      .filter((row) => !isDeletedFolderPath(row.folderPath))
      .map((row) => fullNoteRecord(row.note, row.folderPath));
    return ok({ notes });
  } catch (error) {
    return fail('NOTES_AUTOMATION_ERROR', String(error.message || error));
  }
}

JSON.stringify(main());
"""
        result = subprocess.run(  # noqa: S603 - Fixed osascript executable and generated JXA.
            [self._osascript_path(), "-l", "JavaScript"],
            input=script,
            text=True,
            capture_output=True,
            check=False,
        )
        combined = (result.stdout or "").strip() or (result.stderr or "").strip()
        if result.returncode != 0:
            raise AlcoveError(combined or "Apple Notes automation failed.")
        if not combined:
            raise AlcoveError("Apple Notes automation returned no output.")
        try:
            data = json.loads(combined)
        except json.JSONDecodeError as exc:
            raise AlcoveError("Apple Notes automation returned invalid JSON.") from exc
        return data if isinstance(data, dict) else {}

    def _osascript_path(self) -> str:
        path = shutil.which("osascript")
        if not path:
            raise AlcoveError("Apple Notes local export requires osascript.")
        return path


class AppleNotesConnector:
    connector_id = "apple-notes"

    def __init__(
        self,
        workspace: Workspace | None = None,
        home: AlcoveHome | None = None,
        exporter: AppleNotesExporter | None = None,
    ) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.workspace = self.runtime.workspace
        self.home = self.runtime.home
        self.taxonomy = load_taxonomy(self.runtime.taxonomy_root)
        self.connector_dir = self.runtime.connectors_root / self.connector_id
        self.index_path = self.connector_dir / "index.json"
        self.index_store = ExternalIndexStore(self.runtime.connectors_root)
        self.exporter = exporter or LocalAppleNotesExporter()

    def import_export(self, request: AppleNotesImportRequest) -> dict:
        export_dir = Path(request.export_dir).expanduser().resolve()
        notes_dir = export_dir / "notes"
        if not notes_dir.is_dir():
            raise FileNotFoundError(f"Apple Notes export notes directory not found: {notes_dir}")

        tags = self._normalize_tags(request.tags)
        items: list[dict] = []
        skipped = 0
        reused = 0
        previous_items = self._previous_items()
        for note_json in sorted(notes_dir.glob("*/note.json"), key=lambda item: item.as_posix()):
            stat = note_json.stat()
            relative_path = note_json.relative_to(export_dir).as_posix()
            previous = previous_items.get(relative_path)
            if self._unchanged(previous, stat.st_size, stat.st_mtime_ns, tags):
                items.append(previous)
                reused += 1
                continue
            try:
                raw = json.loads(note_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(raw, dict) or not raw.get("id"):
                skipped += 1
                continue
            items.append(self._item(raw, note_json, export_dir, tags, stat=stat))

        self._save_index(items, export_dir)
        return {
            "connector": self.connector_id,
            "export_dir": compact_user_path(export_dir),
            "index_path": compact_user_path(self.index_path),
            "scanned": len(items),
            "skipped": skipped,
            "reused": reused,
            "items": items,
        }

    def import_local(self, request: AppleNotesLocalImportRequest) -> dict[str, Any]:
        export_dir = self._export_dir(request.export_dir)
        summary = self.exporter.export_all(export_dir)
        report = self.import_export(
            AppleNotesImportRequest(export_dir=str(export_dir), tags=request.tags)
        )
        tags = self._normalize_tags(request.tags)
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_apple_notes(
            source_id=request.source_id or "local",
            source="Notes.app",
            tags=tags,
            export_dir=export_dir,
            index_path=self.index_path,
            item_count=int(summary.get("note_count") or report["scanned"]),
        )
        self._write_okf_sources_from_registry()
        return {
            **report,
            "status": "imported",
            "source": "Notes.app",
            "source_id": request.source_id or "local",
            "exported": int(summary.get("note_count") or report["scanned"]),
            "summary": self._summary_counts(summary),
            "diff": self._summary_diff(summary),
        }

    def refresh_sources(
        self,
        *,
        stale_only: bool = False,
        source_id: str = "",
        now: str | None = None,
        default_ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> dict[str, Any]:
        registry = ConnectorSourceRegistry(self.workspace, home=self.home)
        sources = registry.list(self.connector_id)
        if source_id:
            sources = [source for source in sources if str(source.get("id") or "") == source_id]
        if stale_only:
            stale_ids = {
                str(source.get("id") or "")
                for source in registry.stale_sources(
                    connector=self.connector_id,
                    now=now,
                    default_ttl_hours=default_ttl_hours,
                )
            }
            sources = [source for source in sources if str(source.get("id") or "") in stale_ids]

        reports = []
        for source in sources:
            try:
                report = self._refresh_source(source)
            except Exception as exc:
                report = self._refresh_error(source, exc)
            reports.append(report)
        return {
            "connector": self.connector_id,
            "refreshed": sum(1 for report in reports if report["status"] == "refreshed"),
            "skipped": 0,
            "reused": sum(int(report.get("reused") or 0) for report in reports),
            "errors": sum(1 for report in reports if report["status"] == "error"),
            "sources": reports,
        }

    def _refresh_source(self, source: dict[str, Any]) -> dict[str, Any]:
        source_id = str(source.get("id") or "local")
        export_dir = self._export_dir(str(source.get("export_dir") or ""))
        tags = [str(tag) for tag in source.get("tags") or []]
        summary = self.exporter.export_all(export_dir)
        report = self.import_export(AppleNotesImportRequest(export_dir=str(export_dir), tags=tags))
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_apple_notes(
            source_id=source_id,
            source=str(source.get("source") or "Notes.app"),
            tags=self._normalize_tags(tags),
            export_dir=export_dir,
            index_path=self.index_path,
            item_count=int(summary.get("note_count") or report["scanned"]),
        )
        self._write_okf_sources_from_registry()
        return {
            "connector": self.connector_id,
            "id": source_id,
            "status": "refreshed",
            "exported": int(summary.get("note_count") or report["scanned"]),
            "scanned": report["scanned"],
            "skipped": report["skipped"],
            "reused": report.get("reused", 0),
            "export_dir": compact_user_path(export_dir),
            "index_path": compact_user_path(self.index_path),
            "summary": self._summary_counts(summary),
            "diff": self._summary_diff(summary),
            "error": "",
        }

    def _refresh_error(self, source: dict[str, Any], exc: Exception) -> dict[str, Any]:
        source_id = str(source.get("id") or "local")
        export_dir = self._export_dir(str(source.get("export_dir") or ""))
        refresh = source.get("refresh") if isinstance(source.get("refresh"), dict) else {}
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_apple_notes(
            source_id=source_id,
            source=str(source.get("source") or "Notes.app"),
            tags=[str(tag) for tag in source.get("tags") or []],
            export_dir=export_dir,
            index_path=self.index_path,
            item_count=_int_value(refresh.get("item_count"), 0),
            changed_at=str(refresh.get("last_changed_at") or ""),
            status="error",
            error=str(exc),
        )
        self._write_okf_sources_from_registry()
        return {
            "connector": self.connector_id,
            "id": source_id,
            "status": "error",
            "exported": 0,
            "scanned": 0,
            "skipped": 0,
            "reused": 0,
            "export_dir": compact_user_path(export_dir),
            "index_path": compact_user_path(self.index_path),
            "summary": {"added_count": 0, "updated_count": 0, "removed_count": 0},
            "diff": {"added": [], "removed": [], "updated": [], "unchanged": 0},
            "error": str(exc),
        }

    def _item(
        self,
        raw: dict,
        note_json: Path,
        export_dir: Path,
        tags: list[str],
        *,
        stat: Any,
    ) -> dict:
        note_id = str(raw.get("id") or "")
        title = str(raw.get("title") or "Untitled")
        plaintext = str(raw.get("plaintext") or "")
        return ExternalIndexItemFactory.connector_item(
            connector_id=self.connector_id,
            connector_name="Apple Notes",
            item_type="Apple Note",
            title=title,
            account=str(raw.get("account") or ""),
            folder_path=str(raw.get("folder_path") or ""),
            path=compact_user_path(note_json),
            relative_path=note_json.relative_to(export_dir).as_posix(),
            text=plaintext,
            tags=tags,
            status="active",
            indexed_at=now_iso(),
            extra={
                "note_id": note_id,
                "created_at": str(raw.get("created_at") or ""),
                "updated_at": str(raw.get("updated_at") or ""),
                "file_size": stat.st_size,
                "file_mtime_ns": stat.st_mtime_ns,
            },
        )

    def _save_index(self, items: list[dict], export_dir: Path) -> None:
        self.connector_dir.mkdir(parents=True, exist_ok=True)
        indexed_at = now_iso()
        payload = {
            "schema_version": 1,
            "connector": self.connector_id,
            "export_dir": compact_user_path(export_dir),
            "indexed_at": indexed_at,
            "items": items,
        }
        self.index_store.write_connector_index(self.connector_id, payload)
        write_connector_okf_index(
            connector_dir=self.connector_dir,
            connector_id=self.connector_id,
            connector_name="Apple Notes",
            items=items,
            generated_at=indexed_at,
        )

    def _write_okf_sources_from_registry(self) -> None:
        sources = ConnectorSourceRegistry(self.workspace, home=self.home).list(self.connector_id)
        write_connector_okf_sources(
            connector_dir=self.connector_dir,
            connector_id=self.connector_id,
            connector_name="Apple Notes",
            sources=sources,
            generated_at=now_iso(),
        )

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _previous_items(self) -> dict[str, dict]:
        payload = self.index_store.read_file(self.index_path)
        if payload is None or not isinstance(payload.get("items"), list):
            return {}
        return {
            str(item.get("relative_path") or ""): item
            for item in payload["items"]
            if isinstance(item, dict) and item.get("relative_path")
        }

    def _unchanged(
        self,
        item: dict | None,
        file_size: int,
        file_mtime_ns: int,
        tags: list[str],
    ) -> bool:
        if item is None:
            return False
        return (
            item.get("file_size") == file_size
            and item.get("file_mtime_ns") == file_mtime_ns
            and item.get("tags") == tags
        )

    def _export_dir(self, export_dir: str) -> Path:
        if export_dir:
            return Path(export_dir).expanduser().resolve()
        return (self.connector_dir / "exports" / "full").resolve()

    def _summary_counts(self, summary: dict[str, Any]) -> dict[str, int]:
        return {
            "added_count": _int_value(summary.get("added_count"), 0),
            "updated_count": _int_value(summary.get("updated_count"), 0),
            "removed_count": _int_value(summary.get("removed_count"), 0),
        }

    def _summary_diff(self, summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "added": _string_list(summary.get("added_ids")),
            "removed": _string_list(summary.get("removed_ids") or summary.get("removed_dir_names")),
            "updated": _string_list(summary.get("updated_ids")),
            "unchanged": max(
                _int_value(summary.get("note_count"), 0)
                - _int_value(summary.get("added_count"), 0)
                - _int_value(summary.get("updated_count"), 0),
                0,
            ),
        }


def write_apple_notes_export_tree(notes: list[dict[str, Any]], output_dir: Path | str) -> dict:
    root = Path(output_dir).expanduser().resolve()
    notes_root = root / "notes"
    notes_root.mkdir(parents=True, exist_ok=True)

    canonical_notes = [_canonical_note_record(note) for note in notes]
    canonical_notes.sort(key=lambda item: str(item["id"]))
    active_dir_names = {_note_dir_name(str(note["id"])) for note in canonical_notes}
    previous_json_by_dir: dict[str, str] = {}
    previous_id_by_dir: dict[str, str] = {}
    for child in sorted(notes_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        note_json_path = child / "note.json"
        if not note_json_path.exists():
            continue
        previous_json = note_json_path.read_text(encoding="utf-8")
        previous_json_by_dir[child.name] = previous_json
        try:
            previous_note = json.loads(previous_json)
        except json.JSONDecodeError:
            continue
        if isinstance(previous_note, dict):
            previous_id_by_dir[child.name] = str(previous_note.get("id") or child.name)

    added_ids: list[str] = []
    updated_ids: list[str] = []
    for note in canonical_notes:
        note_id = str(note["id"])
        dir_name = _note_dir_name(note_id)
        note_dir = notes_root / dir_name
        note_dir.mkdir(parents=True, exist_ok=True)
        note_json_content = json.dumps(note, ensure_ascii=False, indent=2) + "\n"
        previous_json = previous_json_by_dir.get(dir_name)
        if previous_json is None:
            added_ids.append(note_id)
            (note_dir / "note.json").write_text(note_json_content, encoding="utf-8")
            (note_dir / "note.md").write_text(_render_note_markdown(note), encoding="utf-8")
        elif previous_json != note_json_content:
            updated_ids.append(note_id)
            (note_dir / "note.json").write_text(note_json_content, encoding="utf-8")
            (note_dir / "note.md").write_text(_render_note_markdown(note), encoding="utf-8")

    removed_ids: list[str] = []
    for child in sorted(notes_root.iterdir(), key=lambda item: item.name):
        if child.is_dir() and child.name not in active_dir_names:
            removed_ids.append(previous_id_by_dir.get(child.name, child.name))
            shutil.rmtree(child)

    manifest = {
        "schema_version": 1,
        "note_count": len(canonical_notes),
        "note_ids": [str(note["id"]) for note in canonical_notes],
        "notes": [
            {
                "id": str(note["id"]),
                "title": str(note["title"]),
                "account": str(note["account"]),
                "folder_path": str(note["folder_path"]),
                "updated_at": str(note["updated_at"]),
                "dir_name": _note_dir_name(str(note["id"])),
            }
            for note in canonical_notes
        ],
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = {
        "schema_version": 1,
        "note_count": len(canonical_notes),
        "added_count": len(added_ids),
        "updated_count": len(updated_ids),
        "removed_count": len(removed_ids),
        "added_ids": added_ids,
        "updated_ids": updated_ids,
        "removed_ids": removed_ids,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def _canonical_note_record(note: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(note.get("id") or ""),
        "title": str(note.get("title") or "Untitled"),
        "account": str(note.get("account") or ""),
        "folder_path": str(note.get("folder_path") or ""),
        "created_at": str(note.get("created_at") or ""),
        "updated_at": str(note.get("updated_at") or ""),
        "plaintext": str(note.get("plaintext") or ""),
        "body_html": str(note.get("body_html") or ""),
    }


def _note_dir_name(note_id: str) -> str:
    return quote(note_id, safe="")


def _render_note_markdown(note: dict[str, Any]) -> str:
    title = str(note.get("title") or "Untitled")
    body = str(note.get("plaintext") or "").rstrip()
    lines = [
        "---",
        f'id: "{_yaml_escape(str(note["id"]))}"',
        f'title: "{_yaml_escape(title)}"',
        f'account: "{_yaml_escape(str(note.get("account") or ""))}"',
        f'folder_path: "{_yaml_escape(str(note.get("folder_path") or ""))}"',
        f'created_at: "{_yaml_escape(str(note.get("created_at") or ""))}"',
        f'updated_at: "{_yaml_escape(str(note.get("updated_at") or ""))}"',
        "generated_from: note.json",
        "---",
        "",
        f"# {title}",
        "",
    ]
    if body:
        lines.extend([body, ""])
    return "\n".join(lines)


def _yaml_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _int_value(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
