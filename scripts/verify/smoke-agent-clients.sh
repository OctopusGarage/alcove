#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

root="${ALCOVE_AGENT_CLIENT_SMOKE_DIR:-$repo_root/.tmp/agent-clients}"
root="$(python3 -c 'import sys; from pathlib import Path; print(Path(sys.argv[1]).expanduser().resolve())' "$root")"
home="$root/home"
kb="$root/research_notes"
hub="$root/hub"
fixtures="$root/fixtures"
report="$root/agent-client-smoke-report.json"
run_codex="${ALCOVE_AGENT_CLIENT_SMOKE_CODEX:-0}"
run_claude="${ALCOVE_AGENT_CLIENT_SMOKE_CLAUDE:-0}"
agent_cli_timeout="${ALCOVE_AGENT_CLIENT_SMOKE_TIMEOUT_SECONDS:-45}"

run() {
  printf 'agent-client-smoke: %s\n' "$*" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
}

run_with_timeout() {
  local seconds="$1"
  local cwd="$2"
  local stdout_path="$3"
  local stderr_path="$4"
  shift 4
  python3 - "$seconds" "$cwd" "$stdout_path" "$stderr_path" "$@" <<'PY'
import subprocess
import sys
from pathlib import Path

seconds = float(sys.argv[1])
cwd = sys.argv[2]
stdout_path = Path(sys.argv[3])
stderr_path = Path(sys.argv[4])
cmd = sys.argv[5:]

try:
    result = subprocess.run(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=seconds,
    )
except subprocess.TimeoutExpired as exc:
    stdout_path.write_text(exc.stdout or "", encoding="utf-8")
    stderr = exc.stderr or ""
    stderr += f"\nagent client probe timed out after {seconds:g}s\n"
    stderr_path.write_text(stderr, encoding="utf-8")
    raise SystemExit(124) from exc

stdout_path.write_text(result.stdout or "", encoding="utf-8")
stderr_path.write_text(result.stderr or "", encoding="utf-8")
raise SystemExit(result.returncode)
PY
}

assert_file_contains() {
  local path="$1"
  local needle="$2"
  if ! grep -Fq "$needle" "$path"; then
    printf 'agent-client-smoke: expected %s to contain %s\n' "$path" "$needle" >&2
    exit 1
  fi
}

rm -rf "$root"
mkdir -p "$fixtures"

export ALCOVE_HOME="$home"
alcove home init --json > "$fixtures/home-init.json"
alcove init "$kb" > "$fixtures/kb-init.txt"
alcove kb add research_notes "$kb" --json > "$fixtures/kb-add.json"

alcove hub init "$hub" --home "$home" --default-kb research_notes --target codex --json \
  > "$fixtures/hub-codex.json"
alcove hub init "$hub" --home "$home" --default-kb research_notes --target claude --json \
  > "$fixtures/hub-claude.json"
alcove kb --home "$home" install research_notes --target codex --json \
  > "$fixtures/kb-codex.json"
alcove kb --home "$home" install research_notes --target claude --json \
  > "$fixtures/kb-claude.json"
alcove global install --home "$home" --target codex --print --json \
  > "$fixtures/global-codex-print.json"
alcove global install --home "$home" --target claude --print --json \
  > "$fixtures/global-claude-print.json"

assert_file_contains "$hub/AGENTS.md" "Alcove"
assert_file_contains "$hub/CLAUDE.md" "Alcove"
assert_file_contains "$hub/.agents/skills/alcove-hub/SKILL.md" "Alcove"
assert_file_contains "$kb/AGENTS.md" "Alcove"
assert_file_contains "$kb/CLAUDE.md" "Alcove"
assert_file_contains "$kb/.agents/skills/alcove-kb/SKILL.md" "Alcove"
assert_file_contains "$kb/.agents/skills/alcove-capture/SKILL.md" "Alcove Capture"
assert_file_contains "$kb/.agents/skills/alcove-capture/SKILL.md" "Clipsmith"
assert_file_contains "$kb/.claude/skills/alcove-capture/SKILL.md" "Alcove Capture"
assert_file_contains "$kb/.claude/skills/alcove-capture/SKILL.md" "Clipsmith"
assert_file_contains "$kb/.claude/commands/inbox-peek.md" "alcove"

alcove inbox --kb research_notes manual-add "Agent Client Smoke" \
  --content "MCP client can read this inbox item." \
  --source "smoke://agent-client" \
  --json > "$fixtures/inbox-add.json"
alcove pin --home "$home" add "Agent Client Pin" \
  --summary "MCP search smoke." \
  --content "MCP client can find this global memory item." \
  --tag smoke \
  --json > "$fixtures/pin-add.json"

run uv run python - "$home" "$kb" "$fixtures/mcp-stdio-client.json" <<'PY'
import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

home = Path(sys.argv[1])
kb = Path(sys.argv[2])
report = Path(sys.argv[3])


