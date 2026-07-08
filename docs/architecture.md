# Alcove Architecture and Feature Overview

Alcove is a local-first personal information system. The product model is intentionally small:

```text
Alcove
├── 1. Knowledge Bases / 知识库体系
├── 2. Pins / 置顶收藏功能
└── 3. Tasks / 任务事务功能
```

This document records the target relationship model and compares it with the current implementation.

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
social_media_posts
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
Current local managed KB: ~/programming/kingson4wu/entropy-nexus/social_media_posts
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

Capture adapters are pluggable. Clipsmith is the current default adapter, but the knowledge base should only depend on the inbox contract, not on Clipsmith internals.

```text
Clipsmith / custom collector
  -> capture bundle
  -> <managed-kb-root>/inbox/<platform>/<capture-id>/
```

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
```

Cardinality and storage:

```text
Alcove -> Mounted Knowledge Base: 1-to-many
Data location: Alcove global state, pointing to external read-only directories
Current global implementation: ~/.alcove/mounts/
Legacy workspace-compatible implementation: <workspace>/mounts/
Main formats: JSON registry + JSON index
```

Mounted KB rules:

- Do not copy all external files into a managed KB.
- Do not force external folders into OKF structure.
- Build lightweight searchable indexes.
- Support full rebuild and future incremental refresh.
- Search results can be linked into a managed KB as OKF `Source` when they become important.

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
│   └── index.json                                 indexed notes metadata/search text
├── github-stars/
│   ├── config.yml
│   └── index.json                                 indexed starred repositories
└── <connector-id>/
    ├── config.yml
    └── index.json
```

Cardinality and storage:

```text
Alcove -> Connector Knowledge Base: 1-to-many
Data location: Alcove global state, pointing to protocol/export/API data
Current global implementation: ~/.alcove/connectors/<connector-id>/index.json
Legacy workspace-compatible implementation: <workspace>/.alcove/connectors/<connector-id>/index.json
Main formats: connector config + JSON index
```

Connector rules:

- Connector indexes belong in Alcove global state, not inside one managed KB.
- A connector index is not the source of truth; the external system/export remains the source.
- Index only key metadata and searchable text by default.
- Future connectors may lazy-fetch full detail after a search hit.
- Search results can be linked into one or more managed KBs as OKF `Source`.

Promotion flow:

```text
external system / export
  -> ~/.alcove/connectors/<connector-id>/index.json
  -> unified search hit
  -> user chooses to keep it
  -> <managed-kb>/knowledge/sources/<connector>/<domain>/*.md
```

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
└── <pin-id>.md                                    Markdown + YAML frontmatter
```

Example format:

```markdown
---
type: Pin
title: Japanese Edge Launcher
description: Launch Edge with TZ=Asia/Tokyo.
tags:
  - app-launcher
priority: medium
status: active
source_refs: []
created_at: "2026-07-08T00:00:00+00:00"
updated_at: "2026-07-08T00:00:00+00:00"
---

# Japanese Edge Launcher

Launch Edge with `TZ=Asia/Tokyo`.
```

Cardinality and storage:

```text
Alcove -> Pins: 1-to-1 global feature
Data location: ~/.alcove/pins/
Legacy workspace-compatible location: <workspace>/pins/
Main format: Markdown + YAML frontmatter
```

Pins should not require selecting a managed KB. They should be globally searchable and available through MCP.

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

## Global State

The implemented state split is:

```text
~/.alcove/                                         Alcove home, 1-to-1 per user
├── config.yml                                     global config
├── knowledge-bases/                               managed KB registry
│   └── social_media_posts.yml                     points to real KB directory
├── pins/                                          global pins
├── tasks/                                         global tasks
├── mounts/                                        external folder/repo indexes
│   ├── mounts.json
│   └── indexes/<mount-id>.json
└── connectors/                                    external protocol/source indexes
    └── <connector-id>/
        ├── config.yml
        └── index.json

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
alcove search "query" --workspace /path/to/social_media_posts
alcove search "query" --kb social_media_posts
alcove search "query" --type Pin
alcove search "query" --type Task
alcove search "query" --type "Mounted Item"
alcove search "query" --platform github-stars
```

Result roots make provenance obvious:

```text
knowledge -> managed KB OKF Markdown
pins -> ~/.alcove/pins/
tasks -> ~/.alcove/tasks/tasks.json
mounts -> ~/.alcove/mounts/indexes/
connectors -> ~/.alcove/connectors/<connector-id>/index.json
```

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
   pins, tasks, mounts, connectors, and multiple managed KBs from one place.

2. Global-lite profile
   Purpose: lightweight access from any unrelated project.
   Install scope: global agent MCP config only.
   Writes: MCP server config pointing at ~/.alcove; no project files.
   Typical use: while coding elsewhere, save a pin/task/note or search Alcove
   without installing heavy KB skills into that project.

3. Managed KB profile
   Purpose: full workflow inside a specific managed KB directory.
   Install scope: the registered KB directory.
   Writes: CLAUDE.md, AGENTS.md, project-local Alcove KB skills.
   Typical use: inbox review, capture-to-inbox workflow, OKF Source/Concept
   creation, validation, gardener, and archive management.
```

