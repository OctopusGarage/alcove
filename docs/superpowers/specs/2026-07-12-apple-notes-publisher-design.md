# Apple Notes Publisher Design

## Goal

Add a generic publishing capability to Alcove so selected local modules can be
rendered into stable human-readable outputs and synchronized to external
destinations. The first destination is Apple Notes.

The immediate user need is offline access to pinned information when the local
dashboard is unavailable outside the LAN. Alcove should periodically format
`regular` and `todo` pins, then update two fixed Apple Notes under a configured
Alcove folder.

This should not be a pins-only script. The design must leave room for later
publishing task digests, radar summaries, knowledge notes, or other module
views to Apple Notes, files, notifications, or future targets.

## Product Model

```text
Alcove Home
├── managed / mounted / connector knowledge sources
├── pins
├── tasks
├── radars
├── dashboard
└── publishers
    ├── collect module data
    ├── render stable output documents
    ├── publish them to target adapters
    └── track target identity and content hashes
```

Connectors remain read/import/index adapters. Publishers are write/sync
adapters. Apple Notes currently exists as a read-only connector in Alcove; this
feature adds an Apple Notes publishing target without changing connector
semantics.

## Apple Notes Layout

Apple Notes should use one configurable Alcove root folder. Module outputs live
under stable subfolders:

```text
Apple Notes
└── iCloud/Alcove/
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

The default implementation mirrors compact, user-facing module views. Large
knowledge bases, mounts, connectors, radar archives, automations, logs, and
usage records remain in Alcove and are accessed through dashboard, search, CLI,
or MCP rather than copied wholesale into Notes.

## Configuration

Publisher definitions are user data under Alcove Home:

```text
~/.alcove/publishers/
├── definitions/
│   └── apple-notes.yml
├── state/
│   └── apple-notes.yml
├── renders/
│   └── <target-id>.md
├── runs/
│   └── <timestamp>-<publisher-id>.json
└── events.jsonl
```

Initial definition shape:

```yaml
schema: alcove/publisher-definition/v1
id: apple-notes
status: active
schedule:
  enabled: true
  ttl_hours: 24
target_defaults:
  type: apple-notes
  root_folder: "iCloud/Alcove"
  mode: replace
  recreate_missing: false
targets:
  pins_regular:
    source:
      module: pins
      filter:
        kind: regular
        status: active
    render:
      template: pins_digest
      title: "Regular Pins"
    target:
      folder: "pins"
      title: "Regular Pins"
  pins_todo:
    source:
      module: pins
      filter:
        kind: todo
        status: active
    render:
      template: pins_digest
      title: "TODO Pins"
    target:
      folder: "pins"
      title: "TODO Pins"
  planner_digest:
    source:
      module: tasks
      filter:
        status: active
    render:
      template: planner_digest
      title: "Planner Digest"
    target:
      folder: "planner"
      title: "Planner Digest"
  prompt_library:
    source:
      module: prompts
      filter:
        status: active
    render:
      template: prompt_library
      title: "Prompt Library"
    target:
      folder: "prompts"
      title: "Prompt Library"
  project_registry:
    source:
      module: projects
      filter: {}
    render:
      template: project_registry
      title: "Project Registry"
    target:
      folder: "projects"
      title: "Project Registry"
```

`root_folder` and each target `folder` combine into an Apple Notes folder path,
for example `iCloud/Alcove/pins`.

## State

The publisher must not rely on title lookup after the first successful sync.
State records stable target identity and last rendered content:

```yaml
schema: alcove/publisher-state/v1
publisher_id: apple-notes
targets:
  pins_regular:
    note_id: "x-coredata://..."
    folder_path: "iCloud/Alcove/pins"
    title: "Regular Pins"
    content_hash: "sha256:..."
    last_synced_at: "2026-07-12T08:00:00+00:00"
    last_status: success
    last_error: ""
```

First sync behavior:

1. Resolve the folder path.
2. Search for an exact title match in that folder.
3. If no match exists, create the note.
4. If exactly one match exists, record its `note_id`.
5. If multiple matches exist, fail with an explicit ambiguous target error.

Later sync behavior:

1. Resolve the target by `note_id`.
2. Render source data and calculate a content hash.
3. If the hash is unchanged, skip the write.
4. If the hash changed, replace the note body and reapply the title.
5. Update state and write an audit run record.

If a stateful note is missing, default behavior is to fail. A target may opt into
`recreate_missing: true`, which recreates the note by folder and title and
stores the new `note_id`.

## Rendering

The first renderers are `pins_digest`, `planner_digest`, `prompt_library`, and
`project_registry`. They output deterministic Markdown that Apple Notes can
render clearly through Alcove's Markdown-to-Notes HTML conversion.

Recommended structure:

```markdown
# Regular Pins

