# ADR 0001: Keep Alcove Home Separate From Managed Knowledge Bases

Date: 2026-07-08

## Status

Accepted

## Context

Alcove has global personal data and one-to-many managed knowledge bases. Pins, tasks, mounted indexes, connector indexes, and the managed-KB registry should not be written into one specific knowledge base.

## Decision

Alcove Home owns global data under `~/.alcove` by default. Managed knowledge bases remain user-chosen directories and own only their full-lifecycle OKF data: `knowledge/`, `inbox/`, `archive/`, and `todo/`.

## Consequences

- Global search can work without a workspace.
- Managed KB workflows still require a selected workspace or registered KB.
- Export can separate Alcove-owned global data from managed KB content.
