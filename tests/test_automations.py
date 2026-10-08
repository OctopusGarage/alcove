import fcntl
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading

import pytest
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


@pytest.mark.parametrize(
    ("outcome", "expected_status"),
    [("success", "success"), ("error", "failed"), ("timeout", "failed")],
)
def test_scheduled_automation_duration_measures_execution_not_schedule_time(
    tmp_path, monkeypatch, outcome, expected_status
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_shell(name="timed job", command="test command", timeout_seconds=3, notify=True)
    scheduled_at = "2020-01-01T00:00:00+00:00"
    notifications = []

    def fake_run(command, **_kwargs):
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 3)
        return subprocess.CompletedProcess(command, 0 if outcome == "success" else 7, "", "error")

    monkeypatch.setattr("alcove.automations.subprocess.run", fake_run)
    monkeypatch.setattr(
        "alcove.automations.send_telegram_message",
        lambda *, home, text: notifications.append(text) or {"status": "sent"},
    )

    payload = module.run_due(now=scheduled_at)

    assert payload["ran"] == 1
    result = payload["jobs"][0]
    assert result["status"] == expected_status
    assert 0 <= result["duration_ms"] < 5000
    job = yaml.safe_load((home.root / "automations/jobs/timed-job.yml").read_text())
    assert job["checked_at"] == scheduled_at
    run = json.loads(next((home.root / "automations/runs").glob("*timed-job.json")).read_text())
    assert run["duration_ms"] == result["duration_ms"]
    event = json.loads((home.root / "automations/events.jsonl").read_text())
    assert event["timestamp"] == scheduled_at
    assert event["duration_ms"] == result["duration_ms"]
    assert len(notifications) == (0 if outcome == "success" else 1)
    if notifications:
        assert f"Duration: {result['duration_ms']} ms" in notifications[0]


