# Alcove Local Smoke Eval

Use this eval when an agent needs to verify Alcove locally without relying on
manual browser clicks or ad hoc shell exploration.

## Goals

- Prove the CLI can drive the main Alcove flows end to end in an isolated
  sandbox.
- Prove the current machine's `~/.alcove` can still be read and summarized
  without mutating user data.
- Give Codex or Claude a repeatable repair loop: run, inspect, fix, rerun,
  report.

## Commands

Verification implementations are grouped in `scripts/verify/`. The top-level
`scripts/*.sh` files are stable wrapper entry points, so existing CI, Codex, and
Claude commands can keep using the shorter paths.

Run the isolated smoke first:

```sh
scripts/smoke.sh
```

Run the real-home read-only smoke second:

```sh
scripts/smoke-real-home.sh
```

To keep the isolated smoke artifacts for debugging:

```sh
ALCOVE_SMOKE_KEEP=1 scripts/smoke.sh
```

To save real-home reports somewhere deterministic:

```sh
ALCOVE_REAL_SMOKE_REPORT_DIR=.tmp/real-home-smoke scripts/smoke-real-home.sh
```

Run high-cost real integrations only when the change touches capture,
connectors, OCR, or MCP process boundaries:

```sh
scripts/smoke-real-integrations.sh
```

Run agent-client smoke when the change touches Hub/KB entry installation,
Codex skills, Claude commands, or MCP client routing:

```sh
scripts/smoke-agent-clients.sh
```

Run focused deeper smokes when the change touches their surfaces:

```sh
scripts/smoke-mcp-matrix.sh
scripts/smoke-dashboard-browser.sh
scripts/smoke-radar-reports.sh
scripts/smoke-export-restore.sh
scripts/smoke-messy-inbox.sh
```

Run AI quality eval when the change touches summarization, classification,
dashboard usefulness, agent prompts, or workflow intent routing:

```sh
scripts/eval-ai.sh
```

Let the repository choose the required smoke/eval plan from the current git
changes:

```sh
scripts/agent-quality-gate.sh --mode coach
```

Enforce the selected plan automatically:

```sh
ALCOVE_AGENT_GATE_MODE=strict scripts/agent-quality-gate.sh --surface manual
```

Prepare the AI packet without calling an AI provider:

```sh
ALCOVE_AI_EVAL_PROVIDER=none scripts/eval-ai.sh
```

If Clipsmith is not cloned next to Alcove as `../clipsmith`, provide its source
checkout explicitly:

```sh
ALCOVE_CLIPSMITH_ROOT=/path/to/clipsmith scripts/smoke-real-integrations.sh
```

## Generic Agent Prompts

Use this prompt in Codex, Claude Code, or another coding agent when you want the
agent to choose the correct verification level:

```text
Run the appropriate Alcove verification for the current change.

Start from the current repository root. First run
scripts/agent-quality-gate.sh --mode coach to inspect the repository-selected
verification plan. Use scripts/smoke.sh by default. Add
scripts/smoke-real-home.sh if the change touches global home data, dashboard,
search, pins, tasks, prompts, projects, mounts, or connectors. Use
scripts/smoke-real-integrations.sh only if the change touches capture,
Clipsmith handoff, GitHub Stars, Apple Notes, OCR, external connector IO, or MCP
stdio behavior. Use scripts/smoke-agent-clients.sh when the change touches
Codex/Claude entry files or MCP client routing. Use the focused deeper smokes
for MCP tool-group coverage, dashboard browser behavior, export restore
readiness, and messy inbox review quality.

Inspect failing JSON artifacts under .tmp/, decide whether the script or
application is wrong, fix the smallest issue, rerun the failed suite, and run
scripts/check.sh before reporting completion. Report command evidence and any
remaining untested external areas.
```

Use this prompt when you want AI judgement over product quality:

