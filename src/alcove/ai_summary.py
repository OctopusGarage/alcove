from __future__ import annotations

from pathlib import Path
import shlex
import shutil
import subprocess
from typing import Any

from alcove.paths import compact_user_paths_in_text


def run_ai_summary(
    *,
    prompt: str,
    policy: dict[str, Any],
    cwd: Path | None = None,
) -> dict[str, Any]:
    provider = str(policy.get("provider") or "claude").strip().lower()
    timeout = _positive_int(policy.get("timeout_seconds"), default=180)
    command = _command(provider, policy)
    executable = shutil.which(command[0])
    if not executable:
        return {
            "status": "skipped",
            "provider": provider,
            "reason": f"{command[0]} is not available",
        }
    command[0] = executable
    try:
        result = subprocess.run(  # noqa: S603
            command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "provider": provider, "error": "AI summary timed out"}
    except OSError as exc:
        return {
            "status": "failed",
            "provider": provider,
            "error": compact_user_paths_in_text(str(exc)),
        }
    summary = result.stdout.strip()
    if result.returncode != 0:
        return {
            "status": "failed",
            "provider": provider,
            "error": compact_user_paths_in_text((result.stderr or result.stdout).strip())[:2000],
            "returncode": result.returncode,
        }
    if not summary:
        return {"status": "failed", "provider": provider, "error": "AI summary was empty"}
    return {"status": "completed", "provider": provider, "summary": summary}


def _command(provider: str, policy: dict[str, Any]) -> list[str]:
    configured = str(policy.get("command") or "").strip()
    if configured:
        command = shlex.split(configured)
    elif provider == "codex":
        command = ["codex", "exec", "--skip-git-repo-check", "--ephemeral", "-"]
    elif provider == "claude":
        command = ["claude", "-p"]
    else:
        raise ValueError(f"unsupported AI summary provider: {provider}")
    model = str(policy.get("model") or "").strip()
    if model:
        if provider == "codex":
            command.extend(["--model", model])
        elif provider == "claude":
            command.extend(["--model", model])
    if command[-1] != "-" and provider == "codex" and "exec" in command:
        command.append("-")
    return command


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default
