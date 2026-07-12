# CLAUDE.md

Claude Code guidance for Alcove.

## Project Commands

- `/smoke` runs the isolated local smoke suite.
- `/smoke keep` runs the isolated smoke and keeps temporary artifacts.
- `/smoke-real-home` reads the current `~/.alcove` and rebuilds only the derived
  dashboard snapshot.
- `/smoke-real-integrations` runs the high-cost external integration smoke:
  GitHub Stars network import, local Notes.app export, Clipsmith web capture,
  local Vision OCR, inbox sink/read, and MCP stdio calls.
- `/eval-ai` runs deterministic setup plus AI quality review across capture,
  knowledge, memory, connectors, dashboard, MCP, export, and agent entries.

## Verification Commands

```bash
scripts/agent-quality-gate.sh --mode coach
scripts/smoke.sh
ALCOVE_REAL_SMOKE_REPORT_DIR=.tmp/real-home-smoke scripts/smoke-real-home.sh
scripts/smoke-real-integrations.sh
scripts/eval-ai.sh
scripts/check.sh
```

## Agent Quality Gate

- Claude Code project hooks are configured in `.claude/settings.json`.
- The `Stop` hook runs `scripts/agent-quality-gate.sh` in coach mode by default.
- Coach mode reports required smoke/eval commands without blocking the turn.
- Set `ALCOVE_AGENT_GATE_MODE=strict` to execute and enforce the selected
  checks automatically.
- See `docs/evals/agent-quality-gates.md` before changing hook, command,
  subagent, skill, AI eval, MCP routing, search, inbox, dashboard, or
  verification behavior.
- Claude path-scoped documentation rules live in `.claude/rules/`.
- Keep implementation and docs aligned in the same change. Use
  `/alcove-doc-sync` when code changes user-visible behavior, storage,
  CLI/MCP contracts, agent entries, dashboard, radars, connectors, mounts, OKF,
  smoke, eval, or install flows.

## Rules

- Prefer `scripts/smoke.sh` for normal implementation checks.
- Run `scripts/check-docs-drift.sh` when changed source behavior may need docs
  updates.
- Run `scripts/smoke-real-home.sh` when global home, dashboard, search, pins,
  tasks, prompts, projects, mounts, or connectors changed.
- Run `scripts/smoke-real-integrations.sh` only when explicitly asked or when
  capture, connector external IO, OCR, or MCP stdio boundaries changed.
- Run `scripts/eval-ai.sh` when AI quality matters: summarization,
  classification, dashboard usefulness, or agent prompt/intent routing changes.
- Do not commit `.tmp/`, dashboard build artifacts, connector exports, or real
  local user data.
- Before reporting completion, run the relevant smoke plus `scripts/check.sh`.
