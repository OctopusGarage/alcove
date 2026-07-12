from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import fnmatch
import json
import os
from pathlib import Path
import subprocess
import sys


SCHEMA = "alcove.agent_quality_gate.v1"
GIT = os.environ.get("GIT", "/usr/bin/git")


@dataclass(frozen=True)
class GateCommand:
    id: str
    display: str
    argv: tuple[str, ...]
    env: dict[str, str]
    reason: str


@dataclass(frozen=True)
class RiskRule:
    id: str
    label: str
    patterns: tuple[str, ...]
    suites: tuple[str, ...]
    requires_ai_eval: bool

    def matches(self, path: str) -> bool:
        return any(_matches_pattern(path, pattern) for pattern in self.patterns)


@dataclass(frozen=True)
class GatePlan:
    schema: str
    mode: str
    surface: str
    changed_files: tuple[str, ...]
    risk_areas: tuple[str, ...]
    commands: tuple[GateCommand, ...]
    requires_ai_eval: bool
    message: str

    @property
    def has_work(self) -> bool:
        return bool(self.commands)


CommandRunner = Callable[[GateCommand, Path], int]


SUITE_COMMANDS: dict[str, GateCommand] = {
    "smoke": GateCommand(
        id="smoke",
        display="scripts/smoke.sh",
        argv=("scripts/smoke.sh",),
        env={},
        reason="baseline isolated CLI/application regression coverage",
    ),
    "real_home": GateCommand(
        id="real_home",
        display="ALCOVE_REAL_SMOKE_REPORT_DIR=.tmp/real-home-smoke scripts/smoke-real-home.sh",
        argv=("scripts/smoke-real-home.sh",),
        env={"ALCOVE_REAL_SMOKE_REPORT_DIR": ".tmp/real-home-smoke"},
        reason="read-mostly coverage for configured local Alcove home data",
    ),
    "real_integrations": GateCommand(
        id="real_integrations",
        display="scripts/smoke-real-integrations.sh",
        argv=("scripts/smoke-real-integrations.sh",),
        env={},
        reason="real connector, capture, OCR, and MCP stdio boundary coverage",
    ),
    "agent_clients": GateCommand(
        id="agent_clients",
        display="scripts/smoke-agent-clients.sh",
        argv=("scripts/smoke-agent-clients.sh",),
        env={},
        reason="Codex, Claude, Hub, KB, and MCP client entry coverage",
    ),
    "mcp_matrix": GateCommand(
        id="mcp_matrix",
        display="scripts/smoke-mcp-matrix.sh",
        argv=("scripts/smoke-mcp-matrix.sh",),
        env={},
        reason="representative MCP tool payload and routing coverage",
    ),
    "dashboard_browser": GateCommand(
        id="dashboard_browser",
        display="scripts/smoke-dashboard-browser.sh",
        argv=("scripts/smoke-dashboard-browser.sh",),
        env={},
        reason="dashboard browser, route, and visual sanity coverage",
    ),
    "radar_reports": GateCommand(
        id="radar_reports",
        display="scripts/smoke-radar-reports.sh",
        argv=("scripts/smoke-radar-reports.sh",),
        env={},
        reason="four-radar report content and browser presentation coverage",
    ),
    "export_restore": GateCommand(
        id="export_restore",
        display="scripts/smoke-export-restore.sh",
        argv=("scripts/smoke-export-restore.sh",),
        env={},
        reason="export, restore, registry, and migration coverage",
    ),
    "messy_inbox": GateCommand(
        id="messy_inbox",
        display="scripts/smoke-messy-inbox.sh",
        argv=("scripts/smoke-messy-inbox.sh",),
        env={},
        reason="messy capture bundle, OCR, truncation, and inbox review coverage",
    ),
    "ai_packet": GateCommand(
        id="ai_packet",
        display="ALCOVE_AI_EVAL_PROVIDER=none scripts/eval-ai.sh",
        argv=("scripts/eval-ai.sh",),
        env={"ALCOVE_AI_EVAL_PROVIDER": "none"},
        reason="build the scoped deterministic evidence packet and AI eval prompt without a model call",
    ),
    "ai_review": GateCommand(
        id="ai_review",
        display="ALCOVE_AI_EVAL_SKIP_REFRESH=1 scripts/eval-ai.sh",
        argv=("scripts/eval-ai.sh",),
        env={"ALCOVE_AI_EVAL_SKIP_REFRESH": "1"},
        reason="ask the configured AI reviewer to judge the scoped product and agent-facing quality",
    ),
    "docs_alignment": GateCommand(
        id="docs_alignment",
        display="scripts/check-docs-drift.sh",
        argv=("scripts/check-docs-drift.sh",),
        env={},
        reason="Documentation alignment check for user-facing behavior and data contract changes",
    ),
    "check": GateCommand(
        id="check",
        display="scripts/check.sh",
        argv=("scripts/check.sh",),
        env={},
        reason="full lint, type, audit, test, diff, and secret gate",
    ),
}


