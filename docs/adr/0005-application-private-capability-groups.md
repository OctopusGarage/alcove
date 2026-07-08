# ADR 0005: Keep AlcoveApplication As A Small Capability Facade

Date: 2026-07-08

## Status

Accepted

## Context

CLI and MCP adapters now share the `AlcoveApplication` interface. As more workflows moved behind that seam, the implementation inside `AlcoveApplication` became wide even though the external interface was correct.

The first pass moved behavior into private capability groups but kept dozens of pass-through public methods on `AlcoveApplication`. That preserved behavior but left the adapter-facing interface wider than the domain model.

## Decision

Keep `AlcoveApplication` as the stable behavior interface for adapters, but expose only six capability groups:

- `_SearchCapabilities`
- `_SystemCapabilities`
- `_InboxCapabilities`
- `_ManagedKnowledgeCapabilities`
- `_GlobalHomeCapabilities`
- `_ExternalCapabilities`

The public facade is:

- `app.search`
- `app.system`
- `app.inbox`
- `app.knowledge`
- `app.global_home`
- `app.external`

CLI and MCP adapters call these groups directly. The CLI command names and MCP tool names do not change.

## Consequences

- Adapter locality stays intact: CLI and MCP still depend on one application seam.
- Implementation locality improves: managed KB, global home, external index, inbox, search, and system behavior can evolve in smaller private modules.
- The public interface no longer grows by one facade method per CLI/MCP action.
- New application files are included in strict mypy coverage to catch drift at the seam.
