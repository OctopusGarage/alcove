# Alcove Architecture and Feature Overview

Alcove is a local-first personal information system. The product model is intentionally small:

```text
Alcove
├── 1. Knowledge Bases / 知识库体系
├── 2. Pins / 置顶收藏功能
├── 3. Tasks / 任务事务功能
└── 4. Global Utilities / 全局工具域
    ├── Projects / 项目别名
    └── Prompt Memory / 提示词库
```

This document records the target relationship model and compares it with the current implementation.
For the project-wide OKF contract, see [okf-profile.md](okf-profile.md). For
the read/write interaction model, see
[read-write-model.md](read-write-model.md).

## 1. Knowledge Bases / 知识库体系

Knowledge bases are one-to-many. Alcove should support multiple knowledge sources with different ownership levels.

```text
Knowledge Bases
├── 1.1 Managed Knowledge Base / 托管知识库
├── 1.2 Mounted Knowledge Base / 挂载知识库
└── 1.3 Connector Knowledge Base / 连接器知识库
```

### 1.1 Managed Knowledge Base

A managed knowledge base is fully managed by Alcove. It has an inbox, archive, formal OKF knowledge, taxonomy, validation, gardening, and note creation workflow.

Current local instance:

```text
research_notes
```

Target structure:

```text
<managed-kb-root>/                                  user-chosen directory
├── .alcove/config.yml                             per-KB config
├── knowledge/                                     OKF formal knowledge
│   ├── concepts/<domain>/<topic>/*.md             durable notes
│   ├── sources/<platform>/<domain>/*.md           provenance records
│   ├── questions/<domain>/<topic>/*.md            reusable Q&A
│   ├── entities/<kind>/*.md                       reusable object profiles
│   ├── topics/<domain>/<topic>.md                 generated indexes
│   ├── tags/<tag>.md                              generated indexes
│   ├── domains/<domain>.md                        generated indexes
│   ├── taxonomy.yml                               domain/topic/tag contract
│   ├── index.md                                   generated root index
│   └── log.md                                     knowledge change log
├── inbox/                                         pending inputs
│   ├── xhs/<capture-id>/                          captured post bundle
│   ├── x/<capture-id>/
│   ├── wechat/<capture-id>/
│   ├── web/<capture-id>/
│   └── manual/<draft-id>/                         copied text or AI discussion draft
├── archive/                                       raw processed evidence
│   └── <topic>/[platform] <capture-id>/
└── todo/                                          deferred inbox items
```

Cardinality and storage:

```text
Alcove -> Managed Knowledge Base: 1-to-many
Data location: user-configured external directory
Example managed KB path: /path/to/research_notes
Main formats: Markdown + YAML frontmatter, taxonomy.yml, capture folders, .archive-meta.json
```

Managed KB workflows:

```text
capture / manual input
  -> inbox/
  -> read / classify
  -> user confirms action
  -> archive only
  -> or write Source
  -> or write Source + Knowledge Concept
  -> optionally write Question / Entity
  -> refresh indexes and log
```

Direct note input should support two modes:

```text
manual draft mode
  -> user pastes copied content or AI discussion summary
  -> Alcove writes <kb>/inbox/manual/<draft-id>/
  -> later processed like any other inbox item

direct knowledge mode
  -> user asks agent to remember/save a note
  -> Alcove writes OKF Source / Concept / Question / Entity directly
```

Capture adapters are pluggable. Clipsmith is the current default adapter, but
the knowledge base should only depend on the inbox contract, not on Clipsmith
internals.

Clipsmith project links:

- GitHub: https://github.com/OctopusGarage/clipsmith
- Project page: https://octopusgarage.github.io/clipsmith/

```text
Clipsmith / custom collector
  -> capture bundle
  -> <managed-kb-root>/inbox/<platform>/<capture-id>/
```

The default Clipsmith handoff command is:

```sh
clipsmith sink inbox "<bundle_dir>" "<managed-kb-root>" --json
```

Any custom collector can replace Clipsmith if it writes equivalent reviewable
content and metadata into the same inbox layout.

Alcove reads Clipsmith bundles through `capture.json.content_files` first. This
keeps OCR text files, summaries, and post text reviewable without hard-coding a
single filename. Legacy folders without `capture.json` still use platform
fallback names such as `summary.md`, `post.md`, `article.md`, `ocr.md`,
`ocr.txt`, and `ocr-merge.txt`.

