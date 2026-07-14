# Alcove Entry Modes

Alcove has four user-facing runtime modes. They are intentionally different:
the hub is an AI routing workspace, the global entry is a lightweight MCP
bridge, a managed KB entry is a focused capture and knowledge workflow, and the
local service is deterministic background infrastructure.

```text
Alcove Home (~/.alcove)
├── Hub workspace                 strong skill + CLI routing, broad daily work
│   └── Business workspaces        lightweight scene-specific AI directories
├── Global MCP                    lightweight tools from unrelated projects
├── Managed KB workspace          KB-scoped skills, inbox, OKF notes, capture
└── Local service                 launchd dashboard + deterministic maintenance
```

Business workspaces do not add a fourth top-level entry mode. They are a
lightweight workspace type managed by the Hub entry for family, work, travel,
stock, or other user-defined scenes.

## Design Principles

Read broadly, write narrowly.

- Reads are AI-led. Start with `alcove search` or MCP `alcove_search`, then
  inspect OKF records, indexes, source refs, connector fetches, mount refs, and
  local files before answering broad questions.
- Writes are governed. Durable changes should go through Alcove CLI/MCP
  mutation commands so paths, OKF frontmatter, indexes, lifecycle state,
  activity logs, and validation stay consistent.
- Skills should route intent, not own business logic. Scripts and durable
  behavior belong in Alcove or the capture adapter.
- Global access should be quiet. Unrelated coding projects should not inherit
  the full admin surface unless the user explicitly installs it.
- Hub is the default human conversation entry. When adding or changing a
  feature, evaluate how the user will trigger it from the Hub first, then decide
  whether the managed-KB entry, global MCP, CLI command hints, dashboard, or
  background service also need updates.

## Feature Entry Impact Checklist

Every user-facing feature change should answer these questions before it is
called done:

```text
Feature / behavior change
├── Hub workspace
│   ├── Does `alcove-hub` need intent routing or a protocol section?
│   ├── Should the Hub agent call CLI directly, search first, or inspect data?
│   └── Does the completion receipt need module-specific wording?
├── Managed KB workspace
│   ├── Does a KB-local workflow need capture, inbox, archive, OKF, or note rules?
│   └── Should KB skills stay narrow instead of becoming global memory tools?
├── Global MCP
│   ├── Is this safe as a lightweight global MCP tool?
│   ├── Should it be a command hint instead of an exposed mutating tool?
│   └── Should it require `full` or KB toolset instead of `lite`?
├── CLI / API
│   ├── Is there a governed write command for durable state?
│   └── Is the command ergonomic for Hub and MCP agents to call?
├── Service / dashboard
│   ├── Does deterministic background work need scheduler support?
│   └── Does the dashboard or exported view need the new state?
└── Verification
    ├── Update docs and profile templates in the same change.
    ├── Run entry/profile smoke when skills, commands, MCP, or profile installs change.
    └── Run AI eval when routing quality, prompt quality, summaries, or dashboard usefulness changes.
```

If the answer is "no change needed" for an entry mode, record that in the final
engineering summary. Silent omissions are how Hub and MCP behavior drift.

## Hub Workspace

The hub is the main conversation workspace for personal information management.
It installs `AGENTS.md`, `CLAUDE.md`, `.alcove-hub.yml`, and the `alcove-hub`
skill.

Use it for:

- broad personal knowledge questions,
- deciding where a new memory belongs,
- managing pins, prompts, projects, tasks, mounts, connectors, exports, and
  multiple managed KBs,
- using AI judgment to route ambiguous "remember/save/record" requests.
- project maintenance requests that originate in the Hub, such as "optimize
  Alcove prompt management" or "add a radar feature". The Hub should route these
  to the relevant project/worktree and preserve the entry impact checklist
  above instead of saving the request as ordinary knowledge by default.

Default routing:

```text
copied article / discussion note / archive -> managed KB inbox or knowledge
stable reference / command / preference    -> pin regular
future practice / later exploration        -> pin todo, idea, or task
reusable instruction                       -> prompt
project path shortcut                      -> project
historical folder or repo                  -> mount
protocol/exported source                   -> connector
broad recall                               -> search, then inspect evidence
```

