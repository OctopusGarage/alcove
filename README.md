# Alcove

Alcove is a local-first personal information alcove for knowledge, pins, tasks, mounted sources, and agent-readable memory.

## Phase 1

- workspace initialization
- Markdown-first OKF knowledge writes
- inbox peek and note processing
- simple knowledge search

Implemented modules now include Pins, Tasks/Routines, Mounts, Apple Notes export
indexing, GitHub Stars indexing, source linking, MCP tools, and installer
status/uninstall flows.

Alcove now separates a global user home from managed knowledge bases:

- Global user state lives in `~/.alcove` by default, or `ALCOVE_HOME`.
- Managed knowledge bases live wherever the user chooses and are registered
  under `~/.alcove/knowledge-bases/`.
- Pins, tasks, mounts, and connector indexes are global by default.

## Install

```sh
uv tool install git+https://github.com/OctopusGarage/alcove.git
alcove --version
```

For local development:

```sh
uv sync
uv run alcove --version
uv tool install --force -e .
```

Install entry profiles:

```sh
alcove home init
alcove kb add social_media_posts /path/to/social_media_posts
alcove hub init ~/AlcoveHub --default-kb social_media_posts
alcove global install
alcove kb install social_media_posts
```

## Commands

```sh
uv run alcove init .
uv run alcove home init
uv run alcove kb add social_media_posts /path/to/social_media_posts
uv run alcove kb list --json
uv run alcove hub init ~/AlcoveHub --default-kb social_media_posts
uv run alcove global install
uv run alcove kb install social_media_posts
uv run alcove status .
uv run alcove doctor --kb social_media_posts --json
uv run alcove inbox --kb social_media_posts peek
uv run alcove inbox --kb social_media_posts read web/example
uv run alcove inbox --kb social_media_posts manual-add "Manual Thought" --content "Copied note text" --source "chat://manual"
uv run alcove knowledge --kb social_media_posts note-source --platform xhs --title "Example" --topic agent-engineering/agent-harness --summary "Summary"
uv run alcove search "Example" --kb social_media_posts
uv run alcove search --kb social_media_posts --tags
uv run alcove search --kb social_media_posts --recent 10
uv run alcove search --kb social_media_posts --tag agent-harness --platform web --json
uv run alcove search --kb social_media_posts --unindexed --json
uv run alcove pin add "Japanese Edge Launcher" --description "Launch Edge with TZ=Asia/Tokyo" --tag app-launcher
uv run alcove pin list --tag app-launcher
uv run alcove pin archive japanese-edge-launcher --confirm
uv run alcove idea add "Review mount design" --notes "Local folders first" --tag mounts
uv run alcove idea promote review-mount-design --priority high --due 2026-07-10
uv run alcove task add "Wire MCP search" --priority high --tag mcp
uv run alcove task complete wire-mcp-search
uv run alcove task routine-add "Weekly inbox review" --every-days 7 --next-due 2026-07-08
uv run alcove task materialize-due --today 2026-07-08 --json
uv run alcove mount add ~/programming/github --name github --type local-folder --tag repos
uv run alcove mount scan github --json
uv run alcove connector apple-notes index ~/exports/apple-notes --tag apple-notes --json
uv run alcove connector github-stars index ~/exports/github-stars.json --tag stars --json
uv run alcove link --kb social_media_posts source "connectors/github-stars#octopusgarage/alcove" ai-knowledge/knowledge-base --summary "Useful reference" --json
uv run alcove export global ~/alcove-backup --json
uv run alcove serve --mcp
uv run alcove global install --status --json
```

Recommended entry profiles:

- `alcove hub init`: project-local hub workspace for daily Alcove conversations.
- `alcove global install`: lightweight MCP access from unrelated projects.
- `alcove kb install`: project-local managed KB workflow files and skills.

Alcove inbox folders can contain Clipsmith capture bundles. When `capture.json`
is present, Alcove uses it as fallback metadata for title, source URL, and date
while keeping Markdown files as the human-readable review surface.

Pins are small, high-value personal notes stored as Markdown under
`~/.alcove/pins/` for global usage. They are included in `alcove search`
alongside knowledge docs when `--home` is provided.

Ideas, tasks, and routines are stored in `~/.alcove/tasks/tasks.json` for
global usage. Active ideas and pending tasks are included in `alcove search`
when `--home` is provided. Routines materialize only when
`task materialize-due` or the matching MCP tool is called.

Mounts let Alcove index external folders or local Git repositories without
copying their content. Global mount registries and indexes live under
`~/.alcove/mounts/`. Scanned mounted items are included in `alcove search`.

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
Global-aware MCP tools accept `home` so pins, tasks, mount lists, and search do
not need a managed KB workspace.

`alcove install` writes MCP client config for Codex and Claude Code. Use
`--print` to preview install or uninstall changes, `--status` to check whether
the configured workspace matches, and `--uninstall` to remove only Alcove's MCP
entry while preserving other servers.
Prefer `alcove global install`, `alcove hub init`, and `alcove kb install` for
new setups. The older `alcove install --workspace ...` path remains for
compatibility.

## Design

See [docs/architecture.md](docs/architecture.md) for the current architecture and feature overview.

See [docs/design/2026-07-07-alcove-design.md](docs/design/2026-07-07-alcove-design.md) for the Phase 1 design.