User-data synchronization is intentionally outside the Alcove runtime. The
recommended operational pattern is:

```text
managed KB roots + ~/.alcove
  -> private Git-backed backup repository
  -> git-auto-sync scheduled synchronization
  -> optional git-crypt encryption before remote push
```

Recommended tools:

- git-auto-sync for periodic Git synchronization:
  https://github.com/OctopusGarage/git-auto-sync
- git-crypt for encrypting sensitive files before syncing to Git:
  https://github.com/AGWA/git-crypt

Alcove should keep data portable as Markdown/JSON/YAML files, but it should not
own git-auto-sync scheduling or git-crypt key management. Users should configure
`.gitattributes` and verify encryption before pushing private knowledge,
archives, connector indexes, pins, tasks, or prompts to a remote repository.

### 1.2 Mounted Knowledge Base

A mounted knowledge base is a read-only external knowledge index. It points at existing folders or repositories that should remain where they are.

Examples:

- historical Git repositories,
- local document folders,
- star-cloned repositories,
- old project archives,
- exported personal files.

Target structure:

```text
~/.alcove/mounts/                                  Alcove-owned global index state
├── mounts.json                                    mount registry
└── indexes/
    └── <mount-id>.json                            indexed file metadata and text snippets
└── okf/
    └── <mount-id>/
        ├── index.md                               OKF-compatible mount summary for agents
        └── items/
            └── <slug>-<hash>.md                   OKF-compatible mounted item mirror
```

Cardinality and storage:

```text
Alcove -> Mounted Knowledge Base: 1-to-many
Data location: Alcove global state, pointing to external read-only directories
Current global implementation: ~/.alcove/mounts/
Legacy workspace-compatible implementation: <workspace>/mounts/
Main formats: JSON registry + JSON index + derived OKF-compatible Markdown index
```

Mounted KB rules:

- Do not copy all external files into a managed KB.
- Do not force external folders into OKF structure.
- Build lightweight searchable indexes.
- Write derived OKF-compatible Markdown under `~/.alcove/mounts/okf/` so Codex,
  Claude Code, and shell tools can inspect mounted content without custom JSON
  parsing.
- Support incremental refresh by reusing unchanged indexed files via size and mtime metadata.
- Search results can be linked into a managed KB as OKF `Source` when they become important.

Mount indexing rules:

- `mount scan` reads text files with `.md`, `.markdown`, `.txt`, and `.rst`
  extensions, skipping `.git`, `.hg`, `.svn`, `.venv`, `node_modules`, and
  `__pycache__`.
- JSON indexes under `indexes/<mount-id>.json` remain the programmatic search
  cache used by `alcove search`.
- OKF-compatible Markdown indexes are derived caches, not the source of truth:
  `okf/<mount-id>/index.md` has `type: Mount Index` and
  `schema: okf/mount-index/v1`; each item has `type: Mounted Item` and
  `schema: okf/mounted-item/v1`.
- Deleted source files are removed from both JSON and OKF-compatible derived indexes
  on the next scan.

### 1.3 Connector Knowledge Base

A connector knowledge base is an indexed external data source reached through a protocol, export format, API, or adapter.

Examples:

- Apple Notes,
- GitHub Stars,
- browser bookmarks,
- Readwise,
- Feishu/Lark docs,
- future custom connectors.

Target structure:

```text
~/.alcove/connectors/                              Alcove-owned global connector state
├── apple-notes/
│   ├── config.yml
│   ├── sources/*.yml                              registered connector sources
│   ├── exports/full/                              retained deterministic Notes.app export
│   ├── index.json                                 indexed notes metadata/search text
│   └── okf/                                       derived agent-readable Markdown index
│       ├── index.md
│       ├── sources/*.md
│       └── items/<slug>-<hash>.md
├── github-stars/
│   ├── config.yml
│   ├── sources/*.yml                              registered users / refresh state
│   ├── exports/*.json                             retained API exports
│   ├── index.json                                 indexed starred repositories
│   └── okf/
│       ├── index.md
│       ├── sources/*.md
│       └── items/<slug>-<hash>.md
├── chrome-bookmarks/
│   ├── config.yml
│   ├── sources/*.yml                              registered Chrome profile files / refresh state
│   ├── index.json                                 indexed bookmark metadata/search text
│   └── okf/
│       ├── index.md
│       ├── sources/*.md
│       └── items/<slug>-<hash>.md
└── <connector-id>/
    ├── config.yml
    ├── sources/*.yml
    ├── index.json
    └── okf/
        ├── index.md
        ├── sources/*.md
        └── items/<slug>-<hash>.md
```