Recommended install:

```sh
alcove hub init ~/AlcoveHub --default-kb social_media_posts
alcove hub install ~/AlcoveHub --default-kb social_media_posts
```

The fixed default Hub can also be initialized through the generic workspace
surface:

```sh
alcove workspace init hub --default-kb social_media_posts
```

Install modes:

- Default copy mode writes generated skills and commands as normal files. This
  is the stable mode for normal users and release installs.
- Development link mode symlinks Alcove-owned skills and Claude commands back
  to the source templates:

```sh
alcove hub install ~/AlcoveHub --default-kb social_media_posts --link
```

`AGENTS.md`, `CLAUDE.md`, and `.alcove-hub.yml` remain normal generated files.
They can contain workspace-specific context, so Alcove updates only the marked
Alcove section instead of replacing the whole file with a symlink.

Agent targets:

```text
--target claude
├── CLAUDE.md                         normal file, Alcove marked section
└── .claude/skills/alcove-hub/SKILL.md copy or symlink

--target codex
├── AGENTS.md                         normal file, Alcove marked section
└── .agents/skills/alcove-hub/SKILL.md copy or symlink
```

The hub should generally use CLI directly and can use MCP when available. If an
MCP server is desired for hub-only sessions, use the full toolset explicitly:

```sh
alcove serve --mcp --toolset full
```

### Business Workspaces

Business workspaces are lightweight directories under the Hub concept. They
carry scene-specific agent context without exposing the full Hub control
surface by default.

Use them for:

- family, work, travel, finance, learning, or other recurring business scenes,
- scoped search across preferred KBs, tags, and modules,
- saving scene-local OKF notes and imported files through `workspace okf`,
- saving pins, tasks, ideas, and prompt recommendations with the workspace tag,
- one-shot agent runs that should inherit a scene's `AGENTS.md`, `CLAUDE.md`,
  and project skill.

Do not use them as system control surfaces. Installing entries, changing global
MCP, service control, export/backup, connector or mount administration, radar
definition changes, publisher configuration, and health fixes belong in the
Hub unless the user explicitly authorizes a command.

Default storage:

```text
~/.alcove/workspaces/
├── hub.yml
├── family.yml
├── work.yml
└── data/
    ├── hub/
    ├── family/
    └── work/
```

Workspace-local OKF:

```text
~/.alcove/workspaces/data/family/
├── documents/          raw family-owned files
└── okf/                managed KB store registered as `family`
```

Use `alcove workspace okf init family --json` to create and bind the local OKF
store. After that, workspace agents should use `alcove workspace okf add-note`,
`import-file`, and `search` for scene-local knowledge before expanding to
Home-wide search.

If `--path` is omitted, `alcove workspace init <id>` creates the agent entry
directory at `~/.alcove/workspaces/data/<id>/`. If `--path` is provided, the
registry still lives under `~/.alcove/workspaces/<id>.yml`, but the agent entry
files are installed in the chosen directory.

Common commands:

```sh
alcove workspace init family --default-kb social_media_posts --tag family
alcove workspace init work --path ~/WorkHub --default-kb work_notes
alcove workspace list --json
alcove workspace status family --json
alcove workspace install family --target all --link
alcove workspace run family --agent codex "整理家庭相关任务" --json
```

Long-running interactive sessions should start in the workspace directory:

```sh
cd ~/.alcove/workspaces/data/family
codex
# or
claude
```

One-shot runs use the workspace as the agent working directory:

```text
codex exec -C <workspace-path> ...
cd <workspace-path> && claude -p ...
```

The generated lightweight `alcove-workspace` skill reads
`.alcove-workspace.yml`, starts with configured scope, preserves workspace tags
on writes, applies a mixed memory policy for durable workspace facts, and routes
Hub-only administration back to the Hub. Low-risk explicit facts can be saved
directly to workspace OKF; sensitive, private, ambiguous, or unstable
information requires confirmation first.

