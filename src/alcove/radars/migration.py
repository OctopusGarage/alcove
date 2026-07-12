from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path
from typing import TYPE_CHECKING, Any, Mapping

import yaml

from alcove.paths import compact_user_path
from alcove.radars.models import RadarDefinition, RadarItem, RadarSchedule

if TYPE_CHECKING:
    from alcove.radars.module import RadarModule


RADAR_MAPPINGS = (
    {
        "id": "tech-news",
        "name": "Tech News",
        "preset": "tech-news",
        "profile": "config/preference_profile.json",
        "fallback_profile": "config/preference_profile.example.json",
        "data": "data/radar",
        "reports": "reports",
    },
    {
        "id": "world-news",
        "name": "World News",
        "preset": "world-news",
        "profile": "config/news_preference_profile.json",
        "data": "data/news_radar",
        "reports": "reports/news",
    },
    {
        "id": "stocks",
        "name": "Stocks",
        "preset": "",
        "profile": "config/stock_preference_profile.json",
        "data": "data/stock_radar",
        "reports": "reports/stock",
    },
)


def import_social_radar(
    module: RadarModule,
    source_home: str | Path,
    *,
    force: bool = False,
) -> dict[str, Any]:
    root = Path(source_home).expanduser()
    if not root.is_dir():
        raise FileNotFoundError(f"social-radar home not found: {compact_user_path(root)}")

    imported: list[dict[str, Any]] = []
    total_secret_fields_removed = 0
    total_blog_reports_skipped = 0
    for mapping in RADAR_MAPPINGS:
        radar_id = str(mapping["id"])
        profile_path = _first_existing(
            root / str(mapping["profile"]),
            root / str(mapping.get("fallback_profile") or ""),
        )
        profile, secret_fields_removed = _read_json_profile(profile_path)
        definition = _definition_for_mapping(module, mapping, profile)
        definition_result = _upsert_definition(module, definition, force=force)
        cache_files = _copy_cache(module, radar_id, root / str(mapping["data"]))
        report_files, blog_reports_skipped = _copy_reports(
            module, radar_id, root / str(mapping["reports"])
        )
        total_secret_fields_removed += secret_fields_removed
        total_blog_reports_skipped += blog_reports_skipped
        imported.append(
            {
                "id": radar_id,
                "definition": definition_result["status"],
                "source_profile": compact_user_path(profile_path) if profile_path else "",
                "target_definition": definition_result["path"],
                "target_cache": compact_user_path(module.cache_root / radar_id),
                "target_reports": compact_user_path(module.reports_root / radar_id),
                "secret_fields_removed": secret_fields_removed,
                "cache_files": cache_files,
                "report_files": report_files,
                "blog_reports_skipped": blog_reports_skipped,
            }
        )

    return {
        "status": "imported",
        "source": compact_user_path(root),
        "target": compact_user_path(module.root),
        "count": len(imported),
        "scrub": {
            "env_files_skipped": len([path for path in root.rglob(".env") if path.is_file()]),
            "secret_fields_removed": total_secret_fields_removed,
            "blog_reports_skipped": total_blog_reports_skipped,
        },
        "radars": imported,
    }


def _definition_for_mapping(
    module: RadarModule,
    mapping: Mapping[str, object],
    profile: dict[str, Any],
) -> RadarDefinition:
    preset = str(mapping.get("preset") or "")
    if preset:
        definition = _definition_from_preset(module, preset)
    else:
        definition = RadarDefinition(
            id=str(mapping["id"]),
            name=str(mapping["name"]),
            schedule=RadarSchedule(enabled=False, ttl_hours=24),
            report={"language": "zh", "style": "briefing", "formats": ["md", "html"]},
            notify={"enabled": False, "channel": "telegram"},
        )
    tags = list(dict.fromkeys([*definition.tags, "imported", "social-radar"]))
    status = "needs_configuration" if not definition.sources else definition.status
    return replace(
        definition,
        id=str(mapping["id"]),
        name=str(mapping["name"]),
        profile=profile or definition.profile,
        tags=tags,
        status=status,
    )


