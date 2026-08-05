import json
import subprocess

import yaml

from alcove.automations import AutomationsModule
from alcove.cli import main
from alcove.home import AlcoveHome
from alcove.service import ServiceModule


def test_shell_automation_runs_and_records_state(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    output = tmp_path / "output.txt"
    module = AutomationsModule(home)
    added = module.add_shell(
        name="write marker",
        command=f"printf ok > {output}",
        timeout_seconds=5,
    )

    result = module.run(added["job"]["id"])

    assert result["status"] == "success"
    assert output.read_text(encoding="utf-8") == "ok"
    job_path = home.root / "automations/jobs/write-marker.yml"
    job = yaml.safe_load(job_path.read_text(encoding="utf-8"))
    assert job["last_status"] == "success"
    assert list((home.root / "automations/runs").glob("*write-marker.json"))


def test_repeated_automation_runs_preserve_distinct_run_records(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    output = tmp_path / "output.txt"
    module = AutomationsModule(home)
    module.add_shell(
        name="fast job",
        command=f"printf run >> {output}",
        timeout_seconds=5,
    )
    monkeypatch.setattr("alcove.automations.now_iso", lambda: "2026-07-29T01:02:03+00:00")

    first = module.run("fast-job")
    second = module.run("fast-job")

    assert first["status"] == "success"
    assert second["status"] == "success"
    assert output.read_text(encoding="utf-8") == "runrun"
    assert len(list((home.root / "automations/runs").glob("*fast-job.json"))) == 2


def test_run_due_skips_agent_jobs_unless_allowed(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    jobs = home.root / "automations/jobs"
    jobs.mkdir(parents=True)
    (jobs / "agent.yml").write_text(
        yaml.safe_dump(
            {
                "id": "agent",
                "name": "Agent",
                "kind": "agent",
                "enabled": True,
                "prompt": "summarize",
                "provider": "claude",
            }
        ),
        encoding="utf-8",
    )

    result = AutomationsModule(home).run_due()

    assert result["ran"] == 0
    assert result["skipped"] == 1
    assert result["jobs"][0]["reason"] == "agent job requires --allow-agent or allow_service"


def test_run_due_runs_active_jobs_in_order_and_ignores_disabled_jobs(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    output = tmp_path / "ordered.txt"
    module = AutomationsModule(home)
    late = module.add_shell(
        name="late job",
        command=f"printf late >> {output}",
        timeout_seconds=5,
    )["job"]
    early = module.add_shell(
        name="early job",
        command=f"printf early- >> {output}",
        timeout_seconds=5,
    )["job"]
    disabled = module.add_shell(
        name="disabled job",
        command=f"printf disabled >> {output}",
        timeout_seconds=5,
    )["job"]
    jobs = home.root / "automations" / "jobs"
    for job_id, order, enabled in [
        (late["id"], 20, True),
        (early["id"], 10, True),
        (disabled["id"], 5, False),
    ]:
        path = jobs / f"{job_id}.yml"
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        payload["order"] = order
        payload["enabled"] = enabled
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = module.run_due(now="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 2
    assert result["skipped"] == 0
    assert [job["id"] for job in result["jobs"]] == ["early-job", "late-job"]
    assert output.read_text(encoding="utf-8") == "early-late"


def test_run_due_handles_legacy_naive_checked_at(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    marker = tmp_path / "should-not-run.txt"
    module = AutomationsModule(home)
    module.add_shell(
        name="Legacy Automation",
        command=f"printf unexpected > {marker}",
        ttl_hours=24,
        timeout_seconds=5,
    )
    job_path = home.root / "automations/jobs/legacy-automation.yml"
    payload = yaml.safe_load(job_path.read_text(encoding="utf-8"))
    payload["checked_at"] = "2026-07-12T08:00:00"
    job_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    result = module.run_due(now="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 0
    assert result["skipped"] == 1
    assert result["jobs"][0]["reason"] == "not_due"
    assert not marker.exists()


def test_failed_shell_automation_persists_failure_state_and_run_event(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_shell(
        name="failing job",
        command="printf 'user-facing failure' >&2; exit 7",
        timeout_seconds=5,
    )

    result = module.run("failing-job", timestamp="2026-07-12T09:00:00+00:00")

    assert result["status"] == "failed"
    assert result["exit_code"] == 7
    assert result["error"] == "user-facing failure"
    job = yaml.safe_load((home.root / "automations/jobs/failing-job.yml").read_text())
    assert job["checked_at"] == "2026-07-12T09:00:00+00:00"
    assert job["last_run_at"] == "2026-07-12T09:00:00+00:00"
    assert job["last_status"] == "failed"
    assert job["last_error"] == "user-facing failure"
    run_payload = json.loads(
        next((home.root / "automations/runs").glob("*failing-job.json")).read_text()
    )
    assert run_payload["error"] == "user-facing failure"
    event = json.loads((home.root / "automations/events.jsonl").read_text().strip())
    assert event["job_id"] == "failing-job"
    assert event["status"] == "failed"


def test_git_sync_noop_reports_success(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    repo = tmp_path / "repo"
    repo.mkdir()
    module = AutomationsModule(home)
    module.add_git_sync(name="sync repo", repo_path=str(repo), timeout_seconds=5)
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args[-1] == "--is-inside-work-tree":
            return subprocess.CompletedProcess(args, 0, "true\n", "")
        if args[-1] == "--porcelain":
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("alcove.automations.subprocess.run", fake_run)

    result = module.run("sync-repo")

    assert result["status"] == "success"
    assert result["changed"] is False
    assert calls[0][1:3] == ["-C", str(repo)]


def test_git_sync_missing_repo_reports_compact_failure_without_git_calls(tmp_path, monkeypatch):
    user_home = tmp_path / "user-home"
    monkeypatch.setenv("HOME", str(user_home))
    home = AlcoveHome.init(user_home / ".alcove")
    missing_repo = user_home / "repos" / "missing"
    module = AutomationsModule(home)
    module.add_git_sync(name="missing repo", repo_path=str(missing_repo), timeout_seconds=5)

    result = module.run("missing-repo")

    assert result["status"] == "failed"
    assert result["error"] == "git repo not found: ~/repos/missing"


def test_agent_automation_rejects_unsupported_provider_without_calling_provider(
    tmp_path, monkeypatch
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_agent(
        name="local model job",
        prompt="summarize local files",
        provider="unsupported-provider",
        allow_service=True,
        timeout_seconds=5,
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("agent provider subprocess should not be called")

    monkeypatch.setattr("alcove.automations.subprocess.run", fail_if_called)

    result = module.run("local-model-job", allow_agent=True)

    assert result["status"] == "failed"
    assert result["error"] == "unsupported agent provider: unsupported-provider"


def test_run_due_reports_and_persists_unsupported_provider_failure(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_agent(
        name="scheduled local model job",
        prompt="summarize local files",
        provider="unsupported-provider",
        allow_service=True,
        timeout_seconds=5,
    )

    result = module.run_due(now="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 1
    assert result["failed"] == 1
    assert result["jobs"][0]["status"] == "failed"
    assert result["jobs"][0]["error"] == "unsupported agent provider: unsupported-provider"
    job = yaml.safe_load(
        (home.root / "automations/jobs/scheduled-local-model-job.yml").read_text(encoding="utf-8")
    )
    assert job["last_status"] == "failed"
    assert job["last_error"] == "unsupported agent provider: unsupported-provider"
    run_payload = json.loads(
        next((home.root / "automations/runs").glob("*scheduled-local-model-job.json")).read_text(
            encoding="utf-8"
        )
    )
    assert run_payload["status"] == "failed"
    event = json.loads((home.root / "automations/events.jsonl").read_text(encoding="utf-8"))
    assert event["job_id"] == "scheduled-local-model-job"
    assert event["status"] == "failed"


def test_cli_automation_add_list_run(tmp_path, capsys):
    home = tmp_path / ".alcove"
    marker = tmp_path / "marker.txt"
    add_code = main(
        [
            "automation",
            "add-shell",
            "--home",
            str(home),
            "marker",
            "--cmd",
            f"printf ok > {marker}",
            "--json",
        ]
    )
    capsys.readouterr()
    list_code = main(["automation", "list", "--home", str(home), "--json"])
    list_output = capsys.readouterr()
    run_code = main(["automation", "run", "--home", str(home), "marker", "--json"])
    run_output = capsys.readouterr()

    assert add_code == 0
    assert list_code == 0
    assert json.loads(list_output.out)["count"] == 1
    assert run_code == 0
    assert json.loads(run_output.out)["status"] == "success"
    assert marker.read_text(encoding="utf-8") == "ok"


def test_cli_automation_add_alcove_stores_args(tmp_path, capsys):
    home = tmp_path / ".alcove"

    add_code = main(
        [
            "automation",
            "add-alcove",
            "--home",
            str(home),
            "refresh dashboard",
            "--args",
            "dashboard refresh --json",
            "--cwd",
            str(tmp_path),
            "--ttl-hours",
            "6",
            "--timeout-seconds",
            "45",
            "--json",
        ]
    )
    add_output = capsys.readouterr()

    assert add_code == 0
    payload = json.loads(add_output.out)
    assert payload["job"]["kind"] == "alcove"
    assert payload["job"]["args"] == ["dashboard", "refresh", "--json"]
    assert payload["job"]["cwd"] == str(tmp_path)
    assert payload["job"]["ttl_hours"] == 6
    assert payload["job"]["timeout_seconds"] == 45


def test_cli_automation_add_agent_stores_guarded_job(tmp_path, capsys):
    home = tmp_path / ".alcove"

    add_code = main(
        [
            "automation",
            "add-agent",
            "--home",
            str(home),
            "daily review",
            "--prompt",
            "Summarize today's inbox",
            "--provider",
            "codex",
            "--allow-service",
            "--ttl-hours",
            "12",
            "--timeout-seconds",
            "90",
            "--json",
        ]
    )
    add_output = capsys.readouterr()

    assert add_code == 0
    payload = json.loads(add_output.out)
    assert payload["job"]["kind"] == "agent"
    assert payload["job"]["prompt"] == "Summarize today's inbox"
    assert payload["job"]["provider"] == "codex"
    assert payload["job"]["allow_service"] is True
    assert payload["job"]["ttl_hours"] == 12
    assert payload["job"]["timeout_seconds"] == 90


def test_service_tick_runs_due_automations(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    marker = tmp_path / "service-marker.txt"
    AutomationsModule(home).add_shell(
        name="service marker",
        command=f"printf service > {marker}",
        timeout_seconds=5,
    )

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        fix_health=False,
    )

    assert result["automations"]["ran"] == 1
    assert marker.read_text(encoding="utf-8") == "service"


def test_service_tick_tolerates_invalid_persisted_automation_mapping_fields(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    jobs = home.root / "automations" / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "bad-metadata.yml").write_text(
        "\n".join(
            [
                "id: bad-metadata",
                "name: Bad Metadata",
                "kind: shell",
                'command: "true"',
                "notify: enabled",
                "source: stale",
                "",
            ]
        ),
        encoding="utf-8",
    )

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_publishers=False,
        refresh_mounts=False,
        fix_health=False,
        today="2026-07-12",
    )

    assert result["status"] == "ok"
    assert result["automations"]["ran"] == 1
    assert result["automations"]["failed"] == 0
