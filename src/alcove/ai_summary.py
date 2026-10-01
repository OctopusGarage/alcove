from __future__ import annotations

import os
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
    selected_provider = provider
    selected_command: list[str] | None = None
    availability_errors: list[str] = []
    for candidate_provider in _provider_candidates(provider, policy):
        command_template = _command(candidate_provider, policy)
        executables = _which_commands(command_template[0])
        if not executables:
            availability_errors.append(f"{command_template[0]} is not available")
            continue
        selected_usable_command: list[str] | None = None
        for executable in executables:
            command = list(command_template)
            command[0] = executable
            if candidate_provider == "codex" and not _codex_starts(executable):
                availability_errors.append(f"{command[0]} is not usable")
                continue
            selected_usable_command = command
            break
        if selected_usable_command is None:
            continue
        selected_provider = candidate_provider
        selected_command = selected_usable_command
        break
    if selected_command is None:
        return {
            "status": "skipped",
            "provider": provider,
            "reason": "; ".join(availability_errors) or f"{provider} is not available",
        }
    try:
        result = subprocess.run(  # noqa: S603
            selected_command,
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired:
        return {"status": "failed", "provider": selected_provider, "error": "AI summary timed out"}
    except OSError as exc:
        return {
            "status": "failed",
            "provider": selected_provider,
            "error": compact_user_paths_in_text(str(exc)),
        }
    summary = result.stdout.strip()
    if result.returncode != 0:
        return {
            "status": "failed",
            "provider": selected_provider,
            "error": compact_user_paths_in_text((result.stderr or result.stdout).strip())[:2000],
            "returncode": result.returncode,
        }
    if not summary:
        return {"status": "failed", "provider": selected_provider, "error": "AI summary was empty"}
    payload = {"status": "completed", "provider": selected_provider, "summary": summary}
    if selected_provider != provider:
        payload["fallback_from"] = provider
    return payload


def _provider_candidates(provider: str, policy: dict[str, Any]) -> list[str]:
    providers = [provider]
    fallback = str(policy.get("fallback_provider") or "").strip().lower()
    if not fallback and provider == "codex":
        fallback = "claude"
    if fallback and fallback not in providers:
        providers.append(fallback)
    return providers


def _which_commands(command: str) -> list[str]:
    candidates: list[str] = []
    executable = shutil.which(command)
    if executable:
        candidates.append(executable)
    for path in _path_bin_dirs():
        candidate = path / command
        if _executable_file(candidate):
            candidates.append(str(candidate))
    if command == "codex":
        for path in _nvm_bin_dirs():
            candidate = path / command
            if _executable_file(candidate):
                candidates.append(str(candidate))
    return list(dict.fromkeys(candidates))


def _executable_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_mode & 0o111 != 0


def _path_bin_dirs() -> list[Path]:
    return [Path(value) for value in os.environ.get("PATH", "").split(os.pathsep) if value]


def _codex_starts(executable: str) -> bool:
    try:
        result = subprocess.run(  # noqa: S603
            [executable, "--version"],
            input="",
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
            cwd=None,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _nvm_bin_dirs() -> list[Path]:
    root = Path.home() / ".nvm" / "versions" / "node"
    if not root.is_dir():
        return []
    return [path for path in sorted(root.glob("*/bin"), reverse=True) if path.is_dir()]


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
