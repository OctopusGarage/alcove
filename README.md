# Alcove

Alcove is a local-first personal information alcove for knowledge, pins, tasks, mounted sources, and agent-readable memory.

## Phase 1

- workspace initialization
- Markdown-first OKF knowledge writes
- inbox peek and note processing
- simple knowledge search

Deferred modules include richer MCP write tools, routine materialization, and
GitHub/star indexes.

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
uv run alcove idea --workspace . promote review-mount-design --priority high --due 2026-07-10
uv run alcove task --workspace . add "Wire MCP search" --priority high --tag mcp
uv run alcove task --workspace . complete wire-mcp-search
uv run alcove task --workspace . routine-add "Weekly inbox review" --every-days 7 --next-due 2026-07-08
uv run alcove task --workspace . materialize-due --today 2026-07-08 --json
uv run alcove mount --workspace . add ~/programming/github --name github --type local-folder --tag repos
uv run alcove mount --workspace . scan github --json
uv run alcove connector --workspace . apple-notes index ~/exports/apple-notes --tag apple-notes --json
uv run alcove connector --workspace . github-stars index ~/exports/github-stars.json --tag stars --json
uv run alcove link --workspace . source "connectors/github-stars#octopusgarage/alcove" ai-knowledge/knowledge-base --summary "Useful reference" --json
uv run alcove serve --mcp --workspace .
uv run alcove install --workspace . --target codex --print
uv run alcove install --workspace . --target codex --status --json
uv run alcove install --workspace . --target codex --uninstall --print
```

Alcove inbox folders can contain Clipsmith capture bundles. When `capture.json`
is present, Alcove uses it as fallback metadata for title, source URL, and date
while keeping Markdown files as the human-readable review surface.

Pins are small, high-value personal notes stored as Markdown under `pins/`.
They are included in `alcove search` alongside knowledge docs by default.

Ideas, tasks, and routines are stored in `tasks/tasks.json`. Active ideas and
pending tasks are included in `alcove search` by default. Routines materialize
only when `task materialize-due` or the matching MCP tool is called.

Mounts let Alcove index external folders or local Git repositories without
copying their content. Scanned mounted items are included in `alcove search`.

The Apple Notes connector indexes deterministic export directories produced by
the local Apple Notes skill contract: `notes/<encoded-note-id>/note.json`.
Alcove does not write to Notes.app and does not require Notes automation
permission for indexing an existing export.

The GitHub Stars connector indexes local JSON exports of starred repositories.
`alcove link source` promotes any indexed external item into an OKF Source while
keeping the original mount or connector as the source of truth.

The MCP server runs over stdio with FastMCP and exposes v1 tools for search,
inbox peek, source notes, topic lookup, pins, tasks, external source linking,
mount listing, and gardener health reports.

`alcove install` writes MCP client config for Codex and Claude Code. Use
`--print` to preview install or uninstall changes, `--status` to check whether
the configured workspace matches, and `--uninstall` to remove only Alcove's MCP
entry while preserving other servers.

## Design

See [docs/design/2026-07-07-alcove-design.md](docs/design/2026-07-07-alcove-design.md) for the Phase 1 design.