Cardinality and storage:

```text
Alcove -> Connector Knowledge Base: 1-to-many
Data location: Alcove global state, pointing to protocol/export/API data
Current global implementation: ~/.alcove/connectors/<connector-id>/index.json
Legacy workspace-compatible implementation: <workspace>/.alcove/connectors/<connector-id>/index.json
Main formats: connector config + JSON index + derived OKF-compatible Markdown index
```

Connector rules:

- Connector indexes belong in Alcove global state, not inside one managed KB.
- A connector index is not the source of truth; the external system/export remains the source.
- Index only key metadata and searchable text by default.
- Write derived OKF-compatible Markdown under `okf/` so agents and shell tools can
  inspect connector indexes without custom JSON parsing. Connector summaries use
  `schema: okf/connector-index/v1`; source summaries use
  `schema: okf/connector-source/v1`; item mirrors use
  `schema: okf/connector-item/v1`.
- Lazy-fetch detail after a search hit through `connectors/<connector-id>#<relative-path>`.
- Search results can be linked into one or more managed KBs as OKF `Source`.

Promotion flow:

```text
external system / export
  -> ~/.alcove/connectors/<connector-id>/index.json
  -> unified search hit
  -> user chooses to keep it
  -> <managed-kb>/knowledge/sources/<connector>/<domain>/*.md
```

Apple Notes supports two read-only import modes:

```text
Notes.app on local macOS
  -> macOS Automation read-only export
  -> ~/.alcove/connectors/apple-notes/exports/full/
  -> ~/.alcove/connectors/apple-notes/sources/local.yml
  -> ~/.alcove/connectors/apple-notes/index.json

existing deterministic export
  -> alcove connector apple-notes index <export-dir>
  -> ~/.alcove/connectors/apple-notes/index.json
```

The local import copies the useful contract from the prior Apple Notes skill into
Alcove: stable note identity is the Apple Notes note id, full export writes
`notes/<encoded-note-id>/note.json` and `note.md`, `manifest.json` is
deterministic, and `summary.json` records added, updated, and removed note ids
for the last sync. Refresh is explicit and local-search-only:
`alcove connector apple-notes refresh local --force` refreshes the registered
source, while `alcove connector refresh --connector apple-notes --stale`
refreshes stale registered Apple Notes sources. The exporter does not rewrite
unchanged `note.json` or `note.md` files, so their mtime remains stable; the
indexer then reuses unchanged Apple Note rows by file size, mtime, and tags.

GitHub Stars currently supports two import modes:

```text
github.com/<user>?tab=stars or <user>
  -> GitHub public starred repositories API
  -> ~/.alcove/connectors/github-stars/exports/<user>-starred.json
  -> ~/.alcove/connectors/github-stars/sources/<user>.yml
  -> ~/.alcove/connectors/github-stars/index.json

local JSON export
  -> alcove connector github-stars index <export-file>
  -> ~/.alcove/connectors/github-stars/index.json
```

The saved export is retained so the connector index can be rebuilt without
re-fetching remote data. The index stores repository name, URL, description,
language, topics, star count, update timestamp, tags, and compact search text.

Connector refresh is separate from search. `alcove search` reads local indexes
only. `alcove connector status` reports registered source freshness using the
source registry TTL, and `alcove connector refresh --stale` refreshes stale
registered sources. `alcove connector github-stars refresh <user> --force`
refreshes one GitHub Stars source explicitly. GitHub Stars refreshes keep the
previous export long enough to report `added`, `removed`, `updated`, and
`unchanged` repository counts. When GitHub returns `304 Not Modified` for a
registered source ETag, Alcove marks the source fresh without rewriting the
export file or rebuilding the index.

Chrome Bookmarks currently supports two import modes:

