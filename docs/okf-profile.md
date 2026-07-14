# Alcove OKF Profile

Alcove uses the official Open Knowledge Format (OKF) as its portable knowledge
file surface, then adds a stricter product profile for reliable writes,
retrieval, indexing, and external integration.

Official references:

- Open Knowledge Format v0.1 draft:
  <https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md>
- Google Cloud introduction:
  <https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing>

## Relationship to Official OKF

Official OKF is intentionally minimal:

- a knowledge bundle is a directory tree of UTF-8 Markdown files,
- every non-reserved `.md` file is a concept document,
- concept documents have YAML frontmatter plus Markdown body,
- only `type` is required by the spec,
- `title`, `description`, `resource`, `tags`, and `timestamp` are recommended,
- `index.md` and `log.md` are reserved filenames,
- consumers must tolerate unknown types, unknown fields, broken links, missing
  optional fields, and missing indexes.

Alcove keeps that compatibility boundary. The stricter rules below are an
Alcove producer profile, not a replacement for official OKF.

```text
Official OKF v0.1
└── Alcove OKF Profile v0.1
    ├── strict write contracts
    ├── module-specific document types
    ├── source-of-truth vs derived-index rules
    ├── global catalog conventions
    └── validation, refresh, and delete behavior
```

## Conformance Levels

Alcove uses three levels so external systems can consume data without adopting
all Alcove internals.

```text
OKF-compatible
  Every concept Markdown file has parseable frontmatter and non-empty type.

Alcove-readable
  Documents include enough common metadata for search and previews:
  title or question, description or summary, tags, status, timestamp or
  updated_at, and stable relative path.

Alcove-governed
  Documents are written by Alcove CLI/MCP and satisfy the module-specific schema,
  provenance, index, lifecycle, validation, activity, and delete contracts.
```

Consumers should read all three levels best-effort. Writers inside Alcove should
target `Alcove-governed` unless explicitly exporting a loose OKF bundle.

## Common Frontmatter

All Alcove-generated concept Markdown should prefer these fields:

```yaml
---
type: Source
schema: alcove/source/v1
title: Example
description: One-sentence search and preview summary.
resource: https://example.com/source
tags:
  - example
status: active
timestamp: "2026-07-11T12:00:00+08:00"
created_at: "2026-07-11T12:00:00+08:00"
updated_at: "2026-07-11T12:00:00+08:00"
---
```

Field meanings:

- `type`: official OKF routing field. Required and never empty.
- `schema`: Alcove profile identifier. Use it for strict validation and
  migrations; tolerate unknown schema values when reading.
- `title`: human display name. For `Question`, `question` may be the primary
  display field.
- `description`: short preview. If a module currently uses `summary`, search
  should treat it as equivalent.
- `resource`: external URI, bundle-relative ref, connector ref, mount ref, or
  empty for abstract concepts.
- `tags`: cross-cutting labels. Prefer stable lowercase slugs where practical,
  but preserve user-language tags.
- `status`: lifecycle state such as `active`, `needs-review`, `archived`,
  `stale`, or `deleted`.
- `timestamp`: official OKF last meaningful change time.
- `created_at` / `updated_at`: Alcove lifecycle timestamps.

Readers must preserve unknown fields during repair or migration.

## Document Types

Managed KB knowledge:

```text
Source              provenance, raw evidence summary, or external reference
Knowledge Concept   durable synthesized knowledge note
Question            reusable question and stable answer
Entity              tool, project, person, organization, system, or object
Domain              generated or managed domain index
Topic               generated or managed topic index
Tag                 generated or managed tag index
```

Global memory:

```text
Pin                 stable reference or future-practice pinned note
Prompt              reusable global prompt memory
Project             local project alias
Task                concrete todo item
Idea                possible future work or investigation
Routine             recurring task template
```

External indexes:

```text
Mount Index         derived overview for a mounted folder
Mounted Item        derived mirror of a mounted file
Connector Index     derived overview for a connector
Connector Source    derived connector source and refresh status
Connector Item      derived mirror of an external item
```

The official OKF spec does not define these types. They are Alcove profile
types, so external consumers must treat unknown ones as generic concepts.

## Body Sections

Official OKF does not require body sections, but Alcove writers should use
structured Markdown to improve retrieval.

Recommended sections:

```text
# <Title>
## Summary / 摘要
## Key Points / 要点
## My Judgment / 我的判断
## Relationships / 关系
## Source / 来源
## Citations
## Revision Log / 修订记录
```

