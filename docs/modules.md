# Alcove Modules

This document summarizes Alcove's feature modules and their storage contracts.

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

## Prompts

Prompts are reusable global memory records stored as OKF-compatible Markdown
under `~/.alcove/prompts/`. Each prompt uses YAML frontmatter with
`type: Prompt`, tags, use cases, source refs, and an active/archive status.
Markdown files are the source of truth; `~/.alcove/prompts/index.json` is a
derived search index rebuilt automatically by save/archive/search flows.

## Tasks, Ideas, and Routines

Ideas, tasks, and routines are stored in `~/.alcove/tasks/tasks.json`.
Active ideas and pending tasks participate in global search when `--home` is
provided. Routines materialize only when `task materialize-due` or the matching
MCP tool is called.

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
