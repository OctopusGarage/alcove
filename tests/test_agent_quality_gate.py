from __future__ import annotations

from pathlib import Path

from alcove.agent_quality_gate import (
    GateCommand,
    build_gate_plan,
    execute_plan,
    hook_response,
    plan_to_json,
)


def test_gate_plan_ignores_generated_artifacts() -> None:
    plan = build_gate_plan(
        changed_files=(
            ".tmp/ai-eval/ai-review.json",
            "src/alcove/__pycache__/ai_eval.cpython-312.pyc",
        ),
        mode="coach",
        surface="codex",
    )

    assert plan.changed_files == ()
    assert plan.risk_areas == ()
    assert plan.commands == ()
    assert hook_response(plan, exit_code=0)["suppressOutput"] is True


def test_agent_prompt_changes_require_agent_smoke_and_ai_eval() -> None:
    plan = build_gate_plan(
        changed_files=(".claude/commands/eval-ai.md", "AGENTS.md"),
        mode="coach",
        surface="claude",
    )

    command_ids = [command.id for command in plan.commands]
    assert "agent_entries" in plan.risk_areas
    assert plan.requires_ai_eval is True
    assert command_ids == [
        "smoke",
        "agent_clients",
        "ai_packet",
        "ai_review",
        "check",
    ]
    ai_packet = next(command for command in plan.commands if command.id == "ai_packet")
    ai_review = next(command for command in plan.commands if command.id == "ai_review")
    assert ai_packet.env["ALCOVE_AI_EVAL_SUITES"] == "isolated,agent_clients"
    assert ai_packet.env["ALCOVE_AI_EVAL_RUN_CHECK"] == "0"
    assert "ALCOVE_AI_EVAL_SUITES=isolated,agent_clients" in ai_packet.display
    assert ai_review.env["ALCOVE_AI_EVAL_SUITES"] == "isolated,agent_clients"
    assert "Set ALCOVE_AGENT_GATE_MODE=strict" in plan.message


def test_dashboard_changes_require_browser_smoke_and_ai_eval() -> None:
    plan = build_gate_plan(
        changed_files=(
            "frontend/dashboard/src/views/home.ts",
            "src/alcove/dashboard.py",
        ),
        mode="coach",
        surface="codex",
    )

    command_ids = [command.id for command in plan.commands]
    assert "dashboard" in plan.risk_areas
    assert "dashboard_browser" in command_ids
    assert "real_home" in command_ids
    ai_packet = next(command for command in plan.commands if command.id == "ai_packet")
    assert ai_packet.env["ALCOVE_AI_EVAL_SUITES"] == ("isolated,real_home,dashboard_browser")


def test_radar_changes_require_report_smoke_and_ai_eval() -> None:
    plan = build_gate_plan(
        changed_files=(
            "src/alcove/radars/reporting.py",
            "src/alcove/radars/presets/tech-news.yml",
        ),
        mode="coach",
        surface="codex",
    )

    command_ids = [command.id for command in plan.commands]
    assert "radars" in plan.risk_areas
    assert plan.requires_ai_eval is True
    assert "radar_reports" in command_ids
    assert "real_home" in command_ids
    ai_packet = next(command for command in plan.commands if command.id == "ai_packet")
    assert ai_packet.env["ALCOVE_AI_EVAL_SUITES"] == "isolated,real_home,radar_reports"


def test_memory_write_changes_get_deterministic_gate_without_ai_eval() -> None:
    plan = build_gate_plan(
        changed_files=("src/alcove/pins.py", "tests/test_tasks.py"),
        mode="coach",
        surface="manual",
    )

    command_ids = [command.id for command in plan.commands]
    assert plan.requires_ai_eval is False
    assert command_ids == [
        "smoke",
        "docs_alignment",
        "mcp_matrix",
        "export_restore",
        "real_home",
        "check",
    ]
    assert "ai_packet" not in command_ids
    assert "ai_review" not in command_ids


def test_docs_sensitive_source_changes_require_docs_alignment_without_docs() -> None:
    plan = build_gate_plan(
        changed_files=("src/alcove/tasks.py",),
        mode="coach",
        surface="codex",
    )

    command_ids = [command.id for command in plan.commands]
    assert "docs_alignment" in plan.risk_areas
    assert "docs_alignment" in command_ids
    assert "Documentation alignment" in plan.message


def test_docs_alignment_is_satisfied_when_related_docs_change() -> None:
    plan = build_gate_plan(
        changed_files=("src/alcove/tasks.py", "docs/modules.md"),
        mode="coach",
        surface="codex",
    )

    command_ids = [command.id for command in plan.commands]
    assert "docs_alignment" not in plan.risk_areas
    assert "docs_alignment" not in command_ids


def test_strict_mode_executes_commands_in_plan_order(tmp_path: Path) -> None:
    plan = build_gate_plan(
        changed_files=("src/alcove/ai_eval.py",),
        mode="strict",
        surface="codex",
    )
    seen: list[str] = []

    def runner(command: GateCommand, repo_root: Path) -> int:
        assert repo_root == tmp_path
        seen.append(command.id)
        return 0

    assert execute_plan(plan, repo_root=tmp_path, runner=runner) == 0
    assert seen == [command.id for command in plan.commands]
    assert hook_response(plan, exit_code=0)["continue"] is True


def test_strict_hook_response_blocks_on_failure() -> None:
    plan = build_gate_plan(
        changed_files=("src/alcove/mcp_server.py",),
        mode="strict",
        surface="claude",
    )

    response = hook_response(plan, exit_code=1)

    assert response["decision"] == "block"
    assert "mcp_cli" in response["reason"]
    assert "Strict mode executes" in response["reason"]


def test_plan_json_is_machine_readable() -> None:
    plan = build_gate_plan(
        changed_files=("src/alcove/connectors/github_stars.py",),
        mode="coach",
        surface="codex",
    )

    payload = plan_to_json(plan, exit_code=0)

    assert payload["schema"] == "alcove.agent_quality_gate.v1"
    assert payload["requires_ai_eval"] is True
    assert any(command["id"] == "real_integrations" for command in payload["commands"])
    assert any(
        "ALCOVE_AI_EVAL_SUITES=isolated,real_home,real_integrations,mcp_matrix"
        in command["display"]
        for command in payload["commands"]
    )
