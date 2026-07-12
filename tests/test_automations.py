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


def test_import_social_radar_tasks_and_git_repos(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    source = tmp_path / ".social_radar"
    (source / "config").mkdir(parents=True)
    (source / "tasks").mkdir()
    (source / "config/tasks.json").write_text(
        json.dumps(
            {
                "tasks": [
                    {"name": "apple_notes_export", "enabled": True, "order": 1, "timeout": 600}
                ],
                "git_repos": [
                    {
                        "name": "notes_repo",
                        "path": str(tmp_path / "notes"),
                        "enabled": True,
                        "commit_message": "chore: sync notes",
                        "timeout": 60,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (source / "tasks/apple_notes_backup.py").write_text(
        "\n".join(
            [
                "from scripts.tasks.base import ClaudeTask",
                'BACKUP_DIR = "/Users/example/notes"',
                "class AppleNotesExportTask(ClaudeTask):",
                '    name = "apple_notes_export"',
                "    def __init__(self):",
                '        super().__init__(name=self.name, prompt=f"Export to {BACKUP_DIR}")',
                "task = AppleNotesExportTask()",
            ]
        ),
        encoding="utf-8",
    )

    result = AutomationsModule(home).import_social_radar(source)
    listed = AutomationsModule(home).list_jobs()

    assert result["status"] == "imported"
    assert {job["id"] for job in listed["jobs"]} == {"apple-notes-export", "notes-repo"}
    agent = next(job for job in listed["jobs"] if job["kind"] == "agent")
    assert agent["allow_service"] is False
    assert agent["prompt"] == "Export to ~/notes"


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
