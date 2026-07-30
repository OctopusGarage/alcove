from __future__ import annotations

from datetime import datetime
import json
import plistlib
import shutil

from alcove.home import AlcoveHome
from alcove.cli import main
from alcove.mounts import AddMountRequest, MountsModule
from alcove.radars import RadarDefinition, RadarModule, RadarSchedule, RadarSource
from alcove.service import ServiceModule
from alcove.service_mount_refresh import ServiceMountRefresh
from alcove.service_task_health import build_task_health_summary, task_health_notification_text
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


def test_service_launchd_path_includes_nvm_codex_bin(tmp_path, monkeypatch):
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    nvm_bin = user_home / ".nvm" / "versions" / "node" / "v24.13.1" / "bin"
    nvm_bin.mkdir(parents=True)
    (nvm_bin / "codex").write_text("#!/bin/sh\n", encoding="utf-8")
    (nvm_bin / "codex").chmod(0o755)

    original_which = shutil.which

    def fake_which(command: str) -> str | None:
        if command == "codex":
            return str(nvm_bin / "codex")
        return original_which(command)

    monkeypatch.setattr("alcove.service_launchd.shutil.which", fake_which)
    home = AlcoveHome.init(user_home / ".alcove")

    ServiceModule(home).install(dashboard=False, scheduler=True)

    scheduler_plist = user_home / "Library/LaunchAgents/com.octopusgarage.alcove.scheduler.plist"
    scheduler = plistlib.loads(scheduler_plist.read_bytes())
    path_entries = scheduler["EnvironmentVariables"]["PATH"].split(":")
    assert str(nvm_bin) in path_entries
    assert len(path_entries) == len(set(path_entries))


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


def test_service_tick_tolerates_invalid_persisted_radar_ttl_hours(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    definition_path = home.root / "radars" / "definitions" / "bad-radar.yml"
    definition_path.parent.mkdir(parents=True, exist_ok=True)
    definition_path.write_text(
        """
schema: alcove/radar-definition/v1
id: bad-radar
name: Bad Radar
schedule:
  enabled: false
  ttl_hours: hourly
sources:
  - id: fixture
    adapter: fixture
""",
        encoding="utf-8",
    )

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        run_automations=False,
        run_publishers=False,
        refresh_mounts=False,
        fix_health=False,
        today="2026-07-12",
    )

    assert result["status"] == "ok"
    assert result["radars"]["skipped"] == 1
    assert result["radars"]["errors"] == 0
    assert (home.root / "dashboard" / "snapshot.json").is_file()


def test_service_tick_tolerates_malformed_connector_source_yaml(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    source_path = home.root / "connectors" / "github-stars" / "sources" / "broken.yml"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    source_path.write_text("source: [", encoding="utf-8")

    result = ServiceModule(home).tick(
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        run_publishers=False,
        refresh_mounts=False,
        fix_health=False,
        today="2026-07-12",
    )

    assert result["status"] == "ok"
    assert result["connectors"]["status"] == "refreshed"
    assert result["health"]["issue_count"] >= 1
    assert (home.root / "dashboard" / "snapshot.json").is_file()


def test_service_tick_tolerates_malformed_publisher_definition_yaml(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    definition_path = home.root / "publishers" / "definitions" / "broken.yml"
    definition_path.parent.mkdir(parents=True, exist_ok=True)
    definition_path.write_text("targets: [", encoding="utf-8")

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        refresh_mounts=False,
        fix_health=False,
        today="2026-07-12",
    )

    assert result["status"] == "ok"
    assert result["publishers"]["status"] == "checked"
    assert result["health"]["issue_count"] >= 1
    assert (home.root / "dashboard" / "snapshot.json").is_file()


def test_service_tick_tolerates_malformed_mount_registry_json(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    mounts_path = home.paths().mounts / "mounts.json"
    mounts_path.parent.mkdir(parents=True, exist_ok=True)
    mounts_path.write_text('{"mounts": [', encoding="utf-8")

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        run_publishers=False,
        fix_health=True,
        today="2026-07-12",
    )

    assert result["status"] == "ok"
    assert result["mounts"]["status"] == "skipped"
    assert result["mounts"]["reason"] == "no_mounts"
    assert result["health"]["issue_count"] >= 1
    assert (home.root / "dashboard" / "snapshot.json").is_file()


def test_service_tick_tolerates_malformed_project_registry_json(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    projects_path = home.paths().projects / "projects.json"
    projects_path.parent.mkdir(parents=True, exist_ok=True)
    projects_path.write_text('{"projects": [', encoding="utf-8")

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        run_publishers=False,
        refresh_mounts=False,
        fix_health=True,
        today="2026-07-12",
    )

    assert result["status"] == "ok"
    assert result["health"]["issue_count"] >= 1
    assert (home.root / "dashboard" / "snapshot.json").is_file()


def test_service_tick_refreshes_mounts_every_two_days(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    source = tmp_path / "mounted-docs"
    source.mkdir()
    note = source / "README.md"
    note.write_text("# Mounted Docs\n\nInitial indexed content.", encoding="utf-8")
    mount = MountsModule(home=home).add(
        AddMountRequest(path=str(source), name="Mounted Docs", mount_type="local-folder")
    )

    first = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        run_publishers=False,
        fix_health=False,
        today="2026-07-10",
    )
    second = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        run_publishers=False,
        fix_health=False,
        today="2026-07-10",
    )
    note.write_text("# Mounted Docs\n\nUpdated indexed content.", encoding="utf-8")
    third = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        run_publishers=False,
        fix_health=False,
        today="2026-07-12",
    )

    assert first["mounts"]["status"] == "checked"
    assert first["mounts"]["checked"] == 1
    assert first["mounts"]["refreshed"] == 1
    assert first["mounts"]["scanned"] == 1
    assert second["mounts"]["status"] == "skipped"
    assert second["mounts"]["reason"] == "not_due"
    assert third["mounts"]["status"] == "checked"
    assert third["mounts"]["checked"] == 1
    assert third["mounts"]["scanned"] == 1
    items = MountsModule(home=home).scan(mount.id)["items"]
    assert items[0]["text"] == "# Mounted Docs\n\nUpdated indexed content."