RISK_RULES: tuple[RiskRule, ...] = (
    RiskRule(
        id="agent_entries",
        label="agent entry prompts and profile installation",
        patterns=(
            "AGENTS.md",
            "CLAUDE.md",
            ".agents/**",
            ".claude/**",
            ".codex/**",
            "src/alcove/profile_installer.py",
            "src/alcove/profile_packs.py",
            "tests/test_entry_profiles.py",
        ),
        suites=("agent_clients",),
        requires_ai_eval=True,
    ),
    RiskRule(
        id="ai_eval",
        label="AI eval packet, prompt, and reviewer contract",
        patterns=(
            "src/alcove/ai_eval.py",
            "scripts/eval-ai.sh",
            "scripts/verify/eval-ai.sh",
            "docs/evals/**",
            "tests/test_ai_eval.py",
        ),
        suites=("agent_clients", "mcp_matrix"),
        requires_ai_eval=True,
    ),
    RiskRule(
        id="search_okf",
        label="OKF, search, and read-path quality",
        patterns=(
            "src/alcove/okf*.py",
            "src/alcove/derived_okf.py",
            "src/alcove/search*.py",
            "src/alcove/connectors/okf_index.py",
            "docs/okf-profile.md",
            "docs/read-write-model.md",
            "tests/test_okf*.py",
            "tests/test_search.py",
        ),
        suites=("real_home", "mcp_matrix"),
        requires_ai_eval=True,
    ),
    RiskRule(
        id="mcp_cli",
        label="CLI, MCP, and application adapter routing",
        patterns=(
            "src/alcove/cli.py",
            "src/alcove/mcp_server.py",
            "src/alcove/application.py",
            "src/alcove/application_capabilities.py",
            "tests/test_cli.py",
            "tests/test_mcp_server.py",
        ),
        suites=("agent_clients", "mcp_matrix"),
        requires_ai_eval=True,
    ),
    RiskRule(
        id="inbox_capture",
        label="capture, inbox, archive, OCR, and source linking",
        patterns=(
            "src/alcove/inbox*.py",
            "src/alcove/knowledge.py",
            "src/alcove/linking.py",
            "scripts/verify/smoke-messy-inbox.sh",
            "tests/test_inbox.py",
            "tests/test_knowledge.py",
            "tests/test_linking.py",
        ),
        suites=("messy_inbox", "real_integrations"),
        requires_ai_eval=True,
    ),
    RiskRule(
        id="connectors_mounts",
        label="connectors, mounts, external indexes, and lazy fetch",
        patterns=(
            "src/alcove/connectors/**",
            "src/alcove/connector*.py",
            "src/alcove/external*.py",
            "src/alcove/mounts.py",
            "tests/test_apple_notes.py",
            "tests/test_chrome_bookmarks.py",
            "tests/test_external*.py",
            "tests/test_github_stars.py",
            "tests/test_mounts.py",
        ),
        suites=("real_home", "real_integrations", "mcp_matrix"),
        requires_ai_eval=True,
    ),
    RiskRule(
        id="dashboard",
        label="dashboard snapshot, rendering, browser behavior, and usage projection",
        patterns=(
            "frontend/dashboard/**",
            "src/alcove/dashboard*.py",
            "src/alcove/usage.py",
            "scripts/verify/smoke-dashboard-browser.sh",
            "tests/test_dashboard*.py",
            "tests/test_usage.py",
        ),
        suites=("real_home", "dashboard_browser"),
        requires_ai_eval=True,
    ),
    RiskRule(
        id="memory_writes",
        label="pins, prompts, projects, tasks, export, validation, and home data writes",
        patterns=(
            "src/alcove/exporter.py",
            "src/alcove/gardener.py",
            "src/alcove/home.py",
            "src/alcove/pins*.py",
            "src/alcove/projects.py",
            "src/alcove/prompts.py",
            "src/alcove/tasks.py",
            "src/alcove/validate.py",
            "src/alcove/workspace.py",
            "tests/test_export*.py",
            "tests/test_home.py",
            "tests/test_pins.py",
            "tests/test_projects.py",
            "tests/test_prompts.py",
            "tests/test_tasks.py",
            "tests/test_workspace.py",
        ),
        suites=("real_home", "export_restore", "mcp_matrix"),
        requires_ai_eval=False,
    ),
    RiskRule(
        id="verification_infra",
        label="verification scripts and quality gates",
        patterns=(
            "scripts/check.sh",
            "scripts/smoke*.sh",
            "scripts/verify/**",
            "src/alcove/verify_suites.py",
        ),
        suites=(
            "agent_clients",
            "mcp_matrix",
            "dashboard_browser",
            "radar_reports",
            "export_restore",
            "messy_inbox",
        ),
        requires_ai_eval=True,
    ),
    RiskRule(
        id="radars",
        label="configurable radars, presets, scoring, reporting, and radar browser reports",
        patterns=(
            "src/alcove/radars/**",
            "tests/test_radar*.py",
            "tests/test_radars.py",
            "docs/radars.md",
        ),
        suites=("real_home", "radar_reports"),
        requires_ai_eval=True,
    ),
)

