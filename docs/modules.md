# Alcove Modules

This document summarizes Alcove's feature modules and their storage contracts.

## Module Map

```text
Alcove Modules
├── Knowledge Sources
│   ├── Managed KBs              1-to-many, user-chosen directories
│   ├── Mounts                   1-to-many, read-only external folders
│   └── Connectors               1-to-many, external protocol/export indexes
├── Capture and Knowledge Writes
│   ├── Clipsmith adapter         default collector, replaceable
│   ├── manual inbox drafts       copied text or AI discussion summaries
│   └── governed knowledge writes Source / Concept / Question / Entity
├── Global Personal Memory
│   ├── Pins                     regular references and todo-style future work
│   ├── Tasks / Ideas / Routines planner state and notifications
│   ├── Prompts                  reusable instructions
│   └── Projects                 local project aliases
├── Intelligence Feeds
│   ├── Configurable Radars       tech/news/stocks/sports or user-defined
│   ├── Watchers                  URL/feed change detection
│   └── Blog Monitor              article discovery and optional capture
├── Observation and Publishing
│   ├── Dashboard                 local browser console
│   └── Apple Notes Publisher     readable mirrors for selected modules
├── Agent Workspaces
│   ├── Hub                       full control workspace
│   └── Business Workspaces       lightweight scene-specific agent entries
├── Background Runtime
│   └── Local Service             launchd dashboard + scheduler ticks
└── Operations
    ├── Health / Validate / Gardener
    ├── OKF catalog build
    ├── Export
    └── Smoke / AI eval / quality gates
```

Storage ownership summary:

```text
~/.alcove
├── global module data            pins, tasks, prompts, projects
├── agent workspace registry       hub and lightweight business workspaces
├── derived/search state           mounts, connectors, dashboard, stats
├── operational state              service logs, watcher/blog/radar runs
├── publisher state                definitions, renders, target note ids
└── managed KB registry            pointers to user-chosen KB roots

<managed-kb-root>
├── inbox                          captures and manual drafts
├── archive                        processed raw evidence
├── knowledge                      OKF source/concept/question/entity notes
└── todo                           deferred inbox items
```

## Managed Knowledge Bases

Managed KBs are user-chosen directories registered under
`~/.alcove/knowledge-bases/`. They own the full knowledge lifecycle:

- `inbox/` for pending captures and manual inputs,
- `archive/` for processed raw evidence,
- `knowledge/` for OKF Markdown notes,
- `todo/` for deferred inbox items,
- `.alcove/config.yml` for KB-local metadata.

Manual inputs and AI discussion summaries can enter the inbox:

```sh
alcove inbox --kb research_notes manual-add "Manual Thought" \
  --content "Copied note text" \
  --source "chat://manual"
```

Established notes can be revised in place while keeping revision metadata:

```sh
alcove knowledge --kb research_notes revise \
  concepts/agent-engineering/agent-harness/example.md \
  --summary "Updated summary" \
  --append "Follow-up from an AI discussion" \
  --reason "AI discussion" \
  --json
```

## Capture

Alcove inbox folders can contain capture bundles from Clipsmith or any collector
that writes the same inbox layout. Clipsmith is the default capture adapter, not
a hard dependency of Alcove.

- GitHub: https://github.com/OctopusGarage/clipsmith
- Project page: https://octopusgarage.github.io/clipsmith/

Default handoff:

```sh
clipsmith sink inbox "<bundle_dir>" "<managed-kb-root>" --json
```

Alcove reads `capture.json.content_files` first, so OCR text, summaries, and
post text remain reviewable without hard-coding a single filename. Legacy
folders without `capture.json` still use fallback names such as `summary.md`,
`post.md`, `article.md`, `ocr.md`, `ocr.txt`, and `ocr-merge.txt`.

## Pins

Pins are small, high-value personal notes stored as OKF-compatible Markdown
under `~/.alcove/pins/`. Current kinds:

- `regular`: repeated reference.
- `todo`: future practice or deeper investigation.

Markdown files are the source of truth; `index.json`, `index.md`, and
`board.html` are derived outputs. Pins participate in global search when
`--home` is provided.

Write pins as small, structured records when possible:

