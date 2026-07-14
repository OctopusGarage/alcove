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
alcove workspace init family --default-kb research_notes
alcove global install --default-kb research_notes
alcove kb install research_notes
```

Development install mode keeps Alcove-owned skills and commands symlinked to
the repository templates:

```sh
alcove hub install ~/AlcoveHub --default-kb research_notes --link
alcove workspace install family --link
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
- `alcove workspace init`: lightweight business-scoped agent workspace under
  the Hub concept. Omit `--path` to use
  `~/.alcove/workspaces/data/<id>/`; pass `--path` for a custom directory.
- `alcove global install`: lightweight MCP access from unrelated projects.
  It writes a `lite` MCP toolset by default; add `--default-kb <kb>` when
  global chats should be able to save pasted notes into a managed KB inbox.
- `alcove kb install`: managed-KB workflow files, Claude slash commands, and
  Claude/Codex skills for inbox review, notes search, social post processing,
  and Clipsmith capture handoff.

Business workspaces are useful when a long-running conversation should inherit
a family, work, travel, or similar scene instead of the full Hub control
surface:

```sh
alcove workspace init family \
  --default-kb research_notes \
  --tag family \
  --context "Family errands, household knowledge, and recurring reminders."

cd ~/.alcove/workspaces/data/family
codex
```

For one-shot work, run the agent inside a registered workspace:

```sh
alcove workspace run family --agent codex "整理家庭相关任务"
alcove workspace run family --agent claude "总结家庭知识记录"
```

For scene-local documents and notes, initialize the workspace OKF store instead
of manually wiring a managed KB:

```sh
alcove workspace okf init family --json
alcove workspace okf add-note family home/insurance "家庭保险资料整理" \
  --summary "家庭保险资料需要按保单、受益人、续费日期归档。" \
  --json
alcove workspace okf import-file family ./documents/insurance.md --topic home/insurance --json
alcove workspace okf search family "保单" --json
```

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
alcove okf --home ~/.alcove catalog build --include-all-status --json
```

Check all module data, OKF files, and derived indexes together:

```sh
alcove health --home ~/.alcove --json
alcove health --home ~/.alcove --kb research_notes --strict --json
alcove health --home ~/.alcove --kb research_notes --fix --json
alcove health --home ~/.alcove --fix --deep --json
alcove health --home ~/.alcove --fix --deep --refresh-stale-connectors --json
```

`--fix` fills missing schema metadata for recognized OKF notes and rebuilds safe
derived indexes plus the global OKF catalog. It does not refresh external
systems, rescan mounts, or rewrite managed KB note bodies.

Use `--deep` for a local full-maintenance pass. It also rescans mounts, rebuilds
usage rollups, rebuilds the dashboard snapshot, and rebuilds the global OKF
catalog again after those derived views are current. Connector refresh remains
explicit: add `--refresh-stale-connectors` for registered stale sources, or
`--refresh-all-connectors` only when a full external refresh is intentional.

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
alcove prompt propose "Code Review Lens" \
  --content "Review for correctness, missing tests, and regression risk." \
  --tag review \
  --use-case "PR review"
alcove prompt save --proposal-id <proposal-id>
alcove prompt recommend "review a dashboard regression before shipping"
alcove prompt compose "review a dashboard regression before shipping"
alcove prompt audit --json
alcove project add alcove /path/to/alcove --note "Personal information core"
alcove task add "Wire MCP search" --priority high --tag mcp
alcove task edit wire-mcp-search --due 2026-07-20 --priority high
alcove idea add "Review mount design" --notes "Local folders first" --tag mounts
alcove idea promote review-mount-design --due 2026-07-18
alcove task routine-add "Weekly inbox review" \
  --frequency weekly \
  --weekday sun \
  --next-due 2026-07-12
alcove task routine-pause weekly-inbox-review
alcove task routine-resume weekly-inbox-review
alcove task materialize-due --today 2026-07-08 --json
alcove task digest --period weekly --notify --json
```

Planner digests are opt-in. To let the local service send a weekly digest,
create `~/.alcove/tasks/notifications.yml`:

```yaml
digests:
  weekly:
    enabled: true
    day: sunday
    time: "21:00"
    notify: true
    sinks:
      - type: telegram
      - type: feishu
        webhook_env: ALCOVE_FEISHU_WEBHOOK_URL
        secret_env: ALCOVE_FEISHU_SECRET
```

`alcove task digest --period weekly --notify --json` also uses the configured
weekly sinks. Without `sinks`, planner notifications default to Telegram. The
local service honors `time` and records sent periods to avoid duplicate weekly
messages.

## Publishers

Publishers render Alcove-owned module data into external readable mirrors. The
first publisher target is Apple Notes, useful when the dashboard is unavailable
outside the local network.

Initialize the default Apple Notes publisher:

```sh
alcove publish init apple-notes --home ~/.alcove --root-folder "iCloud/Alcove" --json
```

