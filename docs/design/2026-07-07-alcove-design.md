# Alcove Design

Date: 2026-07-07

## Summary

Alcove is a local-first personal information core for knowledge, pins, tasks, mounted archives, and agent-readable memory. It lives at `~/programming/OctopusGarage/alcove`, exposes an `alcove` CLI, and is intended to run a local MCP server for Codex, Claude Code, Cursor, and similar agents in a later phase.

The first version should productize the existing `social_media_posts` knowledge workflow without turning Alcove into only a knowledge-base script. The architecture must leave clean room for personal pinned notes, task management, Apple Notes export, browser/bookmark sources, local folder mounts, GitHub repo mounts, and starred-repo indexes.

## Goals

- Extract the current OKF knowledge-management behavior from the `social_media_posts` project into a reusable standalone project.
- Preserve Markdown-first source-of-truth files so the user can inspect, edit, git-track, and migrate data without a database dependency.
- Provide one shared Python core used by both the CLI and MCP server.
- Start with a small set of high-leverage CLI commands and MCP tools rather than mirroring every internal helper.
- Support future personal information modules: Pins, Tasks, Mounts, and Connectors.
- Keep destructive operations explicit and previewable.

## Non-Goals

- Do not build a UI in the first version.
- Do not replace Obsidian, Apple Notes, or GitHub as original data stores.
- Do not make SQLite the source of truth; it is only an optional cache/index.
- Do not implement Apple Notes write operations in the first version.
- Do not implement launchd scheduling in the first version.
- Do not implement full GitHub API sync in the first version; local repo and star-index support can be introduced after Mounts are stable.

## References

### Current Knowledge Tool

The current knowledge workflow lives in:

- `social_media_posts/.claude/skills/social_post_manager/scripts/post_manager.py`
- `social_media_posts/.claude/skills/social_post_manager/scripts/okf_manager.py`
- `social_media_posts/.claude/skills/social_post_manager/scripts/notes_search.py`
- `social_media_posts/.claude/skills/social_post_manager/scripts/okf_gardener.py`

Important behaviors to preserve:

- Inbox scanning by platform and oldest-first `peek`.
- Platform-aware post reading order, especially XHS rich sidecars: `summary.md`, `ocr-merge.txt`, then `post.md`.
- Archive and note flows that create OKF `Source` and optional `Knowledge Concept`.
- Low-friction human judgment fields for selected takeaways, why, connection, action, and personal note.
- `Question` and `Entity` document types.
- Topic/domain/tag taxonomy.
- Knowledge health scan for duplicate concepts, dead source refs, stale content, taxonomy drift, missing Question/Entity backlog, and abandoned todos.

### CodeGraph

`~/programming/github/codegraph` is the product-shape reference, not the implementation stack reference.

Useful patterns:

- A standalone CLI with commands like `init`, `status`, `install`, and `serve --mcp`.
- Per-project local state directory.
- Installer that writes MCP config for multiple agent targets.
- MCP server exposing a small number of deep tools instead of many shallow helpers.
- Shared engine/core used by CLI and MCP rather than duplicating behavior.

Patterns not needed in Alcove v1:

- CodeGraph's static-analysis engine.
- Daemon, file watcher, and worker-thread query pool.
- Bundled Node runtime.

### Social Radar Tasks

`~/programming/kingson4wu/social-radar` provides the task-system reference.

Useful model:

- `IDEA`: low-friction capture, active or archived.
- `TASK`: concrete execution item, pending/done/cancelled.
- `ROUTINE`: recurring template that materializes tasks.
- Promotion from `IDEA` to `TASK` or `ROUTINE`.

For Alcove v1, adopt the object model but not the scheduler. Tasks are personal information objects first; scheduling can come later.

### Apple Notes Local Skill

`~/programming/kingson4wu/labali-skills/skills/private/labali-apple-notes-local` provides the Apple Notes connector reference.

Useful constraints:

- macOS-only.
- Deterministic JSON output.
- Stable note identity is Apple Notes note id, not title or folder path.
- Full export writes stable files under `notes/<encoded-note-id>/`.
- Destructive actions preview first.

For Alcove v1, Apple Notes is read-only/export-only.

## Product Shape

Project:

```text
~/programming/OctopusGarage/alcove
```

Names:

```text
display name: Alcove
CLI: alcove
MCP server: alcove
state dir: .alcove
Python package: alcove
```

Positioning:

> Alcove is a local-first personal knowledge alcove for notes, pins, tasks, archives, mounted sources, and agent-readable memory.

## Data Layout

Alcove should support project-local workspaces. A workspace is any directory initialized with `.alcove/config.yml`.

Recommended workspace layout:

```text
.alcove/
├── config.yml
├── index.sqlite
├── mounts.yml
├── connectors/
└── logs/

knowledge/
inbox/
archive/
pins/
tasks/
mounts/
todo/
```

Rules:

- `.alcove/index.sqlite` is cache only and must be rebuildable from Markdown/JSON source data.
- `knowledge/` keeps the current OKF bundle structure.
- `inbox/`, `archive/`, and `todo/` preserve the current social-media workflow.
- `pins/` stores pinned personal knowledge points and small reusable notes.
- `tasks/` stores Idea/Task/Routine data.
- `mounts/` stores Alcove-owned metadata for external mounted sources, not copies of every mounted file.

## Module Design

### Workspace Module

Interface:

```python
class Workspace:
    @classmethod
    def discover(cls, start: Path | None = None) -> "Workspace"
    @classmethod
    def init(cls, root: Path) -> "Workspace"
    def paths(self) -> WorkspacePaths
    def load_config(self) -> AlcoveConfig
    def status(self) -> WorkspaceStatus
```

Responsibilities:

- Find the nearest `.alcove/config.yml`.
- Initialize workspace directories.
- Resolve all module paths.
- Load and validate config.

This is the external seam for CLI/MCP startup. Other modules receive a `Workspace` or `WorkspacePaths`; they should not rediscover paths themselves.

### Repository Module

Interface:

```python
class MarkdownRepository:
    def read_doc(self, path: Path) -> MarkdownDoc
    def write_doc(self, path: Path, doc: MarkdownDoc) -> Path
    def list_docs(self, root: Path, type_filter: str | None = None) -> list[MarkdownDoc]
```

Responsibilities:

- Parse and write YAML frontmatter.
- Preserve Markdown-first storage.
- Provide common path, slug, and uniqueness helpers.

This module replaces ad hoc frontmatter parsing scattered across current scripts.

### Knowledge Module

Interface:

```python
class KnowledgeModule:
    def note_source(self, request: NoteSourceRequest) -> NoteSourceResult
    def archive_source(self, request: ArchiveSourceRequest) -> ArchiveSourceResult
    def add_question(self, request: AddQuestionRequest) -> KnowledgeDocResult
    def add_entity(self, request: AddEntityRequest) -> KnowledgeDocResult
    def promote_source(self, request: PromoteSourceRequest) -> KnowledgeDocResult
    def refresh_topic(self, request: RefreshTopicRequest) -> RefreshResult
    def gardener(self, request: GardenerRequest) -> GardenerReport
```

Responsibilities:

- Own OKF `Source`, `Knowledge Concept`, `Question`, `Entity`, `Topic`, `Tag`, and `Domain` writes.
- Own taxonomy normalization and index rebuilds.
- Own confidence/status/lifecycle metadata.
- Preserve low-friction human judgment fields.

### Inbox Module

Interface:

```python
class InboxModule:
    def peek(self) -> InboxPost | None
    def read(self, name: str) -> InboxPost
    def classify(self, name: str, proposed_topic: str | None = None) -> ClassificationDraft
    def archive(self, request: InboxArchiveRequest) -> InboxProcessResult
    def note(self, request: InboxNoteRequest) -> InboxProcessResult
    def mark_todo(self, request: InboxTodoRequest) -> InboxProcessResult
    def delete(self, name: str, confirm: bool = False) -> DeletePreview | DeleteResult
```

Responsibilities:

- Platform-aware inbox reading.
- Current-post processing from inbox to archive/todo/delete.
- Delegate OKF writes to `KnowledgeModule`.

Destructive operations must preview unless `confirm=True`.

### Pins Module

Pins are for small, high-value, frequently reused personal items. They are not the same as OKF Concepts.

Examples:

- A command snippet the user wants to keep handy.
- A small personal rule or judgment.
- A frequently needed reminder.
- A short point extracted from a post but not worth a full Concept.
- A pinned reference to an external file, Apple Note, or repo.

Interface:

```python
class PinsModule:
    def add(self, request: AddPinRequest) -> PinResult
    def list(self, request: ListPinsRequest) -> list[Pin]
    def get(self, pin_id: str) -> Pin
    def update(self, request: UpdatePinRequest) -> PinResult
    def archive(self, pin_id: str, confirm: bool = False) -> ArchivePreview | ArchiveResult
```

Suggested frontmatter:

```yaml
type: Pin
title: string
description: string
tags: []
status: active
priority: high|medium|low
source_refs: []
created_at: YYYY-MM-DD
updated_at: YYYY-MM-DD
```

Pins should live under `pins/<slug>.md` initially. Topic/domain can be added later only if it proves useful.

### Tasks Module

Tasks borrow the `social-radar` lifecycle but become part of Alcove's information graph.

Object types:

- `Idea`: low-friction capture.
- `Task`: concrete action.
- `Routine`: recurring template.