def test_service_mount_refresh_tolerates_malformed_state_json(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    source = tmp_path / "mounted-docs"
    source.mkdir()
    (source / "README.md").write_text(
        "# Mounted Docs\n\nInitial indexed content.", encoding="utf-8"
    )
    MountsModule(home=home).add(
        AddMountRequest(path=str(source), name="Mounted Docs", mount_type="local-folder")
    )
    state_path = home.paths().stats / "service-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text('{"mounts": [', encoding="utf-8")

    result = ServiceMountRefresh(home).run(interval_days=2, today="2026-07-10")

    assert result["status"] == "checked"
    assert result["checked"] == 1
    assert result["refreshed"] == 1
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["mounts"]["last_refreshed_at"] == "2026-07-10T00:00:00+00:00"


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


def test_service_tick_builds_and_notifies_task_health_when_enabled(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    telegram: list[str] = []
    feishu: list[str] = []

    def fake_telegram(*, home, text):
        telegram.append(text)
        return {"status": "sent"}

    def fake_feishu(*, home, sink, title, text, report_path=None):
        feishu.append(f"{title}\n{text}")
        return {"status": "sent"}

    monkeypatch.setattr("alcove.service.send_telegram_message", fake_telegram)
    monkeypatch.setattr("alcove.service.send_feishu_message", fake_feishu)

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_automations=False,
        run_publishers=False,
        refresh_mounts=False,
        fix_health=False,
        notify_task_health=True,
        today="2026-07-12",
    )

    assert result["task_health"]["status"] == "failed"
    assert result["task_health"]["checked"] == 8
    assert result["task_health"]["failed"] >= 1
    assert result["task_health_notification"]["status"] == "sent"
    assert telegram[0].startswith("Alcove 任务健康 · 2026-07-12")
    assert "整体状态：需要处理" in telegram[0]
    assert "已检查模块：8 个；失败：1 个；跳过：7 个。" in telegram[0]
    assert "模块结果：" in telegram[0]
    assert "连接器：跳过" in telegram[0]
    assert "健康检查：异常 · 问题 2 个；修复动作 0 个" in telegram[0]
    assert "跳过原因" not in telegram[0]
    assert "refreshed=0" not in telegram[0]
    assert "Status:" not in telegram[0]
    assert "Alcove task health: 2026-07-12" in feishu[0]


def test_task_health_summary_classifies_failed_and_skipped_modules():
    summary = build_task_health_summary(
        {
            "connectors": {"status": "skipped", "refreshed": 0, "skipped": 0, "errors": 0},
            "watchers": {"status": "checked", "checked": 1, "changed": 0, "errors": 2},
            "blogs": {"status": "checked", "checked": 1, "new": 0, "errors": 0},
            "radars": {"status": "checked", "ran": 1, "skipped": 0, "errors": 0},
            "automations": {"status": "checked", "ran": 0, "skipped": 0, "failed": 0},
            "publishers": {"status": "checked", "ran": 1, "updated": 0, "errors": 0},
            "mounts": {"status": "checked", "checked": 1, "refreshed": 0, "skipped": 1},
            "health": {"status": "ok", "issue_count": 0, "action_count": 2},
        }
    )

    assert summary["status"] == "failed"
    assert summary["checked"] == 8
    assert summary["failed"] == 1
    assert summary["skipped"] == 1
    assert summary["checks"][0] == {
        "module": "connectors",
        "status": "skipped",
        "summary": "refreshed=0 skipped=0 errors=0",
    }
    assert summary["checks"][1] == {
        "module": "watchers",
        "status": "failed",
        "summary": "checked=1 changed=0 errors=2",
        "error": "watchers reported errors=2",
    }


def test_task_health_notification_reports_radar_last_run_health_without_skip_noise():
    text = task_health_notification_text(
        {
            "status": "success",
            "checked": 8,
            "failed": 0,
            "skipped": 0,
            "checks": [
                {
                    "module": "radars",
                    "status": "success",
                    "summary": "ran=0 skipped=4 errors=0",
                }
            ],
        },
        day="2026-07-29",
    )

    assert "雷达：正常 · 上次运行成功；本轮运行 0 个；错误 0 个" in text
    assert "跳过 4 个" not in text
    assert "未到执行条件" not in text


def test_task_health_notification_resends_when_prior_send_used_legacy_format(
    tmp_path,
    monkeypatch,
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    state_path = home.paths().stats / "service-state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        '{"task_health_notifications": {"2026-07-29": "sent"}}\n',
        encoding="utf-8",
    )
    telegram: list[str] = []

    def fake_telegram(*, home, text):
        telegram.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("alcove.service.send_telegram_message", fake_telegram)
    monkeypatch.setattr(
        "alcove.service.send_feishu_message",
        lambda **_kwargs: {"status": "skipped"},
    )

    first = ServiceModule(home)._notify_task_health_once_per_day(
        {"status": "success", "checked": 8, "failed": 0, "skipped": 0, "checks": []},
        tick_time=datetime.fromisoformat("2026-07-29T12:00:00+00:00"),
    )
    second = ServiceModule(home)._notify_task_health_once_per_day(
        {"status": "success", "checked": 8, "failed": 0, "skipped": 0, "checks": []},
        tick_time=datetime.fromisoformat("2026-07-29T12:05:00+00:00"),
    )
    state = json.loads(state_path.read_text(encoding="utf-8"))

    assert first["status"] == "partial"
    assert second == {
        "status": "skipped",
        "reason": "already_sent",
        "day": "2026-07-29",
    }
    assert len(telegram) == 1
    assert telegram[0].startswith("Alcove 任务健康 · 2026-07-29")
    assert state["task_health_notifications"]["2026-07-29"]["status"] == "sent"
    assert state["task_health_notifications"]["2026-07-29"]["version"] == 2


def test_cli_service_tick_can_skip_task_health_notification(tmp_path, monkeypatch, capsys):
    home = AlcoveHome.init(tmp_path / ".alcove")
    telegram: list[str] = []

    def fake_telegram(*, home, text):
        telegram.append(text)
        return {"status": "sent"}

    monkeypatch.setattr("alcove.service.send_telegram_message", fake_telegram)

    code = main(
        [
            "service",
            "tick",
            "--home",
            str(home.root),
            "--skip-connectors",
            "--skip-watchers",
            "--skip-blogs",
            "--skip-radars",
            "--skip-automations",
            "--skip-publishers",
            "--skip-mounts",
            "--skip-health-fix",
            "--skip-task-health-notify",
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    assert telegram == []
    assert '"task_health": {' in output.out
    assert "task_health_notification" not in output.out


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
            "--skip-task-health-notify",
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
    assert str(user_home) not in install_output.out
    assert "~/Library/LaunchAgents/com.octopusgarage.alcove.dashboard.plist" in install_output.out
    assert status_code == 0
    assert '"installed": true' in status_output.out
    assert str(user_home) not in status_output.out
    assert "~/Library/LaunchAgents/com.octopusgarage.alcove.dashboard.plist" in status_output.out
    assert tick_code == 0
    assert '"status": "ok"' in tick_output.out
    assert '"radars": {\n    "status": "skipped"' in tick_output.out


def test_cli_service_uninstall_removes_selected_launch_agent(tmp_path, monkeypatch, capsys):
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
    capsys.readouterr()
    dashboard_plist = user_home / "Library/LaunchAgents/com.octopusgarage.alcove.dashboard.plist"
    assert install_code == 0
    assert dashboard_plist.is_file()

    uninstall_code = main(
        [
            "service",
            "uninstall",
            "--home",
            str(alcove_home),
            "--dashboard",
            "--json",
        ]
    )
    uninstall_output = capsys.readouterr()

    assert uninstall_code == 0
    assert not dashboard_plist.exists()
    assert '"status": "uninstalled"' in uninstall_output.out
    assert '"action": "removed"' in uninstall_output.out
    assert str(user_home) not in uninstall_output.out
    assert "~/Library/LaunchAgents/com.octopusgarage.alcove.dashboard.plist" in uninstall_output.out
