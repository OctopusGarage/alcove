from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from alcove.paths import compact_user_path
from alcove.radars.models import RadarDefinition, RadarItem
from alcove.radars.reporting import selected_report_items

if TYPE_CHECKING:
    from alcove.radars.module import RadarModule


def explain_radar_item(
    module: RadarModule,
    definition: RadarDefinition,
    *,
    query: str,
    run_day: str = "",
) -> dict[str, Any]:
    """Explain existing radar artifacts without fetching sources or mutating state."""
    needle = query.strip()
    if not needle:
        raise ValueError("radar explain requires --query")
    selected_day = run_day or _latest_run_day(module, definition.id)
    if not selected_day:
        return _empty_payload(
            definition,
            needle,
            run_day="",
            stage="no_run",
            reason="No radar run artifacts were found.",
        )

    cache_dir = module.cache_root / definition.id / selected_day
    raw_path = cache_dir / "raw.json"
    scored_path = cache_dir / "scored.json"
    run_path = module.runs_root / definition.id / selected_day / "run.json"
    run_payload = _json_mapping(run_path)
    raw_rows = _json_rows(raw_path)
    scored_rows = _json_rows(scored_path)
    raw_matches = [row for row in raw_rows if _matches(row, needle)]
    scored_matches = [row for row in scored_rows if _matches(row, needle)]
    report_items = selected_report_items(definition, _radar_items(scored_rows))
    report_keys = {_item_key(item.as_dict()) for item in report_items}

    matches = [
        _match_payload(row, report_present=_item_key(row) in report_keys) for row in scored_matches
    ]
    raw_only = [
        _match_payload(row, report_present=False)
        for row in raw_matches
        if not any(_same_item(row, scored_row) for scored_row in scored_matches)
    ]
    stage = _stage(
        raw_matches=raw_matches,
        scored_matches=scored_matches,
        matches=matches,
        run_payload=run_payload,
    )
    missing_artifacts: list[str] = []
    if not raw_path.is_file():
        missing_artifacts.append(compact_user_path(raw_path))
    if not scored_path.is_file():
        missing_artifacts.append(compact_user_path(scored_path))
    if not run_path.is_file():
        missing_artifacts.append(compact_user_path(run_path))
    payload = {
        "status": "explained",
        "radar_id": definition.id,
        "name": definition.name,
        "query": needle,
        "date": selected_day,
        "stage": stage,
        "summary": _stage_summary(stage),
        "matches": matches,
        "raw_matches": raw_only,
        "source_failures": _source_failures(run_payload),
        "sources": _source_context(run_payload),
        "artifacts": {
            "raw": compact_user_path(raw_path),
            "scored": compact_user_path(scored_path),
            "run": compact_user_path(run_path),
        },
        "diagnostic_note": (
            "This is read-only diagnostic evidence from existing radar artifacts; "
            "absence from cache does not prove a story was unavailable upstream."
        ),
    }
    if missing_artifacts:
        payload["missing_artifacts"] = missing_artifacts
    return payload


def _empty_payload(
    definition: RadarDefinition,
    query: str,
    *,
    run_day: str,
    stage: str,
    reason: str,
) -> dict[str, Any]:
    return {
        "status": "explained",
        "radar_id": definition.id,
        "name": definition.name,
        "query": query,
        "date": run_day,
        "stage": stage,
        "summary": reason,
        "matches": [],
        "raw_matches": [],
        "source_failures": [],
        "sources": [],
        "artifacts": {},
        "diagnostic_note": (
            "This is read-only diagnostic evidence from existing radar artifacts; "
            "absence from cache does not prove a story was unavailable upstream."
        ),
    }


def _latest_run_day(module: RadarModule, radar_id: str) -> str:
    run_root = module.runs_root / radar_id
    if not run_root.is_dir():
        return ""
    for run_dir in sorted(run_root.iterdir(), reverse=True):
        if (run_dir / "run.json").is_file():
            return run_dir.name
    return ""


