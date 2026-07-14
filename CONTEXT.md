# Alcove Context

Alcove is a local-first personal information core for agent-assisted knowledge work.

## Domain Terms

- Alcove Home: the user-level state directory, normally `~/.alcove`. It owns global pins, tasks, mounted indexes, connector indexes, the managed knowledge-base registry, and export state.
- Managed Knowledge Base: a user-chosen directory fully managed by Alcove. It owns `knowledge/`, `inbox/`, `archive/`, and `todo/`.
- Mounted Knowledge Base: a read-only external folder or repository indexed by Alcove Home. The original files remain outside Alcove.
- Connector Knowledge Base: a read-only external protocol/export index, such as Apple Notes or GitHub Stars, stored under Alcove Home.
- OKF: the Markdown-first knowledge format used inside a managed knowledge base. Main document types are `Source`, `Knowledge Concept`, `Question`, and `Entity`.
- Inbox Item: a captured or manually added bundle waiting to be archived, noted, deleted, or moved to todo.
- Pin: a small global reference item. Pins are not managed-KB OKF concepts.
- Task: a global personal work item. Ideas and routines live in the same task store.

## Architecture Vocabulary

- CLI and MCP are adapters.
- CLI Command Registry owns parsed command dispatch from CLI command names to adapter handlers. `cli.py` owns parser construction and process-level error handling.
- `AlcoveApplication` is the behavior interface shared by adapters.
- `AlcoveApplication` stays a stable facade with six public capability groups: search, system, inbox, knowledge, global home, and external indexes.
- `AlcoveRuntime` carries the active workspace/home scope.
- MCP adapter scope defaults are centralized in a private invocation context before calling `AlcoveApplication`.
- Search spans managed KB, pins, tasks, mounts, and connectors according to runtime scope.
- `SearchQueryPlan` owns search request normalization and row/doc filter semantics.
- `GlobalHomeSearchAdapter` adapts pins, ideas, and tasks into search rows without exposing their storage shape to search.
- Link promotes an indexed external item into a managed KB `Source`; lookup uses runtime scope, writing uses the selected managed KB.
- Mount scans reuse unchanged indexed files. Connector hits can lazy-fetch detail through `connectors/<connector-id>#<relative-path>`.
- `ExternalItemReference` owns external item path identity for connector and mount items.
- `Profile Installation Pack` owns generated agent entry artifacts; `ProfileInstaller` owns idempotent writes and legacy cleanup.
- Export supports global-only, one registered managed KB, or all registered Alcove-owned data.

## Example Local Default

- Default Alcove Home: `~/.alcove`
- Example managed KB: `research_notes`
- Example managed KB path: `/path/to/research_notes`