async def main() -> None:
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
        log_file=report.with_name("mcp-stdio-server.log"),
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)
        search = await client.call_tool(
            "alcove_search",
            {"query": "MCP client", "home": str(home), "workspace": str(kb)},
        )
        inbox = await client.call_tool("alcove_inbox_peek", {"workspace": str(kb)})
        status = await client.call_tool("alcove_connector_status", {"home": str(home)})
        payload = {
            "tool_count": len(tool_names),
            "required_tools": [
                "alcove_command_hints",
                "alcove_search",
                "alcove_inbox_peek",
                "alcove_connector_status",
            ],
            "has_required_tools": all(
                name in tool_names
                for name in [
                    "alcove_command_hints",
                    "alcove_search",
                    "alcove_inbox_peek",
                    "alcove_connector_status",
                ]
            ),
            "search": search.structured_content,
            "inbox": inbox.structured_content,
            "connector_status": status.structured_content,
        }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not payload["has_required_tools"]:
        raise SystemExit("MCP required tools missing")
    if payload["search"].get("count", 0) < 1:
        raise SystemExit("MCP search did not return the smoke item")
    if payload["inbox"].get("item", {}).get("title") != "Agent Client Smoke":
        raise SystemExit("MCP inbox peek did not return the smoke item")


asyncio.run(main())
PY

codex_status="skipped"
codex_detail="ALCOVE_AGENT_CLIENT_SMOKE_CODEX=1 not set"
if [[ "$run_codex" == "1" ]]; then
  if command -v codex >/dev/null 2>&1; then
    set +e
    run_with_timeout "$agent_cli_timeout" "$hub" "$fixtures/codex-cli.log" "$fixtures/codex-cli.err" \
      codex exec \
      --cd "$hub" \
      --sandbox read-only \
      --output-last-message "$fixtures/codex-cli.out" \
      "Read AGENTS.md and answer with exactly: alcove hub entry ok"
    codex_rc=$?
    set -e
    if [[ "$codex_rc" -eq 0 ]] && grep -Fqi "alcove hub entry ok" "$fixtures/codex-cli.out"; then
      codex_status="passed"
      codex_detail="codex exec read the generated Hub AGENTS.md"
    else
      codex_status="failed"
      codex_detail="codex exec failed, timed out, or returned unexpected output; see $fixtures/codex-cli.log and $fixtures/codex-cli.err"
    fi
  else
    codex_status="skipped"
    codex_detail="codex CLI not found"
  fi
fi

claude_status="skipped"
claude_detail="ALCOVE_AGENT_CLIENT_SMOKE_CLAUDE=1 not set"
if [[ "$run_claude" == "1" ]]; then
  if command -v claude >/dev/null 2>&1; then
    set +e
    run_with_timeout "$agent_cli_timeout" "$hub" "$fixtures/claude-cli.out" "$fixtures/claude-cli.log" \
      claude -p "Read AGENTS.md and answer with exactly: alcove hub entry ok" \
      --permission-mode dontAsk --allowedTools Read
    claude_rc=$?
    set -e
    if [[ "$claude_rc" -eq 0 ]] && grep -Fqi "alcove hub entry ok" "$fixtures/claude-cli.out"; then
      claude_status="passed"
      claude_detail="claude -p read the generated Hub AGENTS.md"
    else
      claude_status="failed"
      claude_detail="claude -p failed, timed out, or returned unexpected output; see $fixtures/claude-cli.log"
    fi
  else
    claude_status="skipped"
    claude_detail="claude CLI not found"
  fi
fi

run uv run python - "$root" "$report" "$codex_status" "$codex_detail" "$claude_status" "$claude_detail" <<'PY'
import json
import sys
from pathlib import Path

from alcove.paths import compact_user_paths_in_text

root = Path(sys.argv[1])
report = Path(sys.argv[2])
codex_status, codex_detail, claude_status, claude_detail = sys.argv[3:7]
mcp = json.loads((root / "fixtures" / "mcp-stdio-client.json").read_text(encoding="utf-8"))
unverified_cli = [
    name
    for name, status in (("codex_cli", codex_status), ("claude_cli", claude_status))
    if status == "skipped"
]
checks = [
    {
        "name": "hub_entry_files",
        "status": "passed",
        "detail": "Hub AGENTS.md, CLAUDE.md, and Codex skill generated",
    },
    {
        "name": "managed_kb_entry_files",
        "status": "passed",
        "detail": "KB AGENTS.md, CLAUDE.md, Codex skills, and Claude inbox command generated",
    },
    {
        "name": "global_lite_print",
        "status": "passed",
        "detail": "Codex and Claude global-lite install plans rendered",
    },
    {
        "name": "mcp_stdio_client",
        "status": "passed" if mcp.get("has_required_tools") else "failed",
        "detail": f"{mcp.get('tool_count', 0)} tools; search and inbox calls returned smoke data",
    },
    {"name": "codex_cli", "status": codex_status, "detail": codex_detail},
    {"name": "claude_cli", "status": claude_status, "detail": claude_detail},
]
failed = [check["name"] for check in checks if check["status"] == "failed"]
payload = {
    "status": "failed" if failed else "passed",
    "verified_mode": "mcp_stdio_with_generated_files",
    "unverified_optional_cli_probes": unverified_cli,
    "release_grade_cli_probe_command": (
        "ALCOVE_AGENT_CLIENT_SMOKE_CODEX=1 "
        "ALCOVE_AGENT_CLIENT_SMOKE_CLAUDE=1 "
        "scripts/smoke-agent-clients.sh"
    ),
    "home": compact_user_paths_in_text(str(root / "home")),
    "hub": compact_user_paths_in_text(str(root / "hub")),
    "workspace": compact_user_paths_in_text(str(root / "research_notes")),
    "summary": {
        "mcp_tool_count": mcp.get("tool_count", 0),
        "mcp_search_count": mcp.get("search", {}).get("count", 0),
        "codex_cli": codex_status,
        "claude_cli": claude_status,
    },
    "checks": checks,
    "artifacts": compact_user_paths_in_text(str(root)),
}
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(f"agent client smoke failed: {', '.join(failed)}")
PY
