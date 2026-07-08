# ADR 0007: External Indexes Support Incremental Refresh And Lazy Fetch

Date: 2026-07-08

## Status

Accepted

## Context

Mounted folders and connector sources are external knowledge bases. Alcove should index them for search without pretending to own the original files or protocol data.

Full rescans are simple but wasteful for large mount folders. Connector search indexes should also have a stable way to fetch detail after a search hit, especially when the index intentionally stores only searchable metadata.

## Decision

Mounted indexes store file identity fields:

- `relative_path`
- `file_size`
- `file_mtime_ns`

`alcove mount scan` reuses unchanged indexed items and only rereads changed files. The scan report includes `reused`.

Connector hits use this stable lazy-fetch path format:

```text
connectors/<connector-id>#<relative-path>
```

`alcove connector fetch <item-path>` returns the indexed item and best available detail. Apple Notes currently reads local deterministic export detail from `note.json` when available; other connectors return indexed detail until a richer adapter is added.

## Consequences

- Mount scans become cheaper without copying external folders.
- Search remains the discovery surface, while fetch becomes the detail contract.
- Connector detail can evolve per adapter without changing search row shape.
- External systems remain the source of truth; Alcove owns only the index and linked OKF records.