Interface:

```python
class TasksModule:
    def idea_add(self, request: AddIdeaRequest) -> Idea
    def idea_list(self, request: ListIdeasRequest) -> list[Idea]
    def idea_promote_to_task(self, request: PromoteIdeaRequest) -> Task
    def task_add(self, request: AddTaskRequest) -> Task
    def task_list(self, request: ListTasksRequest) -> list[Task]
    def task_complete(self, task_id: str) -> Task
    def task_cancel(self, task_id: str) -> Task
    def routine_add(self, request: AddRoutineRequest) -> Routine
    def routine_materialize_due(self, today: date | None = None) -> list[Task]
```

V1 storage can be `tasks/tasks.json`, following the Social Radar model. A later version can move to Markdown per task if the user wants git-friendly manual editing.

V1 does not install a scheduler. `routine_materialize_due` runs on explicit CLI/MCP calls.

### Mounts Module

Mounts represent external sources Alcove can search and reference without owning their content.

V1 mount types:

- `local-folder`
- `git-repo-local`

Later mount types:

- `github-star-index`
- `github-repo-remote`
- `browser-bookmarks`
- `apple-notes-export`

Interface:

```python
class MountsModule:
    def add(self, request: AddMountRequest) -> Mount
    def list(self) -> list[Mount]
    def scan(self, mount_id: str | None = None) -> MountScanReport
    def search(self, request: MountSearchRequest) -> list[MountedItem]
    def link_to_source(self, request: LinkMountedItemRequest) -> KnowledgeDocResult
```

Rules:

- Mounts are read-only by default.
- Mount identity must use stable paths or provider ids.
- Alcove stores metadata and search index entries, not full copies of every file.

### Connectors Module

Connectors adapt external applications or services.

V1 connector:

- `apple-notes`: export-only, read-only.

Interface:

```python
class AppleNotesConnector:
    def list_notes(self, request: ListAppleNotesRequest) -> list[AppleNoteSummary]
    def search_notes(self, request: SearchAppleNotesRequest) -> list[AppleNoteSummary]
    def export_all(self, request: ExportAppleNotesRequest) -> AppleNotesExportReport
```

Rules:

- macOS-only.
- Use Apple Notes note id as identity.
- Export deterministically.
- Never write to Apple Notes in v1.

### Search Module

Interface:

```python
class SearchModule:
    def search(self, request: SearchRequest) -> SearchResultSet
    def recent(self, request: RecentRequest) -> SearchResultSet
    def tags(self) -> list[TagStat]
```

Search should cover:

- OKF docs.
- Pins.
- Tasks.
- Mount metadata and indexed text snippets.
- Connector exports.

Implementation can start with file scanning and a simple SQLite cache. The cache must be rebuildable.

## CLI Surface

### Current Implemented Phase 1 Commands

The current Phase 1 CLI in HEAD implements this narrower command set:

```bash
alcove init [path]
alcove status [path] [--json]

alcove inbox --workspace PATH peek
alcove inbox --workspace PATH read NAME
alcove inbox --workspace PATH note NAME TOPIC --summary SUMMARY [--tag TAG]

alcove knowledge --workspace PATH note-source --platform PLATFORM --title TITLE --topic TOPIC [--resource RESOURCE] --summary SUMMARY [--tag TAG]

alcove search [QUERY] --workspace PATH [--json]
alcove search --workspace PATH --tags [--json]
alcove search --workspace PATH --tag-doctor [--json]
alcove search --workspace PATH --recent N [--json]
alcove search --workspace PATH --unindexed [--json]
```

The current inbox reader also accepts Clipsmith capture bundles. If a bundle has
`capture.json`, Alcove treats it as fallback metadata for title, source URL, and
date, while preserving the existing platform-specific Markdown read order.

### Planned Future CLI Surface

The following commands describe the roadmap surface for later phases. They are not all implemented in the current Phase 1 CLI.

```bash
alcove init [path]
alcove status [path] [--json]

alcove inbox --workspace PATH peek
alcove inbox read <name>
alcove inbox classify <name> [topic]
alcove inbox archive <name> <domain/topic> [--summary ...] [--tags ...]
alcove inbox --workspace PATH note <name> <domain/topic> --summary ... [--tags ...]
alcove inbox delete <name> [--confirm]

alcove knowledge --workspace PATH note-source --platform PLATFORM --title TITLE --topic TOPIC [--resource RESOURCE] --summary SUMMARY [--tag TAG]

alcove search <query> --workspace PATH [--json] [--type ...] [--topic ...] [--tag ...]
alcove recent [n]
alcove gardener [--prune]

alcove pin add <title> [--body ...] [--tag ...] [--source-ref ...]
alcove pin list [--tag ...]
alcove pin archive <id> [--confirm]

alcove task add <title> [--category ...] [--due YYYY-MM-DD] [--priority ...]
alcove task list [--status pending]
alcove task complete <id>
alcove idea add <title> [--notes ...]
alcove idea list

alcove mount add <path> [--name ...] [--type local-folder]
alcove mount list
alcove mount scan [id]

alcove connector apple-notes export --output-dir <dir>

alcove serve --mcp
alcove install --target codex,claude
```

