# Security Policy

## Reporting a Vulnerability

Do not open a public GitHub issue for security vulnerabilities. Use GitHub
Private Vulnerability Reporting for the `OctopusGarage/alcove` repository. We
will acknowledge the report within 7 days and keep you informed while we assess
and fix it.

## Scope

Alcove is local-first. It manages personal knowledge-base paths, local indexes,
pins, tasks, and MCP/CLI entrypoints. Credentials and private user data should
stay outside the repository and inside the configured Alcove home or user-owned
data directories.

Key security properties:

- Alcove does not require a hosted service for local CLI/MCP use.
- Connector exports and indexes are local user data under `~/.alcove` by
  default, or under the configured `ALCOVE_HOME`.
- Managed knowledge bases are stored in user-selected directories and registered
  under the Alcove home.
- Backup and encryption are user-controlled; see `docs/data-and-backup.md`.
