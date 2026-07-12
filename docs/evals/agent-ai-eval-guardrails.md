# Agent AI Eval Guardrails

Alcove uses deterministic smoke suites plus an AI reviewer to keep agent-facing
behavior from regressing when prompts, skills, MCP tools, dashboard views, or
knowledge workflows change.

## Source Research

- Codex reads `AGENTS.md` before work and layers global plus project guidance.
  Use it for durable repository expectations, not runtime enforcement:
  <https://developers.openai.com/codex/guides/agents-md>
- Codex skills package reusable workflows with progressive disclosure. Use
  project-local skills for repeatable smoke/eval procedures:
  <https://developers.openai.com/codex/skills>
- Codex project hooks live in `.codex/config.toml`. Command hooks are the
  currently reliable executable hook handler; prompt and agent hook handlers are
  parsed but skipped. Stop hooks can return `decision: "block"` to continue the
  turn with a repair prompt:
  <https://developers.openai.com/codex/hooks>
  <https://developers.openai.com/codex/config-reference>
- Codex custom subagents can be project-scoped under `.codex/agents/`, but they
  are configuration-layered spawned sessions. Use them for delegated work, not
  as the only enforcement mechanism:
  <https://developers.openai.com/codex/subagents>
- Claude Code `CLAUDE.md` and `.claude/rules/` are context, not hard
  enforcement. For mandatory checks, Claude's own docs recommend hooks:
  <https://docs.anthropic.com/en/docs/claude-code/memory>
- Claude Code hooks can run at session, turn, and tool-call events. Command
  hooks receive JSON on stdin and Stop hooks support top-level
  `decision: "block"` with a `reason`:
  <https://docs.anthropic.com/en/docs/claude-code/hooks>
- Claude Code skills supersede custom command files for new reusable workflows,
  while existing `.claude/commands/*.md` files still work:
  <https://docs.anthropic.com/en/docs/claude-code/skills>
- Claude Code subagents can carry specialized instructions and hooks, but their
  own docs still keep permission and configuration changes outside agent
  messages. Use subagents for review execution, not policy authority:
  <https://docs.anthropic.com/en/docs/claude-code/sub-agents>

## Alcove Layering

Alcove keeps the enforcement core tool-neutral:

1. `scripts/agent-quality-gate.sh` maps changed files to required suites.
2. `scripts/eval-ai.sh` builds canonical evidence and asks an AI reviewer for a
   schema-validated judgement.
3. `.codex/config.toml` and `.claude/settings.json` call the same gate from a
   Stop hook.
4. `AGENTS.md`, `CLAUDE.md`, `.agents/skills/alcove-smoke/SKILL.md`, and
   `.claude/commands/*.md` teach agents how to run, inspect, fix, and report the
   suites.
5. `.claude/agents/smoke-eval-runner.md` is a focused reviewer/executor profile
   for Claude Code. Codex currently relies on the project skill and hook-backed
   script gate rather than a custom agent file.

This split is intentional. Rules and prompts help the model choose well, but the
script gate is the stable contract that Codex, Claude Code, CI, and humans can
all run.

## Frozen Examples

The examples are not ad hoc chat transcripts. They are generated from committed
smoke scripts and validated by tests:

- `scripts/verify/smoke-isolated.sh` builds isolated fixtures for managed KB
  writes, inbox review, pins, prompts, projects, tasks, mounts, connectors,
  dashboard, export, doctor, and search.
- `scripts/verify/smoke-mcp-matrix.sh` calls representative MCP tools and saves
  JSON payloads for the AI packet.
- `scripts/verify/smoke-messy-inbox.sh` freezes difficult capture-review
  examples: long content, warnings, OCR, truncation, and missing summaries.
- `scripts/verify/smoke-dashboard-browser.sh` freezes browser-facing examples
  across desktop and mobile routes.
- `scripts/verify/smoke-radar-reports.sh` freezes four radar report examples
  across technology, world news, stocks, and sports, including Markdown
  structure and desktop/mobile browser presentation.
- `src/alcove/ai_eval.py` composes those artifacts into
  `.tmp/ai-eval/ai-eval-packet.json` and `.tmp/ai-eval/ai-eval-prompt.md`.
- `docs/evals/ai-review.schema.json` constrains reviewer output.
- `tests/test_ai_eval.py` and `tests/test_agent_quality_gate.py` pin the packet
  contract and trigger matrix.

When a new feature creates a new user-facing or agent-facing behavior, add a
deterministic fixture first, then expose that fixture in the AI eval packet.

## Modes

- `coach`: default. The Stop hook reports the required suites without blocking.
  Use this during normal development to avoid expensive evals on every turn.
- `strict`: executes the selected suites. If anything fails, the Stop hook
  returns `decision: "block"` with the gate message, so Codex or Claude Code can
  continue the repair loop from the failed evidence.
- `off`: disables hook planning.

Use strict mode for release hardening or prompt/routing work where regressions
are expensive:

```sh
ALCOVE_AGENT_GATE_MODE=strict codex
ALCOVE_AGENT_GATE_MODE=strict claude
```

For one-shot manual enforcement:

```sh
ALCOVE_AGENT_GATE_MODE=strict scripts/agent-quality-gate.sh --surface manual
```

## When AI Eval Must Run

AI eval is required for changes to:

- `AGENTS.md`, `CLAUDE.md`, `.agents/**`, `.claude/**`, `.codex/**`
- `scripts/eval-ai.sh`, `scripts/verify/eval-ai.sh`, `src/alcove/ai_eval.py`
- OKF, search, inbox review, capture, OCR, source linking
- MCP and CLI routing
- connectors, mounts, external indexes, lazy fetch
- dashboard snapshot/rendering/usage projection
- verification scripts that change smoke/eval evidence

Pure write-storage changes, such as planner or pin persistence internals, may be
covered by deterministic smoke, MCP matrix, export-restore, real-home smoke, and
`scripts/check.sh` without AI eval unless they change classification, summaries,
search presentation, or agent instructions.

## Recommended Repair Loop

1. Run `scripts/agent-quality-gate.sh --mode coach --json` to see the selected
   suites.
2. Run the listed deterministic suites.
3. Run `scripts/eval-ai.sh` when the plan includes `ai_packet` and `ai_review`.
4. Read `.tmp/ai-eval/ai-review.json`; fix blocking and should-fix findings.
5. Rerun the failed focused suite, then `scripts/check.sh`.
6. Report pass/fail evidence and any remaining external risks.
