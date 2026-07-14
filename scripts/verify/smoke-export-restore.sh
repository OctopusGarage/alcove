#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

root="${ALCOVE_EXPORT_RESTORE_DIR:-$repo_root/.tmp/export-restore}"
source_home="$root/source-home"
source_kb="$root/source-kb"
restore_home="$root/restore-home"
restore_kb="$root/restore-kb"
fixtures="$root/fixtures"
export_dir="$root/export/all"
report="$root/export-restore-report.json"

run() {
  printf 'export-restore: %s\n' "$*" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
}

rm -rf "$root"
mkdir -p "$fixtures"

export ALCOVE_HOME="$source_home"
alcove home init --json > "$fixtures/source-home-init.json"
alcove init "$source_kb" > "$fixtures/source-kb-init.txt"
alcove kb add source_kb "$source_kb" --json > "$fixtures/source-kb-add.json"
alcove pin --home "$source_home" add "Restore Pin" \
  --summary "Export restore pin." \
  --content "restore global search needle" \
  --tag restore \
  --json > "$fixtures/pin-add.json"
alcove prompt --home "$source_home" save "Restore Prompt" \
  --force \
  --description "Export restore prompt." \
  --content "Use export restore evidence to verify restored prompts, pins, tasks, projects, indexes, and search behavior before reporting success." \
  --tag restore \
  --json > "$fixtures/prompt-save.json"
alcove task --home "$source_home" add "Restore Task" \
  --notes "Export restore task." \
  --tag restore \
  --json > "$fixtures/task-add.json"
project_dir="$root/project-alpha"
mkdir -p "$project_dir"
alcove project --home "$source_home" add restore-project "$project_dir" \
  --note "Export restore project." \
  --json > "$fixtures/project-add.json"
mount_dir="$root/mounted"
mkdir -p "$mount_dir/docs"
printf '# Restore Mount\n\nrestore mounted search needle\n' > "$mount_dir/docs/restore.md"
alcove mount --home "$source_home" add "$mount_dir" \
  --name restore-mount \
  --type local-folder \
  --tag restore \
  --json > "$fixtures/mount-add.json"
alcove mount --home "$source_home" scan restore-mount --json > "$fixtures/mount-scan.json"
github_stars="$fixtures/github-stars.json"
cat > "$github_stars" <<'JSON'
[
  {
    "full_name": "octopusgarage/restore",
    "html_url": "https://github.com/OctopusGarage/restore",
    "description": "Export restore connector fixture.",
    "language": "Python",
    "topics": ["restore", "export"],
    "stargazers_count": 9,
    "updated_at": "2026-07-10T00:00:00Z"
  }
]
JSON
alcove connector --home "$source_home" github-stars index "$github_stars" \
  --tag restore \
  --include-items \
  --json > "$fixtures/github-stars-index.json"
alcove knowledge --kb source_kb add-note restore/test "Restore Concept" \
  --summary "restore knowledge search needle" \
  --tag restore > "$fixtures/knowledge-add.json"
alcove export --home "$source_home" all "$export_dir" --json > "$fixtures/export-all.json"

mkdir -p "$restore_home" "$restore_kb"
cp -R "$export_dir/global/." "$restore_home/"
cp -R "$export_dir/knowledge-bases/source_kb/." "$restore_kb/"

export ALCOVE_HOME="$restore_home"
alcove kb --home "$restore_home" add restored_kb "$restore_kb" --json > "$fixtures/restore-kb-add.json"
alcove pin --home "$restore_home" search "restore global" --json > "$fixtures/restore-pin-search.json"
alcove prompt --home "$restore_home" search "restore prompt" --json > "$fixtures/restore-prompt-search.json"
alcove task --home "$restore_home" list --json > "$fixtures/restore-task-list.json"
alcove project --home "$restore_home" find restore --json > "$fixtures/restore-project-find.json"
alcove mount --home "$restore_home" list --json > "$fixtures/restore-mount-list.json"
alcove connector --home "$restore_home" status --json > "$fixtures/restore-connector-status.json"
alcove connector --home "$restore_home" fetch "connectors/github-stars#octopusgarage/restore" \
  --json > "$fixtures/restore-connector-fetch.json"