- Put the stable one-line meaning in `summary`.
- Put repeated lookup details, commands, links, or markdown notes in `content`.
- Use `resources` for important URLs that should stay visible.
- Avoid using one very large pin for unrelated topics; split unrelated durable
  references into separate pins. Bulk Markdown imports are preserved, but write
  flows normalize line endings, trim trailing whitespace, collapse excessive
  blank lines, and normalize common divider lines to keep later search, board,
  and Apple Notes mirrors readable. Apple Notes mirrors preserve large pins in
  full, adding an outline and section spacing so mobile reading does not turn
  into an undifferentiated raw Markdown dump.

```sh
alcove pin --home ~/.alcove add "Japanese Edge Launcher" \
  --kind regular \
  --summary "Launch Edge with TZ=Asia/Tokyo." \
  --content "Use osacompile to wrap the command." \
  --tag app-launcher
alcove pin --home ~/.alcove search "Edge" --kind regular
alcove pin --home ~/.alcove render-html
```

## Projects

Projects are global aliases for local project paths. They are stored under
`~/.alcove/projects/projects.json`, can scan configured roots, and participate
in global search as `Project` rows.

## Agent Workspaces

Agent workspaces are conversation directories. They install project-local
`AGENTS.md`, `CLAUDE.md`, and skills so Codex or Claude Code inherit the right
scene rules when launched from that directory. Business workspaces can also own
a workspace-local OKF store for scene documents and notes.

```text
~/.alcove/workspaces/
├── hub.yml                       fixed Hub control workspace registry
├── <id>.yml                      custom business workspace registry
└── data/<id>/                    default entry directory when --path omitted
    ├── .alcove-workspace.yml
    ├── documents/                optional workspace-local source files
    ├── okf/                      optional managed KB root for workspace OKF
    ├── AGENTS.md
    ├── CLAUDE.md
    ├── .agents/skills/alcove-workspace/SKILL.md
    └── .claude/skills/alcove-workspace/SKILL.md
```

`hub` is special and uses the full `alcove-hub` profile. Other workspace ids use
the lightweight `alcove-workspace` profile: scoped search, scene-local notes,
pins, tasks, ideas, and prompt reuse. Hub-only administration remains in the
Hub unless explicitly authorized.

Workspace-local OKF is managed through `alcove workspace okf ...`. The command
creates `documents/`, initializes `okf/` with the same managed-KB layout used by
regular knowledge bases, registers it under `~/.alcove/knowledge-bases/`, and
updates workspace `default_kb`. This keeps the user-facing workspace workflow
simple while reusing OKF validation, search, and index behavior.

## Prompts

Prompts are reusable global memory records stored as OKF-compatible Markdown
under `~/.alcove/prompts/`. Each prompt uses YAML frontmatter with `type:
Prompt`, tags, use cases, source refs, kind, domain, intent, surfaces,
triggers, inputs, outputs, quality metadata, and an active/archive status.
Markdown files are the source of truth; `~/.alcove/prompts/index.json` is a
derived search index rebuilt automatically by save/archive/search flows.

Historical prompt folders should first be scanned into
`~/.alcove/prompts/candidates/index.json`; only scored, reusable candidates are
promoted into the active library. Scenario recommendation and ready-to-use
Prompt Pack composition are available through `alcove prompt recommend`,
`alcove prompt compose`, `alcove prompt audit`, `alcove_prompt_recommend`,
`alcove_prompt_compose`, and `alcove_prompt_audit`. See
[Prompt Library](prompts.md).

## Tasks, Ideas, and Routines

Ideas, tasks, and routines are stored in `~/.alcove/tasks/tasks.json`.
Active ideas and pending tasks participate in global search when `--home` is
provided.

The planner model is:

```text
IDEA -> promote -> TASK
     -> promote -> ROUTINE -> materialize -> TASK
```

- `IDEA`: low-friction capture; can be edited, archived, or promoted.
- `TASK`: one-off work item with priority, optional due date, complete/cancel,
  and overdue-first listing.
- `ROUTINE`: recurring template with `daily`, `weekly`, or `monthly` schedule;
  supports edit, pause, resume, archive, and idempotent materialization.

