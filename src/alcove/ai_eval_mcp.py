from __future__ import annotations

import asyncio
from typing import Any

from alcove.mcp_toolsets import (
    MCP_TOOLSET_ALIASES,
    mcp_tool_inventory as _mcp_tool_inventory,
    resolve_mcp_toolset,
)


def mcp_tool_inventory() -> dict[str, list[str]]:
    return _mcp_tool_inventory()


def mcp_toolsets_for_eval() -> dict[str, Any]:
    toolsets: dict[str, Any] = {}
    for name in ("lite", "kb", "full"):
        canonical, tools = resolve_mcp_toolset(name)
        toolsets[name] = {
            "canonical": canonical,
            "tool_count": len(tools),
            "tools": sorted(tools),
        }
    toolsets["aliases"] = {
        alias: canonical for alias, canonical in sorted(MCP_TOOLSET_ALIASES.items()) if alias
    }
    return toolsets


def mcp_matrix_for_eval(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    public = dict(payload)
    inventory = mcp_tool_inventory()
    all_tools = sorted({tool for tools in inventory.values() for tool in tools})
    raw_checks = public.get("checks")
    checks = raw_checks if isinstance(raw_checks, list) else []
    called = {
        str(check.get("tool"))
        for check in checks
        if isinstance(check, dict) and str(check.get("tool") or "")
    }
    external_coverage = public.get("covered_by_external_smoke")
    external_tools = (
        {
            str(item.get("tool"))
            for item in external_coverage
            if isinstance(item, dict) and str(item.get("tool") or "")
        }
        if isinstance(external_coverage, list)
        else set()
    )
    covered = called | external_tools
    uncalled = [tool for tool in all_tools if tool not in called]
    uncovered = [tool for tool in all_tools if tool not in covered]
    public["check_rollup"] = _mcp_check_rollup(checks)
    public["check_rollup_by_module"] = _mcp_check_rollup_by_module(checks)
    public["module_call_counts"] = public.get("module_call_counts") or public.get(
        "module_counts", {}
    )
    public["module_tool_counts"] = {
        module: len(rollup.get("tools", []))
        for module, rollup in public["check_rollup_by_module"].items()
        if isinstance(rollup, dict)
    }
    public["external_coverage_rollup"] = sorted(external_tools)
    policy = public.get("external_coverage_policy")
    if not isinstance(policy, dict):
        policy = {}
    raw_policy_status = str(policy.get("status") or "")
    public["external_coverage_policy"] = {
        "status": "passed" if not uncovered else "failed",
        "mode": raw_policy_status or "derived",
        "direct_call_exceptions": sorted(external_tools),
        "uncovered_tools": uncovered,
        "fail_when": str(
            policy.get("fail_when")
            or "An MCP tool is neither called by the MCP matrix nor externally covered."
        ),
    }
    public["tool_coverage"] = {
        "total_tools": len(all_tools),
        "reported_call_count": public.get("called_tools"),
        "unique_called_tools": len(called),
        "externally_covered_tools": sorted(external_tools),
        "covered_tools": len(covered),
        "uncalled_tools": uncalled,
        "uncalled_count": len(uncalled),
        "uncovered_tools": uncovered,
        "uncovered_count": len(uncovered),
    }
    return public


def mcp_tool_descriptions(warnings: list[str]) -> dict[str, str]:
    try:
        from alcove.mcp_server import create_mcp_server

        async def list_tool_descriptions() -> dict[str, str]:
            tools = await create_mcp_server().list_tools()
            return {tool.name: str(tool.description or "") for tool in tools}

        return asyncio.run(list_tool_descriptions())
    except RuntimeError as exc:
        warnings.append(f"mcp tool description introspection failed: {exc}")
        return {}


def _mcp_check_rollup(checks: list[Any]) -> list[dict[str, str]]:
    rollup: list[dict[str, str]] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        tool = str(check.get("tool") or "").strip()
        if not tool:
            continue
        rollup.append(
            {
                "module": str(check.get("module") or "").strip(),
                "tool": tool,
                "status": str(check.get("status") or "").strip() or "unknown",
            }
        )
    return rollup


def _mcp_check_rollup_by_module(checks: list[Any]) -> dict[str, dict[str, Any]]:
    modules: dict[str, dict[str, Any]] = {}
    for row in _mcp_check_rollup(checks):
        module = row["module"] or "unknown"
        module_rollup = modules.setdefault(
            module,
            {
                "calls": 0,
                "passed": 0,
                "failed": 0,
                "tools": [],
            },
        )
        module_rollup["calls"] += 1
        if row["status"] == "passed":
            module_rollup["passed"] += 1
        else:
            module_rollup["failed"] += 1
        tool_status = f"{row['tool']}:{row['status']}"
        if tool_status not in module_rollup["tools"]:
            module_rollup["tools"].append(tool_status)
    return modules
