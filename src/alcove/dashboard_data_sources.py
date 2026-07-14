from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from alcove.blog_monitor import BlogMonitorModule
from alcove.connector_display import connector_display_name
from alcove.connector_sources import ConnectorSourceRegistry
from alcove.dashboard_activity import DashboardActivityRows
from alcove.dashboard_knowledge import DashboardKnowledgeRows
from alcove.dashboard_time import dashboard_time_iso
from alcove.external_index import ExternalIndexStore
from alcove.external_presentation import ExternalIndexedItemPresenter
from alcove.home import AlcoveHome


class DashboardDataSources:
    """Dashboard projection for external connectors and mounted indexes."""

    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def blog_rows(self) -> list[dict[str, Any]]:
        sources = BlogMonitorModule(self.home).list_sources(status="").get("sources", [])
        rows = []
        for source in sources if isinstance(sources, list) else []:
            if not isinstance(source, dict):
                continue
            raw_capture = source.get("capture")
            capture = raw_capture if isinstance(raw_capture, dict) else {}
            raw_schedule = source.get("schedule")
            schedule = raw_schedule if isinstance(raw_schedule, dict) else {}
            rows.append(
                {
                    "id": str(source.get("id") or ""),
                    "name": str(source.get("name") or ""),
                    "url": str(source.get("url") or ""),
                    "status": str(source.get("status") or ""),
                    "checked_at": dashboard_time_iso(str(source.get("checked_at") or "")),
                    "changed_at": dashboard_time_iso(str(source.get("changed_at") or "")),
                    "capture_enabled": bool(capture.get("enabled")),
                    "kb": str(capture.get("kb") or ""),
                    "inbox_path": str(capture.get("inbox_path") or ""),
                    "ttl_hours": int(schedule.get("ttl_hours") or 0),
                }
            )
        return rows

    def knowledge_base_rows(self, kb_rows: list[Any]) -> list[dict[str, Any]]:
        return DashboardKnowledgeRows(self.home).rows(kb_rows)

    def activity_rows(self) -> list[dict[str, Any]]:
        return DashboardActivityRows(self.home).rows()

    def connector_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        registry = ConnectorSourceRegistry(home=self.home)
        status_by_key = {(row["connector"], row["id"]): row for row in registry.status()["sources"]}
        registered_connectors: set[str] = set()
        for source in registry.list():
            connector = str(source.get("connector") or "")
            source_id = str(source.get("id") or "")
            registered_connectors.add(connector)
            raw_refresh = source.get("refresh")
            refresh = raw_refresh if isinstance(raw_refresh, dict) else {}
            raw_status = status_by_key.get((connector, source_id), {})
            status = raw_status if isinstance(raw_status, dict) else {}
            rows.append(
                {
                    "connector": connector,
                    "id": source_id,
                    "source": self.connector_source_label(connector, source),
                    "status": str(status.get("status") or refresh.get("status") or ""),
                    "freshness_status": str(status.get("status") or refresh.get("status") or ""),
                    "count": int(status.get("item_count") or refresh.get("item_count") or 0),
                    "item_count": int(status.get("item_count") or refresh.get("item_count") or 0),
                    "checked_at": str(
                        status.get("checked_at")
                        or refresh.get("last_checked_at")
                        or refresh.get("last_changed_at")
                        or ""
                    ),
                    "ttl_hours": status.get("ttl_hours") or refresh.get("ttl_hours"),
                    "updated_at": str(
                        status.get("checked_at")
                        or refresh.get("last_checked_at")
                        or refresh.get("last_changed_at")
                        or ""
                    ),
                    "items": self.connector_items(connector, source_id),
                }
            )
        rows.extend(self.fallback_connector_rows(registered_connectors))
        return rows

    def fallback_connector_rows(self, registered_connectors: set[str]) -> list[dict[str, Any]]:
        connectors_root = self.home.paths().connectors
        if not connectors_root.exists():
            return []
        rows: list[dict[str, Any]] = []
        for index_path in sorted(connectors_root.glob("*/index.json")):
            if index_path.parent.name in registered_connectors:
                continue
            try:
                data = json.loads(index_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            items = data.get("items") if isinstance(data, dict) else None
            if not isinstance(items, list):
                items = []
            updated_at = datetime.fromtimestamp(index_path.stat().st_mtime, UTC).isoformat(
                timespec="seconds"
            )
            rows.append(
                self.fallback_connector_row(
                    connector=index_path.parent.name,
                    data=data,
                    item_count=len(items),
                    updated_at=updated_at,
                )
            )
        return rows

    def fallback_connector_row(
        self,
        *,
        connector: str,
        data: dict[str, Any],
        item_count: int,
        updated_at: str,
    ) -> dict[str, Any]:
        ttl_hours = 24
        freshness_status = self.freshness_status(updated_at, ttl_hours)
        return {
            "id": connector,
            "connector": connector,
            "source": self.connector_source_label(connector, data),
            "status": freshness_status,
            "freshness_status": freshness_status,
            "count": item_count,
            "item_count": item_count,
            "checked_at": updated_at,
            "ttl_hours": ttl_hours,
            "updated_at": updated_at,
            "items": self.connector_items(connector, ""),
        }

    def freshness_status(self, updated_at: str, ttl_hours: int) -> str:
        try:
            checked_at = datetime.fromisoformat(updated_at)
        except ValueError:
            return "indexed"
        age_seconds = (datetime.now(UTC) - checked_at).total_seconds()
        return "fresh" if age_seconds <= ttl_hours * 3600 else "stale"

    def connector_source_label(self, connector: str, data: dict[str, Any]) -> str:
        public = public_resource(str(data.get("source") or ""))
        if public and public != connector:
            return public
        return connector_display_name(connector)

    def mount_row(self, mount: Any, mount_items: list[dict[str, Any]]) -> dict[str, Any]:
        all_items = [
            item for item in mount_items if str(item.get("mount_id") or "") == str(mount.id)
        ]
        items = [self.external_item(item) for item in all_items][:5]
        return {
            "id": mount.id,
            "name": mount.name,
            "type": mount.type,
            "tags": mount.tags,
            "status": mount.status,
            "created_at": mount.created_at,
            "updated_at": mount.updated_at,
            "items": items,
            "preview_count": len(items),
            "count": len(all_items),
            "item_count": len(all_items),
        }

    def connector_items(
        self, connector: str, source_id: str, limit: int = 5
    ) -> list[dict[str, Any]]:
        store = ExternalIndexStore(self.home.paths().connectors)
        items: list[dict[str, Any]] = []
        for dataset in store.connector_datasets():
            if dataset.source_id != connector:
                continue
            for item in dataset.items:
                item_source_id = str(item.get("source_id") or "")
                if source_id and item_source_id and item_source_id.lower() != source_id.lower():
                    continue
                items.append(self.external_item(item))
                if len(items) >= limit:
                    return items
        return items

    def external_item(self, item: dict[str, Any]) -> dict[str, Any]:
        presenter = ExternalIndexedItemPresenter.from_item(item)
        if presenter:
            return presenter.dashboard_item()
        text = str(item.get("text") or "")
        return {
            "title": str(item.get("title") or item.get("relative_path") or ""),
            "type": str(item.get("type") or item.get("source_kind") or "External Item"),
            "path": str(item.get("relative_path") or ""),
            "source": str(item.get("connector_name") or item.get("mount_name") or ""),
            "resource": public_resource(str(item.get("resource") or "")),
            "status": str(item.get("status") or "active"),
            "notes": text[:400],
            "updated_at": str(item.get("indexed_at") or item.get("updated_at") or ""),
        }


def public_resource(value: str) -> str:
    if value.startswith(("~", "/", ".")):
        return ""
    return value
