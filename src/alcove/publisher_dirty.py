from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug


PUBLISHER_DIRTY_SCHEMA = "alcove/publisher-dirty/v1"
DEFAULT_DIRTY_PUBLISHER_ID = "apple-notes"


def mark_publisher_source_dirty(
    home: AlcoveHome,
    source: str,
    *,
    publisher_id: str = DEFAULT_DIRTY_PUBLISHER_ID,
    timestamp: str | None = None,
) -> Path | None:
    source = str(source or "").strip()
    publisher_id = normalize_slug(str(publisher_id or DEFAULT_DIRTY_PUBLISHER_ID))
    if not source or not _publisher_definition_exists(home, publisher_id):
        return None
    payload = _load_dirty_payload(home)
    now = timestamp or datetime.now(UTC).isoformat(timespec="seconds")
    publishers = _dict(payload.setdefault("publishers", {}))
    payload["publishers"] = publishers
    publisher = _dict(publishers.setdefault(publisher_id, {}))
    publishers[publisher_id] = publisher
    dirty_sources = _dict(publisher.setdefault("dirty_sources", {}))
    publisher["dirty_sources"] = dirty_sources
    dirty_sources[source] = now
    publisher["updated_at"] = now
    return _write_dirty_payload(home, payload)


def dirty_sources_for_publisher(
    home: AlcoveHome,
    publisher_id: str,
    sources: set[str],
) -> set[str]:
    publisher = _publisher_dirty_record(home, publisher_id)
    dirty_sources = _dict(publisher.get("dirty_sources"))
    return {source for source in dirty_sources if source in sources}


def clear_publisher_dirty_sources(
    home: AlcoveHome,
    publisher_id: str,
    sources: set[str],
) -> Path | None:
    payload = _load_dirty_payload(home)
    publishers = _dict(payload.get("publishers"))
    publisher_id = normalize_slug(publisher_id)
    publisher = _dict(publishers.get(publisher_id))
    dirty_sources = _dict(publisher.get("dirty_sources"))
    for source in sources:
        dirty_sources.pop(source, None)
    if dirty_sources:
        publisher["dirty_sources"] = dirty_sources
        publishers[publisher_id] = publisher
    else:
        publishers.pop(publisher_id, None)
    payload["publishers"] = publishers
    return _write_dirty_payload(home, payload)


def _publisher_dirty_record(home: AlcoveHome, publisher_id: str) -> dict[str, Any]:
    payload = _load_dirty_payload(home)
    publishers = _dict(payload.get("publishers"))
    return _dict(publishers.get(normalize_slug(publisher_id)))


def _load_dirty_payload(home: AlcoveHome) -> dict[str, Any]:
    path = _dirty_path(home)
    if not path.is_file():
        return {"schema": PUBLISHER_DIRTY_SCHEMA, "publishers": {}}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        return {"schema": PUBLISHER_DIRTY_SCHEMA, "publishers": {}}
    payload.setdefault("schema", PUBLISHER_DIRTY_SCHEMA)
    payload.setdefault("publishers", {})
    return payload


def _write_dirty_payload(home: AlcoveHome, payload: dict[str, Any]) -> Path:
    path = _dirty_path(home)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["schema"] = PUBLISHER_DIRTY_SCHEMA
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), "utf-8")
    return path


def _publisher_definition_exists(home: AlcoveHome, publisher_id: str) -> bool:
    return (
        home.root / "publishers" / "definitions" / f"{normalize_slug(publisher_id)}.yml"
    ).is_file()


def _dirty_path(home: AlcoveHome) -> Path:
    return home.root / "publishers" / "dirty.yml"


def _dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
