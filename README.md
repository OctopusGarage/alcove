# Alcove

Alcove is a local-first personal information alcove for knowledge, pins, tasks, mounted sources, and agent-readable memory.

## Phase 1

- workspace initialization
- Markdown-first OKF knowledge writes
- inbox peek and note processing
- simple knowledge search

Deferred modules include Pins, Tasks, Mounts, the Apple Notes connector, and the MCP server.

## Commands

```sh
uv run alcove init .
uv run alcove status .
uv run alcove inbox --workspace . peek
uv run alcove knowledge --workspace . note-source --platform xhs --title "Example" --topic agent-engineering/agent-harness --summary "Summary"
uv run alcove search "Example" --workspace .
```

## Design

See [docs/design/2026-07-07-alcove-design.md](docs/design/2026-07-07-alcove-design.md) for the Phase 1 design.
