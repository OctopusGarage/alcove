# Alcove Read/Write Operating Model

Alcove intentionally separates read operations from write operations.

```text
Read path  -> broad, AI-led investigation over structured local memory
Write path -> narrow, CLI/MCP-governed mutations through Alcove contracts
```

This model exists because personal knowledge work has two different risk
profiles:

- Reads benefit from flexible exploration, query expansion, local file
  inspection, comparison, and synthesis.
- Writes need strict contracts so durable data, indexes, provenance, lifecycle
  state, activity logs, and search behavior stay consistent.

## Read Path

Search is candidate discovery, not final truth.

```text
user question
-> alcove search / MCP alcove_search
-> candidate rows across managed KBs, pins, prompts, tasks, projects, mounts, connectors
-> inspect the concrete local evidence
-> synthesize an answer with cited records
```

Agents should continue beyond search results when the question is broad,
ambiguous, cross-topic, low-confidence, or asks for synthesis:

```text
inspect OKF index.md files
inspect the global OKF catalog under ~/.alcove/okf
inspect domain/topic/tag pages
read Knowledge Concept and Source records
follow source_refs and archive provenance
follow connector fetch refs
follow mount refs into local files
read full pins, prompts, tasks, and project records
use shell search and file reads when useful
compare conflicting records
explain uncertainty and missing evidence
```

The read path is deliberately not limited to grep. Grep, ripgrep, file reads,
MCP search, connector fetch, and model reasoning are all valid investigation
tools. The rule is that the final answer should be grounded in the specific
local records inspected, not in the search result list alone.

## Write Path

Writes are governed operations. Agents should mutate Alcove data through CLI or
MCP commands.

```text
user intent
-> search/list existing records
-> choose the target module
-> call the matching CLI/MCP mutation
-> update source of truth
-> refresh indexes/catalogs
-> validate when needed
```

Examples:

```text
save copied article or AI discussion
  -> inbox manual-add or knowledge add/revise

process current inbox item
  -> archive / note / todo / delete after explicit confirmation

remove an outdated managed-KB post found through search
  -> inspect search result fields: published_at, collected_at, updated_at, status, path
  -> run knowledge delete <path> without --confirm for preview
  -> rerun with --confirm only after the user confirms that specific result
  -> mark the Source as deleted, hide it from default search, update related source_refs,
     and rebuild managed-KB indexes

save stable reference or repeated lookup
  -> pin add/update

save future practice idea
  -> pin kind=todo, idea add, or task add depending on intent

save reusable instruction
  -> prompt save

track work
  -> task / idea / routine commands

add external folder
  -> mount add + mount scan

refresh external source
  -> connector import/refresh

link important external result into a managed KB
  -> link source
```

CLI/MCP writes centralize:

- path and frontmatter conventions,
- OKF profile schema and validation,
- taxonomy/index maintenance,
- source refs and provenance,
- connector/mount stale row handling,
- activity and usage logs,
- dashboard/search index refreshes,
- user-confirmation boundaries for inbox mutation.

Application mutation payloads include a `write_contract` object:

```text
write_contract
├── area                   inbox / knowledge / pin / prompt / task / mount / connector
├── action                 exact governed mutation name
├── target                 user-facing id/path/title for the changed record
├── governed_by            normally "alcove CLI/MCP"
├── source_of_truth        source data area that was changed
├── confirmation_required  whether the payload is a preview or needs explicit user confirmation
└── post_write_checks      validation/rebuild commands useful after manual repair or follow-up
```

This contract is intentionally returned by the application seam, so CLI, MCP,
skills, dashboard diagnostics, and future agents can reason about writes
without reverse-engineering each module's internal files.

## Entry Mode Mapping

The read/write split is enforced differently by each entry mode:

```text
Hub workspace
  -> strong local skill routes intent before writing
  -> CLI is the default durable write surface
  -> optional full MCP only when explicitly needed

Global MCP
  -> lite toolset by default
  -> search, pins, prompts, tasks, ideas, and optional KB manual-add
  -> no connector imports, mount scans, export, gardener, or admin refresh by default

Managed KB workspace
  -> KB-local skills bias toward inbox and OKF operations
  -> raw links capture to inbox
  -> archive/note/todo/delete require explicit current-item confirmation
```

This keeps unrelated projects from seeing the full Alcove admin surface while
still allowing low-friction memory writes. Use `--toolset full` only for a hub
or administrative session where broad control is intentional.

