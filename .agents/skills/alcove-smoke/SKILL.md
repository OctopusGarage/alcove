---
name: alcove-smoke
description: Use when the user asks to run Alcove smoke, eval, local verification, real-home smoke, real integrations, or project health from Codex/agent contexts.
---

# Alcove Smoke

Run Alcove verification suites from the repository root. If the current working
directory is unclear, locate it first:

```bash
repo="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$repo"
```

## Commands

Top-level `scripts/*.sh` files are stable wrappers. Implementations live under
`scripts/verify/`.

Fast isolated smoke:

```bash
scripts/smoke.sh
```

Keep isolated artifacts for debugging:

```bash
ALCOVE_SMOKE_KEEP=1 scripts/smoke.sh
```

Read-mostly real home smoke:

```bash
ALCOVE_REAL_SMOKE_REPORT_DIR=.tmp/real-home-smoke scripts/smoke-real-home.sh
```

High-cost real integrations:

```bash
scripts/smoke-real-integrations.sh
```

Agent-client entry smoke:

```bash
scripts/smoke-agent-clients.sh
```

Focused deep smokes:

```bash
scripts/smoke-mcp-matrix.sh
scripts/smoke-dashboard-browser.sh
scripts/smoke-radar-reports.sh
scripts/smoke-export-restore.sh
scripts/smoke-messy-inbox.sh
```

If Clipsmith is not cloned as `../clipsmith`, set:

```bash
ALCOVE_CLIPSMITH_ROOT=/path/to/clipsmith scripts/smoke-real-integrations.sh
```

Full project gate:

```bash
scripts/check.sh
```

Repository-selected agent gate:

```bash
scripts/agent-quality-gate.sh --mode coach
```

AI quality eval:

```bash
scripts/eval-ai.sh
```

Focused AI eval for a known risk area:

```bash
ALCOVE_AI_EVAL_SUITES=isolated,mcp_matrix ALCOVE_AI_EVAL_PROVIDER=none ALCOVE_AI_EVAL_RUN_CHECK=0 scripts/eval-ai.sh
ALCOVE_AI_EVAL_SUITES=isolated,mcp_matrix ALCOVE_AI_EVAL_SKIP_REFRESH=1 scripts/eval-ai.sh
```

Focused data/OKF health check for the current machine:

```bash
alcove health --home "${ALCOVE_HOME:-$HOME/.alcove}" --json
```

Use `--kb <name> --fix` when a managed KB and safe derived-index rebuilds should
be included.

Generate the packet and prompt without calling an AI provider:

```bash
ALCOVE_AI_EVAL_PROVIDER=none scripts/eval-ai.sh
```

## Selection

- Use `scripts/smoke.sh` by default after Alcove application or CLI changes.
- Use `scripts/smoke-real-home.sh` when global home, dashboard, pins, tasks,
  prompts, projects, mounts, connectors, or search changed.
- Use `scripts/smoke-real-integrations.sh` only when explicitly requested or
  when capture, Apple Notes, GitHub Stars, OCR, connector external IO, or MCP
  stdio changed. It reads local Notes.app data and performs network requests.
- Use `scripts/smoke-agent-clients.sh` when Hub/KB entry installation,
  Codex skills, Claude commands, or MCP client routing changed.
- Use `scripts/smoke-mcp-matrix.sh` when MCP tool routing or payloads changed.
- Use `alcove health --home ... --kb ... --fix --json` when OKF files, indexes,
  mounts, connectors, pins, prompts, or catalog generation changed.
- Use `scripts/smoke-dashboard-browser.sh` when dashboard frontend, snapshot,
  route, or search behavior changed.
- Use `scripts/smoke-radar-reports.sh` when radar presets, scoring, report
  content, or report HTML/CSS changed.
- Use `scripts/smoke-export-restore.sh` when export, backup, home/KB registry,
  or migration behavior changed.
- Use `scripts/smoke-messy-inbox.sh` when inbox reading, capture bundles,
  truncation, warnings, OCR, or review surfaces changed.
- Use `scripts/eval-ai.sh` when the user asks for AI eval or when quality of
  summarization, classification, dashboard usefulness, agent prompts, or
  workflow intent routing matters.
- Prefer `scripts/agent-quality-gate.sh --mode coach --json` to choose focused
  `ALCOVE_AI_EVAL_SUITES`; do not run full AI eval by habit during normal
  regression work.
- Use `scripts/agent-quality-gate.sh --mode coach` when the user asks whether
  the current change needs smoke/eval, or when the changed files span multiple
  modules and the correct verification set is not obvious.
- Use `scripts/check.sh` before claiming code changes are complete.

## Failure Handling

Inspect the failing JSON artifact under `.tmp/`, decide whether the script or
application is wrong, fix the smallest issue, then rerun the failed suite.

Report command outputs as evidence: pass/fail, key counts, changed files, and
remaining untested areas.