DOCS_ALIGNMENT_RULE = RiskRule(
    id="docs_alignment",
    label="Documentation alignment for user-facing behavior, storage, and agent contracts",
    patterns=(),
    suites=("docs_alignment",),
    requires_ai_eval=False,
)

DOCS_ALIGNMENT_SOURCE_PATTERNS = (
    "src/alcove/**",
    "frontend/dashboard/**",
    "scripts/**",
    "pyproject.toml",
)

DOCS_ALIGNMENT_DOC_PATTERNS = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/**",
    ".agents/**",
    ".claude/**",
)

DOCS_ALIGNMENT_RISK_IDS = {
    "agent_entries",
    "search_okf",
    "mcp_cli",
    "inbox_capture",
    "connectors_mounts",
    "dashboard",
    "memory_writes",
    "radars",
}


IGNORED_PREFIXES = (
    ".git/",
    ".mypy_cache/",
    ".pytest_cache/",
    ".ruff_cache/",
    ".tmp/",
    "build/",
    "dist/",
    "frontend/dashboard/dist/",
    "htmlcov/",
    "node_modules/",
)
IGNORED_SUFFIXES = (".log", ".pyc", ".pyo", ".sqlite", ".sqlite3")
IGNORED_PARTS = ("/__pycache__/",)


def discover_changed_files(repo_root: Path) -> tuple[str, ...]:
    files: set[str] = set()
    for args in (
        ("diff", "--name-only", "--diff-filter=ACMRTUXB", "HEAD"),
        ("diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB"),
        ("ls-files", "--others", "--exclude-standard"),
    ):
        result = subprocess.run(  # noqa: S603, S607
            (GIT, "-C", str(repo_root), *args),
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            files.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    return tuple(sorted(_normalize_path(path) for path in files if _is_relevant(path)))


def build_gate_plan(
    *,
    changed_files: tuple[str, ...],
    mode: str,
    surface: str,
) -> GatePlan:
    normalized = tuple(
        sorted(_normalize_path(path) for path in changed_files if _is_relevant(path))
    )
    matched_rules = tuple(
        rule for rule in RISK_RULES if any(rule.matches(path) for path in normalized)
    )
    if _needs_docs_alignment(changed_files=normalized, matched_rules=matched_rules):
        matched_rules = (*matched_rules, DOCS_ALIGNMENT_RULE)
    risk_areas = tuple(rule.id for rule in matched_rules)
    requires_ai_eval = any(rule.requires_ai_eval for rule in matched_rules)

    command_ids: list[str] = []
    if matched_rules:
        command_ids.append("smoke")
        for suite in (
            "docs_alignment",
            "agent_clients",
            "mcp_matrix",
            "dashboard_browser",
            "radar_reports",
            "export_restore",
            "messy_inbox",
            "real_home",
            "real_integrations",
        ):
            if any(suite in rule.suites for rule in matched_rules):
                command_ids.append(suite)
        ai_eval_suites = _ai_eval_suites_for_command_ids(command_ids)
        if requires_ai_eval:
            command_ids.extend(("ai_packet", "ai_review"))
        command_ids.append("check")
    else:
        ai_eval_suites = ()

    commands = tuple(
        _command_for_id(id_, ai_eval_suites=ai_eval_suites) for id_ in _dedupe(command_ids)
    )
    message = _build_message(
        mode=mode,
        surface=surface,
        changed_files=normalized,
        matched_rules=matched_rules,
        commands=commands,
        requires_ai_eval=requires_ai_eval,
    )
    return GatePlan(
        schema=SCHEMA,
        mode=mode,
        surface=surface,
        changed_files=normalized,
        risk_areas=risk_areas,
        commands=commands,
        requires_ai_eval=requires_ai_eval,
        message=message,
    )


def execute_plan(
    plan: GatePlan,
    *,
    repo_root: Path,
    runner: CommandRunner | None = None,
) -> int:
    if not plan.commands:
        return 0
    if plan.mode != "strict":
        return 0
    if os.environ.get("ALCOVE_AGENT_QUALITY_GATE_RUNNING") == "1":
        print("agent-quality-gate: skipped nested strict run")
        return 0
    actual_runner = runner or _run_command
    for command in plan.commands:
        result = actual_runner(command, repo_root)
        if result != 0:
            return result
    return 0


def plan_to_json(plan: GatePlan, *, exit_code: int = 0) -> dict[str, object]:
    return {
        "schema": plan.schema,
        "mode": plan.mode,
        "surface": plan.surface,
        "changed_files": list(plan.changed_files),
        "risk_areas": list(plan.risk_areas),
        "requires_ai_eval": plan.requires_ai_eval,
        "commands": [
            {
                "id": command.id,
                "display": command.display,
                "reason": command.reason,
            }
            for command in plan.commands
        ],
        "exit_code": exit_code,
        "message": plan.message,
    }


def hook_response(plan: GatePlan, *, exit_code: int) -> dict[str, object]:
    if not plan.has_work:
        return {"continue": True, "suppressOutput": True}
    if plan.mode == "strict" and exit_code != 0:
        return {
            "decision": "block",
            "reason": plan.message,
        }
    return {
        "continue": True,
        "systemMessage": plan.message,
    }


def docs_drift_exit_code(*, repo_root: Path) -> int:
    changed_files = discover_changed_files(repo_root)
    plan = build_gate_plan(changed_files=changed_files, mode="strict", surface="manual")
    if "docs_alignment" not in plan.risk_areas:
        print("docs drift check: ok")
        return 0
    print(plan.message)
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or report Alcove agent quality gates.")
    parser.add_argument("--repo-root", default="")
    parser.add_argument("--surface", default="manual", choices=("manual", "codex", "claude"))
    parser.add_argument(
        "--mode",
        default=os.environ.get("ALCOVE_AGENT_GATE_MODE", "coach"),
        choices=("off", "coach", "strict"),
    )
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--hook-json", action="store_true")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).expanduser() if args.repo_root else _git_root(Path.cwd())
    if args.mode == "off":
        plan = build_gate_plan(changed_files=(), mode=args.mode, surface=args.surface)
        _emit(args, plan, 0)
        return 0

    changed_files = tuple(args.changed_file) or discover_changed_files(repo_root)
    plan = build_gate_plan(changed_files=changed_files, mode=args.mode, surface=args.surface)
    exit_code = execute_plan(plan, repo_root=repo_root)
    _emit(args, plan, exit_code)
    return exit_code


def _emit(args: argparse.Namespace, plan: GatePlan, exit_code: int) -> None:
    if args.hook_json:
        print(json.dumps(hook_response(plan, exit_code=exit_code), ensure_ascii=False))
    elif args.json:
        print(json.dumps(plan_to_json(plan, exit_code=exit_code), ensure_ascii=False, indent=2))
    elif plan.has_work:
        print(plan.message)


def _run_command(command: GateCommand, repo_root: Path) -> int:
    env = os.environ.copy()
    env.update(command.env)
    env["ALCOVE_AGENT_QUALITY_GATE_RUNNING"] = "1"
    print(f"agent-quality-gate: running {command.display}", file=sys.stderr)
    return subprocess.run(  # noqa: S603
        command.argv,
        cwd=repo_root,
        env=env,
        check=False,
    ).returncode


def _build_message(
    *,
    mode: str,
    surface: str,
    changed_files: tuple[str, ...],
    matched_rules: tuple[RiskRule, ...],
    commands: tuple[GateCommand, ...],
    requires_ai_eval: bool,
) -> str:
    if not commands:
        return "Alcove agent quality gate: no eval-sensitive local changes detected."
    files = "\n".join(f"  - {path}" for path in changed_files[:12])
    if len(changed_files) > 12:
        files += f"\n  - ... {len(changed_files) - 12} more"
    areas = "\n".join(f"  - {rule.id}: {rule.label}" for rule in matched_rules)
    command_lines = "\n".join(f"  - {command.display} ({command.reason})" for command in commands)
    ai_line = "yes" if requires_ai_eval else "no"
    mode_line = (
        "Coach mode reports the required checks without blocking. "
        "Set ALCOVE_AGENT_GATE_MODE=strict to execute and enforce them automatically."
        if mode == "coach"
        else "Strict mode executes the required checks and blocks on failure."
    )
    return (
        f"Alcove agent quality gate detected verification-sensitive changes "
        f"(surface={surface}, mode={mode}, ai_eval_required={ai_line}).\n"
        f"{mode_line}\n\n"
        f"Changed files:\n{files}\n\n"
        f"Risk areas:\n{areas}\n\n"
        f"Required verification:\n{command_lines}"
    )


def _git_root(cwd: Path) -> Path:
    result = subprocess.run(  # noqa: S603, S607
        (GIT, "rev-parse", "--show-toplevel"),
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return cwd


def _normalize_path(path: str) -> str:
    return path.strip().removeprefix("./")


def _is_relevant(path: str) -> bool:
    normalized = _normalize_path(path)
    return not (
        any(normalized.startswith(prefix) for prefix in IGNORED_PREFIXES)
        or any(part in f"/{normalized}/" for part in IGNORED_PARTS)
        or normalized.endswith(IGNORED_SUFFIXES)
    )


def _matches_pattern(path: str, pattern: str) -> bool:
    if fnmatch.fnmatch(path, pattern):
        return True
    if pattern.endswith("*.py"):
        prefix = pattern[:-4]
        return path.startswith(prefix) and path.endswith(".py")
    return False


def _needs_docs_alignment(
    *,
    changed_files: tuple[str, ...],
    matched_rules: tuple[RiskRule, ...],
) -> bool:
    if not any(rule.id in DOCS_ALIGNMENT_RISK_IDS for rule in matched_rules):
        return False
    if any(_matches_any(path, DOCS_ALIGNMENT_DOC_PATTERNS) for path in changed_files):
        return False
    return any(
        _matches_any(path, DOCS_ALIGNMENT_SOURCE_PATTERNS)
        and not path.startswith("tests/")
        and not path.startswith("scripts/verify/")
        for path in changed_files
    )


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(_matches_pattern(path, pattern) for pattern in patterns)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _ai_eval_suites_for_command_ids(command_ids: list[str]) -> tuple[str, ...]:
    suite_ids = []
    for command_id in command_ids:
        if command_id == "smoke":
            suite_ids.append("isolated")
        elif command_id in {
            "real_home",
            "real_integrations",
            "agent_clients",
            "mcp_matrix",
            "dashboard_browser",
            "radar_reports",
            "export_restore",
            "messy_inbox",
        }:
            suite_ids.append(command_id)
    selected = set(suite_ids)
    return tuple(
        suite
        for suite in (
            "isolated",
            "real_home",
            "real_integrations",
            "agent_clients",
            "mcp_matrix",
            "dashboard_browser",
            "radar_reports",
            "export_restore",
            "messy_inbox",
        )
        if suite in selected
    )


def _command_for_id(command_id: str, *, ai_eval_suites: tuple[str, ...]) -> GateCommand:
    command = SUITE_COMMANDS[command_id]
    if command_id not in {"ai_packet", "ai_review"} or not ai_eval_suites:
        return command
    suite_value = ",".join(ai_eval_suites)
    env = dict(command.env)
    env["ALCOVE_AI_EVAL_SUITES"] = suite_value
    if command_id == "ai_packet":
        env.setdefault("ALCOVE_AI_EVAL_RUN_CHECK", "0")
    display_prefix = f"ALCOVE_AI_EVAL_SUITES={suite_value} "
    if command_id == "ai_packet":
        display_prefix += "ALCOVE_AI_EVAL_PROVIDER=none ALCOVE_AI_EVAL_RUN_CHECK=0 "
    else:
        display_prefix += "ALCOVE_AI_EVAL_SKIP_REFRESH=1 "
    return GateCommand(
        id=command.id,
        display=f"{display_prefix}scripts/eval-ai.sh",
        argv=command.argv,
        env=env,
        reason=command.reason,
    )


if __name__ == "__main__":
    raise SystemExit(main())