Routines materialize when `task materialize-due`, the matching MCP tool, or the
local service tick runs. The service can also send configured planner digests.
Planner notification config lives at `~/.alcove/tasks/notifications.yml`; send
state lives at `~/.alcove/tasks/notification-state.json`.

Example notification config:

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

Supported planner notification sinks are `telegram`, `feishu`, `tcb`, and
`tmux_claude_bot`. If `sinks` is omitted, `telegram` is used for backward
compatibility. `time` is optional; when present, the local service sends the
digest only after that local time and records the period as sent so later ticks
do not duplicate it.

## Mounts

Mounts index external folders or local Git repositories without copying their
content. Global mount registries and indexes live under `~/.alcove/mounts/`.
Repeated scans reuse unchanged file index rows based on file size and mtime.
Scans also write a derived OKF-compatible Markdown index under
`~/.alcove/mounts/okf/`.

## Connectors

Connectors index external systems or exports under
`~/.alcove/connectors/<connector-id>/`.

Current connectors:

- Apple Notes: local read-only Notes.app export or deterministic export folder.
- GitHub Stars: public starred repositories fetched from a user or local JSON export.
- Chrome Bookmarks: local Chrome profile `Bookmarks` JSON or Netscape HTML export.

Connector indexes are local search caches. The external system or export remains
the source of truth. Connector search results can be linked into managed KBs as
OKF Sources.

## Dashboard

The local dashboard is a browser-facing global console over Alcove Home. It is a
read-only observation surface:

- derived snapshot: `~/.alcove/dashboard/snapshot.json`,
- frontend source: `frontend/dashboard/`,
- served as generated static files through Alcove's local stdlib HTTP server.

It has a daily workbench home page plus module pages for Pins, Tasks, Knowledge
Bases, Connectors, Mounts, Activity, Usage, Prompts, and Projects.

Dashboard usage metrics are derived from local privacy-safe events:

- `~/.alcove/logs/activity.jsonl` keeps human-readable semantic activity.
- `~/.alcove/logs/usage.jsonl` keeps machine-readable usage events for
  aggregation.
- `~/.alcove/stats/summary.json` and `~/.alcove/stats/daily/*.json` keep
  derived rollups for fast dashboard and agent reads.
- Dashboard, CLI, and MCP search events record surface, result count, query
  length, local salted query hash, filters, and outcome.
- Knowledge, inbox, pin, task, prompt, project, mount, and connector write
  actions record semantic action names and aggregate counters.
- Raw query text and content snippets are not stored by default.

Read paths and write paths have different contracts. The canonical design is in
[read-write-model.md](read-write-model.md), and the file/index profile is in
[okf-profile.md](okf-profile.md).

- Reads are AI-led. CLI/MCP search provides structured candidates, while agents
  may inspect OKF indexes, source records, connector fetch results, mount
  mirrors, and local files to answer complex questions.
- Writes are Alcove-governed. CLI/MCP mutation commands maintain frontmatter,
  indexes, provenance, activity, usage, stale/delete behavior, and validation
  expectations.
- Direct file edits are repair fallbacks only. Run validation or the nearest
  index rebuild afterward.

The Usage page also includes a data-health summary derived from the same local
snapshot. It reports managed KB, mount, connector, indexed-item, and stats-rollup
counts so stale or empty sources are visible without exposing absolute paths or
content. Each source includes a command hint such as `alcove validate --kb ...`,
`alcove mount scan ...`, or `alcove connector refresh --connector ...` so an
agent can take the next local maintenance step without guessing.

The Activity page stays low-noise. Dashboard route changes and search events are
aggregated on the Usage page instead of being shown as recent activity entries.

## Local Service and Watchers

The local service is the deterministic background layer for macOS. It is
installed as launchd LaunchAgents and does not run background AI.

```text
launchd
├── com.octopusgarage.alcove.dashboard
│   └── alcove serve --dashboard --home ~/.alcove
└── com.octopusgarage.alcove.scheduler
    └── alcove service tick --home ~/.alcove
```

`service tick` runs scheduled maintenance:

