# Alcove Documentation

Use this index as the source map for Alcove's user workflows, operating model,
and implementation constraints. Keep the README short; put durable details here.

## Start Here

- [Usage Guide](usage.md): daily CLI/MCP workflows and common commands.
- [Entry Modes](entry-modes.md): hub workspace, global MCP, managed KB, and
  local service entry profiles.
- [Modules](modules.md): feature groups, ownership boundaries, and storage
  contracts.
- [Prompt Library](prompts.md): reusable prompt records, curation, search,
  scenario recommendation, composition, and quality audit.
- [Data and Backup](data-and-backup.md): data locations, export, Git sync, and
  encryption recommendations.

## Intelligence Workflows

- [Configurable Radars](radars.md): generic radar definitions, presets, source
  adapters, scheduled runs, AI summaries, and notification sinks.
- [Automations](automations.md): repeatable user jobs, service scheduling, and
  task notification behavior.

## Architecture

- [Architecture](architecture.md): system relationship map, feature groups,
  storage boundaries, and implementation overview.
- [Alcove OKF Profile](okf-profile.md): official OKF compatibility plus
  Alcove's stricter document, index, and refresh profile.
- [Read/Write Operating Model](read-write-model.md): broad AI-led reads and
  narrow CLI/MCP-governed writes.

## Quality

- [Coverage](coverage.md): pytest-cov, CI upload, and Codecov badge setup.
- [Local Smoke / Agent Eval](evals/local-smoke.md): deterministic smoke checks
  and AI eval workflows.
- [Agent Quality Gates](evals/agent-quality-gates.md): Codex/Claude hook
  automation, trigger rules, coach mode, and strict mode.

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
