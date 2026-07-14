from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alcove.mcp_context import McpInvocationContext
from alcove.paths import compact_user_path


def register_mcp_resources(mcp: Any, context: McpInvocationContext) -> None:
    @mcp.resource(  # type: ignore[untyped-decorator]
        "alcove://home/config",
        name="alcove_home_config",
        mime_type="text/yaml",
        description="Alcove home configuration file.",
    )
    def alcove_home_config() -> str:
        path = _mcp_home_root(context) / "config.yml"
        return _read_text_or_empty(path)

    @mcp.resource(  # type: ignore[untyped-decorator]
        "alcove://planner/tasks",
        name="alcove_planner_tasks",
        mime_type="application/json",
        description="Alcove tasks, ideas, and routines source-of-truth JSON.",
    )
    def alcove_planner_tasks() -> str:
        path = _mcp_home_root(context) / "tasks" / "tasks.json"
        return _read_text_or_empty(path, default='{"tasks":[],"ideas":[],"routines":[]}\n')

    @mcp.resource(  # type: ignore[untyped-decorator]
        "alcove://radars/latest",
        name="alcove_latest_radar_reports",
        mime_type="application/json",
        description="Latest radar report files grouped by radar id.",
    )
    def alcove_latest_radar_reports() -> str:
        root = _mcp_home_root(context) / "radars" / "reports"
        return json.dumps(_latest_radar_reports(root), ensure_ascii=False, indent=2)

    @mcp.resource(  # type: ignore[untyped-decorator]
        "alcove://radars/{date}",
        name="alcove_radar_reports_by_date",
        mime_type="application/json",
        description="Radar report files for a date in YYYY-MM-DD format.",
    )
    def alcove_radar_reports_by_date(date: str) -> str:
        root = _mcp_home_root(context) / "radars" / "reports"
        return json.dumps(_radar_reports_for_date(root, date), ensure_ascii=False, indent=2)


def register_mcp_prompts(mcp: Any, context: McpInvocationContext) -> None:
    @mcp.prompt(  # type: ignore[untyped-decorator]
        "daily_briefing",
        description="Guide an agent through a daily Alcove briefing.",
    )
    def daily_briefing(focus: str = "", home: str = "") -> str:
        home_hint = home or context.default_home or "~/.alcove"
        focus_line = f"\nFocus: {focus}" if focus else ""
        return (
            "Prepare a concise daily briefing from Alcove.\n"
            f"Home: {home_hint}{focus_line}\n\n"
            "Use broad reads first: alcove_search, recent radar reports, planner tasks, "
            "pins, and managed knowledge-base evidence. Treat search results as leads; "
            "inspect OKF records or source files before making claims. Do not mutate data "
            "unless the user explicitly asks for a governed write."
        )

    @mcp.prompt(  # type: ignore[untyped-decorator]
        "todo_review",
        description="Guide an agent through reviewing Alcove tasks, ideas, and routines.",
    )
    def todo_review(home: str = "") -> str:
        home_hint = home or context.default_home or "~/.alcove"
        return (
            "Review Alcove planner state and produce an actionable summary.\n"
            f"Home: {home_hint}\n\n"
            "Read alcove://planner/tasks and use task/idea/routine tools for governed "
            "writes only after the user confirms changes. Group overdue, due soon, "
            "waiting ideas, and routines that need adjustment. Preserve task ids in the "
            "output so follow-up commands are easy."
        )


def _mcp_home_root(context: McpInvocationContext, home: str = "") -> Path:
    app = context.scoped_app("", home)
    if app.runtime.home is None:
        return Path("~/.alcove").expanduser()
    return app.runtime.home.root


def _read_text_or_empty(path: Path, *, default: str = "") -> str:
    if not path.is_file():
        return default
    return path.read_text(encoding="utf-8")


def _latest_radar_reports(root: Path) -> dict[str, Any]:
    reports: dict[str, dict[str, str]] = {}
    if not root.is_dir():
        return {"reports": reports}
    for radar_root in sorted(path for path in root.iterdir() if path.is_dir()):
        latest = _latest_report_pair(radar_root)
        if latest:
            reports[radar_root.name] = latest
    return {"reports": reports}


def _radar_reports_for_date(root: Path, date: str) -> dict[str, Any]:
    reports: dict[str, dict[str, str]] = {}
    if not root.is_dir():
        return {"date": date, "reports": reports}
    for radar_root in sorted(path for path in root.iterdir() if path.is_dir()):
        paths = {}
        for suffix in ("md", "html", "ai.md"):
            path = radar_root / f"{date}.{suffix}"
            if path.is_file():
                paths[suffix] = compact_user_path(path)
        if paths:
            reports[radar_root.name] = paths
    return {"date": date, "reports": reports}


def _latest_report_pair(radar_root: Path) -> dict[str, str]:
    candidates = sorted(radar_root.glob("*.md"))
    latest_date = ""
    for path in candidates:
        if path.name.endswith(".ai.md"):
            continue
        latest_date = max(latest_date, path.stem)
    if not latest_date:
        return {}
    payload: dict[str, str] = {"date": latest_date}
    for suffix in ("md", "html", "ai.md"):
        path = radar_root / f"{latest_date}.{suffix}"
        if path.is_file():
            payload[suffix] = compact_user_path(path)
    return payload
