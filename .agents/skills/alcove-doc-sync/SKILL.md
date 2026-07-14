---
name: alcove-doc-sync
description: Use when Alcove code, CLI/MCP behavior, storage contracts, agent entries, dashboard, radars, connectors, mounts, OKF, smoke, eval, or install flows change and documentation may need to be updated.
---

# Alcove Doc Sync

Use this workflow to keep Alcove implementation and documentation aligned.

## Procedure

1. Inspect the current diff:

```bash
git diff --name-only HEAD
git diff --cached --name-only
git ls-files --others --exclude-standard
```

2. Map changed behavior to documentation:

- `README.md`: short install and core usage only.
- `docs/architecture.md`: global relationships between managed knowledge
  bases, external knowledge, memory modules, automations, dashboard, and agent
  entries.
- `docs/modules.md`: module contracts, storage shape, and generated indexes.
- `docs/entry-modes.md`: Hub, KB workspace, MCP, Codex, and Claude behavior.
- `docs/data-and-backup.md`: user data paths, exports, backup, and sync.
- `docs/usage.md`: commands and operator flows.
- `docs/radars.md`: radar presets, source adapters, reporting, and
  notifications.
- `docs/okf-profile.md`: OKF conventions, catalogs, and indexes.
- `docs/evals/agent-quality-gates.md`: hooks, smoke, AI eval, and gate rules.

3. Run the entry-mode impact checklist for every user-facing feature:

- Hub workspace: should `src/alcove/profile_templates/hub/skills/alcove-hub/SKILL.md`
  and `src/alcove/profile_packs.py` gain or change intent routing, protocol
  steps, or safety rules? The Hub is the default day-to-day user entry.
- Managed KB workspace: should KB skills, inbox/capture commands, or OKF
  workflows change?
- Global MCP: should this remain a lightweight MCP operation, become a command
  hint, or be exposed only in `full`/KB toolsets?
- CLI: does the command shape still match how Hub and MCP agents should call
  it?
- Service/dashboard: does background or browser behavior need docs, smoke, or
  AI eval updates?

4. Update docs in the same change when behavior, storage, public CLI/MCP
surface, agent routing, dashboard UX, or verification expectations changed.

5. If no docs or entry updates are needed, write a short reason in the final
response.

6. Verify the decision:

```bash
scripts/check-docs-drift.sh
scripts/agent-quality-gate.sh --mode coach
```

Run any additional smoke/eval commands reported by the gate before claiming the
work is complete.
