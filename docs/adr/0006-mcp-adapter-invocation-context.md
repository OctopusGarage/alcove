# ADR 0006: Centralize MCP Adapter Scope In An Invocation Context

Date: 2026-07-08

## Status

Accepted

## Context

The MCP adapter already routed behavior through `AlcoveApplication`, but each MCP tool wrapper repeated the same scope work: combine explicit `workspace` and `home` arguments with `default_workspace` and `default_home`, create `AlcoveRuntime`, then create `AlcoveApplication`.

That repetition made scope behavior easy to drift across tools even though MCP remained an adapter.

## Decision

Keep MCP tools as thin schema/docstring wrappers and centralize MCP scope defaults in a private `_McpInvocationContext`.

The context owns:

- explicit workspace/home handling
- default workspace/home handling
- managed-KB-only invocations
- `AlcoveApplication` creation

## Consequences

- MCP adapter locality improves: scope rules live in one place.
- Adding a new MCP tool is less likely to bypass ADR-0002.
- `mcp_server.py` is now included in strict mypy coverage.
- `AlcoveApplication` remains the adapter-facing behavior interface; this does not reopen ADR-0005.
