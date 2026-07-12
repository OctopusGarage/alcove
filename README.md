# Alcove

[![CI](https://github.com/OctopusGarage/alcove/actions/workflows/ci.yml/badge.svg)](https://github.com/OctopusGarage/alcove/actions/workflows/ci.yml)
[![Gitleaks](https://github.com/OctopusGarage/alcove/actions/workflows/gitleaks.yml/badge.svg)](https://github.com/OctopusGarage/alcove/actions/workflows/gitleaks.yml)
[![Project Health](https://github.com/OctopusGarage/alcove/actions/workflows/project-health.yml/badge.svg)](https://github.com/OctopusGarage/alcove/actions/workflows/project-health.yml)
[![Pages](https://github.com/OctopusGarage/alcove/actions/workflows/pages.yml/badge.svg)](https://octopusgarage.github.io/alcove/)
[![version](https://img.shields.io/badge/version-0.1.0-blue)](pyproject.toml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.12-brightgreen)](https://www.python.org/)
[![uv](https://img.shields.io/badge/managed_with-uv-654FF0)](https://docs.astral.sh/uv/)
[![Ruff](https://img.shields.io/badge/lint-Ruff-261230)](https://docs.astral.sh/ruff/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Alcove is a local-first personal information system for managed knowledge bases,
pins, tasks, projects, prompts, mounted sources, external connectors, and
agent-readable memory.

Website: https://octopusgarage.github.io/alcove/

It keeps global user state separate from managed knowledge bases:

- Global state lives in `~/.alcove` by default, or `ALCOVE_HOME`.
- Managed knowledge bases live wherever the user chooses and are registered
  under `~/.alcove/knowledge-bases/`.
- Pins, tasks, prompts, projects, mounts, connector indexes, and dashboard state
  are global by default.
- User automation jobs live under `~/.alcove/automations/`.
- Usage statistics are local and privacy-safe: search text is not stored by
  default, only query length, result counts, filters, surface, and a local salted
  hash.

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

## Quick Start

```sh
alcove home init
alcove kb add research_notes /path/to/research_notes
alcove hub init ~/AlcoveHub --default-kb research_notes
alcove global install --default-kb research_notes
alcove kb install research_notes
```

For local Alcove development, install Hub/KB workflow skills as symlinks to the
source templates:

```sh
alcove hub install ~/AlcoveHub --default-kb research_notes --link
alcove kb install research_notes --link
```

Both install modes support Claude Code and Codex. By default `--target all`
writes both sets of files:

| Agent | Installed files |
| --- | --- |
| Claude Code | `CLAUDE.md`, `.claude/skills/*/SKILL.md`, `.claude/commands/*.md` |
| Codex | `AGENTS.md`, `.agents/skills/*/SKILL.md` |

`--link` only symlinks Alcove-owned skills and Claude commands. `AGENTS.md` and
`CLAUDE.md` stay normal files with an Alcove-managed section.

Check installed entry profiles:

```sh
alcove hub init ~/AlcoveHub --default-kb research_notes --status --json
alcove global install --status --json
alcove kb install research_notes --status --json
```

Entry profiles:

- `alcove hub init`: local hub workspace for broad personal knowledge work.
- `alcove global install`: lightweight MCP access from unrelated projects
  (`--toolset lite` by default).
- `alcove kb install`: managed-KB workflow files, commands, and skills.
- `alcove service install`: optional macOS launchd services for the dashboard
  and deterministic maintenance ticks.

## Core Commands

Managed KB:

```sh
alcove inbox --kb research_notes peek
alcove inbox --kb research_notes manual-add "Manual Thought" \
  --content "Copied note text" \
  --source "chat://manual"
alcove knowledge --kb research_notes note-source \
  --platform web \
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

Global memory:

```sh
alcove pin add "Useful Pattern" --description "Short reusable note" --tag reference
alcove prompt save "Code Review Lens" --content "Review for correctness." --tag review
alcove task add "Wire MCP search" --priority high --tag mcp
alcove project add alcove /path/to/alcove --note "Personal information core"
```

External indexes:

```sh
alcove mount add /path/to/repos --name repos --type local-folder --tag repos
alcove mount scan repos --json
alcove connector github-stars import-url "https://github.com/octocat?tab=stars" --json
alcove connector chrome-bookmarks import-local --tag bookmarks --json
alcove connector apple-notes import-local --tag apple-notes --json
alcove connector status --json
```

Configurable radars:

```sh
alcove radar preset list --json
alcove radar init tech-news --from-preset tech-news --json
alcove radar init world-news --from-preset world-news --json
alcove radar init stocks --from-preset stocks --json
alcove radar init sports-news --from-preset sports-news --json
alcove radar list --json
alcove radar run tech-news --json
alcove radar run tech-news --force --ai --notify --json
alcove radar run tech-news --skip-fetch --force --ai --notify --json
alcove radar import-social-radar ~/.social_radar --json
```

Automations:

```sh
alcove automation list --json
alcove automation add-git-sync notes ~/notes --commit-message "chore: sync notes" --json
alcove automation run-due --json
alcove automation import-social-radar ~/.social_radar --home ~/.alcove --json
```

MCP and dashboard:

```sh
alcove serve --mcp
alcove serve --mcp --kb research_notes
alcove dashboard --home ~/.alcove build
alcove serve --dashboard --home ~/.alcove --port 8765
```

Local service and watchers:

```sh
alcove service install --dashboard --scheduler --load
alcove service status
alcove service tick --json
alcove watch add "Example Blog" https://example.com/feed.xml --kind rss --kb research_notes
alcove watch check --stale --json
alcove blog add "Anthropic Engineering" https://www.anthropic.com/engineering \
  --id anthropic --discover playwright --link-pattern /engineering/ \
  --kb social_media_posts --inbox-path inbox/anthropic --capture --json
alcove blog add "OpenAI Engineering" https://openai.com/news/engineering/ \
  --id openai --discover playwright --link-pattern /index/ \
  --kb social_media_posts --inbox-path inbox/openai --capture --json
alcove blog seed openai --json
alcove blog check --stale --json
```

The service layer keeps deterministic work outside AI-agent sessions: dashboard
serving, stale connector refreshes, due routine materialization, OKF catalog
rebuilds, usage rollups, health checks, scheduled radar runs, user automation
jobs, watched-source change detection, and blog article discovery. Blog sources
can optionally capture new articles into a managed KB inbox through the configured
capture adapter. AI summarization and
notifications are opt-in. When `--notify` is enabled with Telegram environment
variables configured, Alcove sends one message per new article with its title,
link, and captured `summary.md` content when available.
Discovery or capture failures are recorded under `~/.alcove/blog-monitor/`,
mark the source as `needs_attention`, and send a Telegram failure alert when
notifications are enabled.

Radar AI analysis is opt-in. A radar definition can enable
`ai_summary.enabled: true` and `notify.enabled: true` to run `codex exec` or
`claude -p` after the deterministic report is written, then send notifications
through configured sinks. `telegram` sends the core summary, top links, and the
Markdown and HTML report files when available. `feishu` sends a custom-bot text
message with the same summary and top links through a webhook; local report
paths are not included in notification text. `tcb` delegates notification text
and report attachments to a running `tmux-claude-bot` service through
`tcb notify --attach`, which is the preferred Feishu/Lark attachment path. If AI
fails, the notification falls back to the deterministic report. Manual Hub
requests can force a fresh run with `--force --ai --notify`, or analyze already
fetched data with `--skip-fetch --force --ai --notify`.

Notification credentials can be provided through process environment variables
or a local secret file at `~/.alcove/.env`:

```sh
ALCOVE_TELEGRAM_BOT_TOKEN=...
ALCOVE_TELEGRAM_CHAT_ID=...
ALCOVE_FEISHU_WEBHOOK_URL=...
ALCOVE_FEISHU_SECRET=...
```

Alcove-specific values take precedence over generic `TELEGRAM_*` environment
variables, so a stale shell variable cannot override `~/.alcove/.env`.

Health:

```sh
alcove health --home ~/.alcove --json
alcove health --home ~/.alcove --kb research_notes --fix --json
```

`--fix` repairs safe metadata/index drift: missing managed-KB OKF schema,
pin/prompt indexes, and the global OKF catalog.

Export:

```sh
alcove export global ~/alcove-backup --json
alcove export kb research_notes ~/alcove-backup/research_notes --json
alcove export all ~/alcove-backup-all --json
```

## Default Capture Adapter

Alcove inboxes accept capture bundles from any collector that writes the inbox
contract. The default capture adapter is Clipsmith:

- GitHub: https://github.com/OctopusGarage/clipsmith
- Project page: https://octopusgarage.github.io/clipsmith/

Default handoff:

```sh
clipsmith sink inbox "<bundle_dir>" "<managed-kb-root>" --json
```

## Backup Recommendation

Alcove data is local-first. Back up managed KB roots and `~/.alcove` outside the
runtime. Recommended tools:

- Scheduled Git sync: https://github.com/OctopusGarage/git-auto-sync
- Git encryption before remote sync: https://github.com/AGWA/git-crypt

Alcove does not manage backup scheduling or encryption keys.

## Documentation

- [Documentation Index](docs/README.md): map of user guides, architecture, ADRs,
  and historical notes.
- [Usage Guide](docs/usage.md): common CLI/MCP workflows.
- [Entry Modes](docs/entry-modes.md): hub, global MCP, managed KB, and MCP
  toolsets.
- [Modules](docs/modules.md): feature modules and storage contracts.
- [Configurable Radars](docs/radars.md): generic information radar definitions,
  source adapters, scheduling, and Social Radar migration.
- [Alcove OKF Profile](docs/okf-profile.md): official OKF compatibility plus
  Alcove's stricter write/index rules.
- [Read/Write Operating Model](docs/read-write-model.md): broad AI-led reads and
  narrow CLI/MCP-governed writes.
- [Data and Backup](docs/data-and-backup.md): data locations, export, sync,
  encryption.
- [Architecture](docs/architecture.md): relationship model and implementation overview.
- [Local Smoke / Agent Eval](docs/evals/local-smoke.md): verification and repair
  workflows.
- [Agent Quality Gates](docs/evals/agent-quality-gates.md): Codex/Claude hook
  automation and AI eval trigger rules.

## Verification

```sh
scripts/smoke.sh
scripts/smoke-mcp-matrix.sh
scripts/agent-quality-gate.sh --mode coach
scripts/check.sh
```

See [docs/evals/local-smoke.md](docs/evals/local-smoke.md) for the full
verification matrix.
