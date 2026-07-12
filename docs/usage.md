# Alcove Usage Guide

This guide covers the common user-facing workflows. For architecture details,
see [architecture.md](architecture.md).

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

## Entry Profiles

Alcove separates global personal state from managed knowledge bases.

```sh
alcove home init
alcove kb add research_notes /path/to/research_notes
alcove hub init ~/AlcoveHub --default-kb research_notes
alcove global install --default-kb research_notes
alcove kb install research_notes
```

Development install mode keeps Alcove-owned skills and commands symlinked to
the repository templates:

```sh
alcove hub install ~/AlcoveHub --default-kb research_notes --link
alcove kb install research_notes --link
```

This is useful while tuning prompts locally. `AGENTS.md` and `CLAUDE.md` remain
normal files with an Alcove-managed section so user/project context is not
replaced by a symlink.

Agent targets:

| Target | Files |
| --- | --- |
| `--target claude` | `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/commands/*.md` |
| `--target codex` | `AGENTS.md`, `.agents/skills/*/SKILL.md` |
| default / `--target all` | both Claude Code and Codex files |

Install modes:

| Mode | Command | Use |
| --- | --- | --- |
| copy | `alcove hub install ...` / `alcove kb install ...` | normal users, release installs, portable workspaces |
| link | `alcove hub install ... --link` / `alcove kb install ... --link` | local Alcove development, prompt tuning, immediate source-template feedback |

Current distribution paths:

- Source install: `uv tool install git+https://github.com/OctopusGarage/alcove.git`
- Local editable install: `uv tool install --force -e .`
- Workspace development: `uv sync` + `uv run alcove ...`
- Wheel packaging: `uv build --wheel`

Check installed entry profiles:

```sh
alcove hub init ~/AlcoveHub --default-kb research_notes --status --json
alcove global install --status --json
alcove kb install research_notes --status --json
```

- `alcove hub init`: project-local hub workspace for daily Alcove conversations.
- `alcove global install`: lightweight MCP access from unrelated projects.
  It writes a `lite` MCP toolset by default; add `--default-kb <kb>` when
  global chats should be able to save pasted notes into a managed KB inbox.
- `alcove kb install`: managed-KB workflow files, Claude slash commands, and
  Claude/Codex skills for inbox review, notes search, social post processing,
  and Clipsmith capture handoff.

## Agent Retrieval and Writes

Alcove entry profiles use a read-broadly/write-narrowly model.
See [read-write-model.md](read-write-model.md) for the full operating model and
[okf-profile.md](okf-profile.md) for the OKF-compatible file/index profile.

For read-only questions, start with `alcove search` or MCP `alcove_search` to
discover candidates. Treat those results as leads, not final truth. For broad,
ambiguous, cross-topic, or low-confidence questions, continue with AI-led
investigation over the local OKF structure: read domain/topic/tag/index pages,
inspect candidate notes, follow source or connector references, and use shell
search or file reads when useful.

For writes, use Alcove CLI/MCP commands. Do not directly edit Alcove-owned data
unless the CLI lacks the needed operation. After any direct edit, run the nearest
validation or rebuild command.

Typical pattern:

```text
Question -> search candidates -> inspect OKF/index/source files -> synthesize
Save/update/delete -> CLI/MCP mutation -> validate or rebuild
```

Build the derived global OKF catalog when an agent or external reader needs a
single Markdown entry point across managed KBs, global memory, mounts, and
connectors:

```sh
alcove okf --home ~/.alcove catalog build --json
```

Check all module data, OKF files, and derived indexes together:

```sh
alcove health --home ~/.alcove --json
alcove health --home ~/.alcove --kb research_notes --strict --json
alcove health --home ~/.alcove --kb research_notes --fix --json
```

`--fix` fills missing schema metadata for recognized OKF notes and rebuilds safe
derived indexes plus the global OKF catalog. It does not refresh external
systems or rewrite managed KB note bodies.

## Managed KB

```sh
alcove inbox --kb research_notes peek
alcove inbox --kb research_notes read web/example
alcove inbox --kb research_notes manual-add "Manual Thought" \
  --content "Copied note text" \
  --source "chat://manual"
alcove knowledge --kb research_notes note-source \
  --platform xhs \
  --title "Example" \
  --topic agent-engineering/agent-harness \
  --summary "Summary"
alcove knowledge --kb research_notes revise \
  concepts/agent-engineering/agent-harness/example.md \
  --append "AI discussion follow-up" \
  --tag mcp \
  --json
alcove search "Example" --kb research_notes
```