The entry-mode defaults are code-level policy, not only documentation:

```text
src/alcove/entry_policy.py
├── hub         -> default MCP toolset: full
├── global      -> default MCP toolset: lite
├── managed-kb  -> default MCP toolset: kb
└── service     -> no MCP toolset; deterministic background work
```

`src/alcove/mcp_toolsets.py` resolves aliases such as `global-lite`,
`knowledge-base`, and `hub-full` through that policy. This keeps installer,
MCP, and agent-entry defaults from drifting.

## Read Result Contract

Search rows are a candidate interface shared by CLI, MCP, dashboard, and agent
skills. Every row should expose stable evidence fields:

```text
path             row-local canonical path
title            display title, never a raw full local path when avoidable
type             semantic type
status           lifecycle status
published_at     source publication time when known
collected_at     Alcove ingestion/index time when known
updated_at       latest known update time
notes            preview text, redacted when needed
```

External index rows also expose a unified read reference:

```text
source_ref       stable external source reference
read_ref         reference agents can follow for detail
read_command     command when detail fetch is command-backed
read_hint        short instruction for how to inspect the evidence
```

For connectors, `read_ref` normally equals `fetch_ref` and `read_command` is
`alcove connector fetch <fetch_ref> --json`. For mounts, `read_ref` is the
mount source reference such as `mounts/<id>#<relative-path>` and the agent may
inspect the mounted source file through the configured mount root.

## Direct File Edits

Direct file edits are repair fallbacks, not normal workflow.

They are acceptable only when:

- no CLI/MCP mutation exists for the needed repair,
- the target file is a source-of-truth file rather than a derived cache,
- the edit is narrow and preserves unknown frontmatter fields,
- the agent runs the nearest validation or rebuild command afterward.

Examples:

```text
managed KB repair
  -> edit source-of-truth Markdown
  -> alcove validate --kb <kb> --json

pin/prompt repair
  -> edit source-of-truth Markdown
  -> alcove pin rebuild-index --json
  -> alcove prompt rebuild-index --json

mount repair
  -> fix registry or external files
  -> alcove mount scan <mount-id> --json

connector repair
  -> fix source config/export
  -> alcove connector refresh --connector <connector-id> --json

dashboard repair
  -> alcove dashboard --home <home> build --json
```

Agents should not manually edit derived OKF mirrors, search indexes, dashboard
snapshots, stats rollups, or generated catalogs. Regenerate them.

## Scope Rules

Alcove has multiple entry contexts. The read/write model applies to all of them,
but default scope differs.

```text
Hub workspace
  read: home-wide by default
  write: route by intent to managed KB, pins, prompts, tasks, projects, mounts, connectors

Managed KB workspace
  read: current KB for "this KB" wording; home-wide for personal knowledge wording
  write: current KB for inbox/archive/knowledge, global home for pins/tasks/prompts/etc.

Unrelated project
  read: home-wide through lightweight MCP/global install
  write: governed global or KB command only when user intent is explicit
```

Chinese routing examples:

```text
当前知识库 / 这个知识库 / inbox / archive
  -> current managed KB scope

本地个人知识库 / 个人知识系统 / 全部资料 / OKF / 知识数据 / 汇总总结 / 查一下
  -> home-wide search across managed KBs, pins, tasks, prompts, projects, mounts, connectors

常用收藏 / 置顶收藏 / 以后反复查
  -> pins, after searching existing pins

以后找机会实践 / 深入了解 / TODO
  -> task, idea, or todo pin depending on whether it is actionable
```

## OKF Relationship

The read/write model and the OKF profile reinforce each other:

- The OKF profile defines stable files, metadata, indexes, source refs, and
  catalog conventions that make broad AI-led reads reliable.
- The write model requires CLI/MCP mutations so those OKF files and derived
  indexes remain consistent.

See [okf-profile.md](okf-profile.md) for the document and indexing profile.

## Invariants

These invariants should stay true across modules:

```text
Search returns candidates, not final answers.
AI may inspect local evidence broadly for read-only work.
Durable writes go through CLI/MCP unless repairing.
Derived indexes are regenerated, not hand-edited.
Source-of-truth locations are explicit per module.
Unknown OKF fields are preserved when round-tripping.
Delete/archive/refresh operations remove or mark stale search rows.
Global catalog/indexes are derived from module source-of-truth data.
```

If a future feature violates one of these invariants, it needs a documented
design decision before implementation.