```text
local Chrome profile Bookmarks file
  -> alcove connector chrome-bookmarks import-local [--profile Default]
  -> ~/.alcove/connectors/chrome-bookmarks/sources/default.yml
  -> ~/.alcove/connectors/chrome-bookmarks/index.json

local Bookmarks JSON or Netscape bookmarks HTML export
  -> alcove connector chrome-bookmarks index <export-file>
  -> ~/.alcove/connectors/chrome-bookmarks/index.json
```

The index stores bookmark title, URL, folder path, added/modified timestamps,
tags, and compact search text. `import-local` keeps the external Chrome
Bookmarks file as the source of truth and stores only the registered source
pointer plus derived index state in Alcove. Refresh is explicit:
`alcove connector chrome-bookmarks refresh default --force` refreshes one local
profile source, while `alcove connector refresh --connector chrome-bookmarks
--stale` refreshes stale registered Chrome bookmark sources. Deleted bookmarks
are removed from both `index.json` and the derived OKF item mirrors on the next
refresh.

## 2. Pins / 置顶收藏功能

Pins are a global Alcove feature, not a knowledge base. They are for small, high-value personal reference items that should be easy to retrieve.

Examples:

- common commands,
- stable personal preferences,
- frequently reused snippets,
- important reminders,
- tiny knowledge points,
- links or references that should stay visible.

Target structure:

```text
~/.alcove/pins/                                    Alcove-owned global data
├── <pin-id>.md                                    source-of-truth OKF Pin Markdown
├── index.json                                     derived machine-readable index
├── index.md                                       derived agent-readable index
└── board.html                                     derived visual pin board
```

Pin kinds:

```text
regular                                            常规类；反复查阅、引用、确认
todo                                               待实践类；以后找机会实践、细化、深入理解
```

Both kinds are still "pinned". `kind` separates intent; `priority` controls
how prominently the item sorts inside the board and search/list output.

Example format:

```markdown
---
type: Pin
schema: okf/pin/v1
title: Japanese Edge Launcher
description: Launch Edge with TZ=Asia/Tokyo.
summary: Launch Edge with TZ=Asia/Tokyo.
kind: regular
content_format: text
tags:
  - app-launcher
priority: medium
status: active
source_refs: []
resources: []
created_at: "2026-07-08T00:00:00+00:00"
updated_at: "2026-07-08T00:00:00+00:00"
last_used_at: ""
---

# Japanese Edge Launcher

## Summary

Launch Edge with TZ=Asia/Tokyo.

## Content

Launch Edge with `TZ=Asia/Tokyo`.
```

Cardinality and storage:

```text
Alcove -> Pins: 1-to-1 global feature
Data location: ~/.alcove/pins/
Legacy workspace-compatible location: <workspace>/pins/
Main format: Markdown + YAML frontmatter
Derived formats: JSON index + Markdown index + standalone HTML board
```

Pins should not require selecting a managed KB. They should be globally
searchable and available through CLI/MCP. The Markdown files are the durable
data format; `index.json`, `index.md`, and `board.html` can be regenerated.

## 3. Tasks / 任务事务功能

Tasks are a global Alcove feature, not a knowledge base. They manage personal todos, ideas, routines, and future reminder behavior.

Target structure:

```text
~/.alcove/tasks/                                   Alcove-owned global data
└── tasks.json                                     ideas, tasks, routines, reminders
```

Current object types:

```text
Idea                                               low-friction capture
Task                                               concrete executable item
Routine                                            recurring task template
```

Future object type:

```text
Reminder                                           notification/scheduled reminder metadata
```

Cardinality and storage:

```text
Alcove -> Tasks: 1-to-1 global feature
Data location: ~/.alcove/tasks/tasks.json
Legacy workspace-compatible location: <workspace>/tasks/tasks.json
Main format: JSON
```

Task flows:

```text
idea add
  -> idea promote
  -> task
  -> task complete / cancel

routine add
  -> materialize due
  -> task
```

Tasks should not require selecting a managed KB. They should be globally searchable and available through MCP.

## 4. Global Utilities / 全局工具域

These features are global Alcove Home utilities. They are not managed knowledge bases, but they are searchable and available through CLI/MCP.

### 4.1 Projects / 项目别名

Projects replace the project-alias part of `forge-mcp-server`.

```text
~/.alcove/projects/
└── projects.json                                project aliases and scan roots
```

Cardinality and storage:

```text
Alcove -> Projects: 1-to-1 global feature
Data location: ~/.alcove/projects/projects.json
Main format: JSON
Search row type: Project
MCP/CLI: add, get, find, list, remove, roots-set
```

Project records are lightweight shortcuts to local folders. `find` first checks registered aliases, notes, and paths; if no registry hit exists, it scans configured roots.

### 4.2 Prompt Memory / 提示词库

Prompts replace the prompt-library part of `forge-mcp-server`, but use Alcove's
OKF-compatible Markdown surface instead of a YAML prompt dictionary.

```text
~/.alcove/prompts/
├── <prompt-id>.md                               OKF-compatible Markdown source of truth
└── index.json                                   derived searchable prompt index
```

Example format:

```markdown
---
type: Prompt
schema: okf/prompt/v1
title: Code Review Lens
description: Reusable review prompt.
tags:
  - review
status: active
use_cases:
  - PR review
source_refs: []
created_at: "2026-07-09T00:00:00+00:00"
updated_at: "2026-07-09T00:00:00+00:00"
---
# Code Review Lens

## Prompt

Review for correctness, regressions, and missing tests.
```

Cardinality and storage:

```text
Alcove -> Prompt Memory: 1-to-1 global feature
Data location: ~/.alcove/prompts/
Main format: Markdown + YAML frontmatter
Derived index: ~/.alcove/prompts/index.json
Search row type: Prompt
MCP/CLI: save, search, get, archive, tags, rebuild-index
```

Prompt indexing rules:

- `*.md` prompt files are the source of truth.
- `index.json` is a derived cache for global search and MCP lookups.
- `prompt save` and confirmed `prompt archive` rebuild the index automatically.
- `prompt search` and `prompt tags` rebuild the index when it is missing or stale.
- `prompt rebuild-index` exists for migrations and manual repair.
- Index rebuild validates strict prompt frontmatter under the Alcove OKF
  Profile: `type: Prompt`,
  `schema: okf/prompt/v1`, `title`, `description`, `tags`, `status`,
  `use_cases`, `source_refs`, `created_at`, and `updated_at`.

## Global State

The implemented state split is:

```text
~/.alcove/                                         Alcove home, 1-to-1 per user
├── config.yml                                     global config
├── knowledge-bases/                               managed KB registry
│   └── research_notes.yml                     points to real KB directory
├── projects/                                      global project aliases
│   └── projects.json
├── prompts/                                       reusable global prompt memory
│   └── <prompt-id>.md
├── pins/                                          global pins
├── tasks/                                         global tasks
├── mounts/                                        external folder/repo indexes
│   ├── mounts.json
│   ├── indexes/<mount-id>.json
│   └── okf/<mount-id>/
│       ├── index.md
│       └── items/<slug>-<hash>.md
└── connectors/                                    external protocol/source indexes
    └── <connector-id>/
        ├── config.yml
        ├── sources/<source-id>.yml
        ├── exports/
        ├── index.json
        └── okf/
            ├── index.md
            ├── sources/<source-id>.md
            └── items/<slug>-<hash>.md

<managed-kb-root>/                                 user-controlled data location
├── .alcove/config.yml
├── knowledge/
├── inbox/
├── archive/
└── todo/
```

This creates a clean separation:

- Alcove global state stores cross-cutting personal data and external indexes.
- Managed KB roots store full-lifecycle knowledge-base data.
- External mounted/connector sources remain outside managed KB roots unless linked.

## Unified Search

Search unifies managed KB knowledge and Alcove Home global data while keeping
storage scopes explicit.

Implemented examples:

```sh
alcove search "query"
alcove search "query" --workspace /path/to/research_notes
alcove search "query" --kb research_notes
alcove search "query" --type Pin
alcove search "query" --type Project
alcove search "query" --type Prompt
alcove search "query" --type Task
alcove search "query" --type "Mounted Item"
alcove search "query" --platform github-stars
```

Result roots make provenance obvious:

```text
knowledge -> managed KB OKF Markdown
pins -> ~/.alcove/pins/
projects -> ~/.alcove/projects/projects.json
prompts -> ~/.alcove/prompts/
tasks -> ~/.alcove/tasks/tasks.json
mounts -> ~/.alcove/mounts/indexes/
connectors -> ~/.alcove/connectors/<connector-id>/index.json
```

## Read/Write Operating Model

