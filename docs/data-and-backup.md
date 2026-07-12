# Data and Backup

Alcove is local-first. It stores user data in plain Markdown, JSON, and YAML so
the data remains inspectable and portable.

## Data Locations

Default global home:

```text
~/.alcove/
├── config.yml
├── knowledge-bases/          managed KB registry
├── pins/                     OKF-compatible pinned notes
├── prompts/                  OKF-compatible reusable prompts
├── projects/                 project aliases
├── tasks/                    tasks, ideas, routines
├── mounts/                   external folder indexes
├── connectors/               external connector indexes
├── dashboard/                derived dashboard snapshot/build output
├── stats/
│   ├── summary.json          derived usage summary
│   └── daily/                derived daily usage rollups
└── logs/
    ├── activity.jsonl        human-readable semantic activity
    ├── usage.jsonl           privacy-safe usage events
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
