---
paths:
  - "src/alcove/**/*.py"
  - "frontend/dashboard/**"
  - "scripts/**/*.sh"
  - "README.md"
  - "docs/**/*.md"
  - "AGENTS.md"
  - "CLAUDE.md"
  - ".agents/**/*.md"
  - ".claude/**/*.md"
  - ".codex/**/*.toml"
---

# Documentation Alignment

- When changing user-visible behavior, storage layout, CLI/MCP tools, agent
  entry behavior, dashboard views, radars, publishers, pins, tasks, prompts,
  projects, managed KBs, connectors, mounts, OKF, validation, smoke, eval, or
  install flows, inspect the related documentation in the same turn.
- Update docs in the same change, or state explicitly why the changed behavior
  is internal and does not need user-facing documentation.
- Keep `README.md` concise. Put architecture, data layout, entry mode, module,
  verification, and operational details under `docs/`.
- Prefer these destinations:
  - `docs/architecture.md` for the system relationship map.
  - `docs/modules.md` for module boundaries and data contracts.
  - `docs/entry-modes.md` for Hub, KB, and MCP/agent entry behavior.
  - `docs/data-and-backup.md` for user data, export, backup, and sync paths.
  - `docs/usage.md` for CLI and day-to-day commands.
  - `docs/evals/agent-quality-gates.md` for smoke/eval/hook behavior.
- Before reporting completion, run `scripts/agent-quality-gate.sh --mode coach`
  and follow any docs alignment or eval guidance it reports.
