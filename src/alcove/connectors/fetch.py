from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alcove.external_resolver import ExternalItemResolver
from alcove.home import AlcoveHome
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


class ConnectorFetchModule:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.resolver = ExternalItemResolver(self.runtime)

    def fetch(self, item_path: str) -> dict[str, Any]:
        resolved = self.resolver.resolve_connector(item_path)
        ref = resolved.ref
        item = resolved.item
        presenter = resolved.presenter
        return {
            "status": "fetched",
            "connector": ref.source_id,
            "relative_path": ref.relative_path,
            "display_id": presenter.display_id(),
            "display_label": presenter.display_label(),
            "source_id": ref.source_id,
            "source_label": presenter.source_label(),
            "origin_label": presenter.origin_label(),
            "fetch_ref": ref.path,
            "source": self._source_kind(ref.source_id, item),
            "item": presenter.public_item(),
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
                return self._without_local_path(raw)
        return {
            "title": item.get("title") or "",
            "text": item.get("text") or "",
            "resource": item.get("resource") or "",
            "relative_path": item.get("relative_path") or "",
        }

    def _without_local_path(self, payload: dict[str, Any]) -> dict[str, Any]:
        public = dict(payload)
        public.pop("path", None)
        return public

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
