---
paths:
  - "src/alcove/**/*.py"
  - "frontend/dashboard/**"
  - "scripts/**/*.sh"
  - "README.md"
  - "docs/**/*.md"
  - "site/**"
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
- For every user-facing feature, do an entry-mode impact check before finishing:
  Hub workspace first, then lightweight business workspaces when scene-scoped
  behavior changes, then managed-KB workspace, then global MCP/command hints,
  then local service/dashboard if relevant. Update the matching skills,
  toolsets, docs, and smoke/AI eval coverage when the behavior changes.
- Update docs in the same change, or state explicitly why the changed behavior
  is internal and does not need user-facing documentation.
- Keep `README.md` concise. Put architecture, data layout, entry mode, module,
  verification, and operational details under `docs/`.
- Review `site/index.html` when public overview docs, entry modes, workspaces,
  MCP/CLI routing, dashboard, publishing, install, or module boundaries change.
  Update it only when the global public overview would drift: project
  positioning, entry model, installation path, or top-level module
  relationships. Do not move narrow feature details from `docs/` into the
  landing page.
- Prefer these destinations:
  - `docs/architecture.md` for the system relationship map.
  - `docs/modules.md` for module boundaries and data contracts.
  - `docs/entry-modes.md` for Hub, KB, and MCP/agent entry behavior.
  - `docs/data-and-backup.md` for user data, export, backup, and sync paths.
  - `docs/usage.md` for CLI and day-to-day commands.
  - `docs/evals/agent-quality-gates.md` for smoke/eval/hook behavior.
  - `site/index.html` for the public GitHub Pages overview when the global
    story changes.
- Before reporting completion, run `scripts/agent-quality-gate.sh --mode coach`
  and follow any docs alignment or eval guidance it reports.
