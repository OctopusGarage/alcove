from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


class FixtureAdapter:
    adapter_id = "fixture"

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        path = Path(str(source.params.get("path") or "")).expanduser()
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("fixture radar source must be a JSON list")
        items: list[RadarItem] = []
        limit = source.limit if source.limit > 0 else len(data)
        for row in data[:limit]:
            if not isinstance(row, dict):
                continue
            item = _item_from_row(row, source)
            if item is not None:
                items.append(item)
        return items


def _item_from_row(row: dict[Any, Any], source: RadarSource) -> RadarItem | None:
    title = str(row.get("title") or "").strip()
    url = str(row.get("url") or "").strip()
    if not title or not url:
        return None
    tags = row.get("tags") or []
    metrics = row.get("metrics") or {}
    return RadarItem(
        source_id=source.id,
        adapter=source.adapter,
        title=title,
        url=url,
        summary=str(row.get("summary") or row.get("description") or ""),
        author=str(row.get("author") or ""),
        published_at=str(row.get("published_at") or row.get("date") or ""),
        tags=[str(tag) for tag in tags] if isinstance(tags, list) else [],
        metrics=dict(metrics) if isinstance(metrics, dict) else {},
    )
