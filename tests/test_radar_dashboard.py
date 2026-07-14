from __future__ import annotations

import json

from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSource


def test_dashboard_snapshot_lists_generic_radars(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="sports-news",
            name="Sports News",
            sources=[
                RadarSource(
                    id="fixture",
                    adapter="fixture",
                    params={"path": str(tmp_path / "missing.json")},
                )
            ],
            tags=["sports", "news"],
        )
    )

    snapshot = DashboardModule(home).snapshot()

    assert snapshot["summary"]["counts"]["radars"] == 1
    assert snapshot["summary"]["counts"]["radars_current"] == 0
    assert snapshot["summary"]["counts"]["radars_configured"] == 1
    assert snapshot["summary"]["counts"]["radars_stale"] == 0
    assert (
        next(module for module in snapshot["modules"] if module["id"] == "radars")["href"]
        == "/radars"
    )
    assert snapshot["radars"][0]["id"] == "sports-news"
    assert snapshot["radars"][0]["status"] == "configured"
    assert snapshot["radars"][0]["definition_status"] == "active"
    assert snapshot["radars"][0]["status_label"] == "Configured, not run yet"
    assert snapshot["radars"][0]["run_command"] == "alcove radar run sports-news --json"
    status_row = module.status("sports-news")["radars"][0]
    assert snapshot["radars"][0]["status"] == status_row["operational_status"]
    assert snapshot["radars"][0]["status_label"] == status_row["status_label"]
    assert snapshot["radars"][0]["report_state"] == status_row["report_state"]
    assert snapshot["radars"][0]["report_label"] == status_row["report_label"]
    assert snapshot["radars"][0]["run_command"] == status_row["run_command"]
    assert snapshot["radars"][0]["source_count"] == 1
    assert any(
        row["type"] == "radar" and row["title"] == "Sports News" and row["href"] == "/radars"
        for row in snapshot["search_index"]
    )


def test_dashboard_snapshot_counts_current_active_radars_as_configured(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "AI signal",
                    "url": "https://example.test/ai",
                    "summary": "Useful model release",
                    "tags": ["AI"],
                }
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="sports-news",
            name="Sports News",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI"], "min_score_threshold": 0.5},
        )
    )

    module.run("sports-news")
    snapshot = DashboardModule(home).snapshot()

    assert snapshot["radars"][0]["status"] == "current"
    assert snapshot["radars"][0]["definition_status"] == "active"
    assert snapshot["summary"]["counts"]["radars_current"] == 1
    assert snapshot["summary"]["counts"]["radars_configured"] == 1


def test_dashboard_snapshot_formats_radar_status_labels(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="stocks",
            name="Stocks",
            status="needs_configuration",
        )
    )

    snapshot = DashboardModule(home).snapshot()

    assert snapshot["radars"][0]["status"] == "needs_configuration"
    assert snapshot["radars"][0]["status_label"] == "Needs configuration"
