# ADR 0003: Link Uses Runtime Search Scope And Writes To Managed KB

Date: 2026-07-08

## Status

Accepted

## Context

External items can live in global home indexes, while linked OKF `Source` documents must be written into a managed knowledge base. A workspace-only link lookup misses global mounted and connector indexes.

## Decision

Link lookup uses the same runtime search scope as search. Link writing uses the selected managed KB workspace.

## Consequences

- Global mounted and connector items can be promoted into a managed KB.
- The search/index seam remains consistent between search and link.
- Link still requires a managed KB because it writes OKF documents.
