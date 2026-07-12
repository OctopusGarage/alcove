# Alcove Documentation

Start with the user-facing guides, then use architecture and ADRs when changing
the system design.

## User Guides

- [Usage Guide](usage.md): common CLI/MCP workflows.
- [Entry Modes](entry-modes.md): hub, global MCP, managed KB, and MCP toolsets.
- [Modules](modules.md): feature modules and storage contracts.
- [Configurable Radars](radars.md): generic information radar definitions,
  source adapters, scheduled runs, and Social Radar migration.
- [Automations](automations.md): repeatable user jobs, Social Radar task import,
  service scheduling, and notification behavior.
- [Data and Backup](data-and-backup.md): data locations, export, sync, encryption.
- [Local Smoke / Agent Eval](evals/local-smoke.md): verification and repair workflows.
- [Agent Quality Gates](evals/agent-quality-gates.md): Codex/Claude hook
  automation, AI eval trigger rules, coach mode, and strict mode.

## Design

- [Architecture](architecture.md): relationship model and implementation overview.
- [Alcove OKF Profile](okf-profile.md): official OKF compatibility plus
  Alcove's stricter document, index, and refresh profile.
- [Read/Write Operating Model](read-write-model.md): broad AI-led reads and
  narrow CLI/MCP-governed writes.

## ADRs

- [ADR 0001: Alcove Home and Managed KB](adr/0001-alcove-home-and-managed-kb.md)
- [ADR 0002: CLI and MCP Adapters Use Application](adr/0002-cli-and-mcp-adapters-use-application.md)
- [ADR 0003: Link Uses Runtime Search Scope](adr/0003-link-uses-runtime-search-scope.md)
- [ADR 0004: Link Direct Index Lookup](adr/0004-link-direct-index-lookup.md)
- [ADR 0005: Application Private Capability Groups](adr/0005-application-private-capability-groups.md)
- [ADR 0006: MCP Adapter Invocation Context](adr/0006-mcp-adapter-invocation-context.md)
- [ADR 0007: External Index Refresh and Fetch](adr/0007-external-index-refresh-and-fetch.md)

## Archive

- [Archive Index](archive/README.md): historical design notes that are no
  longer the current command surface.
- [Original 2026-07-07 design notes](archive/2026-07-07-alcove-design.md):
  historical phase-1 planning. Use current guides and ADRs as the source of
  truth.
