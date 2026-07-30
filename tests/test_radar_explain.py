from __future__ import annotations

import json
from typing import Any

from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSource
from alcove.radars.models import RadarItem


RUN_DAY = "2026-07-29"


def test_radar_explain_reports_not_fetched_from_existing_artifacts(tmp_path) -> None:
    module = _module_with_definition(tmp_path)
    _write_artifacts(
        module,
        raw=[],
        scored=[],
        run={"sources": [{"id": "fixture", "status": "fetched", "count": 0}]},
    )

    payload = module.explain("support-radar", query="Spain defeat France", run_day=RUN_DAY)

    assert payload["stage"] == "not_fetched"
    assert payload["matches"] == []
    assert payload["source_failures"] == []


def test_radar_explain_reports_source_failure_when_absent_from_failed_run(tmp_path) -> None:
    module = _module_with_definition(tmp_path)
    _write_artifacts(
        module,
        raw=[],
        scored=[],
        run={
            "sources": [
                {
                    "id": "sports-feed",
                    "status": "error",
                    "count": 0,
                    "error": "feed unavailable",
                }
            ]
        },
    )

    payload = module.explain("support-radar", query="Spain defeat France", run_day=RUN_DAY)

    assert payload["stage"] == "not_fetched_or_source_failed"
    assert payload["source_failures"][0]["id"] == "sports-feed"
    assert payload["source_failures"][0]["error"] == "feed unavailable"


def test_radar_explain_reports_stale_scored_match(tmp_path) -> None:
    module = _module_with_definition(tmp_path)
    item = _item(
        title="Spain defeat France in World Cup",
        score=0.0,
        score_reason="stale published_at: 2026-07-01",
        included=False,
    )
    _write_artifacts(module, raw=[item], scored=[item])

    payload = module.explain("support-radar", query="Spain defeat France", run_day=RUN_DAY)

    assert payload["stage"] == "stale"
    assert payload["matches"][0]["score_reason"] == "stale published_at: 2026-07-01"
    assert payload["matches"][0]["included"] is False


def test_radar_explain_reports_blocked_scored_match(tmp_path) -> None:
    module = _module_with_definition(tmp_path)
    item = _item(
        title="Spain defeat France betting odds",
        score=0.0,
        score_reason="blocked keyword: betting",
        included=False,
    )
    _write_artifacts(module, raw=[item], scored=[item])

    payload = module.explain("support-radar", query="betting odds", run_day=RUN_DAY)

    assert payload["stage"] == "blocked"
    assert payload["matches"][0]["score_reason"] == "blocked keyword: betting"


def test_radar_explain_reports_below_threshold_scored_match(tmp_path) -> None:
    module = _module_with_definition(tmp_path)
    item = _item(
        title="Spain defeat France analysis",
        score=0.35,
        score_reason="baseline source signal",
        included=False,
    )
    _write_artifacts(module, raw=[item], scored=[item])

    payload = module.explain("support-radar", query="Spain defeat France", run_day=RUN_DAY)

    assert payload["stage"] == "below_threshold"
    assert payload["matches"][0]["score"] == 0.35


def test_radar_explain_reports_included_report_match(tmp_path) -> None:
    module = _module_with_definition(tmp_path)
    item = _item(
        title="Spain defeat France in World Cup",
        score=0.9,
        score_reason="matched: world cup",
        included=True,
    )
    _write_artifacts(module, raw=[item], scored=[item])

    payload = module.explain("support-radar", query=item["url"], run_day=RUN_DAY)

    assert payload["stage"] == "included"
    assert payload["matches"][0]["report_present"] is True
    assert payload["artifacts"]["raw"].endswith("raw.json")


def test_radar_explain_reports_included_but_report_limited_match(tmp_path) -> None:
    module = _module_with_definition(tmp_path, report={"formats": ["md"], "max_items": 1})
    selected = _item(
        title="World Cup final selected",
        url="https://example.test/selected",
        score=0.95,
        included=True,
    )
    limited = _item(
        title="Spain defeat France in World Cup",
        url="https://example.test/spain-france",
        score=0.9,
        included=True,
    )
    _write_artifacts(module, raw=[selected, limited], scored=[selected, limited])

    payload = module.explain("support-radar", query="Spain defeat France", run_day=RUN_DAY)

    assert payload["stage"] == "included_but_report_limited_or_deduped"
    assert payload["matches"][0]["included"] is True
    assert payload["matches"][0]["report_present"] is False


def _module_with_definition(
    tmp_path,
    *,
    report: dict[str, Any] | None = None,
) -> RadarModule:
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="support-radar",
            name="Support Radar",
            sources=[RadarSource(id="sports-feed", adapter="fixture")],
            profile={"interest_tags": ["world cup"], "min_score_threshold": 0.5},
            report=report or {"formats": ["md"]},
        )
    )
    return module


def _write_artifacts(
    module: RadarModule,
    *,
    raw: list[dict[str, Any]],
    scored: list[dict[str, Any]],
    run: dict[str, Any] | None = None,
) -> None:
    cache_dir = module.cache_root / "support-radar" / RUN_DAY
    run_dir = module.runs_root / "support-radar" / RUN_DAY
    cache_dir.mkdir(parents=True)
    run_dir.mkdir(parents=True)
    (cache_dir / "raw.json").write_text(json.dumps(raw), encoding="utf-8")
    (cache_dir / "scored.json").write_text(json.dumps(scored), encoding="utf-8")
    payload = {
        "id": "support-radar",
        "date": RUN_DAY,
        "sources": [{"id": "sports-feed", "status": "fetched", "count": len(raw)}],
        **(run or {}),
    }
    (run_dir / "run.json").write_text(json.dumps(payload), encoding="utf-8")


def _item(
    *,
    title: str,
    url: str = "https://example.test/spain-france",
    score: float = 0.0,
    score_reason: str = "baseline source signal",
    included: bool = False,
) -> dict[str, Any]:
    return RadarItem(
        source_id="sports-feed",
        adapter="fixture",
        title=title,
        url=url,
        summary="World Cup match report.",
        score=score,
        score_reason=score_reason,
        included=included,
    ).as_dict()