Use bundle-relative links for internal OKF refs where possible. Use external
URLs only for source citations or resources that live outside Alcove.

## Source of Truth

Alcove separates durable state from derived OKF mirrors.

```text
Managed KB
  source of truth: <kb>/knowledge/*.md, inbox/, archive/, todo/
  derived: generated domain/topic/tag/index/log files

Pins
  source of truth: ~/.alcove/pins/*.md
  derived: index.json, index.md, board.html

Prompts
  source of truth: ~/.alcove/prompts/*.md
  derived: index.json

Tasks, Ideas, Routines
  source of truth: ~/.alcove/tasks/tasks.json
  derived: future OKF catalog entries or dashboard/search indexes

Projects
  source of truth: ~/.alcove/projects/projects.json
  derived: future OKF catalog entries or dashboard/search indexes

Mounts
  source of truth: external folder plus ~/.alcove/mounts/indexes/*.json
  derived: ~/.alcove/mounts/okf/

Connectors
  source of truth: external system/export plus ~/.alcove/connectors/<id>/index.json
  derived: ~/.alcove/connectors/<id>/okf/

Dashboard and usage
  source of truth: module state and local event logs
  derived: ~/.alcove/dashboard/, ~/.alcove/stats/
```

Rule: derived OKF is agent-readable cache, not an authority. Agents should not
manually edit derived OKF. Regenerate it through the relevant Alcove command.

## Write Contract

Alcove writes should be narrow and governed:

```text
search for existing records
-> choose the target module
-> mutate through CLI/MCP
-> update source of truth
-> rebuild affected JSON/OKF indexes
-> update activity and usage logs
-> validate or expose a repair command
```

Module write expectations:

- Managed KB writes create or revise `Source`, `Knowledge Concept`, `Question`,
  or `Entity` documents and refresh knowledge indexes.
- Inbox capture writes only pending input until the user confirms archive,
  note, todo, delete, or direct knowledge creation.
- Pins and prompts are Markdown source of truth and rebuild their search index.
- Tasks, ideas, routines, and projects currently write JSON source of truth and
  participate in global search and dashboard indexes.
- Mount scans update JSON rows and derived OKF mirrors; stale files are removed.
- Mount scans apply the per-mount index policy before writing JSON rows or
  derived OKF mirrors. The resolved policy is recorded on the `Mount Index`
  document so agents know whether the mount is docs-, notes-, site-, raw-, or
  capture-bundle-oriented.
- Connector refresh/import updates source registries, JSON rows, derived OKF
  mirrors, freshness status, and stale/deleted rows.

Direct file edits are repair fallbacks. After direct edits, run the nearest
validation or rebuild command.

## Health Checks

`alcove health` is the cross-module data and OKF consistency gate. It checks the
source-of-truth files and the derived indexes together:

```sh
alcove health --home ~/.alcove --json
alcove health --home ~/.alcove --kb social_media_posts --strict --json
alcove health --home ~/.alcove --kb social_media_posts --fix --json
alcove health --home ~/.alcove --fix --deep --json
```

Coverage:

- managed KB paths and OKF validation issues,
- registered managed KBs under `~/.alcove/knowledge-bases/*.yml`,
- pin and prompt Markdown frontmatter plus JSON index counts,
- task and project JSON stores,
- mount JSON indexes plus derived `~/.alcove/mounts/okf/` item counts,
- connector JSON indexes plus derived `~/.alcove/connectors/<id>/okf/` item
  counts,
- global OKF catalog files under `~/.alcove/okf/`,
- dashboard snapshot shape when a snapshot exists,
- publisher definitions/runs,
- radar definitions/runs,
- watcher and blog-monitor source configs/runs,
- automation job configs/runs,
- usage stats rollups when present.

Default mode is read-only. `--fix` only performs safe local repairs: it fills
missing `schema` metadata for recognized managed-KB OKF documents, then rebuilds
safe derived data such as the pin index, prompt index, and global OKF catalog.
It does not refresh network connectors, export Apple Notes, rescan mounts, or
rewrite managed KB note bodies.

`--fix --deep` is a local full-maintenance pass. It additionally rescans mounts,
refreshes usage rollups, rebuilds the dashboard snapshot, and rebuilds the
global OKF catalog after those derived views are current. Connector refresh is
still explicit: use `--refresh-stale-connectors` or `--refresh-all-connectors`
when external-source refresh is intended.