def test_adding_automation_preserves_unreadable_job_file(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    jobs = home.root / "automations" / "jobs"
    jobs.mkdir(parents=True)
    existing = jobs / "backup.yml"
    original = "name: [unfinished\n"
    existing.write_text(original, encoding="utf-8")

    added = AutomationsModule(home).add_shell(name="backup", command="true")

    assert added["job"]["id"] == "backup-2"
    assert existing.read_text(encoding="utf-8") == original
    assert (jobs / "backup-2.yml").is_file()


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


def test_concurrent_automation_runs_preserve_distinct_run_records(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_shell(name="concurrent job", command="side-effect", timeout_seconds=5)
    fixed = "2026-07-29T01:02:03+00:00"
    monkeypatch.setattr("alcove.automations.now_iso", lambda: fixed)
    monkeypatch.setattr(
        "alcove.automations.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )
    loaded_barrier = threading.Barrier(2)
    original_get_job = module._get_job

    def synchronized_get_job(job_id):
        job = original_get_job(job_id)
        loaded_barrier.wait(timeout=5)
        return job

    monkeypatch.setattr(module, "_get_job", synchronized_get_job)
    run_path = home.root / "automations/runs/2026-07-29T010203Z0000-concurrent-job.json"
    second_open_started = threading.Event()
    first_open_completed = threading.Event()
    open_attempts = 0
    open_attempts_guard = threading.Lock()
    original_open = Path.open

    def synchronized_open(path, mode="r", *args, **kwargs):
        nonlocal open_attempts
        if path == run_path and mode == "x":
            with open_attempts_guard:
                open_attempts += 1
                attempt = open_attempts
            if attempt == 1:
                assert second_open_started.wait(timeout=5)
                handle = original_open(path, mode, *args, **kwargs)
                first_open_completed.set()
                return handle
            if attempt == 2:
                second_open_started.set()
                assert first_open_completed.wait(timeout=5)
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", synchronized_open)
    results: list[dict] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            results.append(module.run("concurrent-job", timestamp=fixed))
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert not any(thread.is_alive() for thread in threads)
    assert errors == []
    assert len(results) == 2
    assert open_attempts == 2
    assert len(list((home.root / "automations/runs").glob("*concurrent-job.json"))) == 2


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


def test_run_due_does_not_execute_job_with_quoted_false_enabled(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    jobs = home.root / "automations/jobs"
    jobs.mkdir(parents=True)
    (jobs / "disabled.yml").write_text(
        yaml.safe_dump(
            {
                "id": "disabled",
                "name": "Disabled",
                "kind": "shell",
                "command": "side-effect",
                "enabled": "false",
            }
        ),
        encoding="utf-8",
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("disabled job should not execute")

    monkeypatch.setattr("alcove.automations.subprocess.run", fail_if_called)

    result = AutomationsModule(home).run_due()

    assert result["ran"] == 0
    assert result["jobs"] == []


def test_run_due_guards_agent_with_quoted_false_allow_service(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    jobs = home.root / "automations/jobs"
    jobs.mkdir(parents=True)
    (jobs / "agent.yml").write_text(
        yaml.safe_dump(
            {
                "id": "agent",
                "name": "Agent",
                "kind": "agent",
                "provider": "codex",
                "prompt": "side-effect",
                "allow_service": "false",
            }
        ),
        encoding="utf-8",
    )

    def fail_if_called(*args, **kwargs):
        raise AssertionError("guarded agent should not execute")

    monkeypatch.setattr("alcove.automations.subprocess.run", fail_if_called)

    result = AutomationsModule(home).run_due()

    assert result["ran"] == 0
    assert result["skipped"] == 1
    assert result["jobs"][0]["reason"] == "agent job requires --allow-agent or allow_service"


def test_run_due_records_guarded_agent_skip_as_checked(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_agent(
        name="guarded agent",
        prompt="summarize",
        provider="claude",
        ttl_hours=24,
        allow_service=False,
    )

    first = module.run_due(now="2026-07-12T09:00:00+00:00")
    second = module.run_due(now="2026-07-12T09:01:00+00:00")

    assert first["jobs"] == [
        {
            "id": "guarded-agent",
            "status": "skipped",
            "reason": "agent job requires --allow-agent or allow_service",
        }
    ]
    assert second["jobs"] == [{"id": "guarded-agent", "status": "skipped", "reason": "not_due"}]
    job = yaml.safe_load(
        (home.root / "automations/jobs/guarded-agent.yml").read_text(encoding="utf-8")
    )
    assert job["checked_at"] == "2026-07-12T09:00:00+00:00"
    assert job["last_run_at"] == ""
    assert job["last_status"] == "skipped"


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


def test_overlapping_run_due_invocations_execute_job_once(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_shell(name="single run", command="side-effect", timeout_seconds=5)
    first_started = threading.Event()
    second_lock_attempted = threading.Event()
    release_first = threading.Event()
    calls: list[str] = []
    lock_attempts = 0
    lock_attempts_guard = threading.Lock()
    original_flock = fcntl.flock

    def observed_flock(fd, operation):
        nonlocal lock_attempts
        if operation == fcntl.LOCK_EX:
            with lock_attempts_guard:
                lock_attempts += 1
                if lock_attempts == 2:
                    second_lock_attempted.set()
        return original_flock(fd, operation)

    def blocked_run(command, **_kwargs):
        calls.append(command)
        first_started.set()
        assert release_first.wait(5)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("alcove.automations.subprocess.run", blocked_run)
    monkeypatch.setattr("alcove.automations.fcntl.flock", observed_flock)
    results: list[dict] = []

    def run_due() -> None:
        results.append(module.run_due(now="2026-07-12T09:00:00+00:00"))

    first = threading.Thread(target=run_due)
    second = threading.Thread(target=run_due)
    first.start()
    assert first_started.wait(5)
    second.start()
    assert second_lock_attempted.wait(5)
    release_first.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert len(calls) == 1
    assert sorted(result["ran"] for result in results) == [0, 1]
    assert sorted(result["skipped"] for result in results) == [0, 1]


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


def test_automation_run_rejects_event_log_symlink_without_appending_to_target(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_shell(name="event guard", command="true", timeout_seconds=5)
    target = tmp_path / "events-target.jsonl"
    target.write_text("keep me\n", encoding="utf-8")
    events_path = home.root / "automations/events.jsonl"
    events_path.parent.mkdir(parents=True, exist_ok=True)
    events_path.symlink_to(target)

    with pytest.raises(RuntimeError, match="Refusing to write automation event through symlink"):
        module.run("event-guard", timestamp="2026-07-12T09:00:00+00:00")

    assert target.read_text(encoding="utf-8") == "keep me\n"


def test_timed_out_automation_persists_actionable_failure_state(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_shell(name="slow job", command="sleep 60", timeout_seconds=3)

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=3)

    monkeypatch.setattr("alcove.automations.subprocess.run", timeout)

    result = module.run("slow-job", timestamp="2026-07-12T09:00:00+00:00")

    assert result["status"] == "failed"
    assert result["error"] == "timed out after 3s"
    job = yaml.safe_load((home.root / "automations/jobs/slow-job.yml").read_text())
    assert job["last_status"] == "failed"
    assert job["last_error"] == "timed out after 3s"
    run_payload = json.loads(
        next((home.root / "automations/runs").glob("*slow-job.json")).read_text()
    )
    assert run_payload["error"] == "timed out after 3s"
    event = json.loads((home.root / "automations/events.jsonl").read_text().strip())
    assert event["status"] == "failed"


def test_failed_automation_notifies_each_configured_sink_and_reports_partial_delivery(
    tmp_path, monkeypatch
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_shell(name="notified failure", command="exit 7", notify=True)
    job_path = home.root / "automations/jobs/notified-failure.yml"
    job = yaml.safe_load(job_path.read_text(encoding="utf-8"))
    job["notify"]["sinks"] = [
        {"type": "telegram", "name": "Operations"},
        {"type": "feishu", "name": "Operations"},
    ]
    job_path.write_text(yaml.safe_dump(job, sort_keys=False), encoding="utf-8")

    sent: list[str] = []

    def send_telegram(*, home, text):
        sent.append(text)
        return {"status": "sent"}

    def send_feishu(*, home, sink, title, text):
        sent.append(f"{title}\n{text}")
        return {"status": "failed", "error": "webhook unavailable"}

    monkeypatch.setattr("alcove.automations.send_telegram_message", send_telegram)
    monkeypatch.setattr("alcove.automations.send_feishu_message", send_feishu)

    result = module.run("notified-failure", timestamp="2026-07-12T09:00:00+00:00")

    assert result["status"] == "failed"
    assert result["notify"] == {
        "status": "partial",
        "sinks": {
            "operations": {"status": "sent"},
            "operations-2": {"status": "failed", "error": "webhook unavailable"},
        },
    }
    assert len(sent) == 2
    assert all("Status: failed" in message for message in sent)


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


def test_git_sync_pushes_existing_commit_when_worktree_is_clean(tmp_path, monkeypatch):
    remote = tmp_path / "remote.git"
    repo = tmp_path / "repo"
    git = shutil.which("git")
    assert git is not None
    for name in os.environ:
        if name.startswith("GIT_"):
            monkeypatch.delenv(name)

    def git_run(*args: str) -> str:
        result = subprocess.run(  # noqa: S603 - fixed git executable and local test paths
            [git, *args], check=True, capture_output=True, text=True
        )
        return result.stdout.strip()

    git_run("init", "--bare", str(remote))
    git_run("init", str(repo))
    git_run("-C", str(repo), "config", "user.name", "Alcove Test")
    git_run("-C", str(repo), "config", "user.email", "test@example.invalid")
    git_run("-C", str(repo), "remote", "add", "origin", str(remote))
    (repo / "note.txt").write_text("pending backup\n", encoding="utf-8")
    git_run("-C", str(repo), "add", "note.txt")
    git_run("-C", str(repo), "commit", "-m", "pending backup")
    git_run("-C", str(repo), "push", "-u", "origin", "HEAD")
    (repo / "note.txt").write_text("new backup\n", encoding="utf-8")
    git_run("-C", str(repo), "commit", "-am", "new backup")

    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_git_sync(name="sync repo", repo_path=str(repo), timeout_seconds=5)
    result = module.run("sync-repo")

    local_head = git_run("-C", str(repo), "rev-parse", "HEAD")
    remote_head = git_run("--git-dir", str(remote), "rev-parse", "HEAD")
    assert result["status"] == "success"
    assert local_head == remote_head


def test_run_due_reports_nonmapping_job_yaml_as_failure(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    jobs = home.root / "automations" / "jobs"
    jobs.mkdir(parents=True)
    (jobs / "broken.yml").write_text("- not-a-job\n", encoding="utf-8")

    result = AutomationsModule(home).run_due(now="2026-07-12T09:00:00+00:00")

    assert result["failed"] == 1
    assert result["jobs"][0]["id"] == "broken"
    assert "mapping" in result["jobs"][0]["error"]


def test_run_due_rejects_job_id_that_disagrees_with_filename(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    jobs = home.root / "automations" / "jobs"
    jobs.mkdir(parents=True)
    marker = tmp_path / "marker.txt"
    mismatched = jobs / "old-name.yml"
    mismatched.write_text(
        yaml.safe_dump(
            {"id": "new-name", "name": "Renamed", "kind": "shell", "command": f"touch {marker}"}
        ),
        encoding="utf-8",
    )

    result = AutomationsModule(home).run_due(now="2026-07-12T09:00:00+00:00")

    assert result["ran"] == 0
    assert result["failed"] == 1
    assert result["jobs"][0]["id"] == "old-name"
    assert "filename" in result["jobs"][0]["error"]
    assert not marker.exists()
    assert not (jobs / "new-name.yml").exists()


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


def test_git_sync_commit_failure_does_not_push_and_records_failure(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    repo = tmp_path / "repo"
    repo.mkdir()
    module = AutomationsModule(home)
    module.add_git_sync(name="sync repo", repo_path=str(repo), timeout_seconds=5)
    calls = []

    def fake_git(_repo, args, _timeout):
        calls.append(args)
        if args[0] == "commit":
            return subprocess.CompletedProcess(args, 1, "", "commit rejected")
        output = "M changed.txt\n" if args[0] == "status" else ""
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(module, "_git", fake_git)

    result = module.run("sync-repo", timestamp="2026-07-12T09:00:00+00:00")

    assert any(args[0] == "commit" for args in calls)
    assert not any(args[0] == "push" for args in calls)
    assert result["status"] == "failed"
    assert result["error"] == "commit rejected"
    job = yaml.safe_load((home.root / "automations/jobs/sync-repo.yml").read_text())
    assert job["last_status"] == "failed"
    assert job["last_error"] == "commit rejected"


def test_git_sync_push_failure_is_not_reported_as_synced(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    repo = tmp_path / "repo"
    repo.mkdir()
    module = AutomationsModule(home)
    module.add_git_sync(name="sync repo", repo_path=str(repo), timeout_seconds=5)
    calls = []

    def fake_git(_repo, args, _timeout):
        calls.append(args)
        if args[0] == "push":
            return subprocess.CompletedProcess(args, 128, "", "remote unavailable")
        output = "M changed.txt\n" if args[0] == "status" else ""
        return subprocess.CompletedProcess(args, 0, output, "")

    monkeypatch.setattr(module, "_git", fake_git)

    result = module.run("sync-repo", timestamp="2026-07-12T09:00:00+00:00")

    assert any(args[0] == "push" for args in calls)
    assert result["status"] == "failed"
    assert result["changed"] is False
    assert result["error"] == "remote unavailable"
    job = yaml.safe_load((home.root / "automations/jobs/sync-repo.yml").read_text())
    assert job["last_status"] == "failed"
    assert job["last_error"] == "remote unavailable"
    run = json.loads(next((home.root / "automations/runs").glob("*sync-repo.json")).read_text())
    assert run["status"] == "failed"
    assert run["changed"] is False


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


@pytest.mark.parametrize(
    ("provider", "allow_agent", "allow_service", "outcome", "expected_command"),
    [
        ("claude", True, False, "success", ["claude", "-p", "Summarize inbox"]),
        ("codex", False, True, "success", ["codex", "exec", "Summarize inbox"]),
        ("claude", False, True, "error", ["claude", "-p", "Summarize inbox"]),
        ("codex", True, False, "timeout", ["codex", "exec", "Summarize inbox"]),
    ],
)
def test_allowed_agent_run_due_dispatches_and_records_outcome(
    tmp_path, monkeypatch, provider, allow_agent, allow_service, outcome, expected_command
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    cwd = tmp_path / "agent-work"
    cwd.mkdir()
    module = AutomationsModule(home)
    module.add_agent(
        name="inbox review",
        prompt="Summarize inbox",
        provider=provider,
        cwd=str(cwd),
        allow_service=allow_service,
        timeout_seconds=7,
    )
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if outcome == "timeout":
            raise subprocess.TimeoutExpired(command, 7)
        return subprocess.CompletedProcess(
            command,
            0 if outcome == "success" else 9,
            "summary\n",
            "provider failed\n" if outcome == "error" else "",
        )

    monkeypatch.setattr("alcove.automations.subprocess.run", fake_run)
    timestamp = "2026-07-12T09:00:00+00:00"

    payload = module.run_due(now=timestamp, allow_agent=allow_agent)

    assert calls == [
        (
            expected_command,
            {
                "cwd": str(cwd),
                "text": True,
                "capture_output": True,
                "timeout": 7,
                "check": False,
            },
        )
    ]
    expected_status = "success" if outcome == "success" else "failed"
    assert payload["ran"] == 1
    assert payload["failed"] == (0 if outcome == "success" else 1)
    result = payload["jobs"][0]
    assert result["status"] == expected_status
    if outcome == "timeout":
        assert result["error"] == "timed out after 7s"
    else:
        assert result["exit_code"] == (0 if outcome == "success" else 9)
        assert result["stdout"] == "summary"
        if outcome == "error":
            assert result["error"] == "provider failed"

    job = yaml.safe_load((home.root / "automations/jobs/inbox-review.yml").read_text())
    assert job["checked_at"] == timestamp
    assert job["last_run_at"] == timestamp
    assert job["last_status"] == expected_status
    assert job["last_error"] == result.get("error", "")
    run = json.loads(next((home.root / "automations/runs").glob("*inbox-review.json")).read_text())
    assert run == result
    event = json.loads((home.root / "automations/events.jsonl").read_text())
    assert event["timestamp"] == timestamp
    assert event["job_id"] == "inbox-review"
    assert event["status"] == expected_status
    assert event["duration_ms"] == result["duration_ms"]


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


def test_cli_automation_run_failure_returns_nonzero_with_json(tmp_path, capsys):
    home = AlcoveHome.init(tmp_path / ".alcove")
    AutomationsModule(home).add_shell(name="failing command", command="exit 7")

    code = main(["automation", "run", "--home", str(home.root), "failing-command", "--json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "failed"
    assert payload["exit_code"] == 7


def test_cli_automation_run_due_failure_returns_nonzero_with_json(tmp_path, capsys):
    home = AlcoveHome.init(tmp_path / ".alcove")
    AutomationsModule(home).add_shell(name="failing command", command="exit 7")

    code = main(["automation", "run-due", "--home", str(home.root), "--json"])

    assert code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["failed"] == 1
    assert payload["jobs"][0]["status"] == "failed"


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


def test_service_tick_uses_today_for_automation_due_checks(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    marker = tmp_path / "should-not-run.txt"
    AutomationsModule(home).add_shell(
        name="daily marker",
        command=f"printf unexpected > {marker}",
        ttl_hours=24,
        timeout_seconds=5,
    )
    job_path = home.root / "automations" / "jobs" / "daily-marker.yml"
    job = yaml.safe_load(job_path.read_text(encoding="utf-8"))
    job["checked_at"] = "2026-07-10T00:00:00+00:00"
    job_path.write_text(yaml.safe_dump(job, sort_keys=False), encoding="utf-8")

    result = ServiceModule(home).tick(
        refresh_connectors=False,
        check_watchers=False,
        check_blogs=False,
        check_radars=False,
        run_publishers=False,
        refresh_mounts=False,
        fix_health=False,
        today="2026-07-10",
    )

    assert result["automations"]["ran"] == 0
    assert result["automations"]["jobs"] == [
        {"id": "daily-marker", "status": "skipped", "reason": "not_due"}
    ]
    assert not marker.exists()
    persisted = yaml.safe_load(job_path.read_text(encoding="utf-8"))
    assert persisted["checked_at"] == "2026-07-10T00:00:00+00:00"


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


def test_automation_run_rejects_job_file_symlink_without_overwriting_target(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    jobs_root = home.root / "automations" / "jobs"
    jobs_root.mkdir(parents=True)
    target = tmp_path / "do-not-clobber.yml"
    target.write_text(
        yaml.safe_dump(
            {
                "id": "linked-job",
                "name": "Linked Job",
                "kind": "shell",
                "command": "true",
                "enabled": True,
            }
        ),
        encoding="utf-8",
    )
    (jobs_root / "linked-job.yml").symlink_to(target)

    with pytest.raises(RuntimeError, match="Refusing to write automation job through symlink"):
        AutomationsModule(home).run("linked-job", timestamp="2026-07-12T09:00:00+00:00")

    payload = yaml.safe_load(target.read_text(encoding="utf-8"))
    assert "checked_at" not in payload
    assert "last_status" not in payload


def test_automation_run_rejects_run_record_symlink_without_writing_target(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = AutomationsModule(home)
    module.add_shell(name="run record guard", command="true", timeout_seconds=5)
    monkeypatch.setattr("alcove.automations.now_iso", lambda: "2026-07-12T09:00:00+00:00")
    runs_root = home.root / "automations" / "runs"
    runs_root.mkdir(parents=True)
    target = tmp_path / "run-record-target.json"
    (runs_root / "2026-07-12T090000Z0000-run-record-guard.json").symlink_to(target)

    with pytest.raises(RuntimeError, match="Refusing to write automation run through symlink"):
        module.run("run-record-guard", timestamp="2026-07-12T09:00:00+00:00")

    assert not target.exists()
