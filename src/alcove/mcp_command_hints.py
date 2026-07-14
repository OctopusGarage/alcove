from __future__ import annotations

from typing import Any

from alcove.paths import compact_user_path


def command_hints_tool(
    workspace: str = "",
    home: str = "",
    workflow: str = "",
) -> dict[str, Any]:
    """Return command hints for Alcove workflows intentionally kept outside MCP."""
    home_hint = compact_user_path(home) if home else "~/.alcove"
    workspace_hint = compact_user_path(workspace) if workspace else "<managed-kb>"
    workflows = [
        {
            "id": "agent_workspaces",
            "title": "Agent workspaces",
            "surface": "cli",
            "intent": "Create, inspect, or run Hub-managed lightweight business workspaces.",
            "commands": [
                f"alcove workspace list --home {home_hint} --json",
                f"alcove workspace status --home {home_hint} <workspace-id> --json",
                f'alcove workspace run --home {home_hint} <workspace-id> --agent codex "prompt" --json',
            ],
            "notes": [
                "Hub remains the control workspace; custom workspaces are lightweight scene entries.",
                "Use one-shot runs for scoped work, or open Codex/Claude from the workspace directory.",
            ],
        },
        {
            "id": "workspace_okf",
            "title": "Workspace-local OKF",
            "surface": "cli",
            "intent": "Initialize, write, import, and search scene-local workspace knowledge.",
            "commands": [
                f"alcove workspace okf init --home {home_hint} <workspace-id> --json",
                f'alcove workspace okf add-note --home {home_hint} <workspace-id> <domain/topic> "Title" --summary "..." --json',
                f"alcove workspace okf import-file --home {home_hint} <workspace-id> ./documents/file.md --topic <domain/topic> --json",
                f'alcove workspace okf search --home {home_hint} <workspace-id> "query" --json',
            ],
            "notes": [
                "Use this inside business workspaces for documents, notes, and scene-local recall.",
                "The implementation reuses managed-KB OKF storage while keeping the workspace command surface simple.",
            ],
        },
        {
            "id": "blog_monitor",
            "title": "Blog monitoring",
            "surface": "cli",
            "intent": "Discover configured blog updates, capture new articles, and notify.",
            "commands": [
                f"alcove blog list --home {home_hint} --status '' --json",
                f"alcove blog check --home {home_hint} --json",
                f"alcove blog check --home {home_hint} <source-id> --json",
            ],
            "notes": [
                "Use this from the Hub entry or scheduled service.",
                "A failed scheduled run should notify the user so they can retry from Hub.",
            ],
        },
        {
            "id": "radars",
            "title": "Radar reports",
            "surface": "cli",
            "intent": "Run user-defined radar sources, score items, render reports, and notify.",
            "commands": [
                f"alcove radar list --home {home_hint} --json",
                f"alcove radar status --home {home_hint} <radar-id> --json",
                f"alcove radar run --home {home_hint} <radar-id> --force --ai --notify --json",
                f"alcove radar run --home {home_hint} <radar-id> --skip-fetch --force --ai --notify --json",
            ],
            "notes": [
                "Each radar has its own prompt/profile; do not treat radar types as hard-coded modules.",
                "Use --skip-fetch when the user asks to re-analyze already fetched results.",
            ],
        },
        {
            "id": "dashboard",
            "title": "Dashboard",
            "surface": "cli",
            "intent": "Build or serve the local Alcove dashboard snapshot.",
            "commands": [
                f"alcove dashboard build --home {home_hint} --json",
                f"alcove serve --dashboard --home {home_hint}",
            ],
            "notes": [
                "Dashboard reads generated snapshots and should not be used as the write contract.",
                "Use the browser/UI for inspection; use CLI/MCP writes for data changes.",
            ],
        },
        {
            "id": "publishers",
            "title": "Publishers and Apple Notes export",
            "surface": "cli",
            "intent": "Publish selected Alcove module views to external destinations.",
            "commands": [
                f"alcove publish list --home {home_hint} --json",
                f"alcove publish run --home {home_hint} apple-notes --json",
                f"alcove publish init apple-notes --home {home_hint} --root-folder 'iCloud/Alcove' --json",
            ],
            "notes": [
                "Apple Notes publishing is scheduled when enabled in publisher definitions.",
                "Keep exported content complete; formatting belongs in publisher templates.",
            ],
        },
        {
            "id": "knowledge_base_admin",
            "title": "Managed knowledge-base setup",
            "surface": "cli",
            "intent": "Install or refresh agent entry files for a managed KB workspace.",
            "commands": [
                f"alcove kb install-agent --workspace {workspace_hint} --mode symlink",
                f"alcove kb install-agent --workspace {workspace_hint} --mode copy",
                f"alcove validate --workspace {workspace_hint} --json",
            ],
            "notes": [
                "Use symlink mode for local development and copy mode for portable repository state.",
                "Committed KB repositories should ignore local agent install artifacts when symlinked.",
            ],
        },
    ]
    query = workflow.strip().lower()
    if query:
        workflows = [
            item
            for item in workflows
            if query in str(item["id"]).lower() or query in str(item["title"]).lower()
        ]
    return {
        "status": "ok",
        "home": home_hint,
        "workspace": workspace_hint,
        "workflow": workflow,
        "count": len(workflows),
        "workflows": workflows,
    }
