#!/usr/bin/env bash
set -euo pipefail

uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pip-audit
uv run pytest
uv run python -m compileall -q src tests
git diff --check

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-git --redact --config .gitleaks.toml
else
  echo "gitleaks not found; install it to run local secret scanning."
fi