def _json_rows(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    return [dict(row) for row in payload if isinstance(row, dict)]


def _json_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _matches(row: dict[str, Any], query: str) -> bool:
    query_text = query.strip().lower()
    url = str(row.get("url") or "").strip().lower()
    if query_text.startswith(("http://", "https://")) and query_text == url:
        return True
    haystack = " ".join(
        [
            str(row.get("title") or ""),
            str(row.get("url") or ""),
            str(row.get("summary") or ""),
        ]
    ).lower()
    return query_text in haystack


def _radar_items(rows: list[dict[str, Any]]) -> list[RadarItem]:
    items: list[RadarItem] = []
    for row in rows:
        raw_tags = row.get("tags")
        tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
        raw_metrics = row.get("metrics")
        metrics = dict(raw_metrics) if isinstance(raw_metrics, dict) else {}
        items.append(
            RadarItem(
                source_id=str(row.get("source_id") or ""),
                adapter=str(row.get("adapter") or ""),
                title=str(row.get("title") or ""),
                url=str(row.get("url") or ""),
                summary=str(row.get("summary") or ""),
                author=str(row.get("author") or ""),
                published_at=str(row.get("published_at") or ""),
                tags=tags,
                metrics=metrics,
                score=_float(row.get("score")),
                score_reason=str(row.get("score_reason") or ""),
                included=bool(row.get("included", False)),
            )
        )
    return items


def _match_payload(row: dict[str, Any], *, report_present: bool) -> dict[str, Any]:
    return {
        "source_id": str(row.get("source_id") or ""),
        "adapter": str(row.get("adapter") or ""),
        "title": str(row.get("title") or ""),
        "url": str(row.get("url") or ""),
        "summary": str(row.get("summary") or ""),
        "score": _float(row.get("score")),
        "score_reason": str(row.get("score_reason") or ""),
        "included": bool(row.get("included", False)),
        "report_present": report_present,
    }


def _stage(
    *,
    raw_matches: list[dict[str, Any]],
    scored_matches: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    run_payload: dict[str, Any],
) -> str:
    if not raw_matches and not scored_matches:
        return "not_fetched_or_source_failed" if _source_failures(run_payload) else "not_fetched"
    if raw_matches and not scored_matches:
        return "fetched_but_deduped"
    if not matches:
        return "not_fetched"
    if any(match["included"] and match["report_present"] for match in matches):
        return "included"
    if any(match["included"] for match in matches):
        return "included_but_report_limited_or_deduped"
    reasons = " ".join(str(match.get("score_reason") or "").lower() for match in matches)
    if "stale published_at" in reasons:
        return "stale"
    if "blocked keyword" in reasons:
        return "blocked"
    return "below_threshold"


def _stage_summary(stage: str) -> str:
    summaries = {
        "no_run": "No radar run artifacts were found.",
        "not_fetched": "No matching item was found in the raw or scored cache.",
        "not_fetched_or_source_failed": (
            "No matching item was found; one or more sources failed during this run."
        ),
        "fetched_but_deduped": "A raw match was fetched but did not survive deduplication/scoring.",
        "stale": "A match was scored but excluded as stale.",
        "blocked": "A match was scored but excluded by a blocked keyword.",
        "below_threshold": "A match was scored but did not pass the inclusion threshold.",
        "included_but_report_limited_or_deduped": (
            "A match passed scoring but was not selected for the final report."
        ),
        "included": "A match was included and selected for the final report.",
    }
    return summaries.get(stage, stage.replace("_", " "))


def _source_failures(run_payload: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(source)
        for source in _source_context(run_payload)
        if str(source.get("status") or "") == "error"
    ]


def _source_context(run_payload: dict[str, Any]) -> list[dict[str, Any]]:
    sources = run_payload.get("sources")
    if not isinstance(sources, list):
        return []
    return [dict(source) for source in sources if isinstance(source, dict)]


def _same_item(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return _item_key(left) == _item_key(right)


def _item_key(row: dict[str, Any]) -> tuple[str, str]:
    url = str(row.get("url") or "").strip().lower()
    title = str(row.get("title") or "").strip().lower()
    return (url, title)


def _float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
