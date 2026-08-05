from __future__ import annotations

from typing import Any

from alcove.agent_targets import VALID_AGENT_TARGETS
from alcove.entry_policy import default_toolset_for_entry
from alcove.mcp_toolsets import resolve_mcp_toolset
from alcove.profile_packs import ProfileInstallationPack
from alcove.profile_skill_templates import profile_skill_source_path


ENTRY_CONTRACT_SCHEMA = "alcove/agent-entry-contract-matrix/v1"


def entry_contract_matrix(*, home_part: str = "") -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for profile, toolset, install, status, skill_name in (
        (
            "hub",
            "full",
            "alcove hub install <path> --target <client>",
            "alcove hub install <path> --target <client> --status --json",
            "alcove-hub",
        ),
        (
            "workspace",
            "full",
            "alcove workspace install <id> --target <client>",
            "alcove workspace status <id> --json",
            "alcove-workspace",
        ),
        (
            "managed-kb",
            "kb",
            "alcove kb install <name> --target <client>",
            "alcove kb install <name> --target <client> --status --json",
            "alcove-kb",
        ),
    ):
        for client in sorted(VALID_AGENT_TARGETS):
            rows.append(
                {
                    "profile": profile,
                    "client": client,
                    "toolset": toolset,
                    "skill": skill_name,
                    "install_path": install,
                    "status_path": status,
                    "home_scope": {
                        "default": "implicit ~/.alcove",
                        "explicit": home_part or "--home <path>",
                        "transformation": "insert --home after each governed alcove command root",
                    },
                    "generated_output": "copy or symlink skill; marked AGENTS/CLAUDE section",
                }
            )
    rows.append(
        {
            "profile": "global",
            "client": "codex+claude",
            "toolset": "lite (configurable kb/full)",
            "skill": "MCP server config",
            "install_path": "alcove global install --target <client>",
            "status_path": "alcove global install --target <client> --status --json",
            "home_scope": {
                "default": "implicit ~/.alcove",
                "explicit": home_part or "--home <path>",
                "transformation": "persist compact home path in client config",
            },
            "generated_output": "deterministic MCP argv/config; no model calls",
        }
    )
    return {"schema": ENTRY_CONTRACT_SCHEMA, "count": len(rows), "contracts": rows}


def validate_entry_contract_matrix(*, home_part: str = "") -> dict[str, Any]:
    errors: list[str] = []
    matrix = entry_contract_matrix(home_part=home_part)
    expected_toolsets = {"hub": "full", "workspace": "full", "managed-kb": "kb"}
    for profile, toolset in expected_toolsets.items():
        policy_profile = "hub" if profile == "workspace" else profile
        if default_toolset_for_entry(policy_profile) != toolset:
            errors.append(f"entry policy drift: {profile} -> {toolset}")
        try:
            resolved, _ = resolve_mcp_toolset(toolset)
        except ValueError as exc:
            errors.append(f"MCP toolset unavailable: {toolset}: {exc}")
        else:
            if resolved != toolset:
                errors.append(f"MCP toolset alias drift: {toolset} -> {resolved}")
    for profile in ("hub", "workspace", "managed-kb"):
        pack = ProfileInstallationPack(
            profile=profile,
            skill_name="alcove-kb" if profile == "managed-kb" else f"alcove-{profile}",
        )
        first_skill = pack.skill_content("contract_kb", home_part)
        second_skill = pack.skill_content("contract_kb", home_part)
        first_entry = pack.entry_section("~/.alcove", "contract_kb", home_part)
        second_entry = pack.entry_section("~/.alcove", "contract_kb", home_part)
        if first_skill != second_skill or first_entry != second_entry:
            errors.append(f"generated output is not stable: {profile}")
        if profile_skill_source_path(profile) is None:
            errors.append(f"missing source template: {profile}")
        if "--home" in home_part and home_part not in first_skill:
            errors.append(f"home-scope transformation missing: {profile}")
        if "ALCOVE ENTRY START" not in first_entry or "ALCOVE ENTRY END" not in first_entry:
            errors.append(f"marked entry section missing: {profile}")
    return {
        "schema": ENTRY_CONTRACT_SCHEMA,
        "status": "pass" if not errors else "failed",
        "errors": errors,
        "contracts": matrix["contracts"],
        "model_calls": 0,
    }