Use `manual-add` when copied text or an AI discussion should first land in the
inbox. Use `knowledge revise` when a discussion should update an existing OKF
note.

## Global Memory

Pins, prompts, projects, ideas, tasks, routines, mounts, and connectors are
global by default and live under `~/.alcove`.

```sh
alcove pin add "Japanese Edge Launcher" \
  --description "Launch Edge with TZ=Asia/Tokyo" \
  --tag app-launcher
alcove prompt save "Code Review Lens" \
  --content "Review for correctness and missing tests." \
  --tag review \
  --use-case "PR review"
alcove project add alcove /path/to/alcove --note "Personal information core"
alcove task add "Wire MCP search" --priority high --tag mcp
alcove idea add "Review mount design" --notes "Local folders first" --tag mounts
alcove task routine-add "Weekly inbox review" --every-days 7 --next-due 2026-07-08
alcove task materialize-due --today 2026-07-08 --json
```

## External Indexes

Mounts index local folders without copying them:

```sh
alcove mount add /path/to/github-repos --name github --type local-folder --tag repos
alcove mount scan github --json
```

Connectors index external systems or exports:

```sh
alcove connector apple-notes import-local --tag apple-notes --json
alcove connector github-stars import-url "https://github.com/octocat?tab=stars" \
  --tag github-stars \
  --json
alcove connector chrome-bookmarks import-local --tag bookmarks --json
alcove connector status --json
alcove connector refresh --stale --json
alcove connector fetch "connectors/apple-notes#notes/example-note/note.json" --json
```

Promote an indexed external item into a managed KB:

```sh
alcove link --kb research_notes source \
  "connectors/github-stars#octopusgarage/alcove" \
  ai-knowledge/knowledge-base \
  --summary "Useful reference" \
  --json
```

## Search-Driven Cleanup

Managed KB cleanup is result-driven, not a blanket retention sweep. Search first,
inspect the candidate metadata, then delete only the confirmed outdated record:

```sh
alcove search --kb social_media_posts "query" --type Source --json
alcove knowledge --kb social_media_posts delete "sources/web/topic/item.md" --json
alcove knowledge --kb social_media_posts delete "sources/web/topic/item.md" \
  --reason "confirmed obsolete from search result" \
  --confirm \
  --json
alcove search --kb social_media_posts "query" --status deleted --json
```

Search rows include `published_at`, `collected_at`, `updated_at`, `deleted_at`,
`status`, and `path`. `knowledge delete` is a soft delete: it marks the Source as
`deleted`, hides it from default search, updates related `source_refs`, and
rebuilds managed-KB indexes. Use `--status deleted` for audit.

## Dashboard

```sh
alcove dashboard --home ~/.alcove build
alcove serve --dashboard --home ~/.alcove --port 8765
```

The dashboard includes a Usage page for local aggregate statistics:

- search count, zero-result count, and zero-result rate,
- CLI / MCP / Dashboard surface split,
- dashboard route views when events are recorded through the Alcove dashboard
  server,
- data-health counts for managed KBs, mounts, connectors, indexed items, and
  stats rollups,
- recent privacy-safe usage events.

Usage events are stored in `~/.alcove/logs/usage.jsonl`. Search query text is not
stored by default; Alcove records query length and a local salted query hash for
deduplication-oriented analysis.

Usage summaries and retention:

```sh
alcove usage summary --home ~/.alcove --json
alcove usage prune --home ~/.alcove --days 90 --json
```

`alcove usage summary` refreshes `~/.alcove/stats/summary.json` and
`~/.alcove/stats/daily/*.json`. `usage prune` removes old `usage.jsonl` and
`activity.jsonl` entries, then regenerates the rollups.

Optional pin import:

```sh
alcove dashboard --home ~/.alcove import-pins \
  --regular-file ~/Downloads/regular.txt \
  --todo-file ~/Downloads/todo.txt
```

## Export

```sh
alcove export global ~/alcove-backup --json
alcove export kb research_notes ~/alcove-backup/research_notes --json
alcove export all ~/alcove-backup-all --json
```

## MCP

```sh
alcove serve --mcp
alcove serve --mcp --toolset lite
alcove serve --mcp --toolset kb --kb research_notes
alcove serve --mcp --kb research_notes
alcove global install --status --json
alcove hub init ~/AlcoveHub --default-kb research_notes --status --json
alcove kb install research_notes --status --json
```

Global-aware MCP tools accept `home`. Managed-KB MCP tools require `workspace`
or a configured default KB.