## Global MCP

The global entry is for unrelated projects where the user only occasionally
wants to search Alcove or save a small piece of memory.

Global install defaults to the `lite` MCP toolset:

```sh
alcove global install
alcove global install --default-kb social_media_posts
```

It also initializes the default Apple Notes publisher and installs the scheduler
LaunchAgent. The generated Notes remain readable mirrors; background publishing
runs when the scheduler's `alcove service tick` determines the publisher is due
by TTL or by an Alcove write marking a mirrored source dirty.

`lite` keeps the exposed MCP surface small:

- command hints for CLI-only workflows such as blog monitoring, radars,
  dashboard serving, and publisher syncs,
- search,
- pins,
- prompts propose/save/search/recommend/compose/get,
- lightweight planner tools: tasks, ideas, task edit, complete/cancel,
- manual-add into a default managed KB inbox when `--default-kb` is configured.

It intentionally hides heavier/admin operations:

- connector imports,
- mount scans,
- export,
- gardener,
- routine administration and planner digest notification,
- full KB archive/note/delete flows.

Use `alcove_command_hints` when an MCP-only client needs to discover the right
CLI command for a complex Hub workflow. This keeps discovery available without
turning global MCP into the full orchestration surface.

Install a wider global surface only when the user explicitly wants it:

```sh
alcove global install --toolset kb --default-kb social_media_posts
alcove global install --toolset full
```

## Local Service

The local service is the non-AI background layer. It can keep the dashboard
available and run deterministic maintenance without requiring an open Codex or
Claude Code session.

```text
Local Service
├── dashboard LaunchAgent   -> alcove serve --dashboard --home ~/.alcove
└── scheduler LaunchAgent   -> alcove service tick --home ~/.alcove
```

Recommended install:

```sh
alcove service install --dashboard --scheduler --load
alcove service status
```

One maintenance tick runs:

- due routine materialization,
- configured planner digest notification,
- stale connector refresh,
- watched-source checks,
- monitored blog checks,
- scheduled radar runs,
- due user automation jobs,
- global OKF catalog rebuild,
- health check/fix,
- usage rollup refresh and pruning,
- dashboard snapshot rebuild.

Background service work is deterministic by default. It should discover and
record changes, not silently write synthesized knowledge notes. Watchers can add
changed pages to a managed KB inbox for later interactive review. Blog monitor
sources can discover new article URLs and optionally capture the article bundle
into a configured KB inbox subdirectory.
Radar definitions may optionally enable `ai_summary` and Telegram `notify`.
That AI step runs after deterministic fetching/scoring/report generation, uses
the radar-specific prompt from the definition, and falls back to the original
report if the AI provider fails.

Automations are included in the scheduler as repeatable user maintenance jobs.
Deterministic `shell`, `git-sync`, and `alcove` jobs can run when due. Guarded
`agent` jobs do not run from launchd unless the job explicitly sets
`allow_service: true`; manual execution can pass `--allow-agent`.

Watchers:

```sh
alcove watch add "Example Blog" https://example.com/feed.xml --kind rss --kb social_media_posts
alcove watch list --json
alcove watch check --stale --json
```

Watcher data lives under `~/.alcove/watchers/`.

Blog monitor:

```sh
alcove blog add "Anthropic Engineering" https://www.anthropic.com/engineering \
  --id anthropic --discover playwright --link-pattern /engineering/ \
  --kb social_media_posts --inbox-path inbox/anthropic --capture
alcove blog add "OpenAI Engineering" https://openai.com/news/engineering/ \
  --id openai --discover playwright --link-pattern /index/ \
  --kb social_media_posts --inbox-path inbox/openai --capture
alcove blog seed openai
alcove blog check --stale --json
```

Blog monitor data lives under `~/.alcove/blog-monitor/`. Summary and notification
are opt-in with `--summary` and `--notify` or the matching source config fields.
Discovery or capture failures are recorded as failed runs, mark the source as
`needs_attention`, and send a Telegram alert when notifications are enabled.
The launchd scheduler does not auto-start Codex or Claude; agent-assisted
diagnosis is a manual follow-up from the alert.

