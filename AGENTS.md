# AGENTS.md

Rules for Codex and other coding agents in this repo.

@RTK.md

## Smoke / Eval Shortcuts

Project-local Codex skill:

- `$alcove-smoke`: choose and run the appropriate Alcove smoke/eval suite.

Claude Code project commands:

- `/smoke`
- `/smoke keep`
- `/smoke-real-home`
- `/smoke-real-integrations`
- `/eval-ai`

Direct commands:

```bash
scripts/agent-quality-gate.sh --mode coach
scripts/smoke.sh
ALCOVE_REAL_SMOKE_REPORT_DIR=.tmp/real-home-smoke scripts/smoke-real-home.sh
scripts/smoke-real-integrations.sh
scripts/eval-ai.sh
scripts/check.sh
```

Agent quality gate:

- Codex project hooks are configured in `.codex/config.toml`.
- Hooks run `scripts/agent-quality-gate.sh` on `Stop` in coach mode by default.
- Coach mode reports required smoke/eval commands without blocking the turn.
- Set `ALCOVE_AGENT_GATE_MODE=strict` to execute and enforce the selected
  checks automatically.
- See `docs/evals/agent-quality-gates.md` before changing hook, prompt, skill,
  AI eval, MCP routing, search, inbox, dashboard, or verification behavior.

Selection rule:

- Use `scripts/smoke.sh` by default for normal code changes.
- Add `scripts/smoke-real-home.sh` for global home, dashboard, search, pins,
  tasks, prompts, projects, mounts, or connector changes.
- Use `scripts/smoke-real-integrations.sh` for capture, Clipsmith handoff,
  GitHub Stars, Apple Notes, OCR, external connector IO, or MCP stdio changes.
  It performs real network/local app work.
- Use `scripts/eval-ai.sh` for AI judgement over summary quality,
  classification/routing quality, dashboard usefulness, and agent prompt
  quality.
- Run `scripts/check.sh` before reporting implementation complete.