```text
Run Alcove's AI quality eval from the current repository root:
scripts/eval-ai.sh.

Read .tmp/ai-eval/ai-review.json after it finishes. Report the AI verdict,
score, blocking findings, should-fix findings, and whether the deterministic
setup smoke suites all passed. If findings identify concrete bugs or prompt
quality issues, fix the smallest issue and rerun scripts/eval-ai.sh plus
scripts/check.sh.
```

Use this prompt when you only want a non-mutating local health read:

```text
Run Alcove's read-mostly real-home smoke from the current repository root:
ALCOVE_REAL_SMOKE_REPORT_DIR=.tmp/real-home-smoke scripts/smoke-real-home.sh.
Do not create, archive, refresh network connectors, or modify user records.
Report the summary counts and failed artifact path if any check fails.
```

## What `scripts/smoke.sh` Covers

- `home init`
- workspace initialization
- KB registry and KB-local entry installation
- hub and global install print flows
- inbox manual add, peek, read, note
- knowledge source, concept writes, and structured note revision
- KB search
- pins, prompts, projects, tasks, ideas, routines
- mount add, scan, search participation
- GitHub Stars indexing from a local fixture
- Chrome Bookmarks indexing and search from a local fixture
- Apple Notes indexing from a local fixture
- connector fetch
- source linking into a managed KB
- dashboard pin import and build
- export all
- doctor

This script uses temporary directories and fixture data. It must not read or
write the user's real `~/.alcove`.

## What `scripts/smoke-real-home.sh` Covers

- Connector status
- Mount list
- KB registry list
- Pin list
- Task list
- Idea list
- Prompt search
- Project list
- Dashboard snapshot rebuild without rebuilding frontend assets
- A non-mutating global search

This script may rebuild `~/.alcove/dashboard/snapshot.json`, but it must not
create, update, archive, delete, refresh, export from network, or modify user
records.

## What `scripts/smoke-real-integrations.sh` Covers

- Live GitHub Stars network import and search.
- Local Notes.app export and Apple Notes connector search.
- Clipsmith generic web capture, bundle validation, finalize, inbox sink, and
  Alcove inbox read.
- Local macOS Vision OCR through Clipsmith, `ocr.md` bundle persistence, inbox
  sink, and Alcove inbox read that includes OCR text.
- MCP stdio process startup, tool listing, search, inbox peek, and connector
  status calls.

This script writes only to `.tmp/real-integrations` by default, but it does make
real network requests and reads the local Notes.app library. It may require
macOS Automation permission for the terminal or agent host process.

## What `scripts/smoke-agent-clients.sh` Covers

- Hub entry installation for Codex and Claude profiles.
- Managed-KB entry installation for Codex and Claude profiles.
- Global-lite install plan rendering for Codex and Claude.
- MCP stdio client startup, tool listing, search, inbox peek, and connector
  status calls.
- Optional `codex exec` and `claude -p` probes when explicitly enabled with
  `ALCOVE_AGENT_CLIENT_SMOKE_CODEX=1` or
  `ALCOVE_AGENT_CLIENT_SMOKE_CLAUDE=1`.

This script writes only to `.tmp/agent-clients` by default. It does not call
Codex or Claude model clients unless the opt-in environment variables are set.

## What Focused Deep Smokes Cover

- `scripts/smoke-mcp-matrix.sh`: calls representative MCP tools across inbox,
  knowledge, global memory, planner, external indexes, search, and health/export.
- `scripts/smoke-dashboard-browser.sh`: builds an isolated dashboard and checks
  desktop/mobile routes including Usage/data health, search results,
  per-module screenshots, horizontal overflow, mobile topbar compactness,
  mobile snapshot-meta hiding, and console errors with Playwright when
  available.
- `scripts/smoke-radar-reports.sh`: builds deterministic technology, world
  news, stocks, and sports radar reports, then checks Markdown structure,
  report HTML, desktop/mobile screenshots, and horizontal overflow.
- `scripts/smoke-export-restore.sh`: exports an isolated home/KB, restores the
  data into a fresh home/workspace, re-registers the KB, and verifies search,
  list, doctor, and validate flows.
