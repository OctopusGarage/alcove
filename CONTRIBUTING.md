# Contributing

Alcove is a Python package managed with `uv`.

## Development Setup

```bash
uv sync --dev
scripts/install-git-hooks.sh
```

The git hook uses `scripts/check.sh`, which runs the same local gates expected in
CI: Ruff, pytest, Python compile checks, whitespace checks, and gitleaks when the
CLI is installed.

## Before Opening A PR

```bash
scripts/check.sh
uv build
```

For focused verification:

```bash
scripts/smoke.sh                    # isolated CLI/application smoke
scripts/smoke-mcp-matrix.sh         # MCP tool matrix
scripts/eval-ai.sh                  # AI-facing quality eval
```

Use the real integration suites only when the change touches external data
sources, browser/OCR capture, local Apple Notes, Clipsmith handoff, or live MCP
stdio boundaries:

```bash
scripts/smoke-real-home.sh
scripts/smoke-real-integrations.sh
```

New behavior should be covered by tests or a smoke/eval fixture. Keep changes
close to the module that owns the behavior.

## Sensitive Data

Keep user data out of the repo. Local runtime state belongs under the configured
Alcove home, usually `~/.alcove`, or in explicitly configured knowledge-base
directories.

Do not hardcode personal paths, credentials, tokens, exported connector data, or
private notes. Examples and tests should use `~`, `/path/to/...`, or temporary
directories.

## Conventions

- Conventional commits: `feat:`, `fix:`, `refactor:`, `docs:`, `test:`,
  `chore:`.
- Current behavior belongs in `README.md` and `docs/`.
- Design decisions belong in `docs/adr/`.
- Historical plans belong in `docs/archive/` and must not be presented as the
  current command surface.
