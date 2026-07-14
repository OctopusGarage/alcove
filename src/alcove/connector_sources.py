from __future__ import annotations

import builtins
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
from typing import Any

import yaml

from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.workspace import Workspace


DEFAULT_TTL_HOURS = 24


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class ConnectorSourceStatus:
    connector: str
    id: str
    source: str
    status: str
    checked_at: str
    item_count: int
    ttl_hours: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "connector": self.connector,
            "id": self.id,
            "source": self.source,
            "status": self.status,
            "checked_at": self.checked_at,
            "item_count": self.item_count,
            "ttl_hours": self.ttl_hours,
        }


class ConnectorSourceRegistry:
    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.root = self.runtime.connectors_root

    def upsert_github_stars(
        self,
        *,
        source_id: str,
        source: str,
        username: str,
        tags: list[str],
        export_file: Path | str,
        index_path: Path | str,
        item_count: int,
        checked_at: str | None = None,
        changed_at: str | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        status: str = "fresh",
        error: str = "",
        etag: str = "",
    ) -> dict[str, Any]:
        payload = self._connector_source_payload(
            connector="github-stars",
            source_id=source_id,
            source=source,
            tags=tags,
            index_path=index_path,
            item_count=item_count,
            checked_at=checked_at,
            changed_at=changed_at,
            ttl_hours=ttl_hours,
            status=status,
            error=error,
            extra={
                "username": username,
                "export_file": compact_user_path(export_file),
            },
            refresh_extra={"etag": etag} if etag else None,
        )
        self._write("github-stars", source_id, payload)
        return payload

    def upsert_apple_notes(
        self,
        *,
        source_id: str,
        source: str,
        tags: list[str],
        export_dir: Path | str,
        index_path: Path | str,
        item_count: int,
        checked_at: str | None = None,
        changed_at: str | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        status: str = "fresh",
        error: str = "",
    ) -> dict[str, Any]:
        payload = self._connector_source_payload(
            connector="apple-notes",
            source_id=source_id,
            source=source,
            tags=tags,
            index_path=index_path,
            item_count=item_count,
            checked_at=checked_at,
            changed_at=changed_at,
            ttl_hours=ttl_hours,
            status=status,
            error=error,
            extra={"export_dir": compact_user_path(export_dir)},
        )
        self._write("apple-notes", source_id, payload)
        return payload

    def upsert_chrome_bookmarks(
        self,
        *,
        source_id: str,
        source: str,
        profile: str,
        tags: list[str],
        source_file: Path | str,
        index_path: Path | str,
        item_count: int,
        checked_at: str | None = None,
        changed_at: str | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
        status: str = "fresh",
        error: str = "",
    ) -> dict[str, Any]:
        payload = self._connector_source_payload(
            connector="chrome-bookmarks",
            source_id=source_id,
            source=source,
            tags=tags,
            index_path=index_path,
            item_count=item_count,
            checked_at=checked_at,
            changed_at=changed_at,
            ttl_hours=ttl_hours,
            status=status,
            error=error,
            extra={
                "profile": profile,
                "source_file": compact_user_path(source_file),
            },
        )
        self._write("chrome-bookmarks", source_id, payload)
        return payload

    def _connector_source_payload(
        self,
        *,
        connector: str,
        source_id: str,
        source: str,
        tags: list[str],
        index_path: Path | str,
        item_count: int,
        checked_at: str | None,
        changed_at: str | None,
        ttl_hours: int,
        status: str,
        error: str,
        extra: dict[str, Any],
        refresh_extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        checked = checked_at or now_iso()
        changed = changed_at or checked
        refresh = {
            "policy": "stale",
            "ttl_hours": ttl_hours,
            "last_checked_at": checked,
            "last_changed_at": changed,
            "last_status": "ok" if not error else "error",
            "status": status,
            "last_error": error,
            "item_count": item_count,
        }
        if refresh_extra:
            refresh.update({key: value for key, value in refresh_extra.items() if value})
        return {
            "schema": "alcove/connector-source/v1",
            "connector": connector,
            "id": source_id,
            "source": source,
            "tags": tags,
            "index_path": compact_user_path(index_path),
            **extra,
            "refresh": refresh,
        }

    def get(self, connector: str, source_id: str) -> dict[str, Any]:
        path = self._source_path(connector, source_id)
        if not path.is_file():
            raise FileNotFoundError(f"Connector source not registered: {connector}/{source_id}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Connector source is invalid: {path}")
        return data

    def list(self, connector: str | None = None) -> list[dict[str, Any]]:
        pattern = f"{connector}/sources/*.yml" if connector else "*/sources/*.yml"
        sources: list[dict[str, Any]] = []
        for path in sorted(self.root.glob(pattern), key=lambda item: item.as_posix()):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                sources.append(data)
        return sources

    def status(
        self,
        *,
        connector: str | None = None,
        now: str | None = None,
        default_ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> dict[str, Any]:
        checked_at = _parse_time(now or now_iso()) or datetime.now(UTC)
        rows = [
            self._status_row(source, checked_at, default_ttl_hours).as_dict()
            for source in self.list(connector)
        ]
        registered_connectors = {row["connector"] for row in rows}
        rows_by_key = {(row["connector"], row["id"]): row for row in rows}
        for row in self._indexed_status_rows(
            connector=connector,
            checked_at=checked_at,
            default_ttl_hours=default_ttl_hours,
        ):
            if row["connector"] in registered_connectors:
                continue
            rows_by_key.setdefault((row["connector"], row["id"]), row)
        rows = list(rows_by_key.values())
        return {"count": len(rows), "sources": rows}

    def stale_sources(
        self,
        *,
        connector: str | None = None,
        now: str | None = None,
        default_ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> builtins.list[dict[str, Any]]:
        status_rows = self.status(
            connector=connector,
            now=now,
            default_ttl_hours=default_ttl_hours,
        ).get("sources", [])
        if not isinstance(status_rows, builtins.list):
            return []
        status_by_key = {
            (row["connector"], row["id"]): row for row in status_rows if isinstance(row, dict)
        }
        stale = []
        for source in self.list(connector):
            key = (str(source.get("connector") or ""), str(source.get("id") or ""))
            if status_by_key.get(key, {}).get("status") == "stale":
                stale.append(source)
        return stale

    def _status_row(
        self,
        source: dict[str, Any],
        now_value: datetime,
        default_ttl_hours: int,
    ) -> ConnectorSourceStatus:
        raw_refresh = source.get("refresh")
        refresh: dict[str, Any] = raw_refresh if isinstance(raw_refresh, dict) else {}
        checked = str(refresh.get("last_checked_at") or "")
        ttl_hours = _positive_int(refresh.get("ttl_hours"), default_ttl_hours)
        status = str(refresh.get("status") or "")
        if status not in {"fresh", "stale", "error"}:
            status = "fresh"
        checked_time = _parse_time(checked) if checked else None
        if status != "error" and (
            checked_time is None or now_value - checked_time > timedelta(hours=ttl_hours)
        ):
            status = "stale"
        return ConnectorSourceStatus(
            connector=str(source.get("connector") or ""),
            id=str(source.get("id") or ""),
            source=str(source.get("source") or ""),
            status=status,
            checked_at=checked,
            item_count=_positive_int(refresh.get("item_count"), 0),
            ttl_hours=ttl_hours,
        )

    def _indexed_status_rows(
        self,
        *,
        connector: str | None,
        checked_at: datetime,
        default_ttl_hours: int,
    ) -> builtins.list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        rows: list[dict[str, Any]] = []
        pattern = f"{connector}/index.json" if connector else "*/index.json"
        for path in sorted(self.root.glob(pattern), key=lambda item: item.as_posix()):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            row = self._status_row_from_index(
                payload,
                path,
                checked_at=checked_at,
                default_ttl_hours=default_ttl_hours,
            )
            if row is not None:
                rows.append(row)
        return rows

    def _status_row_from_index(
        self,
        payload: dict[str, Any],
        path: Path,
        *,
        checked_at: datetime,
        default_ttl_hours: int,
    ) -> dict[str, Any] | None:
        connector = str(payload.get("connector") or path.parent.name)
        if not connector:
            return None
        source_id = str(payload.get("source_id") or path.parent.name)
        source = str(payload.get("source") or _connector_display_name(connector))
        indexed_at = str(payload.get("indexed_at") or "")
        indexed_time = _parse_time(indexed_at) if indexed_at else None
        ttl_hours = default_ttl_hours
        status = "fresh"
        if indexed_time is None or checked_at - indexed_time > timedelta(hours=ttl_hours):
            status = "stale"
        items = payload.get("items")
        item_count = len(items) if isinstance(items, list) else 0
        return {
            "connector": connector,
            "id": source_id,
            "source": source,
            "status": status,
            "checked_at": indexed_at,
            "item_count": item_count,
            "ttl_hours": ttl_hours,
        }

    def _write(self, connector: str, source_id: str, payload: dict[str, Any]) -> None:
        path = self._source_path(connector, source_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _source_path(self, connector: str, source_id: str) -> Path:
        return self.root / connector / "sources" / f"{source_id}.yml"


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _positive_int(value: object, default: int) -> int:
    try:
        parsed = value if isinstance(value, int) else int(str(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _connector_display_name(connector: str) -> str:
    names = {
        "apple-notes": "Apple Notes index",
        "chrome-bookmarks": "Chrome Bookmarks index",
        "github-stars": "GitHub Stars index",
    }
    return names.get(connector, f"{connector} index")
