#!/usr/bin/env bash
set -euo pipefail

retry() {
  local attempts="$1"
  shift
  local attempt=1
  until "$@"; do
    if [[ "$attempt" -ge "$attempts" ]]; then
      return 1
    fi
    printf 'check: retrying %s (%s/%s)\n' "$*" "$((attempt + 1))" "$attempts" >&2
    sleep "$attempt"
    attempt=$((attempt + 1))
  done
}

uv run ruff check .
uv run ruff format --check .
uv run mypy
retry 3 uv run pip-audit
uv run pytest
uv run python -m compileall -q src tests
git diff --check

if command -v gitleaks >/dev/null 2>&1; then
  gitleaks detect --no-git --redact --config .gitleaks.toml
else
  echo "gitleaks not found; install it to run local secret scanning."
fi
