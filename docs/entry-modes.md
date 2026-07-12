# Alcove Entry Modes

Alcove has three user-facing entry modes. They are intentionally different:
the hub is an AI routing workspace, the global entry is a lightweight MCP
bridge, and a managed KB entry is a focused capture and knowledge workflow.

```text
Alcove Home (~/.alcove)
├── Hub workspace                 strong skill + CLI routing, broad daily work
├── Global MCP                    lightweight tools from unrelated projects
└── Managed KB workspace          KB-scoped skills, inbox, OKF notes, capture
```

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

## Global MCP

The global entry is for unrelated projects where the user only occasionally
wants to search Alcove or save a small piece of memory.

Global install defaults to the `lite` MCP toolset:

```sh
alcove global install
alcove global install --default-kb social_media_posts
```

`lite` keeps the exposed MCP surface small:

- search,
- pins,
- prompts save/search/get,
- tasks and ideas,
- manual-add into a default managed KB inbox when `--default-kb` is configured.

It intentionally hides heavier/admin operations:

- connector imports,
- mount scans,
- export,
- gardener,
- full KB archive/note/delete flows.

Install a wider global surface only when the user explicitly wants it:

```sh
alcove global install --toolset kb --default-kb social_media_posts
alcove global install --toolset full
```

## Managed KB Workspace

A managed KB is where capture, inbox review, source archiving, and OKF note
maintenance happen. It installs `alcove-kb`, `notes-search`, and
`social_post_manager` skills plus Claude commands.

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
├── .claude/skills/social_post_manager/SKILL.md   copy or symlink
├── .claude/commands/inbox-peek.md                copy or symlink
└── .claude/commands/into-kb.md                   copy or symlink

--target codex
├── AGENTS.md                                     normal file, Alcove marked section
├── .agents/skills/alcove-kb/SKILL.md             copy or symlink
├── .agents/skills/notes-search/SKILL.md          copy or symlink
└── .agents/skills/social_post_manager/SKILL.md   copy or symlink
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
├── prompt save/search/get
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