Command design rules:

- Commands return human-readable output by default.
- Every command that mutates data should support `--json`.
- Every destructive command should require `--confirm` after preview.
- CLI errors should use explicit exit codes and concise messages.

## MCP Surface

V1 MCP tools should be small in count and deep in behavior:

- `alcove_search`: search across Knowledge, Pins, Tasks, Mounts, and connector exports.
- `alcove_inbox_peek`: inspect oldest pending inbox item.
- `alcove_note_source`: archive inbox item and create OKF Source/Concept.
- `alcove_get_topic`: return topic overview and active docs.
- `alcove_pin_add`: create a pinned note.
- `alcove_task_add`: create a task.
- `alcove_task_list`: list active tasks.
- `alcove_mount_list`: show configured mounts.
- `alcove_gardener`: report knowledge health.

MCP write tools should return object ids and filesystem paths. MCP destructive tools should either be omitted in v1 or require an explicit `confirm` argument.

## Error Handling

- Missing workspace: tell the user to run `alcove init`.
- Invalid topic: return candidate domains/topics from taxonomy.
- Ambiguous ids: return candidates instead of auto-picking.
- Destructive action without confirm: return preview, not an error.
- Apple Notes unavailable or permissions denied: return a machine-readable connector error and remediation.
- Mount path outside allowed filesystem: refuse only if configured policy requires it; otherwise mount read-only.
- Corrupt SQLite index: tell user to run `alcove index rebuild`; Markdown data remains valid.

## Testing Strategy

Unit tests:

- Workspace discovery and initialization.
- Markdown frontmatter parsing/writing.
- OKF Source/Concept/Question/Entity creation.
- Inbox platform read ordering.
- Pin add/list/archive.
- Task lifecycle: Idea, Task, Routine materialization.
- Mount add/list/scan on fixture folders.
- Apple Notes connector command construction using fake executor.

Integration tests:

- CLI `init`, `inbox peek`, `inbox note`, `search`, `pin add`, `task add`.
- MCP tools calling the same core modules as CLI.
- Layout validation after knowledge writes.

Regression fixtures:

- XHS folder with `summary.md`, `ocr-merge.txt`, and sparse `post.md`.
- Web article folder with `article.md`.
- Existing OKF bundle migrated from `social_media_posts`.
- Social Radar task JSON sample.
- Apple Notes deterministic export sample.

## Implementation Phases

### Phase 1: Core and OKF Extraction

- Create `~/programming/OctopusGarage/alcove`.
- Set up Python package with `uv`, tests, and CLI entrypoint.
- Implement Workspace, Repository, Knowledge, Inbox, and Search basics.
- Port current OKF behavior with tests.
- Preserve current `social_media_posts` workflow through Alcove CLI.

### Phase 2: Pins and Tasks

- Add Pins module and CLI.
- Add Tasks module using Social Radar IDEA/TASK/ROUTINE model.
- Expose search across Knowledge, Pins, and Tasks.

### Phase 3: MCP Server and Installer

- Add FastMCP server.
- Expose the V1 MCP tools.
- Add `alcove install --target codex,claude` to write MCP configs.

### Phase 4: Mounts and Apple Notes

- Add local-folder mounts.
- Add read-only Apple Notes export connector.
- Index mounted/exported content into search.

### Phase 5: GitHub and Star Indexes

- Add local GitHub repo mount conventions.
- Add star repository index import.
- Add `link_to_source` to promote mounted items into OKF Sources.

## Open Design Choices

- Whether tasks should remain in JSON long-term or move to one Markdown file per item.
- Whether Pins should support topic/domain taxonomy immediately or stay flat.
- Whether Alcove should support multiple workspace roots or one active workspace per command.
- Whether GitHub star indexing should use GitHub API, local exported lists, or both.
- Whether a future UI should be terminal-only, web, or desktop.

These are intentionally deferred. The MVP should make them possible without forcing decisions now.

## Approval Status

The user approved:

- Name: Alcove.
- Path: `~/programming/OctopusGarage/alcove`.
- Scheme C: local personal information core plus first OKF extraction.
- Technical route: Python + uv + Markdown-first + FastMCP/CLI.
- References: current OKF tool, CodeGraph product shape, Social Radar tasks, Apple Notes local skill, pins, and historical mounts.
