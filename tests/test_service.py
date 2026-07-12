from __future__ import annotations

import plistlib

from alcove.home import AlcoveHome
from alcove.cli import main
from alcove.radars import RadarDefinition, RadarModule, RadarSchedule, RadarSource
from alcove.service import ServiceModule
from alcove.tasks import AddRoutineRequest, AddTaskRequest, TasksModule


def test_service_install_writes_dashboard_and_scheduler_launch_agents(tmp_path, monkeypatch):
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    home = AlcoveHome.init(user_home / ".alcove")

    result = ServiceModule(home).install(
        dashboard=False,
        scheduler=False,
        host="127.0.0.1",
        port=8765,
        interval_minutes=15,
    )

    dashboard_plist = user_home / "Library/LaunchAgents/com.octopusgarage.alcove.dashboard.plist"
    scheduler_plist = user_home / "Library/LaunchAgents/com.octopusgarage.alcove.scheduler.plist"
    dashboard = plistlib.loads(dashboard_plist.read_bytes())
    scheduler = plistlib.loads(scheduler_plist.read_bytes())
    assert result["targets"] == ["dashboard", "scheduler"]
    assert dashboard["Label"] == "com.octopusgarage.alcove.dashboard"
    assert "alcove serve --dashboard" in dashboard["ProgramArguments"][-1]
    assert dashboard["KeepAlive"] is True
    assert str(user_home / ".local" / "bin") in dashboard["EnvironmentVariables"]["PATH"]
    assert scheduler["Label"] == "com.octopusgarage.alcove.scheduler"
    assert "alcove service tick" in scheduler["ProgramArguments"][-1]
    assert scheduler["StartInterval"] == 900


def test_service_tick_materializes_routines_and_writes_stats(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "radar-items.json"
    fixture.write_text(
        '[{"title":"AI service signal","url":"https://example.test/ai","summary":"LLM"}]',
        encoding="utf-8",
    )
    RadarModule(home).upsert_definition(
        RadarDefinition(
            id="service-radar",
            name="Service Radar",
            schedule=RadarSchedule(enabled=True, ttl_hours=1),
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI", "LLM"], "min_score_threshold": 0.5},
        )
    )
    TasksModule(home=home).routine_add(
        AddRoutineRequest(
            title="Review local service",
            notes="Check deterministic tick.",
            tags=["service"],
            next_due="2026-07-10",
        )
    )

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        fix_health=True,
    )

    assert result["status"] == "ok"
    assert result["tasks"]["materialized"] == 1
    assert result["connectors"]["status"] == "skipped"
    assert result["watchers"]["status"] == "skipped"
    assert result["radars"]["status"] == "checked"
    assert result["radars"]["ran"] == 1
    assert (home.paths().stats / "summary.json").is_file()
    assert (home.root / "dashboard" / "snapshot.json").is_file()


def test_service_tick_sends_configured_task_digest(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    TasksModule(home=home).task_add(AddTaskRequest(title="Digest item"))
    notifications_path = home.paths().tasks / "notifications.yml"
    notifications_path.parent.mkdir(parents=True, exist_ok=True)
    notifications_path.write_text(
        "digests:\n  weekly:\n    enabled: true\n    day: sunday\n    notify: true\n",
        encoding="utf-8",
    )
    sent: list[str] = []

    def fake_send(*, home, text):
        sent.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("alcove.tasks.send_telegram_message", fake_send)

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        fix_health=False,
        today="2026-07-12",
    )

    assert result["task_notifications"]["sent"] == 1
    assert "weekly planner digest" in sent[0]


def test_service_tick_sends_configured_task_digest_to_multiple_sinks(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    TasksModule(home=home).task_add(AddTaskRequest(title="Digest sink item"))
    notifications_path = home.paths().tasks / "notifications.yml"
    notifications_path.parent.mkdir(parents=True, exist_ok=True)
    notifications_path.write_text(
        "\n".join(
            [
                "digests:",
                "  weekly:",
                "    enabled: true",
                "    day: sunday",
                "    notify: true",
                "    sinks:",
                "      - type: telegram",
                "      - type: feishu",
                "        webhook_env: ALCOVE_TEST_FEISHU",
                "",
            ]
        ),
        encoding="utf-8",
    )
    sent_telegram: list[str] = []
    sent_feishu: list[str] = []

    def fake_send_telegram(*, home, text):
        sent_telegram.append(text)
        return {"status": "sent"}

    def fake_send_feishu(*, home, sink, title, text, report_path=None):
        sent_feishu.append(f"{title}\n{text}")
        return {"status": "sent"}

    monkeypatch.setattr("alcove.tasks.send_telegram_message", fake_send_telegram)
    monkeypatch.setattr("alcove.tasks.send_feishu_message", fake_send_feishu)

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        fix_health=False,
        today="2026-07-12",
    )

    assert result["task_notifications"]["sent"] == 1
    notify = result["task_notifications"]["digests"][0]["notify"]
    assert notify["status"] == "sent"
    assert notify["sinks"]["telegram"]["status"] == "sent"
    assert notify["sinks"]["feishu"]["status"] == "sent"
    assert "Digest sink item" in sent_telegram[0]
    assert "Digest sink item" in sent_feishu[0]


def test_cli_service_install_status_and_tick(tmp_path, monkeypatch, capsys):
    user_home = tmp_path / "user-home"
    alcove_home = user_home / ".alcove"
    monkeypatch.setenv("HOME", str(user_home))

    install_code = main(
        [
            "service",
            "install",
            "--home",
            str(alcove_home),
            "--dashboard",
            "--json",
        ]
    )
    install_output = capsys.readouterr()
    status_code = main(["service", "status", "--home", str(alcove_home), "--dashboard", "--json"])
    status_output = capsys.readouterr()
    tick_code = main(
        [
            "service",
            "tick",
            "--home",
            str(alcove_home),
            "--skip-connectors",
            "--skip-watchers",
            "--skip-radars",
            "--json",
        ]
    )
    tick_output = capsys.readouterr()

    assert install_code == 0
    assert (
        plistlib.loads(
            (
                user_home / "Library/LaunchAgents/com.octopusgarage.alcove.dashboard.plist"
            ).read_bytes()
        )["Label"]
        == "com.octopusgarage.alcove.dashboard"
    )
    assert '"targets": [\n    "dashboard"\n  ]' in install_output.out
    assert status_code == 0
    assert '"installed": true' in status_output.out
    assert tick_code == 0
    assert '"status": "ok"' in tick_output.out
    assert '"radars": {\n    "status": "skipped"' in tick_output.out
