from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alcove.external_index import ExternalIndexStore, ExternalItemReference
from alcove.home import AlcoveHome
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


class ConnectorFetchModule:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.store = ExternalIndexStore(self.runtime.connectors_root)

    def fetch(self, item_path: str) -> dict[str, Any]:
        ref = ExternalItemReference.parse_connector(item_path)
        item = self.store.find_item(ref)
        if item is None:
            raise FileNotFoundError(f"Connector item not found: {item_path}")
        return {
            "status": "fetched",
            "connector": ref.source_id,
            "relative_path": ref.relative_path,
            "source": self._source_kind(ref.source_id, item),
            "item": item,
            "detail": self._detail(ref.source_id, item),
        }

    def _source_kind(self, connector_id: str, item: dict[str, Any]) -> str:
        if connector_id == "apple-notes" and self._item_path(item).is_file():
            return "local-export"
        return "index"

    def _detail(self, connector_id: str, item: dict[str, Any]) -> dict[str, Any]:
        if connector_id == "apple-notes":
            raw = self._read_json(self._item_path(item))
            if raw:
                return raw
        return {
            "title": item.get("title") or "",
            "text": item.get("text") or "",
            "resource": item.get("resource") or "",
            "path": item.get("path") or "",
        }

    def _item_path(self, item: dict[str, Any]) -> Path:
        path = str(item.get("path") or "")
        return Path(path).expanduser() if path else Path()

    def _read_json(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