```text
Read broadly; write narrowly.
Search gives candidates; AI investigation produces answers.
CLI/MCP writes the durable state.
```

The detailed contract is maintained in
[read-write-model.md](read-write-model.md). The OKF document and indexing
profile that supports this model is maintained in
[okf-profile.md](okf-profile.md).

## CLI/MCP Surface

The CLI makes global features and KB-scoped features distinct while preserving
legacy `--workspace` compatibility for older flows.

Alcove has three installation profiles. They intentionally solve different
entry problems instead of forcing one heavy global install.

```text
1. Hub workspace profile
   Purpose: main daily conversation entry for personal information management.
   Install scope: one user-chosen directory, not global agent config.
   Writes: CLAUDE.md, AGENTS.md, project-local Alcove skills, .alcove-hub.yml.
   Typical use: open this directory in Codex/Claude Code and manage search,
   pins, prompts, projects, tasks, mounts, connectors, export, and multiple
   managed KBs from one place.
   Intent model: install a strong `alcove-hub` skill that routes ambiguous
   "record/save/remember" requests before writing data.

2. Global-lite profile
   Purpose: lightweight access from any unrelated project.
   Install scope: global agent MCP config only.
   Writes: MCP server config pointing at ~/.alcove; no project files.
   MCP toolset: `lite` by default, optionally bound to a default KB.
   Typical use: while coding elsewhere, save a pin/task/note or search Alcove
   without installing heavy KB skills into that project.
   Intent model: no default project-local skill. Rely on MCP tool names,
   descriptions, and explicit user phrasing to keep the install light. Heavy
   connector import, mount scan, export, and gardener/admin tools are not
   exposed unless `--toolset full` is installed explicitly.

3. Managed KB profile
   Purpose: full workflow inside a specific managed KB directory.
   Install scope: the registered KB directory.
   Writes: CLAUDE.md, AGENTS.md, Claude slash commands, and project-local
   Claude/Codex skills.
   Typical use: inbox review, capture-to-inbox workflow, OKF Source/Concept
   creation, validation, gardener, and archive management.
   Intent model: install workflow skills that bias toward KB-scoped inbox and
   OKF operations. Global pins/prompts/projects/tasks remain available but are
   not the default destination for article/archive work.
```

Profile installation modes:

```text
copy mode
├── normal release/user mode
├── writes generated skills and commands as normal files
└── works with any configured Alcove Home

link mode
├── local Alcove development mode
├── symlinks Alcove-owned skills and Claude commands to source templates
├── supports both Claude Code and Codex targets
├── Claude Code: .claude/skills/* and .claude/commands/*
├── Codex: .agents/skills/*
└── keeps AGENTS.md, CLAUDE.md, and .alcove-hub.yml as normal files
```

`AGENTS.md` and `CLAUDE.md` are not symlinked because they may contain
workspace-owned context outside the Alcove marked section. Alcove owns only its
marked section in those files.

Routing defaults:

```text
Hub
├── copied source / article / archive / discussion note -> managed KB
├── tiny durable reference / command / preference       -> pin
│   ├── explicit new reference                          -> new regular pin
│   └── "收藏" / "常用收藏" / "置顶收藏" wording          -> update matching collection pin first
├── reusable instruction or agent prompt                -> prompt
├── local project path shortcut                         -> project
├── todo / reminder / recurring work                    -> task / idea / routine
├── read-only folder or historical repo                 -> mount
├── exported/protocol source                            -> connector
└── broad recall                                        -> search first

For collection pins, preserve the user's purpose and future-use context with
the link. A save that keeps only the bare URL is incomplete when the user
supplied why the item is worth keeping. Verification should check the entry
point the user will read, such as `常用收藏.md`, not only standalone pin search
results.

Global-lite
└── MCP-only access from unrelated projects; no local skill files by default

Managed KB
├── raw link                                            -> Clipsmith capture to inbox
├── pending inbox item                                  -> peek, then explicit user action
├── archive / note / delete / todo                      -> requires current-item confirmation
└── article summaries                                   -> KB Source/Concept, not Prompt
```

