#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

home="${ALCOVE_HOME:-$HOME/.alcove}"
report_dir="${ALCOVE_REAL_SMOKE_REPORT_DIR:-$(mktemp -d)}"
report="$report_dir/real-home-smoke-report.json"
mkdir -p "$report_dir"

run() {
  printf 'real-smoke: %s\n' "$*" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
}

capture_json() {
  local name="$1"
  shift
  "$@" > "$report_dir/$name.json"
}

capture_json connector-status alcove connector --home "$home" status --json
capture_json mount-list alcove mount --home "$home" list --json
capture_json kb-list alcove kb --home "$home" list --json
capture_json pin-list alcove pin --home "$home" list --json
capture_json task-list alcove task --home "$home" list --json
capture_json idea-list alcove idea --home "$home" list --json
capture_json prompt-search alcove prompt --home "$home" search --json
capture_json project-list alcove project --home "$home" list --json
capture_json radar-list alcove radar --home "$home" list --json
capture_json radar-status alcove radar --home "$home" status --json
capture_json dashboard-build alcove dashboard --home "$home" build --skip-frontend-build --json
capture_json dashboard-audit run uv run scripts/verify/audit-dashboard-data.py \
  --home "$home" \
  --snapshot "$home/dashboard/snapshot.json" \
  --json
capture_json search-smoke alcove search --home "$home" smoke --json

run uv run python - "$home" "$report_dir" "$report" <<'PY'
import json
import sys
from pathlib import Path

home = Path(sys.argv[1]).expanduser()
report_dir = Path(sys.argv[2])
report_path = Path(sys.argv[3])

def load(name: str):
    return json.loads((report_dir / f"{name}.json").read_text(encoding="utf-8"))

connector_status = load("connector-status")
mounts = load("mount-list")
kbs = load("kb-list")
pins = load("pin-list")
tasks = load("task-list")
ideas = load("idea-list")
prompts = load("prompt-search")
projects = load("project-list")
radar_list = load("radar-list")
radar_status = load("radar-status")
dashboard = load("dashboard-build")
dashboard_audit = load("dashboard-audit")

checks = [
    ("home_exists", home.is_dir(), str(home)),
    ("config_exists", (home / "config.yml").is_file(), str(home / "config.yml")),
    ("connector_status_readable", isinstance(connector_status.get("sources"), list), "connector status"),
    ("mount_list_readable", isinstance(mounts, list), "mount list"),
    ("kb_list_readable", isinstance(kbs, list), "kb list"),
    ("pin_list_readable", isinstance(pins, list), "pin list"),
    ("task_list_readable", isinstance(tasks, list), "task list"),
    ("idea_list_readable", isinstance(ideas, list), "idea list"),
    ("prompt_search_readable", isinstance(prompts, list), "prompt search"),
    ("project_list_readable", isinstance(projects, list), "project list"),
    ("radar_list_readable", isinstance(radar_list.get("definitions"), list), "radar list"),
    ("radar_status_readable", isinstance(radar_status.get("radars"), list), "radar status"),
    ("dashboard_built", dashboard.get("status") == "built", dashboard.get("index", "")),
    ("dashboard_snapshot_exists", (home / "dashboard" / "snapshot.json").is_file(), str(home / "dashboard" / "snapshot.json")),
    ("dashboard_data_audit", dashboard_audit.get("status") == "passed", json.dumps(dashboard_audit.get("failures", []), ensure_ascii=False)),
]
failed = [name for name, ok, _detail in checks if not ok]
report = {
    "status": "failed" if failed else "passed",
    "home": str(home),
    "summary": {
        "connectors": len(connector_status.get("sources", [])),
        "mounts": len(mounts),
        "knowledge_bases": len(kbs),
        "pins": len(pins),
        "tasks": len(tasks),
        "ideas": len(ideas),
        "prompts": len(prompts),
        "projects": len(projects),
        "radars": len(radar_list.get("definitions", [])),
    },
    "checks": [
        {"name": name, "status": "passed" if ok else "failed", "detail": detail}
        for name, ok, detail in checks
    ],
    "artifacts": str(report_dir),
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(f"real home smoke failed: {', '.join(failed)}")
PY

printf 'real-smoke: report %s\n' "$report"