For an immediate Hub request such as "check whether monitored blogs updated",
use `alcove blog check --json`. Do not use `alcove service tick` for that
request; tick is the scheduled maintenance path and may skip sources whose TTL
has not expired. For a failure alert, run `alcove blog list --status '' --json`
to inspect `last_error`, then retry the affected source with
`alcove blog check <source-id> --json`.

For immediate radar requests from the Hub:

```sh
alcove radar run tech-news --force --ai --notify --json
alcove radar run tech-news --skip-fetch --force --ai --notify --json
```

Use the first command to refetch sources and analyze the new report. Use the
second command when the user asks to analyze or resend the already fetched
results without touching external sources. Scheduled radar definitions may use
`schedule.daily_time` and `schedule.timezone`, so the service can send reports
after a daily local window such as `10:00` in `Asia/Singapore` instead of just
after midnight.

## Managed KB Workspace

A managed KB is where capture, inbox review, source archiving, and OKF note
maintenance happen. It installs `alcove-kb`, `notes-search`, and
`alcove-capture` skills plus Claude commands.

Use it for:

- Clipsmith capture into `inbox/`,
- reviewing one pending item at a time,
- writing Sources, Knowledge Concepts, Questions, and Entities,
- adding pasted or AI-discussion notes through `manual-add` or knowledge
  commands,
- validating and gardening the KB.

Default rules:

- A raw link means capture to inbox, not permission to process existing inbox
  items.
- Archive/note/todo/delete require explicit confirmation for the current item.
- OCR and bundle repair belong in Clipsmith; Alcove reads declared
  `capture.json.content_files`.
- Article summaries belong in KB Source/Concept records, not prompts, unless
  the user explicitly asks for a reusable prompt.

Recommended install:

```sh
alcove kb install social_media_posts
```

Development link mode is available for managed KB workflow files:

```sh
alcove kb install social_media_posts --link
```

This symlinks `.agents/.claude/skills/*/SKILL.md` and
`.claude/commands/*.md` to Alcove source templates. `AGENTS.md` and
`CLAUDE.md` stay as normal files with an Alcove-managed section. Link mode is
intended for local Alcove development and currently requires the default
Alcove Home context, so generated commands do not need embedded `--home`
arguments.

Managed KB target layout:

```text
--target claude
├── CLAUDE.md                                      normal file, Alcove marked section
├── .claude/skills/alcove-kb/SKILL.md             copy or symlink
├── .claude/skills/notes-search/SKILL.md          copy or symlink
├── .claude/skills/alcove-capture/SKILL.md   copy or symlink
├── .claude/commands/inbox-peek.md                copy or symlink
└── .claude/commands/into-kb.md                   copy or symlink

--target codex
├── AGENTS.md                                     normal file, Alcove marked section
├── .agents/skills/alcove-kb/SKILL.md             copy or symlink
├── .agents/skills/notes-search/SKILL.md          copy or symlink
└── .agents/skills/alcove-capture/SKILL.md   copy or symlink
```

For MCP sessions focused on a KB, use the `kb` toolset:

```sh
alcove serve --mcp --toolset kb --kb social_media_posts
```

## MCP Toolsets

```text
lite
├── search
├── pin add/list/get/search/update
├── prompt propose/save/search/get/recommend/compose
├── task add/list/complete/cancel
├── idea add/list/promote
├── inbox manual-add, when a default KB is configured
└── health

kb
├── lite-style common memory tools
├── inbox peek/read/manual-add/archive/note/todo/delete
├── knowledge add/revise/promote/refresh/topics
├── link source
└── doctor/validate/health

full
├── all lite and kb tools
├── projects
├── prompts archive/tags/rebuild
├── routines
├── mounts
├── connectors
├── export
└── gardener/health/admin operations
```

The default `alcove serve --mcp` remains `full` for backward compatibility.
Installers should choose the narrowest useful toolset for the entry mode.
