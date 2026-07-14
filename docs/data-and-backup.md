# Data and Backup

Alcove is local-first. It stores user data in plain Markdown, JSON, and YAML so
the data remains inspectable and portable.

## Data Locations

Default global home:

```text
~/.alcove/
├── config.yml
├── workspaces/               Hub and business agent workspace registry/data
├── knowledge-bases/          managed KB registry
├── pins/                     OKF-compatible pinned notes
├── prompts/                  OKF-compatible reusable prompts
├── projects/                 project aliases
├── tasks/                    tasks, ideas, routines
├── mounts/                   external folder indexes
├── connectors/               external connector indexes
├── watchers/                 watched URL/feed sources and change events
├── blog-monitor/             monitored blog sources and seen state
├── radars/                   radar definitions, run cache, reports, and OKF indexes
├── automations/              repeatable user job configs, runs, and events
├── publishers/               rendered mirrors and external publish state
├── dashboard/                derived dashboard snapshot/build output
├── stats/
│   ├── summary.json          derived usage summary
│   └── daily/                derived daily usage rollups
└── logs/
    ├── activity.jsonl        human-readable semantic activity
    ├── usage.jsonl           privacy-safe usage events
    ├── service/              launchd stdout/stderr logs
    └── .usage_salt           local salt for query hashes
```

Managed KB roots live wherever the user chooses:

```text
<managed-kb-root>/
├── .alcove/config.yml
├── inbox/
├── archive/
├── knowledge/
└── todo/
```

Connector and mount indexes are Alcove-owned caches. Managed KB `archive/` and
`knowledge/` are tracked user data.

Agent workspace registry and default entry directories live under Alcove Home:

```text
~/.alcove/workspaces/
├── hub.yml                   fixed Hub control workspace
├── <workspace-id>.yml        family/work/travel scene registry
└── data/<workspace-id>/      default AGENTS.md / CLAUDE.md / skills directory
```

If a workspace is created with `--path`, the registry remains in
`~/.alcove/workspaces/`, while the entry directory lives at the user-chosen
path.

Business workspaces can optionally own a workspace-local OKF store:

```text
<workspace-path>/
├── documents/                 raw scene-local source files
└── okf/                       managed KB root registered in ~/.alcove/knowledge-bases/
```

This is user data. Back it up with the workspace directory and the matching
registry records under `~/.alcove/workspaces/` and `~/.alcove/knowledge-bases/`.

Watcher state is Alcove-owned operational data:

```text
~/.alcove/watchers/
├── sources/*.yml             watched URL/feed configs and refresh state
└── events.jsonl              detected change events
```

When a watcher is configured with `--kb <name>`, changed sources are copied into
that managed KB's `inbox/manual/` for later AI-assisted review. The watcher
event itself remains in `~/.alcove/watchers/events.jsonl`.

Blog monitor state is Alcove-owned operational data:

```text
~/.alcove/blog-monitor/
├── sources/*.yml             blog source configs and refresh policy
├── seen/*.json               URLs already discovered for each source
├── captures/<source-id>/     temporary/default Clipsmith web capture output
├── runs/*.json               per-run audit records
└── events.jsonl              discovered article events
```

If a blog source has capture enabled, new articles are captured through the
configured adapter and written under the selected managed KB inbox path, such as
`social_media_posts/inbox/openai`. The source article remains external; Alcove
stores seen state, run logs, and capture routing metadata.

Automation state is Alcove-owned operational data:

```text
~/.alcove/automations/
├── jobs/*.yml                 job definitions and latest run state
├── runs/*.json                per-run audit records
└── events.jsonl               automation run events
```

The source of truth for each automation is the YAML job file. Run records and
events are append/derived operational evidence and can be pruned or archived
separately from user knowledge.

Publisher state is Alcove-owned operational data:

```text
~/.alcove/publishers/
├── definitions/*.yml          publisher definitions
├── state/*.yml                external target identity and content hashes
├── renders/*.md               latest rendered outbound documents
├── runs/*.json                per-run audit records
└── events.jsonl               publisher run events
```

For Apple Notes publishing, Alcove stores the target `note_id` after the first
successful sync and updates by note id on later runs. Generated Apple Notes are
readable mirrors. The source data remains in Alcove, such as `~/.alcove/pins`,
`~/.alcove/tasks`, `~/.alcove/prompts`, and `~/.alcove/projects`.

The default Apple Notes publisher mirrors selected, user-facing views: regular
pins, todo pins, planner digest, prompt library, and project registry. Pin note
content is preserved in full and formatted with outlines and section spacing.
High-volume knowledge bases, connector indexes, mount indexes, radar archives,
and operational logs remain in Alcove rather than being copied into Notes.

Usage logs are local operational data. Search events store query length, result
count, filters, surface, outcome, and a local salted query hash. Raw query text
and content snippets are not stored by default.

Semantic write events are split by purpose:

- `activity.jsonl`: low-noise events worth showing to a person, such as adding a
  pin, writing a knowledge note, scanning a mount, or indexing a connector.
- `usage.jsonl`: aggregate-friendly event stream used by the dashboard Usage
  page for action counts, area distribution, recent operations, and search
  health.
- `stats/summary.json` and `stats/daily/*.json`: derived rollups regenerated
  from `usage.jsonl`; safe to rebuild and useful for fast dashboard/AI reads.
- Dashboard data-health counts are derived from managed KB registries, mount
  indexes, connector indexes, and stats rollups. They are observation data, not a
  new source of truth.

## Export

```sh
alcove export global ~/alcove-backup --json
alcove export kb research_notes ~/alcove-backup/research_notes --json
alcove export all ~/alcove-backup-all --json
```

Exports are useful for migration, restore drills, and point-in-time snapshots.

## Recommended Git Backup

User-data synchronization is intentionally outside the Alcove runtime. The
recommended operational pattern is:

```text
managed KB roots + ~/.alcove
  -> private Git-backed backup repository
  -> git-auto-sync scheduled synchronization
  -> optional git-crypt encryption before remote push
```

Recommended sync tool:

https://github.com/OctopusGarage/git-auto-sync

Use it to periodically commit and push the repositories that contain Alcove Home
and managed KB data.

## Encryption

For sensitive knowledge, pins, tasks, prompts, connector indexes, or archived
captures, encrypt before pushing to a remote Git repository.

Recommended encryption layer:

https://github.com/AGWA/git-crypt

Alcove does not manage git-crypt keys. Configure encryption in the repository
that stores user data, verify `.gitattributes` before the first push, and avoid
committing plaintext secrets to any remote.

## Boundaries

- Alcove writes portable local data.
- Alcove exports data on demand.
- Alcove does not own backup scheduling.
- Alcove does not manage encryption keys.
- Users should validate restore workflows periodically with
  `scripts/smoke-export-restore.sh` in development.