def _definition_from_preset(module: RadarModule, preset: str) -> RadarDefinition:
    path = module._presets_root() / f"{preset}.yml"
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError(f"Radar preset is invalid: {preset}")
    return module._definition(payload)


def _upsert_definition(
    module: RadarModule, definition: RadarDefinition, *, force: bool
) -> dict[str, Any]:
    path = module.definitions_root / f"{definition.id}.yml"
    if path.exists() and not force:
        return {"status": "kept", "path": compact_user_path(path)}
    result = module.upsert_definition(definition)
    return {"status": result["status"], "path": result["path"]}


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if str(path) and path.is_file():
            return path
    return None


def _read_json_profile(path: Path | None) -> tuple[dict[str, Any], int]:
    if path is None:
        return {}, 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {compact_user_path(path)}")
    scrubbed, removed = _scrub_secrets(payload)
    return scrubbed, removed


_SECRET_KEY_PARTS = (
    "api_key",
    "apikey",
    "auth",
    "bot_token",
    "chat_id",
    "cookie",
    "credential",
    "password",
    "secret",
    "session",
    "token",
    "webhook",
)


def _scrub_secrets(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        removed = 0
        for key, child in value.items():
            key_text = str(key).lower().replace("-", "_")
            if any(part in key_text for part in _SECRET_KEY_PARTS):
                removed += 1
                continue
            scrubbed, child_removed = _scrub_secrets(child)
            result[str(key)] = scrubbed
            removed += child_removed
        return result, removed
    if isinstance(value, list):
        rows: list[Any] = []
        removed = 0
        for child in value:
            scrubbed, child_removed = _scrub_secrets(child)
            rows.append(scrubbed)
            removed += child_removed
        return rows, removed
    return value, 0


def _copy_cache(module: RadarModule, radar_id: str, data_dir: Path) -> int:
    if not data_dir.is_dir():
        return 0
    copied = 0
    for source in sorted(data_dir.glob("all_*.json")):
        day = source.stem.removeprefix("all_")
        items = _items_from_legacy_cache(source)
        target_dir = module.cache_root / radar_id / day
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "scored.json").write_text(
            _json([item.as_dict() for item in items]), encoding="utf-8"
        )
        (target_dir / "legacy.json").write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8"
        )
        copied += 1
    return copied


def _items_from_legacy_cache(path: Path) -> list[RadarItem]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    return [_item_from_legacy_row(row) for row in rows if isinstance(row, dict)]


def _item_from_legacy_row(row: dict[str, Any]) -> RadarItem:
    tags = row.get("tags")
    source = str(row.get("source") or "social-radar")
    title = str(row.get("title") or row.get("name") or row.get("symbol") or "")
    summary = str(
        row.get("report_summary") or row.get("description") or row.get("interest_reason") or ""
    )
    report_score = row.get("report_score")
    return RadarItem(
        source_id=source,
        adapter="social-radar-import",
        title=title,
        url=str(row.get("url") or ""),
        summary=summary,
        author=str(row.get("author") or ""),
        published_at=str(row.get("fetched_at") or ""),
        tags=[str(tag) for tag in tags] if isinstance(tags, list) else [],
        metrics={key: value for key, value in row.items() if key not in _RADAR_ITEM_FIELDS},
        score=_float_or_zero(report_score),
        score_reason=str(row.get("interest_reason") or ""),
        included=bool(row.get("included_in_report", False)),
    )


_RADAR_ITEM_FIELDS = {
    "source",
    "title",
    "url",
    "author",
    "description",
    "tags",
    "fetched_at",
    "report_score",
    "report_summary",
    "included_in_report",
    "interest_reason",
}


def _float_or_zero(value: object) -> float:
    if not isinstance(value, (int, float, str)):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _copy_reports(module: RadarModule, radar_id: str, reports_dir: Path) -> tuple[int, int]:
    if not reports_dir.is_dir():
        return 0, 0
    target_dir = module.reports_root / radar_id
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0
    for source in sorted([*reports_dir.glob("*.md"), *reports_dir.glob("*.html")]):
        if source.name.startswith("blogs_"):
            skipped += 1
            continue
        shutil.copy2(source, target_dir / source.name)
        copied += 1
    return copied, skipped


def _json(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
