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
- Keep implementation and docs aligned in the same change. When code changes
  user-visible behavior, storage, CLI/MCP contracts, agent entries, dashboard,
  radars, connectors, mounts, OKF, smoke, eval, or install flows, update the
  related docs or state why no docs change is needed. Use `$alcove-doc-sync`
  for the checklist.
- Review the public GitHub Pages site when public docs, entry modes,
  workspaces, MCP/CLI routing, publishing, dashboard, or install flows change.
  Update `site/index.html` only when the global public overview would drift:
  project positioning, entry model, installation path, or top-level module
  relationships changed. Do not add narrow feature details to the site just
  because a feature changed.
- Treat entry-mode impact as part of every feature change. Most day-to-day
  usage starts from the Hub workspace, so new or changed behavior must answer:
  does `alcove-hub` need routing/protocol updates, do lightweight business
  workspaces need `alcove-workspace` guidance, does the managed-KB entry need
  workflow updates, and should global MCP expose only a lightweight tool or
  command hint? Update the relevant skill templates, MCP toolsets, docs, and
  smoke/eval coverage in the same change.

Selection rule:

- Use `scripts/smoke.sh` by default for normal code changes.
- Use `scripts/check-docs-drift.sh` or `$alcove-doc-sync` when changed source
  behavior may need docs updates or a public Pages review.
- Add `scripts/smoke-real-home.sh` for global home, dashboard, search, pins,
  tasks, prompts, projects, mounts, or connector changes.
- Use `scripts/smoke-real-integrations.sh` for capture, Clipsmith handoff,
  GitHub Stars, Apple Notes, OCR, external connector IO, or MCP stdio changes.
  It performs real network/local app work.
- Use `scripts/eval-ai.sh` for AI judgement over summary quality,
  classification/routing quality, dashboard usefulness, and agent prompt
  quality.
- Run `scripts/check.sh` before reporting implementation complete.