```text
alcove home init                                   initialize default ~/.alcove
alcove kb add/list                                 managed KB registry
alcove kb install <kb>                             install managed KB entry files
alcove hub init <path> --default-kb <kb>           create a hub workspace
alcove hub install <path>                          refresh hub entry files
alcove global install                              install global-lite MCP

alcove inbox --kb <kb> ...                         managed KB via registry
alcove inbox --kb <kb> manual-add ...              manual draft into KB inbox
alcove knowledge --kb <kb> ...                     managed KB OKF writes

alcove pin ...                                     global pins
alcove idea ...                                    global low-friction ideas
alcove task ...                                    global tasks/routines

alcove mount ...                                   global mounted KB indexes
alcove connector ...                               global connector KB indexes
alcove link --kb <kb> source ...                   promote external item to managed KB Source

alcove search ...                                  global search
alcove search --kb <kb> ...                        registry-routed KB search
alcove export global <output-dir>                  export Alcove-owned global data
```

Every command accepts `--home <path>` when a non-default Alcove Home is needed.
Legacy `--workspace <kb-root>` remains supported for compatibility.

MCP follows the same split. Current global-aware tools accept `home` and do not
require a workspace:

```text
alcove_search(home=...)
alcove_pin_add(home=...)
alcove_task_add(home=...)
alcove_task_list(home=...)
alcove_mount_list(home=...)
```

MCP tools that write or inspect managed KB content still require a workspace:

```text
alcove_inbox_peek(workspace=...)                   or server default --kb
alcove_note_source(workspace=...)
alcove_get_topic(workspace=...)
alcove_link_source(workspace=...)
alcove_gardener(workspace=...)
```

The preferred MCP server config for a default KB is now registry based:

```text
alcove serve --mcp --kb social_media_posts
```

The preferred MCP server config for global-lite is:

```text
alcove serve --mcp
```

## Export and Backup

Alcove-owned global data should be exportable independently from managed KB data.

Implemented export shape:

```text
alcove export --home <home> global <output-dir>
  -> pins/
  -> tasks/
  -> mounts/
  -> connectors/
  -> knowledge-bases registry
  -> config.yml
  -> manifest.json
```

Planned export shapes:

```text
alcove export kb social_media_posts
  -> knowledge/
  -> inbox/
  -> archive/
  -> todo/

alcove export all
  -> global export
  -> selected or all managed KB exports
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
├── global tasks/ideas/routines under ~/.alcove/tasks/tasks.json
├── global mounts under ~/.alcove/mounts/
├── global Apple Notes / GitHub Stars connector indexes
├── global export command
├── registry-routed --kb CLI usage
├── hub workspace profile install
├── global-lite MCP install
└── managed KB profile install

Still planned
├── no connector lazy-fetch contract yet
├── no mount incremental indexing yet
├── no KB/all export command yet
└── MCP coverage for every CLI operation is not complete yet
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
   -> register existing social_media_posts

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

6. Add manual inbox and global export                     done
   -> inbox manual-add
   -> export global
```

## Safety Rules

- Managed KB destructive operations require explicit confirmation.
- Inbox processing should only happen after user intent for that item or an explicit batch instruction.
- `archive/` and `knowledge/` are tracked data, not disposable cache.
- Global pins and tasks are user data and must be easy to export.
- Mounts and connectors are indexes over external sources, not owners of the external source.
- Linking an external result into a managed KB should create an OKF `Source` with provenance back to the mount/connector item.
- Generated indexes should be rebuildable from canonical Markdown/JSON/YAML source data.

## Verification

Current implemented test suite:

```sh
uv run pytest -q
```

At the time this document was last updated, the suite passed with:

```text
160 passed
```

For a real managed KB workspace:

```sh
alcove doctor --kb social_media_posts --json
alcove validate --kb social_media_posts --json
```