alcove search --home "$restore_home" --kb restored_kb "restore knowledge" --json \
  > "$fixtures/restore-kb-search.json"
alcove doctor --home "$restore_home" --kb restored_kb --json > "$fixtures/restore-doctor.json"
alcove validate --home "$restore_home" --kb restored_kb --json > "$fixtures/restore-validate.json"

run uv run python - "$fixtures" "$export_dir" "$restore_home" "$restore_kb" "$report" <<'PY'
import json
import sys
from pathlib import Path

fixtures = Path(sys.argv[1])
export_dir = Path(sys.argv[2])
restore_home = Path(sys.argv[3])
restore_kb = Path(sys.argv[4])
report = Path(sys.argv[5])

def load(name: str):
    return json.loads((fixtures / name).read_text(encoding="utf-8"))

pin_results = load("restore-pin-search.json")
prompt_results = load("restore-prompt-search.json")
tasks = load("restore-task-list.json")
projects = load("restore-project-find.json")["projects"]
mounts_payload = load("restore-mount-list.json")
mounts = mounts_payload["mounts"] if isinstance(mounts_payload, dict) else mounts_payload
connectors = load("restore-connector-status.json")["sources"]
connector_fetch = load("restore-connector-fetch.json")
kb_results = load("restore-kb-search.json")
doctor = load("restore-doctor.json")
validate = load("restore-validate.json")

checks = [
    ("export_manifest", (export_dir / "manifest.json").is_file(), str(export_dir / "manifest.json")),
    ("restore_home_config", (restore_home / "config.yml").is_file(), str(restore_home / "config.yml")),
    ("restore_kb_config", (restore_kb / ".alcove" / "config.yml").is_file(), str(restore_kb / ".alcove" / "config.yml")),
    ("pin_search", any(row.get("title") == "Restore Pin" for row in pin_results), "Restore Pin"),
    ("prompt_search", any(row.get("title") == "Restore Prompt" for row in prompt_results), "Restore Prompt"),
    ("task_list", any(row.get("title") == "Restore Task" for row in tasks), "Restore Task"),
    ("project_find", any(row.get("alias") == "restore-project" for row in projects), "restore-project"),
    ("mount_list", any(row.get("id") == "restore-mount" for row in mounts), "restore-mount"),
    ("connector_status", any(row.get("connector") == "github-stars" for row in connectors), "github-stars"),
    ("connector_fetch", connector_fetch.get("item", {}).get("title") == "octopusgarage/restore", "octopusgarage/restore"),
    ("kb_search", any(row.get("title") == "Restore Concept" for row in kb_results), "Restore Concept"),
    ("doctor", doctor.get("status") in {"ok", "issues"}, doctor.get("status", "")),
    ("validate", isinstance(validate.get("issues"), list), "issues list"),
]
failed = [name for name, ok, _detail in checks if not ok]
payload = {
    "status": "failed" if failed else "passed",
    "source_export": str(export_dir),
    "restore_home": str(restore_home),
    "restore_kb": str(restore_kb),
    "summary": {
        "pin_results": len(pin_results),
        "prompt_results": len(prompt_results),
        "tasks": len(tasks),
        "projects": len(projects),
        "mounts": len(mounts),
        "connectors": len(connectors),
        "connector_fetch": connector_fetch.get("item", {}).get("title", ""),
        "kb_results": len(kb_results),
        "validation_issues": len(validate.get("issues", [])),
    },
    "checks": [
        {"name": name, "status": "passed" if ok else "failed", "detail": detail}
        for name, ok, detail in checks
    ],
    "artifacts": str(report.parent),
}
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(f"export restore smoke failed: {', '.join(failed)}")
PY
