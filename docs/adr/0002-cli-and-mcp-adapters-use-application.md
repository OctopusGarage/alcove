# ADR 0002: Route CLI and MCP Behavior Through AlcoveApplication

Date: 2026-07-08

## Status

Accepted

## Context

Alcove has multiple entry points: CLI, MCP, and future agent skills. Duplicating behavior in each adapter makes runtime scope, payload shape, and validation drift likely.

## Decision

CLI and MCP should act as adapters. Shared behavior should cross the `AlcoveApplication` interface and use `AlcoveRuntime` for workspace/home scope.

## Consequences

- Entry behavior has better locality.
- CLI and MCP can share tests through the same application seam.
- CLI may still own parsing and terminal rendering.
