from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSchedule, RadarSource


def test_radar_definition_round_trips_as_user_data(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)
    definition = RadarDefinition(
        id="sports-news",
        name="Sports News",
        sources=[
            RadarSource(
                id="nba-rss",
                adapter="rss",
                enabled=False,
                limit=15,
                params={"url": "https://example.com/rss"},
            )
        ],
        profile={"interest_tags": ["NBA"], "blocked_keywords": ["betting"]},
        scoring={"min_score": 0.7},
        report={
            "language": "zh",
            "style": "concise-briefing",
            "formats": ["md"],
        },
        schedule=RadarSchedule(
            enabled=True,
            ttl_hours=0,
            daily_time="10:00",
            timezone="Asia/Singapore",
        ),
        tags=["sports"],
    )

    saved = module.upsert_definition(definition)
    loaded = module.get("sports-news")

    assert saved["status"] == "saved"
    assert loaded.as_dict() == saved["definition"]
    assert loaded.id == "sports-news"
    assert loaded.sources[0].adapter == "rss"
    assert loaded.sources[0].enabled is False
    assert loaded.sources[0].limit == 15
    assert loaded.scoring == {"min_score": 0.7}
    assert loaded.schedule.as_dict() == {
        "enabled": True,
        "ttl_hours": 1,
        "daily_time": "10:00",
        "timezone": "Asia/Singapore",
    }
    assert loaded.notify == {}
    assert loaded.tags == ["sports"]
    assert (home.root / "radars" / "definitions" / "sports-news.yml").is_file()


def test_radar_definition_validation_rejects_missing_source_adapter(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    path = home.root / "radars" / "definitions" / "bad.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        """
schema: alcove/radar-definition/v1
id: bad
name: Bad Radar
sources:
  - id: missing-adapter
""",
        encoding="utf-8",
    )
    module = RadarModule(home)

    with pytest.raises(ValueError, match="source adapter is required"):
        module.get("bad")


def test_radar_list_is_generic_and_does_not_assume_fixed_ids(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="custom-ai-products",
            name="Custom AI Products",
            sources=[RadarSource(id="ai-feed", adapter="rss")],
        )
    )

    listed = module.list()

    assert listed["count"] == 1
    assert [definition["id"] for definition in listed["definitions"]] == ["custom-ai-products"]


def test_radar_definition_as_dict_does_not_leak_mutable_internals():
    source = RadarSource(id="feed", adapter="rss", params={"url": "https://example.com"})
    definition = RadarDefinition(
        id="mutable-check",
        name="Mutable Check",
        sources=[source],
        profile={"interest_tags": ["ai"]},
        scoring={"min_score": 0.5},
        report={"formats": ["md"]},
        ai_summary={"provider": "codex", "prompt": "custom"},
        notify={"channel": "telegram"},
        tags=["ai"],
    )

    payload = definition.as_dict()
    payload["sources"][0]["params"]["url"] = "changed"
    payload["profile"]["interest_tags"].append("changed")
    payload["scoring"]["min_score"] = 1
    payload["report"]["formats"].append("json")
    payload["ai_summary"]["provider"] = "changed"
    payload["notify"]["channel"] = "changed"
    payload["tags"].append("changed")

    assert source.params == {"url": "https://example.com"}
    assert definition.profile == {"interest_tags": ["ai"]}
    assert definition.scoring == {"min_score": 0.5}
    assert definition.report == {"formats": ["md"]}
    assert definition.ai_summary == {"provider": "codex", "prompt": "custom"}
    assert definition.notify == {"channel": "telegram"}
    assert definition.tags == ["ai"]


@pytest.mark.parametrize(
    ("yaml_body", "message"),
    [
        ("sources: rss\n", "sources must be a list"),
        ("sources:\n  - rss\n", "radar source must be a mapping"),
        (
            "sources:\n  - id: feed\n    adapter: rss\n    params: nope\n",
            "source params must be a mapping",
        ),
        ("tags: ai\n", "tags must be a list"),
        ("profile: ai\n", "profile must be a mapping"),
        ("schedule: hourly\n", "schedule must be a mapping"),
        ("ai_summary: codex\n", "ai_summary must be a mapping"),
    ],
)
def test_radar_definition_rejects_malformed_user_yaml_shapes(tmp_path, yaml_body, message):
    home = AlcoveHome.init(tmp_path / ".alcove")
    path = home.root / "radars" / "definitions" / "bad-shape.yml"
    path.parent.mkdir(parents=True)
    path.write_text(
        f"""
schema: alcove/radar-definition/v1
id: bad-shape
name: Bad Shape
{yaml_body}
""",
        encoding="utf-8",
    )
    module = RadarModule(home)

    with pytest.raises(ValueError, match=message):
        module.get("bad-shape")


def test_radar_check_stale_runs_enabled_scheduled_radars(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        '[{"title":"AI signal","url":"https://example.test/ai","summary":"LLM"}]',
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="scheduled-radar",
            name="Scheduled Radar",
            schedule=RadarSchedule(enabled=True, ttl_hours=1),
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI", "LLM"], "min_score_threshold": 0.5},
        )
    )
    module.upsert_definition(
        RadarDefinition(
            id="manual-radar",
            name="Manual Radar",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
        )
    )

    payload = module.check_stale()

    assert payload["status"] == "checked"
    assert payload["ran"] == 1
    assert payload["skipped"] == 1
    assert payload["errors"] == 0
    assert payload["radars"][0]["id"] == "scheduled-radar"


def test_radar_check_stale_waits_until_daily_time_in_configured_timezone(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        '[{"title":"AI signal","url":"https://example.test/ai","summary":"LLM"}]',
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="scheduled-radar",
            name="Scheduled Radar",
            schedule=RadarSchedule(
                enabled=True,
                ttl_hours=24,
                daily_time="10:00",
                timezone="Asia/Singapore",
            ),
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI", "LLM"], "min_score_threshold": 0.5},
        )
    )

    zone = ZoneInfo("Asia/Singapore")
    today = datetime.now(zone).date()
    before = module.check_stale(current_time=datetime.combine(today, datetime.min.time(), zone))
    after = module.check_stale(
        current_time=datetime.combine(today, datetime.min.time(), zone).replace(hour=10)
    )
    repeated = module.check_stale(
        current_time=datetime.combine(today, datetime.min.time(), zone).replace(hour=10, minute=30)
    )

    assert before["ran"] == 0
    assert before["radars"][0]["reason"] == "before_daily_time"
    assert before["radars"][0]["next_run_after"] == f"{today.isoformat()}T10:00+08:00"
    assert after["ran"] == 1
    assert repeated["ran"] == 0
    assert repeated["radars"][0]["reason"] == "already_ran_today"