Individual repair commands remain available:

```sh
alcove mount scan <mount-id> --json
alcove connector refresh --stale --json
alcove pin rebuild-index --json
alcove prompt rebuild-index --json
alcove okf --home ~/.alcove catalog build --json
```

Agents should run health after direct repair edits, after index/catalog changes,
and when a user asks whether Alcove data is still coherent. Write tools should
surface the nearest validation, rebuild, or health command when they detect
stale or malformed data.

## Query Contract

Alcove reads are broad and AI-led. Search returns candidates, not final truth.

```text
alcove search / alcove_search
-> inspect module-local OKF indexes
-> read candidate records
-> follow source_refs, connector fetch refs, mount refs, and archive provenance
-> use shell search, file reads, and model reasoning as useful
-> synthesize from the specific local evidence found
```

The profile exists to make that investigation reliable. Required metadata,
stable paths, index pages, source refs, and fetch refs reduce query ambiguity
without forcing every read through a single rigid search API.

See [read-write-model.md](read-write-model.md) for the full operating model.

## Global OKF Catalog

Alcove exposes a derived global catalog under `~/.alcove/okf/`.

```text
~/.alcove/okf/
├── index.md                         global progressive-disclosure entry
├── log.md                           generated catalog update log
├── managed-kbs.md                   registered managed KBs
├── global-memory.md                 pins, prompts, tasks, projects overview
├── external-indexes.md              mounts and connectors overview
├── search-map.md                    agent retrieval routing guide
└── modules/
    ├── pins.md
    ├── prompts.md
    ├── tasks.md
    ├── projects.md
    ├── mounts.md
    └── connectors.md
```

This catalog is derived, not authoritative. Its purpose is to give external
agents and simple file readers a stable OKF-compatible entry point across
modules.

Rebuild it through the governed derived-index path:

```sh
alcove okf --home ~/.alcove catalog build --json
alcove okf --home ~/.alcove catalog build --include-all-status --json
```

The default catalog lists active working records for the main read path. Use
`--include-all-status` for audit and cleanup flows where archived, deleted, or
otherwise inactive records must remain visible.

MCP exposes the same operation as `alcove_okf_catalog_build`.

If the global catalog is absent or partially generated, readers should fall back
to `alcove search`, managed KB `index.md` files, mount/connector OKF indexes,
and module-local registries. Writers should still use CLI/MCP mutation commands
so the catalog can be regenerated later without losing provenance.

## Index and Refresh Contract

Every index-producing module should follow the same lifecycle:

```text
full rebuild
  read source of truth
  write JSON/search index
  write derived OKF index
  delete stale derived rows
  update global catalog

incremental refresh
  detect added/updated/removed records
  reuse unchanged rows
  sync JSON/search index
  sync derived OKF index
  update source freshness and catalog status

delete/archive
  update source lifecycle state
  remove or mark stale search rows
  remove stale derived OKF mirrors
  update global catalog
```

Recommended change keys:

```text
Managed KB: relative path + frontmatter updated_at + content hash
Pins/Prompts: Markdown path + frontmatter schema + updated_at/hash
Tasks/Ideas/Routines: record id + updated_at + status
Projects: alias + path + updated_at
Mounts: mount id + relative path + size + mtime + resolved index policy + optional content hash
Connectors: connector id + source id + external item id + updated_at/hash
```

## External Consumption

External systems should be able to consume Alcove data at two levels:

- Generic OKF consumers can read Markdown files, frontmatter, links, indexes,
  and logs without knowing Alcove-specific schemas.
- Alcove-aware consumers can use `schema`, `source_refs`, `fetch_ref`,
  `connector_id`, `mount_id`, `status`, and module paths for richer workflows.

Alcove should not require external consumers to run Python code, start MCP, or
understand private JSON caches just to read exported knowledge.

## Validation Rules

Validation should distinguish hard errors from warnings.

Hard errors for Alcove-governed writes:

- missing or empty `type`,
- missing required profile fields for the document type,
- invalid YAML frontmatter,
- source-of-truth and derived index mismatch after a rebuild,
- stale derived rows that still appear in search.

Warnings:

- missing official OKF recommended fields such as `description` or `timestamp`,
- broken links,
- unknown type or schema,
- missing `index.md`,
- missing citations for low-confidence claims,
- low-information connector items.

This preserves official OKF's permissive consumption model while keeping Alcove
writes strict enough for reliable personal knowledge management.
