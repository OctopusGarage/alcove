#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

output_dir="${ALCOVE_AI_EVAL_DIR:-$repo_root/.tmp/ai-eval}"
provider="${ALCOVE_AI_EVAL_PROVIDER:-codex}"
skip_refresh="${ALCOVE_AI_EVAL_SKIP_REFRESH:-0}"
eval "$(uv run python -m alcove.verify_suites --root "$output_dir" --shell)"
packet="$output_dir/ai-eval-packet.json"
prompt="$output_dir/ai-eval-prompt.md"
review="$output_dir/ai-review.json"
bundle_info="$output_dir/ai-eval-bundle.json"
review_schema="$repo_root/docs/evals/ai-review.schema.json"

run() {
  printf 'ai-eval: %s\n' "$*" >&2
  "$@"
}

mkdir -p "$output_dir"

if [[ "$skip_refresh" != "1" ]]; then
  rm -rf \
    "$smoke_root" \
    "$real_home_dir" \
    "$real_integrations_dir" \
    "$agent_clients_dir" \
    "$mcp_matrix_dir" \
    "$dashboard_browser_dir" \
    "$export_restore_dir" \
    "$messy_inbox_dir"
  mkdir -p \
    "$smoke_root" \
    "$real_home_dir" \
    "$real_integrations_dir" \
    "$agent_clients_dir" \
    "$mcp_matrix_dir" \
    "$dashboard_browser_dir" \
    "$export_restore_dir" \
    "$messy_inbox_dir"
  run scripts/verify/check.sh > "$output_dir/check.log" 2>&1
  run env ALCOVE_SMOKE_TMP="$smoke_root" ALCOVE_SMOKE_KEEP=1 \
    scripts/verify/smoke-isolated.sh > "$output_dir/smoke.log" 2>&1
  run env ALCOVE_REAL_SMOKE_REPORT_DIR="$real_home_dir" \
    scripts/verify/smoke-real-home.sh > "$output_dir/real-home.log" 2>&1
  run env ALCOVE_REAL_INTEGRATION_DIR="$real_integrations_dir" \
    scripts/verify/smoke-real-integrations.sh > "$output_dir/real-integrations.log" 2>&1
  run env ALCOVE_AGENT_CLIENT_SMOKE_DIR="$agent_clients_dir" \
    scripts/verify/smoke-agent-clients.sh > "$output_dir/agent-clients.log" 2>&1
  run env ALCOVE_MCP_MATRIX_DIR="$mcp_matrix_dir" \
    scripts/verify/smoke-mcp-matrix.sh > "$output_dir/mcp-matrix.log" 2>&1
  run env ALCOVE_DASHBOARD_BROWSER_DIR="$dashboard_browser_dir" \
    scripts/verify/smoke-dashboard-browser.sh > "$output_dir/dashboard-browser.log" 2>&1
  run env ALCOVE_EXPORT_RESTORE_DIR="$export_restore_dir" \
    scripts/verify/smoke-export-restore.sh > "$output_dir/export-restore.log" 2>&1
  run env ALCOVE_MESSY_INBOX_DIR="$messy_inbox_dir" \
    scripts/verify/smoke-messy-inbox.sh > "$output_dir/messy-inbox.log" 2>&1
fi

run uv run python -m alcove.ai_eval \
  --output-dir "$output_dir" \
  --smoke-root "$smoke_root" \
  --real-home-report "$real_home_dir/real-home-smoke-report.json" \
  --real-integrations-dir "$real_integrations_dir" \
  --agent-client-report "$agent_clients_dir/agent-client-smoke-report.json" \
  --mcp-matrix-report "$mcp_matrix_dir/mcp-matrix-report.json" \
  --dashboard-browser-report "$dashboard_browser_dir/dashboard-browser-report.json" \
  --export-restore-report "$export_restore_dir/export-restore-report.json" \
  --messy-inbox-report "$messy_inbox_dir/messy-inbox-report.json" \
  --json > "$bundle_info"

if [[ "$provider" == "none" ]]; then
  printf 'ai-eval: prepared packet %s\n' "$packet"
  printf 'ai-eval: prepared prompt %s\n' "$prompt"
  exit 0
fi

if [[ "$provider" == "codex" ]]; then
  if ! command -v codex >/dev/null 2>&1; then
    printf 'ai-eval: codex not found; set ALCOVE_AI_EVAL_PROVIDER=claude or none\n' >&2
    exit 1
  fi
  run codex exec \
    --cd "$repo_root" \
    --sandbox read-only \
    --output-schema "$review_schema" \
    --output-last-message "$review" \
    - < "$prompt" > "$output_dir/codex-events.log"
elif [[ "$provider" == "claude" ]]; then
  if ! command -v claude >/dev/null 2>&1; then
    printf 'ai-eval: claude not found; set ALCOVE_AI_EVAL_PROVIDER=codex or none\n' >&2
    exit 1
  fi
  run claude -p \
    --permission-mode dontAsk \
    --allowedTools Read \
    < "$prompt" > "$review"
else
  printf 'ai-eval: unknown provider %s; expected codex, claude, or none\n' "$provider" >&2
  exit 1
fi

run uv run python - "$review" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8").strip()
if text.startswith("```"):
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    text = "\n".join(lines).strip()
try:
    payload = json.loads(text)
except json.JSONDecodeError as exc:
    raise SystemExit(f"AI review did not return valid JSON: {exc}\n{text[:2000]}") from exc
required = {"verdict", "score", "module_scores", "findings", "strong_points", "untested_risks"}
missing = sorted(required - set(payload))
if missing:
    raise SystemExit(f"AI review JSON missing required keys: {', '.join(missing)}")
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({
    "verdict": payload.get("verdict"),
    "score": payload.get("score"),
    "findings": len(payload.get("findings", [])),
}, ensure_ascii=False, indent=2))
PY

printf 'ai-eval: packet %s\n' "$packet"
printf 'ai-eval: review %s\n' "$review"
