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

Keep user data out of the repo. Local runtime state belongs under the configured
Alcove home, usually `~/.alcove`, or in explicitly configured knowledge-base
directories.
