#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

root="${ALCOVE_MCP_MATRIX_DIR:-$repo_root/.tmp/mcp-matrix}"
home="$root/home"
kb="$root/kb"
fixtures="$root/fixtures"
report="$root/mcp-matrix-report.json"

run() {
  printf 'mcp-matrix: %s\n' "$*" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
}

rm -rf "$root"
mkdir -p "$fixtures"

export ALCOVE_HOME="$home"
alcove home init --json > "$fixtures/home-init.json"
alcove init "$kb" > "$fixtures/kb-init.txt"
alcove kb add matrix_kb "$kb" --json > "$fixtures/kb-add.json"

mount_dir="$root/mounted"
mkdir -p "$mount_dir/docs"
printf '# Matrix Mount\n\nMCP matrix mounted content.\n' > "$mount_dir/docs/matrix.md"
github_stars="$fixtures/github-stars.json"
cat > "$github_stars" <<'JSON'
[
  {
    "full_name": "octopusgarage/matrix",
    "html_url": "https://github.com/OctopusGarage/matrix",
    "description": "MCP matrix connector fixture.",
    "language": "Python",
    "topics": ["matrix", "mcp"],
    "stargazers_count": 7,
    "updated_at": "2026-07-10T00:00:00Z"
  }
]
JSON
chrome_bookmarks="$fixtures/chrome-bookmarks.json"
cat > "$chrome_bookmarks" <<'JSON'
{
  "roots": {
    "bookmark_bar": {
      "type": "folder",
      "name": "Bookmarks Bar",
      "children": [
        {
          "type": "url",
          "name": "Matrix Bookmark",
          "url": "https://example.com/matrix-bookmark",
          "date_added": "13300000000000000"
        }
      ]
    }
  }
}
JSON
apple_export="$fixtures/apple-notes-export"
mkdir -p "$apple_export/notes/x-coredata%3A%2F%2Fmatrix-note"
cat > "$apple_export/notes/x-coredata%3A%2F%2Fmatrix-note/note.json" <<'JSON'
{
  "id": "x-coredata://matrix-note",
  "title": "Matrix Apple Note",
  "account": "iCloud",
  "folder_path": "iCloud/Matrix",
  "created_at": "2026-07-10T08:00:00Z",
  "updated_at": "2026-07-10T09:00:00Z",
  "plaintext": "MCP matrix apple note.",
  "body_html": "<div>MCP matrix apple note.</div>"
}
JSON

run uv run python - "$home" "$kb" "$mount_dir" "$github_stars" "$chrome_bookmarks" "$apple_export" "$report" <<'PY'
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

home = Path(sys.argv[1])
kb = Path(sys.argv[2])
mount_dir = Path(sys.argv[3])
github_stars = Path(sys.argv[4])
chrome_bookmarks = Path(sys.argv[5])
apple_export = Path(sys.argv[6])
report_path = Path(sys.argv[7])


def status_from_payload(payload: dict[str, Any], *keys: str) -> str:
    if payload.get("error"):
        return "failed"
    for key in keys:
        if key in payload:
            return "passed"
    return "passed" if payload else "failed"


LOCAL_PATH_KEYS = {
    "home",
    "workspace",
    "path",
    "source_path",
    "archive",
    "export_file",
    "export_dir",
    "index_path",
    "artifacts",
}


