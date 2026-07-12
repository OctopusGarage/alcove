from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
from typing import Any

import yaml

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.notifications import send_feishu_message, send_tcb_notification, send_telegram_message
from alcove.paths import compact_user_path, compact_user_paths_in_text


DEFAULT_TTL_HOURS = 24
SUPPORTED_KINDS = {"shell", "alcove", "git-sync", "agent"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class AutomationJob:
    id: str
    name: str
    kind: str
    enabled: bool = True
    order: int = 100
    ttl_hours: int = DEFAULT_TTL_HOURS
    timeout_seconds: int = 600
    cwd: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    repo_path: str = ""
    commit_message: str = ""
    provider: str = ""
    prompt: str = ""
    allow_service: bool = False
    notify: dict[str, Any] = field(default_factory=dict)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    checked_at: str = ""
    last_run_at: str = ""
    last_status: str = ""
    last_error: str = ""
    source: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutomationsModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home
        self.root = home.root / "automations"
        self.jobs_root = self.root / "jobs"
        self.runs_root = self.root / "runs"
        self.events_path = self.root / "events.jsonl"

    def add_shell(
        self,
        *,
        name: str,
        command: str,
        cwd: str = "",
        ttl_hours: int = DEFAULT_TTL_HOURS,
        timeout_seconds: int = 600,
        notify: bool = False,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        job = AutomationJob(
            id=self._unique_id(name),
            name=name.strip(),
            kind="shell",
            command=command.strip(),
            cwd=compact_user_path(Path(cwd).expanduser()) if cwd else "",
            ttl_hours=max(ttl_hours, 1),
            timeout_seconds=max(timeout_seconds, 1),
            notify={"enabled": notify, "on": "failure"},
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._write_job(job)
        return {"status": "added", "job": job.as_dict()}

    def add_git_sync(
        self,
        *,
        name: str,
        repo_path: str,
        commit_message: str = "chore: sync local data",
        ttl_hours: int = DEFAULT_TTL_HOURS,
        timeout_seconds: int = 60,
        notify: bool = False,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        repo = Path(repo_path).expanduser()
        job = AutomationJob(
            id=self._unique_id(name),
            name=name.strip(),
            kind="git-sync",
            repo_path=compact_user_path(repo),
            commit_message=commit_message.strip() or "chore: sync local data",
            ttl_hours=max(ttl_hours, 1),
            timeout_seconds=max(timeout_seconds, 1),
            notify={"enabled": notify, "on": "failure"},
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._write_job(job)
        return {"status": "added", "job": job.as_dict()}

    def list_jobs(self, *, status: str = "active") -> dict[str, Any]:
        jobs = [job.as_dict() for job in self._load_jobs() if (not status or job.status == status)]
        return {"count": len(jobs), "jobs": jobs}

    def run_due(self, *, now: str | None = None, allow_agent: bool = False) -> dict[str, Any]:
        timestamp = now or now_iso()
        results = []
        ran = 0
        skipped = 0
        failed = 0
        for job in self._enabled_jobs():
            if not self._is_due(job, timestamp):
                skipped += 1
                results.append({"id": job.id, "status": "skipped", "reason": "not_due"})
                continue
            result = self.run(job.id, allow_agent=allow_agent, service=True, timestamp=timestamp)
            results.append(result)
            if result.get("status") == "skipped":
                skipped += 1
            else:
                ran += 1
            if result.get("status") == "failed":
                failed += 1
        return {
            "status": "checked",
            "ran": ran,
            "skipped": skipped,
            "failed": failed,
            "jobs": results,
        }

    def run(
        self,
        job_id: str,
        *,
        allow_agent: bool = False,
        service: bool = False,
        timestamp: str | None = None,
    ) -> dict[str, Any]:
        timestamp = timestamp or now_iso()
        job = self._get_job(job_id)
        if job.status != "active":
            return {"id": job.id, "status": "skipped", "reason": f"job status is {job.status}"}
        if job.kind == "agent" and not (allow_agent or (service and job.allow_service)):
            return {
                "id": job.id,
                "status": "skipped",
                "reason": "agent job requires --allow-agent or allow_service",
            }
        result = self._run_job(job, timestamp=timestamp)
        updated = replace(
            job,
            checked_at=timestamp,
            last_run_at=timestamp,
            last_status=str(result.get("status") or ""),
            last_error=str(result.get("error") or ""),
            updated_at=timestamp,
        )
        self._write_job(updated)
        self._write_run(updated, result)
        self._record_event(updated, result, timestamp=timestamp)
        notify_payload = self._maybe_notify(updated, result)
        if notify_payload:
            result["notify"] = notify_payload
        return result

    def import_social_radar(self, source_home: str | Path) -> dict[str, Any]:
        source_root = Path(source_home).expanduser()
        config_path = source_root / "config" / "tasks.json"
        if not config_path.is_file():
            return {
                "status": "failed",
                "error": f"social-radar tasks config not found: {compact_user_path(config_path)}",
            }
        config = json.loads(config_path.read_text(encoding="utf-8"))
        imported: list[dict[str, Any]] = []
        skipped: list[dict[str, Any]] = []
        for entry in config.get("git_repos") or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "git-sync")
            imported.append(
                self._upsert_imported_job(
                    AutomationJob(
                        id=normalize_slug(name) or "git-sync",
                        name=name,
                        kind="git-sync",
                        enabled=bool(entry.get("enabled", True)),
                        order=200,
                        ttl_hours=24,
                        timeout_seconds=_positive_int(entry.get("timeout"), default=60),
                        repo_path=compact_user_path(str(entry.get("path") or "")),
                        commit_message=str(entry.get("commit_message") or "chore: sync local data"),
                        notify={"enabled": True, "on": "failure"},
                        source={
                            "system": "social-radar",
                            "path": compact_user_path(config_path),
                            "kind": "git_repos",
                        },
                    )
                )
            )
        for entry in config.get("tasks") or []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name") or "").strip()
            if not name:
                continue
            parsed = self._parse_social_radar_agent_task(source_root, name)
            if parsed is None:
                skipped.append({"name": name, "reason": "unsupported task module"})
                continue
            imported.append(
                self._upsert_imported_job(
                    AutomationJob(
                        id=normalize_slug(name) or "agent-task",
                        name=name,
                        kind="agent",
                        enabled=bool(entry.get("enabled", True)),
                        order=_positive_int(entry.get("order"), default=100),
                        ttl_hours=24,
                        timeout_seconds=_positive_int(entry.get("timeout"), default=600),
                        provider=parsed["provider"],
                        prompt=parsed["prompt"],
                        allow_service=False,
                        notify={"enabled": True, "on": "failure"},
                        source={
                            "system": "social-radar",
                            "path": parsed["path"],
                            "kind": "tasks",
                            "allow_service_review_required": True,
                        },
                    )
                )
            )
        return {
            "status": "imported",
            "source": compact_user_path(source_root),
            "imported": imported,
            "skipped": skipped,
        }

    def _run_job(self, job: AutomationJob, *, timestamp: str) -> dict[str, Any]:
        started = datetime.fromisoformat(timestamp)
        try:
            if job.kind == "shell":
                result = self._run_shell(job)
            elif job.kind == "alcove":
                result = self._run_alcove(job)
            elif job.kind == "git-sync":
                result = self._run_git_sync(job)
            elif job.kind == "agent":
                result = self._run_agent(job)
            else:
                result = {"status": "failed", "error": f"unsupported automation kind: {job.kind}"}
        except subprocess.TimeoutExpired as exc:
            result = {"status": "failed", "error": f"timed out after {exc.timeout}s"}
        except Exception as exc:  # pragma: no cover - defensive boundary for user commands
            result = {"status": "failed", "error": str(exc)}
        finished = datetime.now(UTC)
        duration_ms = int((finished - started).total_seconds() * 1000)
        result.update(
            {
                "id": job.id,
                "name": job.name,
                "kind": job.kind,
                "duration_ms": max(duration_ms, 0),
                "finished_at": finished.isoformat(timespec="seconds"),
            }
        )
        return result

    def _run_shell(self, job: AutomationJob) -> dict[str, Any]:
        if not job.command:
            return {"status": "failed", "error": "shell automation command is empty"}
        completed = subprocess.run(  # noqa: S602 - user-defined local automation command
            job.command,
            shell=True,
            cwd=str(_expand_path(job.cwd)) if job.cwd else None,
            text=True,
            capture_output=True,
            timeout=job.timeout_seconds,
            check=False,
        )
        return _completed_result(completed)

    def _run_alcove(self, job: AutomationJob) -> dict[str, Any]:
        if not job.args:
            return {"status": "failed", "error": "alcove automation args are empty"}
        executable = shutil.which("alcove")
        args = (
            [executable, *job.args] if executable else [sys.executable, "-m", "alcove", *job.args]
        )
        completed = subprocess.run(  # noqa: S603 - local alcove executable
            args,
            cwd=str(_expand_path(job.cwd)) if job.cwd else None,
            text=True,
            capture_output=True,
            timeout=job.timeout_seconds,
            check=False,
        )
        return _completed_result(completed)

    def _run_git_sync(self, job: AutomationJob) -> dict[str, Any]:
        if not job.repo_path:
            return {"status": "failed", "error": "git-sync repo_path is empty"}
        repo = _expand_path(job.repo_path)
        if not repo.exists():
            return {"status": "failed", "error": f"git repo not found: {compact_user_path(repo)}"}
        inside = self._git(repo, ["rev-parse", "--is-inside-work-tree"], job.timeout_seconds)
        if inside.returncode != 0:
            return _completed_result(inside)
        status = self._git(repo, ["status", "--porcelain"], job.timeout_seconds)
        if status.returncode != 0:
            return _completed_result(status)
        if not status.stdout.strip():
            return {"status": "success", "changed": False, "message": "no changes"}
        add = self._git(repo, ["add", "-A"], job.timeout_seconds)
        if add.returncode != 0:
            return _completed_result(add)
        commit = self._git(repo, ["commit", "-m", job.commit_message], job.timeout_seconds)
        if commit.returncode != 0:
            return _completed_result(commit)
        push = self._git(repo, ["push"], job.timeout_seconds)
        result = _completed_result(push)
        result["changed"] = result["status"] == "success"
        return result

    def _run_agent(self, job: AutomationJob) -> dict[str, Any]:
        provider = (job.provider or "claude").strip().lower()
        if provider == "claude":
            args = ["claude", "-p", job.prompt]
        elif provider == "codex":
            args = ["codex", "exec", job.prompt]
        else:
            return {"status": "failed", "error": f"unsupported agent provider: {provider}"}
        if not job.prompt.strip():
            return {"status": "failed", "error": "agent prompt is empty"}
        completed = subprocess.run(  # noqa: S603 - configured local agent CLI
            args,
            cwd=str(_expand_path(job.cwd)) if job.cwd else None,
            text=True,
            capture_output=True,
            timeout=job.timeout_seconds,
            check=False,
        )
        return _completed_result(completed)

    def _git(
        self, repo: Path, args: list[str], timeout_seconds: int
    ) -> subprocess.CompletedProcess[str]:
        git = shutil.which("git") or "/usr/bin/git"
        return subprocess.run(  # noqa: S603 - fixed git command with explicit args
            [git, "-C", str(repo), *args],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )

    def _enabled_jobs(self) -> list[AutomationJob]:
        return sorted(
            [job for job in self._load_jobs() if job.enabled and job.status == "active"],
            key=lambda item: (item.order, item.id),
        )

    def _is_due(self, job: AutomationJob, timestamp: str) -> bool:
        if not job.checked_at:
            return True
        checked_at = datetime.fromisoformat(job.checked_at)
        current = datetime.fromisoformat(timestamp)
        return current >= checked_at + timedelta(hours=max(job.ttl_hours, 1))

    def _load_jobs(self) -> list[AutomationJob]:
        if not self.jobs_root.is_dir():
            return []
        jobs = []
        for path in sorted(self.jobs_root.glob("*.yml")):
            payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(payload, dict):
                jobs.append(self._job(payload))
        return jobs

    def _get_job(self, job_id: str) -> AutomationJob:
        slug = normalize_slug(job_id)
        for job in self._load_jobs():
            if job.id == slug:
                return job
        raise FileNotFoundError(f"Automation job not found: {job_id}")

    def _write_job(self, job: AutomationJob) -> None:
        self.jobs_root.mkdir(parents=True, exist_ok=True)
        self._validate_job(job)
        path = self.jobs_root / f"{job.id}.yml"
        path.write_text(
            yaml.safe_dump(job.as_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _write_run(self, job: AutomationJob, result: dict[str, Any]) -> None:
        self.runs_root.mkdir(parents=True, exist_ok=True)
        suffix = now_iso().replace(":", "").replace("+", "Z")
        path = self.runs_root / f"{suffix}-{job.id}.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _record_event(self, job: AutomationJob, result: dict[str, Any], *, timestamp: str) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "type": "automation.run",
            "timestamp": timestamp,
            "job_id": job.id,
            "name": job.name,
            "kind": job.kind,
            "status": result.get("status"),
            "duration_ms": result.get("duration_ms"),
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _maybe_notify(self, job: AutomationJob, result: dict[str, Any]) -> dict[str, Any]:
        notify = job.notify or {}
        if not notify.get("enabled"):
            return {}
        mode = str(notify.get("on") or "failure").lower()
        if mode == "failure" and result.get("status") != "failed":
            return {}
        title = f"Alcove automation {job.name}: {result.get('status')}"
        lines = [
            f"Job: {job.name}",
            f"Kind: {job.kind}",
            f"Status: {result.get('status')}",
            f"Duration: {result.get('duration_ms', 0)} ms",
        ]
        if result.get("error"):
            lines.append(f"Error: {result['error']}")
        text = "\n".join(lines)
        sinks = notify.get("sinks") or [{"type": "telegram"}]
        payload: dict[str, Any] = {"status": "sent", "sinks": {}}
        for sink in sinks:
            if not isinstance(sink, dict):
                continue
            sink_type = str(sink.get("type") or "telegram")
            if sink_type == "telegram":
                sink_result = send_telegram_message(home=self.home, text=f"{title}\n\n{text}")
            elif sink_type == "feishu":
                sink_result = send_feishu_message(
                    home=self.home,
                    sink=sink,
                    title=title,
                    text=text,
                )
            elif sink_type == "tcb":
                sink_result = send_tcb_notification(
                    sink=sink,
                    title=title,
                    text=text,
                    attachments=[],
                )
            else:
                sink_result = {"status": "skipped", "reason": f"unsupported sink: {sink_type}"}
            payload["sinks"][sink_type] = sink_result
            if sink_result.get("status") not in {"sent", "skipped"}:
                payload["status"] = "partial"
        return payload

    def _job(self, payload: dict[str, Any]) -> AutomationJob:
        return AutomationJob(
            id=normalize_slug(str(payload.get("id") or payload.get("name") or "automation")),
            name=str(payload.get("name") or payload.get("id") or ""),
            kind=str(payload.get("kind") or "shell"),
            enabled=bool(payload.get("enabled", True)),
            order=_positive_int(payload.get("order"), default=100),
            ttl_hours=_positive_int(payload.get("ttl_hours"), default=DEFAULT_TTL_HOURS),
            timeout_seconds=_positive_int(payload.get("timeout_seconds"), default=600),
            cwd=str(payload.get("cwd") or ""),
            command=str(payload.get("command") or ""),
            args=[str(arg) for arg in payload.get("args") or []],
            repo_path=str(payload.get("repo_path") or ""),
            commit_message=str(payload.get("commit_message") or ""),
            provider=str(payload.get("provider") or ""),
            prompt=str(payload.get("prompt") or ""),
            allow_service=bool(payload.get("allow_service", False)),
            notify=dict(payload.get("notify") or {}),
            status=str(payload.get("status") or "active"),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            checked_at=str(payload.get("checked_at") or ""),
            last_run_at=str(payload.get("last_run_at") or ""),
            last_status=str(payload.get("last_status") or ""),
            last_error=str(payload.get("last_error") or ""),
            source=dict(payload.get("source") or {}),
        )

    def _validate_job(self, job: AutomationJob) -> None:
        if job.kind not in SUPPORTED_KINDS:
            raise ValueError(f"Unsupported automation kind: {job.kind}")
        if not job.id:
            raise ValueError("Automation job id is required")
        if not job.name:
            raise ValueError("Automation job name is required")

    def _unique_id(self, name: str) -> str:
        base = normalize_slug(name) or "automation"
        existing = {job.id for job in self._load_jobs()}
        if base not in existing:
            return base
        index = 2
        while f"{base}-{index}" in existing:
            index += 1
        return f"{base}-{index}"

    def _upsert_imported_job(self, job: AutomationJob) -> dict[str, Any]:
        timestamp = now_iso()
        existing_ids = {existing.id for existing in self._load_jobs()}
        target = job
        if job.id in existing_ids:
            existing = self._get_job(job.id)
            target = replace(
                job,
                created_at=existing.created_at or timestamp,
                updated_at=timestamp,
                checked_at=existing.checked_at,
                last_run_at=existing.last_run_at,
                last_status=existing.last_status,
                last_error=existing.last_error,
            )
        else:
            target = replace(job, created_at=timestamp, updated_at=timestamp)
        self._write_job(target)
        return target.as_dict()

    def _parse_social_radar_agent_task(
        self, source_root: Path, task_name: str
    ) -> dict[str, str] | None:
        for path in sorted((source_root / "tasks").glob("*.py")):
            text = path.read_text(encoding="utf-8")
            if task_name not in text or "ClaudeTask" not in text:
                continue
            prompt = _extract_python_prompt(text)
            if not prompt:
                continue
            return {
                "provider": "claude",
                "prompt": compact_user_paths_in_text(prompt),
                "path": compact_user_path(path),
            }
        return None


def _completed_result(completed: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = compact_user_paths_in_text(completed.stdout.strip())
    stderr = compact_user_paths_in_text(completed.stderr.strip())
    result: dict[str, Any] = {
        "status": "success" if completed.returncode == 0 else "failed",
        "exit_code": completed.returncode,
    }
    if stdout:
        result["stdout"] = stdout[-4000:]
    if stderr:
        result["stderr"] = stderr[-4000:]
    if completed.returncode != 0:
        result["error"] = (
            stderr or stdout or f"command failed with exit code {completed.returncode}"
        )
    return result


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(parsed, 1)


def _expand_path(path: str) -> Path:
    return Path(path).expanduser()


def _extract_python_prompt(text: str) -> str:
    constants = {
        match.group(1): match.group(2)
        for match in re.finditer(r"^([A-Z_]+)\s*=\s*[\"']([^\"']+)[\"']", text, re.MULTILINE)
    }
    prompt_match = re.search(r"prompt\s*=\s*f?[\"']([^\"']+)[\"']", text, re.DOTALL)
    if not prompt_match:
        return ""
    prompt = prompt_match.group(1)
    for key, value in constants.items():
        prompt = prompt.replace(f"{{{key}}}", value)
    return " ".join(shlex.split(prompt)) if "\n" not in prompt else prompt.strip()
