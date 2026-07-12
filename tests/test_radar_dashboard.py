from __future__ import annotations

from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSource


def test_dashboard_snapshot_lists_generic_radars(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    RadarModule(home).upsert_definition(
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
    assert (
        next(module for module in snapshot["modules"] if module["id"] == "radars")["href"]
        == "/radars"
    )
    assert snapshot["radars"][0]["id"] == "sports-news"
    assert snapshot["radars"][0]["source_count"] == 1
    assert any(
        row["type"] == "radar" and row["title"] == "Sports News" and row["href"] == "/radars"
        for row in snapshot["search_index"]
    )