Updated: 2026-07-12 18:30 SGT
Count: 42

## High Priority

1. Title
   Summary or first content paragraph.
   Tags: tag-a, tag-b
   Resources:
   - https://example.com

## Medium Priority
...
```

Pins content remains source-of-truth in `~/.alcove/pins/*.md`. Apple Notes is a
readable mirror, not an edit surface. Manual edits to the generated Apple Notes
will be overwritten on the next successful publish.

Renderers should preserve enough original meaning to be useful offline, but may
normalize headings, ordering, timestamps, labels, tags, and resource lists for
mobile readability. The Notes output should use headings, numbered lists, bullet
lists, emphasized labels, and spacing; it should not be a raw text dump.

## Apple Notes Target Adapter

The Apple Notes adapter uses local macOS Notes.app automation through JXA
(`osascript -l JavaScript`). It should share behavior constraints with the
existing Apple Notes local tooling:

- macOS only.
- Notes.app automation permission is required.
- Prefer `note_id` over title lookup.
- Do not guess when title lookup is ambiguous.
- When replacing body and title, write body first and reapply title second
  because Apple Notes may derive a visible title from body content.

Required target operations:

```text
resolve_or_create(folder_path, title, state) -> TargetRef
replace_note_body(note_id, title, body) -> result
get_note(note_id) -> result
```

Folder creation should be supported for configured paths. Destructive
operations such as deleting notes or folders are out of scope for publishers.

## CLI

The first CLI surface should be small:

```sh
alcove publish list --home ~/.alcove --json
alcove publish run apple-notes --home ~/.alcove --json
alcove publish run apple-notes --target pins_regular --home ~/.alcove --json
alcove publish init apple-notes --home ~/.alcove --root-folder "iCloud/Alcove" --json
```

`init apple-notes` writes the default two pins targets if no definition exists.
It should not overwrite an existing definition unless a future `--force` option
is added.

## Scheduling

Publishing should integrate with the existing launchd-backed service:

```text
alcove service tick --home ~/.alcove
  -> run stale publishers
  -> rebuild OKF/health/dashboard
```

Publisher definitions use `ttl_hours` like automations and radars. Scheduled
publish runs should skip unchanged content. Failures should be recorded in
`~/.alcove/publishers/runs/`, appended to `events.jsonl`, and surfaced in the
dashboard data-health area later.

Unattended service runs must not depend on an open Codex or Claude session. The
pins renderer is deterministic and does not require AI.

## Generalization

The module should be designed around three internal roles:

```text
source provider -> renderer -> target adapter
```

Initial implementations:

- source provider: `pins`
- renderer: `pins_digest`
- target adapter: `apple-notes`

Future implementations can add:

- sources: `tasks`, `radars`, `knowledge`, `prompts`, `custom-command`
- renderers: `task_digest`, `radar_briefing`, `markdown_passthrough`
- targets: `filesystem`, `telegram`, `feishu`, `tcb`

This keeps module-specific logic out of the Apple Notes adapter and keeps
Apple Notes behavior out of the pins module.

## Error Handling

Errors should be explicit and machine-readable:

- `APPLE_NOTES_UNAVAILABLE`: not macOS or Notes.app is unavailable.
- `AUTOMATION_PERMISSION_DENIED`: host process cannot control Notes.app.
- `TARGET_AMBIGUOUS`: folder/title lookup found multiple notes.
- `TARGET_MISSING`: state has a `note_id`, but the note no longer exists.
- `FOLDER_CREATE_FAILED`: configured folder path cannot be created.
- `RENDER_FAILED`: source or renderer failed.

Each run result includes target-level statuses so one failed target does not
hide other successful targets.

## Testing

Unit tests should cover:

- definition parsing and validation
- pins source filtering
- pins digest rendering order and content preservation
- stateful skip when content hash is unchanged
- first-run target resolution behavior
- missing and ambiguous Apple Notes target handling through a fake adapter
- service tick invokes stale publisher runs

Smoke tests should cover:

- `alcove publish init apple-notes`
- `alcove publish run apple-notes` with a fake Apple Notes adapter
- AI eval packet includes publisher evidence after local smoke

Manual local verification should cover a real Notes.app sync because macOS
Automation permissions and Apple Notes behavior cannot be fully validated in CI.

## Out of Scope

- Bidirectional sync from Apple Notes back into pins.
- Editing pins inside Apple Notes.
- Deleting generated Apple Notes automatically.
- AI summarization for pins publisher output.
- Publishing every Alcove module in the first implementation.