- `scripts/smoke-messy-inbox.sh`: creates messy inbox bundles with long
  truncated content, warnings, duplicated OCR, missing summaries, and validates
  the agent review surface.

## What `scripts/eval-ai.sh` Covers

- Runs the deterministic setup suites: isolated smoke, real-home smoke, and
  real integrations, plus agent-client and focused deep smokes.
- Builds `.tmp/ai-eval/ai-eval-packet.json` with representative evidence for
  capture/inbox, OKF knowledge, pins/prompts/projects/tasks, connectors/mounts,
  the global OKF catalog, dashboard, MCP, export/health, messy inbox fixtures,
  restore rehearsal, and agent entries.
- Includes planner digest notification text so the AI reviewer can catch
  repeated titles, leaked internal record ids, confusing section spacing, or
  missing actionable detail.
- Includes dashboard browser layout summaries for desktop/mobile routes so the
  AI reviewer can see whether the navigation and module pages remain readable,
  not just whether the build succeeded.
- Builds `.tmp/ai-eval/ai-eval-prompt.md`.
- Calls an AI reviewer through `codex exec` by default, or `claude -p` when
  `ALCOVE_AI_EVAL_PROVIDER=claude`.
- Writes `.tmp/ai-eval/ai-review.json` and validates that the result is
  machine-readable JSON.
- Blog monitor evidence is deterministic by default: fixture-backed discovery,
  capture-to-inbox, summary output, notification contract, and structured
  failure alerts. Live Playwright checks against user-configured blog sites are
  release-grade or user-data-specific checks because external sites can drift.

Run the release-grade Codex/Claude entry probe when agent prompts, skills, or
entry wiring change:

```sh
ALCOVE_AGENT_CLIENT_SMOKE_CODEX=1 ALCOVE_AGENT_CLIENT_SMOKE_CLAUDE=1 scripts/smoke-agent-clients.sh
```

## What `scripts/agent-quality-gate.sh` Covers

- Discovers changed files from git, including staged, unstaged, and untracked
  files.
- Maps changed files to risk areas: agent entries, AI eval, OKF/search,
  CLI/MCP, inbox/capture, connectors/mounts, dashboard, memory writes, and
  verification infrastructure.
- Selects focused AI eval suites with `ALCOVE_AI_EVAL_SUITES` so everyday
  regression checks do not refresh unrelated smoke evidence.
- Emits valid hook JSON for Codex and Claude Code when `--hook-json` is used.
- Defaults to coach mode so hooks report required checks without blocking.
- Supports strict mode with `ALCOVE_AGENT_GATE_MODE=strict`, which executes the
  selected checks and returns a Stop-hook continuation reason on failure, so
  Codex or Claude Code can keep repairing instead of finishing with a broken
  gate.

See [Agent Quality Gates](agent-quality-gates.md) for the hook contract and
trigger matrix, and [Agent AI Eval Guardrails](agent-ai-eval-guardrails.md) for
the Codex/Claude source research behind the design.

## Agent Repair Loop

When a smoke script fails:

1. Read the failing command and the JSON artifact path in the script output.
2. Reproduce only the failing command with the same temporary paths.
3. Decide whether the script expectation is wrong or the application behavior
   is wrong.
4. Fix the smallest application or script issue.
5. Rerun `scripts/smoke.sh`.
6. If the fix touches home/global behavior, rerun `scripts/smoke-real-home.sh`.
7. Report:
   - command that failed
   - root cause
   - files changed
   - verification commands and outcomes
   - remaining untested areas

## Current Boundaries

The smoke suite intentionally does not:

- Drive login-gated X, XHS, or WeChat captures.
- Pull private GitHub or authenticated connector data.
- Validate a real Codex or Claude MCP client configuration outside stdio unless
  the optional CLI probes are explicitly enabled.
- Prove live Playwright discovery against every user-configured blog source on
  every eval run.
- Prove interactive Codex/Claude UI behavior unless the optional CLI probes are
  explicitly enabled.

Those flows remain higher-cost manual or semi-automated checks.