```text
alcove home init                                   initialize default ~/.alcove
alcove kb add/list                                 managed KB registry
alcove kb install <kb>                             install managed KB entry files
alcove kb install <kb> --link                      symlink KB skills/commands for development
alcove kb install <kb> --status                    inspect managed KB entry files
alcove hub init <path> --default-kb <kb>           create a hub workspace
alcove hub install <path>                          refresh hub entry files
alcove hub install <path> --link                   symlink Hub skills for development
alcove hub init <path> --status                    inspect hub entry files
alcove global install                              install global-lite MCP
alcove global install --default-kb <kb>            allow lite MCP manual-add into KB
alcove global install --toolset full               install full MCP intentionally
alcove global install --status                     inspect global-lite MCP

alcove inbox --kb <kb> ...                         managed KB via registry
alcove inbox --kb <kb> manual-add ...              manual draft into KB inbox
alcove knowledge --kb <kb> ...                     managed KB OKF writes
alcove knowledge --kb <kb> revise <path>           structured revision of an OKF note

alcove pin ...                                     global pins
alcove idea ...                                    global low-friction ideas
alcove task ...                                    global tasks/routines

alcove mount ...                                   global mounted KB indexes
alcove mount scan <mount-id>                       incremental external folder index refresh
alcove connector ...                               global connector KB indexes
alcove connector fetch <item-path>                 lazy-fetch connector detail after a hit
alcove link --kb <kb> source ...                   promote external item to managed KB Source

alcove search ...                                  global search
alcove search --kb <kb> ...                        registry-routed KB search
alcove export global <output-dir>                  export Alcove-owned global data
alcove export kb <kb> <output-dir>                 export one registered managed KB
alcove export all <output-dir>                     export global state and all registered KBs
```

Every command accepts `--home <path>` when a non-default Alcove Home is needed.
Legacy `--workspace <kb-root>` remains supported for compatibility.

MCP follows the same split. Global-aware tools accept `home` and do not require
a workspace:

```text
alcove_search(home=...)
alcove_pin_add(home=...)
alcove_pin_list(home=...)
alcove_pin_archive(home=...)
alcove_idea_add(home=...)
alcove_idea_list(home=...)
alcove_idea_promote(home=...)
alcove_task_add(home=...)
alcove_task_list(home=...)
alcove_task_complete(home=...)
alcove_task_cancel(home=...)
alcove_routine_add(home=...)
alcove_routine_list(home=...)
alcove_routine_materialize_due(home=...)
alcove_mount_add(home=...)
alcove_mount_list(home=...)
alcove_mount_scan(home=...)
alcove_connector_fetch(home=...)
alcove_connector_apple_notes_index(home=...)
alcove_connector_apple_notes_import_local(home=...)
alcove_connector_github_stars_index(home=...)
alcove_connector_github_stars_import_url(home=...)
alcove_connector_chrome_bookmarks_index(home=...)
alcove_connector_chrome_bookmarks_import_local(home=...)
alcove_export_global(home=...)
alcove_export_kb(home=...)
alcove_export_all(home=...)
```

MCP tools that write or inspect managed KB content still require a workspace:

```text
alcove_inbox_peek(workspace=...)                   or server default --kb
alcove_inbox_read(workspace=...)
alcove_inbox_manual_add(workspace=...)
alcove_inbox_archive(workspace=...)
alcove_inbox_note(workspace=...)
alcove_inbox_todo(workspace=...)
alcove_inbox_delete(workspace=...)
alcove_note_source(workspace=...)
alcove_knowledge_add_note(workspace=...)
alcove_knowledge_revise(workspace=...)
alcove_knowledge_add_question(workspace=...)
alcove_knowledge_add_entity(workspace=...)
alcove_knowledge_promote(workspace=...)
alcove_knowledge_refresh(workspace=...)
alcove_knowledge_topics(workspace=...)
alcove_get_topic(workspace=...)
alcove_link_source(workspace=...)
alcove_doctor(workspace=...)
alcove_validate(workspace=...)
alcove_gardener(workspace=...)
```

MCP toolsets:

```text
lite
├── search
├── pins
├── prompts save/search/get
├── tasks and ideas
└── inbox manual-add when a default KB is configured

kb
├── search and common memory tools
├── inbox review and mutation
├── OKF knowledge writes/revisions
├── link source
└── doctor/validate

full
└── every MCP tool, including projects, routines, mounts, connectors, export,
    gardener, and admin refresh/index operations
```

The preferred MCP server config for a default KB is now registry based:

```text
alcove serve --mcp --toolset kb --kb research_notes
```

