# ADR 0004: Link External Items Through Direct Index Lookup

Date: 2026-07-08

## Status

Accepted

## Context

`LinkingModule` promotes an indexed mounted or connector item into a managed KB `Source`. The previous implementation found the item by running broad search and comparing row paths, which made link depend on the whole search pipeline for a single external item lookup.

## Decision

Link should first use the external index seam to look up `connectors/<connector-id>#<relative-path>` and `mounts/<mount-id>#<relative-path>` directly. Search remains available for discovery, but link lookup should not require a full search scan.

## Consequences

- Link has clearer locality: lookup rules live at the external index seam.
- Failure modes are sharper when an indexed item is missing.
- Search can evolve without silently changing link semantics.