- materialize due routines,
- refresh stale connector sources,
- check watched URL/feed sources,
- check monitored blog sources,
- run enabled scheduled radars,
- run due user automation jobs,
- refresh mounted knowledge indexes when their two-day maintenance window is due,
- rebuild the global OKF catalog,
- run health repair,
- refresh and prune usage rollups,
- rebuild the dashboard snapshot.

Mount refresh is deliberately lightweight: the scheduler does not install a
filesystem watcher. It reuses `alcove mount scan` and its incremental file
metadata checks, then records the last service refresh in
`~/.alcove/stats/service-state.json`.

Watchers live under `~/.alcove/watchers/`. Each source is a YAML config with
refresh state, and changes are appended to `events.jsonl`. If a watcher is
bound to a managed KB, changed content is added to that KB's inbox as a manual
item for later review.

Blog monitor lives under `~/.alcove/blog-monitor/`. It is higher-level than
watchers: each source discovers article URLs, compares them with seen state, and
can optionally capture new articles into a managed KB inbox subdirectory.

```text
~/.alcove/blog-monitor/
├── sources/*.yml
├── seen/*.json
├── captures/<source-id>/
├── runs/*.json
└── events.jsonl
```

Default capture uses Clipsmith when the `clipsmith-web` skill and `clipsmith`
CLI are available. Other capture adapters can be added later if they implement
the same result contract. Summary and notification are disabled unless the
source or command explicitly enables them.
Blog index pages should use `discover.method: playwright`, which renders the
page with the Playwright runtime available through the Clipsmith web skill and
keeps discovery aligned with Clipsmith's browser-based capture model. Discovery
and capture failures move the source to `needs_attention`, write a failed run,
and optionally send a Telegram alert. The scheduler never starts Codex or
Claude automatically; agent-assisted repair is a manual follow-up.

## Automations

Automations are generic repeatable user jobs under `~/.alcove/automations/`.
They cover repeatable shell, git-sync, Alcove CLI, and guarded agent jobs without
importing arbitrary Python modules as Alcove core behavior.

```text
~/.alcove/automations/
├── jobs/*.yml
├── runs/*.json
└── events.jsonl
```

Supported job kinds are `shell`, `git-sync`, `alcove`, and guarded `agent`.
The local service runs due jobs according to `ttl_hours`. Agent jobs are skipped
unless `allow_service: true` is explicitly set or a manual command passes
`--allow-agent`.

```sh
alcove automation list --json
alcove automation add-git-sync notes ~/notes --commit-message "chore: sync notes" --json
alcove automation run notes --json
alcove automation run-due --json
```

## Configurable Radars

Radars are generic user-defined information briefings under `~/.alcove/radars/`.
Alcove owns the engine, storage contract, adapters, reports, scheduled
maintenance hook, and dashboard projection. Specific categories
such as tech news, world news, stocks, sports, or personal hobby feeds are user
definitions, not hard-coded product modules.

```text
~/.alcove/radars/
├── definitions/*.yml
├── cache/<radar-id>/<date>/{raw.json,scored.json}
├── runs/<radar-id>/<date>/run.json
├── reports/<radar-id>/<date>.{md,html}
├── reports/<radar-id>/<date>.ai.md
├── okf/<radar-id>/index.md
└── events.jsonl
```

Built-in `tech-news` and `world-news` presets are starter definitions. Users can
create or edit any number of additional radar definitions. Current adapters
include fixture JSON, RSS/Atom, generic HTML, Hacker News, and GitHub Trending.

```sh
alcove radar preset list --json
alcove radar init tech-news --from-preset tech-news --json
alcove radar run tech-news --json
alcove radar run tech-news --force --ai --notify --json
alcove radar run tech-news --skip-fetch --force --ai --notify --json
```

`service tick` runs scheduled radar definitions only when `schedule.enabled` is
true. Definitions can set `schedule.daily_time` plus `schedule.timezone`, for
example `10:00` in `Asia/Singapore`, so the local service waits until that
daily window instead of sending reports just after midnight. Scheduled runs are
deterministic by default. They invoke `codex exec` or `claude -p` only when the
definition explicitly enables `ai_summary`. If AI fails and notifications are
enabled, Alcove sends the deterministic report instead. Notification sinks
currently support Telegram and Feishu custom bot webhooks. See
[radars.md](radars.md) for the full contract and runtime behavior.