The preferred MCP server config for global-lite is:

```text
alcove serve --mcp --toolset lite --home ~/.alcove
```

## Export and Backup

Alcove-owned global data should be exportable independently from managed KB data.

Implemented export shapes:

```text
alcove export --home <home> global <output-dir>
  -> pins/
  -> tasks/
  -> mounts/
  -> connectors/
  -> knowledge-bases registry
  -> config.yml
  -> manifest.json

alcove export --home <home> kb research_notes <output-dir>
  -> .alcove/config.yml
  -> knowledge/
  -> inbox/
  -> archive/
  -> todo/
  -> manifest.json

alcove export --home <home> all <output-dir>
  -> global export
  -> all registered managed KB exports
  -> manifest.json
```

Export should preserve plain Markdown/JSON/YAML wherever possible.

## Current Implementation Status

Current implementation is aligned with the core model and remains backward
compatible with the original single-workspace layout.

```text
Implemented
├── AlcoveHome global state under ~/.alcove or ALCOVE_HOME
├── Managed KB registry under ~/.alcove/knowledge-bases/
├── Managed KB mechanics for one workspace
├── OKF knowledge writes
├── inbox/archive/note/todo/delete/manual-add
├── unified search over workspace + global home
├── validation and doctor
├── MCP server and installer
├── Clipsmith integration through inbox
├── global pins under ~/.alcove/pins/
├── global project aliases under ~/.alcove/projects/
├── global prompt memory under ~/.alcove/prompts/
├── global tasks/ideas/routines under ~/.alcove/tasks/tasks.json
├── global mounts under ~/.alcove/mounts/
├── incremental mount scan reuse for unchanged files
├── global Apple Notes / GitHub Stars connector indexes
├── connector lazy-fetch contract
├── global, KB, and all export commands
├── registry-routed --kb CLI usage
├── hub workspace profile install
├── global-lite MCP install
├── managed KB profile install with inbox/social-post workflow wrappers
├── MCP coverage for the core CLI workflows
└── AlcoveApplication facade narrowed to six capability groups
```

Legacy workspace layout remains readable and writable for compatibility:

```text
<workspace>/
├── .alcove/config.yml
├── knowledge/
├── inbox/
├── archive/
├── todo/
├── pins/
├── tasks/tasks.json
├── mounts/
└── .alcove/connectors/
```

## Migration Direction

The migration has been implemented incrementally and backward compatibly:

```text
1. Introduce AlcoveHome                                  done
   -> default ~/.alcove
   -> configurable with ALCOVE_HOME

2. Add managed KB registry                               done
   -> ~/.alcove/knowledge-bases/<name>.yml
   -> register existing research_notes

3. Move global features for new global usage              done
   -> pins under ~/.alcove/pins
   -> tasks under ~/.alcove/tasks

4. Move external indexes for new global usage             done
   -> mounts under ~/.alcove/mounts
   -> connectors under ~/.alcove/connectors

5. Add scoped CLI/MCP                                     done
   -> --kb for managed KB operations
   -> --home only when using a non-default Home
   -> legacy --workspace remains available

6. Add manual inbox and exports                           done
   -> inbox manual-add
   -> export global
   -> export kb
   -> export all

7. Add efficient external index workflows                 done
   -> mount incremental scan reuse
   -> connector fetch
   -> broader MCP coverage
   -> smaller application facade
```

## Safety Rules

- Managed KB destructive operations require explicit confirmation.
- Inbox processing should only happen after user intent for that item or an explicit batch instruction.
- `archive/` and `knowledge/` are tracked data, not disposable cache.
- Global pins and tasks are user data and must be easy to export.
- Mounts and connectors are indexes over external sources, not owners of the external source.
- Linking an external result into a managed KB should create an OKF `Source` with provenance back to the mount/connector item.
- Generated indexes should be rebuildable from canonical Markdown/JSON/YAML source data.
- User-data backup/sync is recommended through Git, preferably automated with
  git-auto-sync and encrypted with git-crypt when private or sensitive data is
  pushed to a remote.

## Verification

Current implemented test suite:

```sh
uv run pytest -q
```

At the time this document was last updated, the suite passed with:

```text
180 passed
```

For a real managed KB workspace:

```sh
alcove doctor --kb research_notes --json
alcove validate --kb research_notes --json
```