def sample_payload(value: Any, *, depth: int = 0) -> Any:
    if depth > 4:
        return "[nested payload omitted]"
    if isinstance(value, dict):
        sample: dict[str, Any] = {}
        for key, item in value.items():
            if key in LOCAL_PATH_KEYS:
                continue
            if key in {"items", "results", "sources", "issues", "checks"} and isinstance(item, list):
                sample[key] = [sample_payload(row, depth=depth + 1) for row in item[:2]]
                if len(item) > 2:
                    sample[f"{key}_truncated_count"] = len(item) - 2
                continue
            if key in {
                "status",
                "count",
                "tool_count",
                "refreshed",
                "skipped",
                "reused",
                "errors",
                "scanned",
                "item_count",
                "exported",
                "connector",
                "display_id",
                "display_label",
                "source_id",
                "source_label",
                "origin_label",
                "fetch_ref",
                "relative_path",
                "source",
                "resource",
                "url",
                "html_url",
                "description",
                "text",
                "language",
                "stars",
                "updated_at",
                "id",
                "title",
                "type",
                "kind",
                "summary",
                "question",
                "answer",
                "topic",
                "tags",
                "priority",
                "due",
                "item",
                "pin",
                "task",
                "idea",
                "prompt",
                "project",
                "mount",
                "detail",
                "diff_summary",
            }:
                sampled = sample_payload(item, depth=depth + 1)
                if key == "source" and isinstance(sampled, str) and _looks_like_local_path(sampled):
                    continue
                sample[key] = sampled
                if isinstance(item, list) and len(item) > 2:
                    sample[f"{key}_truncated_count"] = len(item) - 2
        if sample:
            return sample
        return {key: sample_payload(item, depth=depth + 1) for key, item in list(value.items())[:4]}
    if isinstance(value, list):
        return [sample_payload(item, depth=depth + 1) for item in value[:2]]
    if isinstance(value, str):
        text = value
        for root in (str(home), str(kb), str(report_path.parent), str(Path.home())):
            if root:
                text = text.replace(root, "~")
        if len(text) > 240:
            return text[:240] + f"...[truncated {len(text) - 240} chars]"
        return text
    return value


def _looks_like_local_path(value: str) -> bool:
    return value.startswith("~/") or value.startswith("/") or "/.alcove/" in value


def sample_score(value: Any) -> int:
    if isinstance(value, dict):
        score = 0
        for key, item in value.items():
            if key in {
                "status",
                "title",
                "display_id",
                "display_label",
                "source_id",
                "source_label",
                "origin_label",
                "fetch_ref",
                "results",
            }:
                score += 3
            if key in {"item", "pin", "task", "idea", "prompt", "project", "mount"}:
                score += 2
            score += sample_score(item)
        return score
    if isinstance(value, list):
        return min(len(value), 3) + sum(sample_score(item) for item in value[:2])
    if isinstance(value, str) and value:
        return 1
    return 0


