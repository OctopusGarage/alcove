from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path

from alcove.external_index import ExternalIndexItemFactory, ExternalIndexStore
from alcove.home import AlcoveHome
from alcove.runtime import AlcoveRuntime
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AppleNotesImportRequest:
    export_dir: str
    tags: list[str] = field(default_factory=list)


class AppleNotesConnector:
    connector_id = "apple-notes"

    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.workspace = self.runtime.workspace
        self.home = self.runtime.home
        self.taxonomy = load_taxonomy(self.runtime.taxonomy_root)
        self.connector_dir = self.runtime.connectors_root / self.connector_id
        self.index_path = self.connector_dir / "index.json"
        self.index_store = ExternalIndexStore(self.runtime.connectors_root)

    def import_export(self, request: AppleNotesImportRequest) -> dict:
        export_dir = Path(request.export_dir).expanduser().resolve()
        notes_dir = export_dir / "notes"
        if not notes_dir.is_dir():
            raise FileNotFoundError(f"Apple Notes export notes directory not found: {notes_dir}")

        tags = self._normalize_tags(request.tags)
        items: list[dict] = []
        skipped = 0
        for note_json in sorted(notes_dir.glob("*/note.json"), key=lambda item: item.as_posix()):
            try:
                raw = json.loads(note_json.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                skipped += 1
                continue
            if not isinstance(raw, dict) or not raw.get("id"):
                skipped += 1
                continue
            items.append(self._item(raw, note_json, export_dir, tags))

        self._save_index(items, export_dir)
        return {
            "connector": self.connector_id,
            "export_dir": str(export_dir),
            "index_path": str(self.index_path),
            "scanned": len(items),
            "skipped": skipped,
            "items": items,
        }

    def _item(self, raw: dict, note_json: Path, export_dir: Path, tags: list[str]) -> dict:
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
            path=str(note_json),
            relative_path=note_json.relative_to(export_dir).as_posix(),
            text=plaintext,
            tags=tags,
            status="active",
            indexed_at=now_iso(),
            extra={
                "note_id": note_id,
                "created_at": str(raw.get("created_at") or ""),
                "updated_at": str(raw.get("updated_at") or ""),
            },
        )

    def _save_index(self, items: list[dict], export_dir: Path) -> None:
        self.connector_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "connector": self.connector_id,
            "export_dir": str(export_dir),
            "indexed_at": now_iso(),
            "items": items,
        }
        self.index_store.write_connector_index(self.connector_id, payload)

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)
