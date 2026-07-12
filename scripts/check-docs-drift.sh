#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

uv run python - <<'PY'
from pathlib import Path

from alcove.agent_quality_gate import docs_drift_exit_code

raise SystemExit(docs_drift_exit_code(repo_root=Path.cwd()))
PY
