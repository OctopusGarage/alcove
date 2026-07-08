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
uv run alcove doctor --workspace . --json
uv run alcove inbox --workspace . peek
uv run alcove inbox --workspace . read web/example
uv run alcove knowledge --workspace . note-source --platform xhs --title "Example" --topic agent-engineering/agent-harness --summary "Summary"
uv run alcove search "Example" --workspace .
uv run alcove search --workspace . --tags
uv run alcove search --workspace . --recent 10
uv run alcove search --workspace . --tag agent-harness --platform web --json
uv run alcove search --workspace . --unindexed --json
uv run alcove pin --workspace . add "Japanese Edge Launcher" --description "Launch Edge with TZ=Asia/Tokyo" --tag app-launcher
uv run alcove pin --workspace . list --tag app-launcher
uv run alcove pin --workspace . archive japanese-edge-launcher --confirm
uv run alcove idea --workspace . add "Review mount design" --notes "Local folders first" --tag mounts
uv run alcove task --workspace . add "Wire MCP search" --priority high --tag mcp
uv run alcove task --workspace . complete wire-mcp-search
uv run alcove mount --workspace . add ~/programming/github --name github --type local-folder --tag repos
uv run alcove mount --workspace . scan github --json
uv run alcove serve --mcp --workspace .
uv run alcove install --workspace . --target codex --print
```

Alcove inbox folders can contain Clipsmith capture bundles. When `capture.json`
is present, Alcove uses it as fallback metadata for title, source URL, and date
while keeping Markdown files as the human-readable review surface.

Pins are small, high-value personal notes stored as Markdown under `pins/`.
They are included in `alcove search` alongside knowledge docs by default.

Ideas and tasks are stored in `tasks/tasks.json`. Active ideas and pending tasks
are included in `alcove search` by default.

Mounts let Alcove index external folders or local Git repositories without
copying their content. Scanned mounted items are included in `alcove search`.

The MCP server runs over stdio with FastMCP and currently exposes read-only
tools for search, inbox peek, and mount listing.

`alcove install` writes MCP client config for Codex and Claude Code. Use
`--print` to preview the exact config without writing files.

## Design

See [docs/design/2026-07-07-alcove-design.md](docs/design/2026-07-07-alcove-design.md) for the Phase 1 design.