async def main() -> None:
    async def inspect_toolset(
        name: str,
        required: set[str],
        forbidden: set[str],
    ) -> dict[str, Any]:
        transport = StdioTransport(
            command="uv",
            args=[
                "run",
                "alcove",
                "serve",
                "--mcp",
                "--toolset",
                name,
                "--home",
                str(home),
                "--workspace",
                str(kb),
            ],
            cwd=str(Path.cwd()),
            log_file=report_path.with_name(f"mcp-{name}-server.log"),
        )
        async with Client(transport) as client:
            names = sorted(tool.name for tool in await client.list_tools())
        missing = sorted(required - set(names))
        unexpected = sorted(forbidden & set(names))
        return {
            "status": "passed" if not missing and not unexpected else "failed",
            "toolset": name,
            "tool_count": len(names),
            "missing_required": missing,
            "unexpected_tools": unexpected,
            "sample_tools": names[:20],
        }

    transport = StdioTransport(
        command="uv",
        args=[
            "run",
            "alcove",
            "serve",
            "--mcp",
            "--home",
            str(home),
            "--workspace",
            str(kb),
        ],
        cwd=str(Path.cwd()),
        log_file=report_path.with_name("mcp-matrix-server.log"),
    )
    checks: list[dict[str, Any]] = []
    samples: dict[str, dict[str, Any]] = {}
    async with Client(transport) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)

        async def call(module: str, name: str, args: dict[str, Any], expect: str = "") -> dict[str, Any]:
            result = await client.call_tool(name, args)
            payload = result.structured_content or {}
            check = {
                "module": module,
                "tool": name,
                "status": status_from_payload(payload),
                "expect": expect,
                "summary": summarize(payload),
            }
            checks.append(check)
            sample = {
                "tool": name,
                "summary": check["summary"],
                "payload": sample_payload(payload),
            }
            existing = samples.get(module)
            if (
                existing is None
                or name == "alcove_connector_fetch"
                or existing["tool"] == "alcove_connector_fetch"
                or sample_score(sample["payload"]) >= sample_score(existing["payload"])
            ):
                if existing is None or existing["tool"] != "alcove_connector_fetch" or name == "alcove_connector_fetch":
                    samples[module] = sample
            if check["status"] != "passed":
                raise SystemExit(f"{name} failed: {payload}")
            return payload

        await call("inbox", "alcove_inbox_manual_add", {
            "workspace": str(kb),
            "title": "MCP Matrix Inbox",
            "content": "MCP matrix inbox body.",
            "source": "smoke://mcp-matrix",
        })
        inbox = await call("inbox", "alcove_inbox_peek", {"workspace": str(kb)})
        identifier = inbox["item"]["identifier"]
        await call("inbox", "alcove_inbox_read", {"workspace": str(kb), "name": identifier})
        await call("knowledge", "alcove_inbox_note", {
            "workspace": str(kb),
            "name": identifier,
            "topic": "agent-engineering/mcp",
            "summary": "MCP matrix inbox note.",
            "tags": ["mcp", "matrix"],
            "selected_takeaways": ["MCP tools can mutate inbox"],
            "why": "Exercise MCP inbox to OKF flow.",
        })
        archive_item = await call("inbox", "alcove_inbox_manual_add", {
            "workspace": str(kb),
            "title": "MCP Matrix Archive",
            "content": "MCP matrix archive body.",
            "source": "smoke://mcp-matrix/archive",
        })
        archived = await call("inbox", "alcove_inbox_archive", {
            "workspace": str(kb),
            "name": archive_item["id"],
            "topic": "agent-engineering/mcp",
            "summary": "MCP matrix archive source.",
            "tags": ["mcp", "archive"],
        })
        todo_item = await call("inbox", "alcove_inbox_manual_add", {
            "workspace": str(kb),
            "title": "MCP Matrix Todo",
            "content": "MCP matrix todo body.",
            "source": "smoke://mcp-matrix/todo",
        })
        await call("inbox", "alcove_inbox_todo", {
            "workspace": str(kb),
            "name": todo_item["id"],
            "reason": "Exercise MCP inbox todo routing.",
        })
        delete_item = await call("inbox", "alcove_inbox_manual_add", {
            "workspace": str(kb),
            "title": "MCP Matrix Delete",
            "content": "MCP matrix delete body.",
            "source": "smoke://mcp-matrix/delete",
        })
        await call("inbox", "alcove_inbox_delete", {
            "workspace": str(kb),
            "name": delete_item["id"],
            "confirm": False,
        })
        await call("inbox", "alcove_inbox_delete", {
            "workspace": str(kb),
            "name": delete_item["id"],
            "confirm": True,
        })
        await call("knowledge", "alcove_knowledge_revise", {
            "workspace": str(kb),
            "path": "concepts/agent-engineering/mcp/mcp-matrix-inbox.md",
            "summary": "MCP matrix revised concept.",
            "append": "MCP matrix revision note.",
            "tags": ["mcp", "revised"],
            "reason": "matrix revision",
        })
        await call("knowledge", "alcove_knowledge_add_question", {
            "workspace": str(kb),
            "topic": "agent-engineering/mcp",
            "question": "What does MCP matrix prove?",
            "answer": "It proves representative MCP tools can be called through stdio.",
            "tags": ["mcp"],
        })
        await call("knowledge", "alcove_knowledge_add_entity", {
            "workspace": str(kb),
            "topic": "agent-engineering/mcp",
            "name": "MCP Matrix",
            "kind": "tool",
            "summary": "Representative MCP tool smoke matrix.",
            "tags": ["mcp"],
        })
        await call("knowledge", "alcove_knowledge_topics", {"workspace": str(kb)})
        await call("knowledge", "alcove_get_topic", {
            "workspace": str(kb),
            "topic": "agent-engineering/mcp",
        })
        await call("knowledge", "alcove_knowledge_add_note", {
            "workspace": str(kb),
            "topic": "agent-engineering/mcp",
            "title": "MCP Matrix Standalone Note",
            "summary": "Standalone MCP matrix concept.",
            "tags": ["mcp", "standalone"],
        })
        await call("knowledge", "alcove_knowledge_promote", {
            "workspace": str(kb),
            "source": archived["source"],
            "topic": "agent-engineering/mcp",
            "summary": "Promoted MCP matrix archive source.",
        })
        await call("knowledge", "alcove_note_source", {
            "workspace": str(kb),
            "platform": "web",
            "title": "MCP Matrix Active Source",
            "topic": "agent-engineering/mcp",
            "resource": "https://example.com/mcp-matrix-active",
            "summary": "Active source used by MCP matrix refresh.",
            "tags": ["mcp", "active"],
        })
        await call("knowledge", "alcove_note_source", {
            "workspace": str(kb),
            "platform": "web",
            "title": "MCP Matrix Cleanup Source",
            "topic": "agent-engineering/mcp",
            "resource": "https://example.com/mcp-matrix-cleanup",
            "summary": "Obsolete source used by MCP matrix cleanup.",
            "tags": ["mcp", "cleanup"],
        })
        await call("knowledge", "alcove_knowledge_delete", {
            "workspace": str(kb),
            "path": "sources/web/agent-engineering/mcp-matrix-cleanup-source.md",
            "confirm": False,
        })
        await call("knowledge", "alcove_knowledge_delete", {
            "workspace": str(kb),
            "path": "sources/web/agent-engineering/mcp-matrix-cleanup-source.md",
            "confirm": True,
            "reason": "confirmed obsolete from MCP matrix search result",
        })
        await call("knowledge", "alcove_knowledge_refresh", {
            "workspace": str(kb),
            "topic": "agent-engineering/mcp",
            "summary": "Refreshed MCP matrix topic.",
        })

        pin = await call("global_memory", "alcove_pin_add", {
            "home": str(home),
            "title": "MCP Matrix Pin",
            "summary": "MCP matrix pin summary.",
            "content": "MCP matrix pin body.",
            "tags": ["mcp"],
        })
        pin_id = pin["pin"]["id"]
        await call("global_memory", "alcove_pin_get", {"home": str(home), "pin_id": pin_id})
        await call("global_memory", "alcove_pin_list", {"home": str(home)})
        await call("global_memory", "alcove_pin_search", {"home": str(home), "query": "matrix"})
        await call("global_memory", "alcove_pin_update", {
            "home": str(home),
            "pin_id": pin_id,
            "summary": "MCP matrix updated pin summary.",
            "tags": ["mcp", "updated"],
        })
        await call("global_memory", "alcove_pin_archive", {
            "home": str(home),
            "pin_id": pin_id,
            "confirm": False,
        })
        await call("global_memory", "alcove_pin_rebuild_index", {"home": str(home)})
        await call("global_memory", "alcove_pin_render_html", {
            "home": str(home),
            "output_path": str(report_path.parent / "pins.html"),
        })
        prompt = await call("global_memory", "alcove_prompt_save", {
            "home": str(home),
            "title": "MCP Matrix Prompt",
            "content": "Review MCP matrix output.",
            "description": "Prompt fixture.",
            "tags": ["mcp"],
        })
        await call("global_memory", "alcove_prompt_search", {"home": str(home), "query": "matrix"})
        prompt_id = prompt["prompt"]["id"]
        await call("global_memory", "alcove_prompt_get", {
            "home": str(home),
            "prompt_id": prompt_id,
        })
        await call("global_memory", "alcove_prompt_tags", {"home": str(home)})
        await call("global_memory", "alcove_prompt_archive", {
            "home": str(home),
            "prompt_id": prompt_id,
            "confirm": False,
        })
        await call("global_memory", "alcove_prompt_rebuild_index", {"home": str(home)})
        await call("global_memory", "alcove_project_add", {
            "home": str(home),
            "alias": "mcp-matrix",
            "path": str(kb),
            "note": "MCP project fixture.",
        })
        await call("global_memory", "alcove_project_get", {
            "home": str(home),
            "alias": "mcp-matrix",
        })
        await call("global_memory", "alcove_project_find", {"home": str(home), "keyword": "matrix"})
        await call("global_memory", "alcove_project_list", {"home": str(home)})
        project_root = report_path.parent / "project-roots"
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "matrix-root-project").mkdir(parents=True, exist_ok=True)
        await call("global_memory", "alcove_project_roots_set", {
            "home": str(home),
            "roots": [str(project_root)],
        })
        await call("global_memory", "alcove_okf_catalog_build", {
            "home": str(home),
        })

        task = await call("planner", "alcove_task_add", {
            "home": str(home),
            "title": "MCP Matrix Task",
            "notes": "Task fixture.",
            "tags": ["mcp"],
        })
        cancel_task = await call("planner", "alcove_task_add", {
            "home": str(home),
            "title": "MCP Matrix Cancel Task",
            "notes": "Task cancellation fixture.",
            "tags": ["mcp"],
        })
        await call("planner", "alcove_task_list", {"home": str(home)})
        idea = await call("planner", "alcove_idea_add", {
            "home": str(home),
            "title": "MCP Matrix Idea",
            "notes": "Idea fixture.",
            "tags": ["mcp"],
        })
        await call("planner", "alcove_idea_list", {"home": str(home)})
        await call("planner", "alcove_idea_promote", {
            "home": str(home),
            "idea_id": idea["idea"]["id"],
            "notes": "Promoted by MCP matrix.",
        })
        await call("planner", "alcove_task_complete", {
            "home": str(home),
            "task_id": task["task"]["id"],
        })
        await call("planner", "alcove_task_cancel", {
            "home": str(home),
            "task_id": cancel_task["task"]["id"],
        })
        await call("planner", "alcove_routine_add", {
            "home": str(home),
            "title": "MCP Matrix Routine",
            "notes": "Routine fixture.",
            "tags": ["mcp"],
            "next_due": "2026-07-10",
        })
        await call("planner", "alcove_routine_list", {"home": str(home)})
        await call("planner", "alcove_routine_materialize_due", {
            "home": str(home),
            "today": "2026-07-10",
        })

        await call("external_indexes", "alcove_mount_add", {
            "home": str(home),
            "path": str(mount_dir),
            "name": "mcp-matrix",
            "tags": ["mcp"],
        })
        await call("external_indexes", "alcove_mount_scan", {"home": str(home), "mount_id": "mcp-matrix"})
        await call("external_indexes", "alcove_mount_list", {"home": str(home)})
        await call("external_indexes", "alcove_connector_github_stars_index", {
            "home": str(home),
            "export_file": str(github_stars),
            "tags": ["mcp"],
        })
        await call("external_indexes", "alcove_connector_apple_notes_index", {
            "home": str(home),
            "export_dir": str(apple_export),
            "tags": ["mcp"],
        })
        await call("external_indexes", "alcove_connector_chrome_bookmarks_index", {
            "home": str(home),
            "export_file": str(chrome_bookmarks),
            "tags": ["mcp"],
        })
        await call("external_indexes", "alcove_connector_chrome_bookmarks_import_local", {
            "home": str(home),
            "source_file": str(chrome_bookmarks),
            "source_id": "matrix-local",
            "tags": ["mcp", "local"],
        })
        await call("external_indexes", "alcove_connector_refresh", {
            "home": str(home),
            "connector": "chrome-bookmarks",
            "source_id": "matrix-local",
            "stale_only": False,
        })
        await call("external_indexes", "alcove_connector_fetch", {
            "home": str(home),
            "item_path": "connectors/github-stars#octopusgarage/matrix",
        })
        await call("external_indexes", "alcove_link_source", {
            "home": str(home),
            "workspace": str(kb),
            "item_path": "connectors/github-stars#octopusgarage/matrix",
            "topic": "agent-engineering/mcp",
            "summary": "Linked MCP matrix GitHub star.",
            "create_concept": True,
        })
        connector_status = await call("external_indexes", "alcove_connector_status", {"home": str(home)})
        status_connectors = {
            str(source.get("connector") or "")
            for source in connector_status.get("sources", [])
            if isinstance(source, dict)
        }
        if connector_status.get("count", 0) < 3 or not {
            "github-stars",
            "apple-notes",
            "chrome-bookmarks",
        }.issubset(status_connectors):
            raise SystemExit(f"connector status missed indexed sources: {connector_status}")

        await call("search", "alcove_search", {
            "home": str(home),
            "workspace": str(kb),
            "query": "matrix",
        })
        await call("health_export", "alcove_validate", {"workspace": str(kb)})
        await call("health_export", "alcove_gardener", {"workspace": str(kb)})
        await call("health_export", "alcove_doctor", {"workspace": str(kb)})
        await call("health_export", "alcove_health", {
            "home": str(home),
            "workspace": str(kb),
            "fix": True,
        })
        await call("health_export", "alcove_export_global", {
            "home": str(home),
            "output_dir": str(report_path.parent / "export-global"),
        })
        await call("health_export", "alcove_export_kb", {
            "home": str(home),
            "kb": "matrix_kb",
            "output_dir": str(report_path.parent / "export-kb"),
        })
        await call("health_export", "alcove_export_all", {
            "home": str(home),
            "output_dir": str(report_path.parent / "export-all"),
        })
        await call("global_memory", "alcove_project_remove", {
            "home": str(home),
            "alias": "mcp-matrix",
        })

    toolset_checks = {
        "lite": await inspect_toolset(
            "lite",
            {
                "alcove_search",
                "alcove_pin_add",
                "alcove_task_add",
                "alcove_prompt_save",
                "alcove_inbox_manual_add",
                "alcove_health",
            },
            {
                "alcove_connector_github_stars_import_url",
                "alcove_mount_scan",
                "alcove_export_all",
                "alcove_gardener",
            },
        ),
        "kb": await inspect_toolset(
            "kb",
            {
                "alcove_search",
                "alcove_inbox_peek",
                "alcove_inbox_note",
                "alcove_knowledge_revise",
                "alcove_knowledge_delete",
                "alcove_validate",
                "alcove_health",
            },
            {
                "alcove_connector_chrome_bookmarks_import_local",
                "alcove_export_all",
                "alcove_gardener",
            },
        ),
    }

    failed = [check for check in checks if check["status"] != "passed"]
    for check in toolset_checks.values():
        if check["status"] != "passed":
            failed.append(
                {
                    "module": "toolsets",
                    "tool": str(check["toolset"]),
                    "status": "failed",
                    "expect": "Lite and KB MCP toolsets expose the intended narrow surfaces.",
                    "summary": json.dumps(check, ensure_ascii=False),
                }
            )
    modules: dict[str, int] = {}
    for check in checks:
        modules[check["module"]] = modules.get(check["module"], 0) + 1
    external_coverage = [
        {
            "tool": "alcove_connector_apple_notes_import_local",
            "reason": "Requires macOS Notes automation permissions; covered by real integrations smoke.",
        },
        {
            "tool": "alcove_connector_github_stars_import_url",
            "reason": "Requires live GitHub/network; covered by real integrations smoke.",
        },
    ]
    cli_only_workflows = {
        "blog_monitor": {
            "reason": "Blog monitoring is a scheduled/Hub CLI workflow, not a global MCP mutation surface.",
            "commands": [
                "alcove blog list --status '' --json",
                "alcove blog check --json",
                "alcove blog check <source-id> --json",
            ],
            "covered_by": ["isolated smoke blog-monitor-smoke.json", "Hub entry skill routing"],
        },
        "radars": {
            "reason": "Radar definitions and runs are user-selected CLI workflows; MCP search can discover generated reports.",
            "commands": [
                "alcove radar list --json",
                "alcove radar status <radar-id> --json",
                "alcove radar run <radar-id> --json",
            ],
            "covered_by": ["isolated smoke radar-list/run/status", "Hub entry skill routing"],
        },
        "dashboard": {
            "reason": "Dashboard is served over local HTTP and validated by browser smoke, not MCP calls.",
            "commands": [
                "alcove dashboard build --json",
                "alcove serve --dashboard --home ~/.alcove",
            ],
            "covered_by": ["dashboard browser smoke", "real-home dashboard build"],
        },
    }
    called_tools = {str(check.get("tool") or "") for check in checks}
    external_tools = {str(item["tool"]) for item in external_coverage}
    uncovered_tools = sorted(set(tool_names) - called_tools - external_tools)
    if uncovered_tools:
        failed.extend(
            {
                "module": "coverage",
                "tool": tool,
                "status": "failed",
                "expect": "Every MCP tool must be directly called or explicitly covered by an external smoke suite.",
                "summary": "uncovered MCP tool",
            }
            for tool in uncovered_tools
        )
    check_rollup = [
        {
            "module": str(check.get("module", "")),
            "tool": str(check.get("tool", "")),
            "status": str(check.get("status", "")),
        }
        for check in checks
    ]
    check_rollup_by_module: dict[str, dict[str, Any]] = {}
    for row in check_rollup:
        module = row["module"] or "unknown"
        module_rollup = check_rollup_by_module.setdefault(
            module,
            {"calls": 0, "passed": 0, "failed": 0, "tools": []},
        )
        module_rollup["calls"] += 1
        if row["status"] == "passed":
            module_rollup["passed"] += 1
        else:
            module_rollup["failed"] += 1
        tool_status = f"{row['tool']}:{row['status']}"
        if tool_status not in module_rollup["tools"]:
            module_rollup["tools"].append(tool_status)
    payload = {
        "status": "failed" if failed else "passed",
        "tool_count": len(tool_names),
        "called_tools": len(checks),
        "module_counts": modules,
        "module_call_counts": modules,
        "module_tool_counts": {
            module: len(rollup["tools"])
            for module, rollup in check_rollup_by_module.items()
        },
        "checks": checks,
        "check_rollup": check_rollup,
        "check_rollup_by_module": check_rollup_by_module,
        "samples": samples,
        "toolset_checks": toolset_checks,
        "artifacts": str(report_path.parent),
        "covered_by_external_smoke": external_coverage,
        "cli_only_workflows": cli_only_workflows,
        "external_coverage_policy": {
            "status": "enforced",
            "direct_call_exceptions": sorted(external_tools),
            "uncovered_tools": uncovered_tools,
            "fail_when": "An MCP tool is neither called by the MCP matrix nor externally covered.",
        },
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if failed:
        raise SystemExit("MCP matrix failed")


def summarize(payload: dict[str, Any]) -> str:
    for key in ("status", "count", "tool_count"):
        if key in payload:
            return f"{key}={payload[key]}"
    if "item" in payload and isinstance(payload["item"], dict):
        return str(payload["item"].get("title") or payload["item"].get("name") or "item")
    if "results" in payload:
        return f"results={len(payload.get('results') or [])}"
    if "task" in payload and isinstance(payload["task"], dict):
        return str(payload["task"].get("title") or "task")
    if "pin" in payload and isinstance(payload["pin"], dict):
        return str(payload["pin"].get("title") or "pin")
    public_keys = [key for key in sorted(payload.keys()) if key not in LOCAL_PATH_KEYS]
    return ",".join(public_keys[:4])


asyncio.run(main())
PY