This creates five generated notes:

```text
iCloud/Alcove/
├── pins/
│   ├── Regular Pins
│   └── TODO Pins
├── planner/
│   └── Planner Digest
├── prompts/
│   └── Prompt Library
└── projects/
    └── Project Registry
```

Run it manually:

```sh
alcove publish run apple-notes --home ~/.alcove --json
alcove publish run apple-notes --home ~/.alcove --target pins_regular --force --json
alcove publish list --home ~/.alcove --json
```

The generated Apple Notes are readable mirrors. Alcove-owned data remains the
source of truth under `~/.alcove`, such as `~/.alcove/pins`, `~/.alcove/tasks`,
`~/.alcove/prompts`, and `~/.alcove/projects`. Manual edits inside generated
Apple Notes can be overwritten by the next publish run.

Publisher output is presentation-optimized for phone reading. It uses one
module icon, quiet section dividers, compact item spacing, and short metadata
labels. Long pin content is preserved in full; the publisher adds an outline,
extra spacing around sections, and cleaner table rows so Apple Notes remains
readable without hiding details.

Pin source data should still be written as structured records: concise
`summary`, focused `content`, explicit tags, and URL-like references in
`resources` when they are important. Pin writes normalize excessive blank lines
and common divider variants before indexing and publishing.

Apple Notes publishing is intentionally selective. It mirrors small, human
readable module views for offline access. Large knowledge bases, mounts,
connectors, radar archives, automations, logs, and usage records should stay in
Alcove and be accessed through dashboard, search, CLI, or MCP.

The local scheduler also runs due publishers during `alcove service tick`.
Use `alcove service tick --skip-publishers --json` to skip this part of a manual
maintenance run.

## External Indexes

Mounts index local folders without copying them:

```sh
alcove mount add /path/to/github-repos --name github --type local-folder --profile docs --tag repos
alcove mount scan github --dry-run --json
alcove mount scan github --json
```

Mount profiles keep indexes focused:

```sh
alcove mount add ~/notes --name notes --profile notes
alcove mount add ~/blog --name blog --profile site --exclude ".agents/**"
alcove mount update github --profile docs --exclude "archived-*/**" --exclude "**/_build/**"
```

Use `--dry-run` before a large rebuild to inspect `scanned`, `skipped`, and
`skip_reasons` without writing `~/.alcove/mounts/indexes/` or derived OKF files.

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

For a LAN-facing dashboard, keep Alcove bound to localhost and expose it through
a local reverse proxy. This keeps the Alcove process private while letting nginx
own the LAN port and hostname:

```nginx
server {
    listen 80;
    server_name my-mac.local alcove.local alcove.lan 192.168.1.10;

    location = / {
        return 302 /alcove/dashboard/;
    }

    location = /alcove/dashboard {
        return 301 /alcove/dashboard/;
    }

    location /alcove/dashboard/ {
        proxy_pass http://127.0.0.1:8765/;
        proxy_set_header Host $http_host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-Host $http_host;
        proxy_buffering off;
    }
}
```

Reload and verify:

```sh
nginx -t && nginx -s reload
curl -I http://my-mac.local/alcove/dashboard/
curl -I http://192.168.1.10/alcove/dashboard/
```

`my-mac.local` is the macOS Bonjour hostname and usually works from phones on
the same Wi-Fi. Custom names such as `alcove.local` or `alcove.lan` also need a
router/local-DNS record pointing at the Mac. If the phone cannot connect, check
that nginx is listening on `*:80` and that the macOS firewall allows incoming
connections.

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

## Local Service and Watchers

Install macOS launchd services:

```sh
alcove service install --dashboard --scheduler --load
alcove service status --json
```

Without `--dashboard` or `--scheduler`, `service install` targets both services.
Use explicit flags to operate on only one service. The dashboard service runs
`alcove serve --dashboard`; the scheduler runs `alcove service tick` at the
configured interval.

Manual maintenance tick:

```sh
alcove service tick --home ~/.alcove --json
alcove service tick --home ~/.alcove --skip-radars --json
alcove service tick --home ~/.alcove --skip-automations --json
alcove service tick --home ~/.alcove --mount-refresh-days 2 --json
```

Each tick materializes due routines, sends configured planner digests, refreshes
stale connector sources, checks watchers and monitored blogs, runs enabled
scheduled radars, runs due user automation jobs, refreshes mounted knowledge
indexes when their two-day maintenance window is due, rebuilds the global OKF
catalog, runs health repair, refreshes usage rollups, prunes old usage events,
and rebuilds the dashboard snapshot. Mount refresh uses the existing incremental
scan and can be disabled for a manual tick with `--skip-mounts`. This is
deterministic maintenance; blog summary, radar AI analysis, automation
notifications, and agent automation jobs are opt-in.

Watch a site or feed:

```sh
alcove watch add "Example Blog" https://example.com/feed.xml \
  --kind rss \
  --kb research_notes \
  --tag blog \
  --json
alcove watch check --stale --json
```

Watcher sources are stored in `~/.alcove/watchers/sources/*.yml`, and change
events are appended to `~/.alcove/watchers/events.jsonl`. If a watcher is bound
to `--kb <name>`, detected changes are added to that managed KB inbox as manual
items for later review.

Monitor blogs for new articles:

```sh
alcove blog add "Anthropic Engineering" https://www.anthropic.com/engineering \
  --id anthropic \
  --discover playwright \
  --link-pattern /engineering/ \
  --kb social_media_posts \
  --inbox-path inbox/anthropic \
  --capture \
  --json

alcove blog add "OpenAI Engineering" https://openai.com/news/engineering/ \
  --id openai \
  --discover playwright \
  --link-pattern /index/ \
  --kb social_media_posts \
  --inbox-path inbox/openai \
  --capture \
  --json

alcove blog seed openai --json
alcove blog check --stale --json
```

Blog sources are stored in `~/.alcove/blog-monitor/sources/*.yml`. Seen URLs
live in `~/.alcove/blog-monitor/seen/`. When capture is enabled, new article
bundles are written into the configured managed KB inbox path, such as
`social_media_posts/inbox/openai`. When notification is enabled and Telegram
credentials are present, Alcove sends one message per new article with the
article title, URL, and the captured inbox `summary.md` content when available.
Use `--discover playwright` for monitored blog index pages. This keeps discovery
consistent with Clipsmith's browser-based capture model, runs unattended through
the scheduled service, and does not invoke Codex, Claude, or `claude -p`. If
discovery or capture fails, the source is marked `needs_attention`, the failed
run is recorded, and Telegram receives an actionable alert when notifications
are enabled.
For a user-triggered check from the Hub workspace, use `alcove blog check --json`
or `alcove blog check <source-id> --json` to force an immediate run. `alcove
service tick` is reserved for scheduled stale maintenance and may skip sources
whose TTL has not expired.
Telegram credentials can be provided by process environment variables or
`~/.alcove/.env`:

```sh
ALCOVE_TELEGRAM_BOT_TOKEN=...
ALCOVE_TELEGRAM_CHAT_ID=...
```

Credential priority is `ALCOVE_*` process environment, then `~/.alcove/.env`,
then generic `TELEGRAM_*` process environment.

## Automations

Automations are repeatable user jobs stored under `~/.alcove/automations/`.
They are useful for local maintenance such as syncing exported notes or backing
up repositories.

```sh
alcove automation list --home ~/.alcove --json
alcove automation add-shell "backup cache" \
  --cmd "rsync -a ~/source/ ~/backup/" \
  --ttl-hours 24 \
  --json
alcove automation add-git-sync notes ~/notes \
  --commit-message "chore: sync notes" \
  --notify \
  --json
alcove automation run notes --home ~/.alcove --json
alcove automation run-due --home ~/.alcove --json
```

`shell`, `git-sync`, and `alcove` jobs can run from the local service when due.
`agent` jobs are guarded: scheduled service execution requires
`allow_service: true`, and manual execution requires `--allow-agent` unless the
job is already service-approved. This keeps background launchd maintenance from
silently starting Codex or Claude.

## Configurable Radars

Radars are generic user-defined briefings. Built-in presets are starter
definitions; user-specific categories live under `~/.alcove/radars/definitions/`.

```sh
alcove radar preset list --json
alcove radar init tech-news --from-preset tech-news --json
alcove radar init world-news --from-preset world-news --json
alcove radar list --json
alcove radar run tech-news --json
alcove radar run tech-news --force --ai --notify --json
alcove radar run tech-news --skip-fetch --force --ai --notify --json
alcove radar status tech-news --json
```

Scheduled radars can use a local daily window:

```yaml
schedule:
  enabled: true
  daily_time: "10:00"
  timezone: Asia/Singapore
  ttl_hours: 24
```

See [radars.md](radars.md) for the storage contract and adapter model. Optional
`ai_summary` post-processing writes `<date>.ai.md` and can send notifications
through configured sinks. Telegram sends the Markdown and HTML report files when
available. Feishu custom bot webhooks send a text message with the summary and
top links; local report paths are not included in notification text. For
Feishu/Lark attachments, use the `tcb` sink, which delegates report upload to a
running [`tmux-claude-bot`](https://github.com/OctopusGarage/tmux-claude-bot)
service through `tcb notify --attach`. The AI step
analyzes the report without changing fetched items or deterministic scores.

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
or a configured default KB. Complex workflows that intentionally stay on the
CLI/Hub surface, such as blog monitoring, radar reports, dashboard serving, and
publisher syncs, can be discovered through MCP `alcove_command_hints` instead
of widening the global MCP mutation surface.
