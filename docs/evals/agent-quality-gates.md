# Agent Quality Gates

Alcove has deterministic smoke tests and an AI reviewer. This page defines how
Codex, Claude Code, and humans decide when those checks must run.

## Operating Model

Agent quality gates are intentionally layered:

1. Cheap deterministic checks prove commands, schemas, indexes, and browser
   smoke behavior.
2. AI eval reviews product quality: summarization usefulness, routing quality,
   prompt quality, dashboard usefulness, and whether useful evidence is hidden.
3. Hooks run in coach mode by default so everyday agent work is not blocked by
   expensive evals. Strict mode is available for release work or risky changes.
   When strict mode fails, the hook returns a `decision: "block"` response so
   Codex or Claude Code continues with the failure reason instead of silently
   finishing the turn.

The shared implementation is:

```sh
scripts/agent-quality-gate.sh
```

It discovers the current git changes, maps changed files to risk areas, and
prints or executes the required verification commands. The reusable rule engine
lives in `src/alcove/agent_quality_gate.py` and is covered by unit tests.

## Installed Agent Hooks

Codex project hook:

```text
.codex/config.toml
```

Claude Code project hook:

```text
.claude/settings.json
```

Both hooks run on `Stop` and call the same gate script. They default to coach
mode:

```sh
ALCOVE_AGENT_GATE_MODE=coach
```

Coach mode returns a hook message with the required commands but does not block
the agent. To enforce the gate automatically:

```sh
ALCOVE_AGENT_GATE_MODE=strict
```

Strict mode runs the required checks and returns a blocking hook response if a
check fails. The hook sets a recursion guard so nested model-review calls do not
re-enter the gate.

See [Agent AI Eval Guardrails](agent-ai-eval-guardrails.md) for the source
research behind the Codex/Claude hook, skill, command, and subagent layering.

## AI Eval Trigger Rules

The gate requires AI eval when changed files touch any of these areas:

- `.claude/**`, `.agents/**`, `.codex/**`, `AGENTS.md`, `CLAUDE.md`
- agent profile installation or generated entry content
- `scripts/eval-ai.sh`, `scripts/verify/eval-ai.sh`, `src/alcove/ai_eval.py`
- OKF, search, MCP, CLI adapter routing, and read-path behavior
- inbox review, capture bundles, OCR, source linking, and summarization
- connectors, mounts, external indexes, lazy fetch, GitHub Stars, Apple Notes,
  Chrome Bookmarks
- dashboard snapshot, browser routes, usage projection, frontend views
- verification scripts that affect smoke/eval evidence

For AI-sensitive changes, the gate requires:

```sh
ALCOVE_AI_EVAL_PROVIDER=none scripts/eval-ai.sh
ALCOVE_AI_EVAL_SKIP_REFRESH=1 scripts/eval-ai.sh
```

The first command refreshes deterministic evidence and writes the AI eval
packet/prompt without calling a model. The second command reuses that evidence
and asks the configured reviewer, usually Codex in Codex and Claude in Claude
Code.

## Deterministic Trigger Rules

All matched changes require `scripts/smoke.sh` and `scripts/check.sh`.

Additional focused checks are selected by file area:

- Agent entry/profile changes: `scripts/smoke-agent-clients.sh`
- MCP/CLI/search changes: `scripts/smoke-mcp-matrix.sh`
- Dashboard changes: `scripts/smoke-dashboard-browser.sh`
- Export, backup, registry, or migration changes:
  `scripts/smoke-export-restore.sh`
- Inbox/capture/OCR review changes: `scripts/smoke-messy-inbox.sh`
- Configured home/search/pins/tasks/prompts/projects/mounts/connectors:
  `scripts/smoke-real-home.sh`
- Connector, capture, OCR, and process-boundary changes:
  `scripts/smoke-real-integrations.sh`

## Manual Use

Show the gate plan for current changes:

```sh
scripts/agent-quality-gate.sh --mode coach
```

Show machine-readable output:

```sh
scripts/agent-quality-gate.sh --mode coach --json
```

Run and enforce the plan:

```sh
ALCOVE_AGENT_GATE_MODE=strict scripts/agent-quality-gate.sh --surface manual
```

Run against explicit files when testing rules:

```sh
scripts/agent-quality-gate.sh \
  --mode coach \
  --changed-file .claude/commands/eval-ai.md \
  --changed-file src/alcove/ai_eval.py
```

## Contract

- Default hook behavior must stay coach mode unless the caller opts into strict.
- Hook output must be valid JSON when `--hook-json` is used.
- Strict hook failures must return `decision: "block"` with an actionable
  `reason`, allowing Codex/Claude to continue the repair loop from the failed
  smoke or AI eval evidence.
- Rules must be updated with tests whenever a new agent-facing, AI-quality, or
  verification-sensitive surface is added.
- Direct `scripts/eval-ai.sh` remains the source of truth for the AI review
  packet and reviewer schema.
