from __future__ import annotations

from datetime import datetime, timezone
import json

from alcove.home import AlcoveHome
from alcove.usage import UsageRecorder


def test_usage_recorder_writes_privacy_safe_search_events(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    recorder = UsageRecorder(home)

    first = recorder.record_search(
        surface="dashboard",
        query="private search text with secret tail",
        result_count=0,
        filters={"type": "GitHub Star"},
    )
    second = recorder.record_search(
        surface="cli",
        query="private search text with secret tail",
        result_count=2,
        filters={"type": "GitHub Star"},
    )

    lines = (home.paths().logs / "usage.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines]
    summary = recorder.summary()

    assert first["privacy"]["query_stored"] is False
    assert first["privacy"]["query_preview_stored"] is True
    assert first["metrics"]["query_length"] == len("private search text with secret tail")
    assert first["metrics"]["result_count"] == 0
    assert first["metrics"]["query_hash"]
    assert first["metrics"]["query_hash"] == second["metrics"]["query_hash"]
    assert first["metrics"]["query_preview"] == "private search text with secret..."
    assert first["summary"] == "Search: private search text with secret..."
    assert "private search text with secret tail" not in json.dumps(events, ensure_ascii=False)
    assert events[0]["surface"] == "dashboard"
    assert events[0]["area"] == "search"
    assert events[0]["action"] == "search.run"
    assert events[0]["outcome"] == "empty"
    assert events[1]["outcome"] == "success"
    assert summary["search"]["total"] == 2
    assert summary["search"]["zero_result"] == 1
    assert summary["search"]["surfaces"] == {"cli": 1, "dashboard": 1}
    assert summary["search"]["types"] == {"GitHub Star": 2}


def test_usage_recorder_keeps_short_query_previews_readable(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    recorder = UsageRecorder(home)

    event = recorder.record_search(
        surface="dashboard",
        query="Cleanup obsolete",
        result_count=1,
    )

    assert event["metrics"]["query_preview"] == "Cleanup obso..."
    assert event["summary"] == "Search: Cleanup obso..."
    assert "Cleanup obsolete" not in json.dumps(event, ensure_ascii=False)


def test_usage_summary_keeps_recent_events_without_noisy_payloads(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    recorder = UsageRecorder(home)
    recorder.record_usage(
        surface="dashboard",
        area="dashboard",
        action="dashboard.route",
        summary="Dashboard route viewed",
        metadata={"route": "/pins"},
    )
    recorder.record_search(
        surface="mcp", query="secret query text with private suffix", result_count=3
    )

    summary = recorder.summary(limit=5)

    assert summary["total_events"] == 2
    assert summary["dashboard"]["routes"] == {"/pins": 1}
    assert summary["search"]["surfaces"] == {"mcp": 1}
    assert summary["recent"][0]["summary"] == "Search: secret query text with private s..."
    assert summary["recent"][0]["metrics"]["query_preview"] == "secret query text with private s..."
    assert "secret query text with private suffix" not in json.dumps(summary, ensure_ascii=False)


def test_usage_recorder_records_actions_and_visible_activity(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    recorder = UsageRecorder(home)

    usage = recorder.record_action(
        surface="application",
        area="pin",
        action="pin.add",
        summary="Pinned Reference Pattern",
        metadata={"id": "reference-pattern"},
        visible=True,
    )

    activity_lines = (home.paths().logs / "activity.jsonl").read_text(encoding="utf-8").splitlines()
    activity = [json.loads(line) for line in activity_lines]
    summary = recorder.summary()

    assert usage["area"] == "pin"
    assert usage["action"] == "pin.add"
    assert summary["actions"]["areas"] == {"pin": 1}
    assert summary["actions"]["names"] == {"pin.add": 1}
    assert activity[0]["type"] == "event"
    assert activity[0]["area"] == "pin"
    assert activity[0]["action"] == "pin.add"
    assert activity[0]["summary"] == "Pinned Reference Pattern"
    assert activity[0]["visible"] is True


def test_usage_recorder_writes_summary_and_daily_rollups(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    recorder = UsageRecorder(home)

    recorder.record_usage(
        surface="dashboard",
        area="dashboard",
        action="dashboard.route",
        summary="Dashboard route viewed",
        metadata={"route": "/usage"},
    )
    recorder.record_search(
        surface="cli",
        query="rollup query with private suffix extra",
        result_count=0,
    )
    recorder.record_action(
        surface="application",
        area="connector",
        action="connector.refresh",
        summary="Refreshed connector sources",
        metrics={"refreshed": 1},
        visible=False,
    )

    summary_path = home.paths().stats / "summary.json"
    daily_path = (
        home.paths().stats / "daily" / f"{datetime.now(timezone.utc).astimezone():%Y-%m-%d}.json"
    )
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    daily = json.loads(daily_path.read_text(encoding="utf-8"))

    assert summary["total_events"] == 3
    assert summary["search"]["zero_result"] == 1
    assert summary["actions"]["areas"] == {"connector": 1}
    assert daily["event_count"] == 3
    assert daily["search"]["total"] == 1
    assert daily["actions"]["names"] == {"connector.refresh": 1}
    assert "rollup query with private suffix extra" not in summary_path.read_text(encoding="utf-8")
    assert "rollup query with private suffix extra" not in daily_path.read_text(encoding="utf-8")


def test_usage_recorder_prunes_old_usage_and_activity_events(tmp_path):
    home = AlcoveHome.init(tmp_path / "home")
    recorder = UsageRecorder(home)
    usage_path = home.paths().logs / "usage.jsonl"
    activity_path = home.paths().logs / "activity.jsonl"
    usage_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-06-01T00:00:00+08:00",
                        "surface": "cli",
                        "area": "search",
                        "action": "search.run",
                        "summary": "Old search",
                        "metrics": {"result_count": 0},
                        "metadata": {},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-07-10T00:00:00+08:00",
                        "surface": "cli",
                        "area": "search",
                        "action": "search.run",
                        "summary": "Recent search",
                        "metrics": {"result_count": 1},
                        "metadata": {},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    activity_path.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "updated_at": "2026-06-01T00:00:00+08:00",
                        "area": "pin",
                        "action": "pin.add",
                        "summary": "Old pin",
                    }
                ),
                json.dumps(
                    {
                        "updated_at": "2026-07-10T00:00:00+08:00",
                        "area": "pin",
                        "action": "pin.add",
                        "summary": "Recent pin",
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    result = recorder.prune(retention_days=14, now="2026-07-10T12:00:00+08:00")
    summary = recorder.summary()
    activity = activity_path.read_text(encoding="utf-8")

    assert result == {"usage_removed": 1, "activity_removed": 1}
    assert summary["total_events"] == 1
    assert summary["search"]["total"] == 1
    assert "Old search" not in usage_path.read_text(encoding="utf-8")
    assert "Recent search" in usage_path.read_text(encoding="utf-8")
    assert "Old pin" not in activity
    assert "Recent pin" in activity
