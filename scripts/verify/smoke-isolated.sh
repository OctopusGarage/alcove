#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

tmp_root="${ALCOVE_SMOKE_TMP:-$(mktemp -d)}"
keep_tmp="${ALCOVE_SMOKE_KEEP:-0}"
if [[ "$keep_tmp" != "1" ]]; then
  trap 'rm -rf "$tmp_root"' EXIT
fi

home="$tmp_root/home"
kb="$tmp_root/research_notes"
hub="$tmp_root/hub"
fixtures="$tmp_root/fixtures"
export_root="$tmp_root/export"
report="$tmp_root/smoke-report.json"

mkdir -p "$fixtures"

run() {
  printf 'smoke: %s\n' "$*" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
}

write_json() {
  local path="$1"
  local payload="$2"
  printf '%s\n' "$payload" > "$path"
}

assert_json() {
  local label="$1"
  local path="$2"
  local code="$3"
  run uv run python - "$label" "$path" "$code" <<'PY'
import json
import sys
from pathlib import Path

label, path, code = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
payload = json.loads(path.read_text(encoding="utf-8"))
namespace = {"payload": payload, "Path": Path}
try:
    ok = bool(eval(code, namespace))
except Exception as exc:
    raise SystemExit(f"{label}: assertion raised {exc!r}") from exc
if not ok:
    raise SystemExit(f"{label}: assertion failed: {code}\nPayload: {json.dumps(payload, ensure_ascii=False, indent=2)[:4000]}")
PY
}

assert_file_contains() {
  local path="$1"
  local needle="$2"
  if ! grep -Fq "$needle" "$path"; then
    printf 'smoke: expected %s to contain %s\n' "$path" "$needle" >&2
    exit 1
  fi
}

run uv run python - <<'PY'
import importlib

for module in ["alcove.cli", "fastmcp", "yaml"]:
    importlib.import_module(module)
PY

export ALCOVE_HOME="$home"
alcove home init --json > "$fixtures/home.json"
assert_json "home init" "$fixtures/home.json" "payload['status'] == 'initialized'"

alcove init "$kb" > "$fixtures/kb-init.txt"
test -f "$kb/.alcove/config.yml"
alcove kb add research_notes "$kb" --json > "$fixtures/kb-add.json"
alcove kb list --json > "$fixtures/kb-list.json"
assert_json "kb list" "$fixtures/kb-list.json" "payload[0]['name'] == 'research_notes'"

alcove hub init "$hub" --home "$home" --default-kb research_notes --target codex --json > "$fixtures/hub-init.json"
assert_json "hub init" "$fixtures/hub-init.json" "payload['profile'] == 'hub' and len(payload['files']) >= 2"
alcove hub init "$hub" --home "$home" --default-kb research_notes --target codex --status --json > "$fixtures/hub-status.json"
assert_json "hub status" "$fixtures/hub-status.json" "payload['profile'] == 'hub' and all(item['installed'] and item['workspace_match'] for item in payload['files'])"

alcove global install --home "$home" --target codex --print --json > "$fixtures/global-print.json"
assert_json "global install print" "$fixtures/global-print.json" "payload['profile'] == 'global-lite' and 'codex' in payload['configs']"

alcove kb --home "$home" install research_notes --target codex --json > "$fixtures/kb-install.json"
assert_json "kb install" "$fixtures/kb-install.json" "payload['profile'] == 'managed-kb' and len(payload['files']) >= 2"
alcove kb --home "$home" install research_notes --target codex --status --json > "$fixtures/kb-status.json"
assert_json "kb install status" "$fixtures/kb-status.json" "payload['profile'] == 'managed-kb' and all(item['installed'] and item['workspace_match'] for item in payload['files'])"

alcove inbox --kb research_notes manual-add "Smoke Manual" \
  --content "Smoke inbox body with a local integration needle." \
  --source "smoke://manual" \
  --json > "$fixtures/inbox-add.json"
assert_json "inbox manual add" "$fixtures/inbox-add.json" "payload['status'] == 'added' and payload['id'] == 'manual/smoke-manual'"

alcove inbox --kb research_notes peek --json > "$fixtures/inbox-peek.json"
assert_json "inbox peek" "$fixtures/inbox-peek.json" "payload['title'] == 'Smoke Manual' and payload['content_source'].endswith('note.md')"

alcove inbox --kb research_notes read manual/smoke-manual --json > "$fixtures/inbox-read.json"
assert_json "inbox read" "$fixtures/inbox-read.json" "'local integration needle' in payload['content']"

alcove inbox --kb research_notes note manual/smoke-manual agent-engineering/smoke \
  --summary "Smoke summary from inbox." \
  --tag smoke \
  --selected-takeaways "one,two" \
  --why "Verify inbox note path." \
  --connection "Connects capture to knowledge." \
  --action "Keep script green." \
  --personal-note "Agent-visible note." \
  --validate \
  --json > "$fixtures/inbox-note.json"
assert_json "inbox note" "$fixtures/inbox-note.json" "payload['archive'] and payload['source'] and payload['concept']"

alcove knowledge --kb research_notes note-source \
  --platform web \
  --title "Smoke Source" \
  --topic agent-engineering/smoke \
  --resource "https://example.test/smoke" \
  --summary "Smoke source summary." \
  --tag smoke > "$fixtures/note-source.txt"
assert_file_contains "$fixtures/note-source.txt" "source:"

alcove knowledge --kb research_notes add-note agent-engineering/smoke "Smoke Concept" \
  --summary "Smoke concept summary." \
  --tag smoke > "$fixtures/add-note.json"
assert_json "knowledge add note" "$fixtures/add-note.json" "payload['status'] == 'noted'"
alcove knowledge --kb research_notes revise concepts/agent-engineering/smoke/smoke-concept.md \
  --summary "Smoke concept revised summary." \
  --append "Smoke revision note from AI discussion." \
  --tag revised \
  --reason "smoke revision" \
  --json > "$fixtures/revise-note.json"
assert_json "knowledge revise" "$fixtures/revise-note.json" "payload['status'] == 'revised'"

alcove knowledge --kb research_notes add-note agent-engineering/okf "OKF 知识库检索原则" \
  --summary "本地个人知识库 OKF 相关的知识数据应该先通过 Alcove search 发现候选，再检查 OKF concept/source、mount refs 和 connector fetch refs。" \
  --tag okf \
  --tag 知识库 > "$fixtures/add-okf-note.json"
assert_json "knowledge add okf note" "$fixtures/add-okf-note.json" "payload['status'] == 'noted'"

alcove search --kb research_notes "Smoke" --limit 20 --json > "$fixtures/kb-search.json"
assert_json "kb search" "$fixtures/kb-search.json" "any(row['title'] == 'Smoke Concept' for row in payload) and any(row['title'] == 'Smoke Source' for row in payload)"

alcove knowledge --kb research_notes note-source \
  --platform web \
  --title "Cleanup Source" \
  --topic agent-engineering/smoke \
  --resource "https://example.test/cleanup" \
  --summary "Cleanup obsolete needle." \
  --tag cleanup > "$fixtures/cleanup-source.txt"
assert_file_contains "$fixtures/cleanup-source.txt" "source:"
alcove search --kb research_notes "Cleanup obsolete" --type Source --json > "$fixtures/cleanup-search.json"
assert_json "cleanup search lifecycle fields" "$fixtures/cleanup-search.json" \
  "payload[0]['title'] == 'Cleanup Source' and payload[0]['collected_at'] and payload[0]['published_at'] == '' and payload[0]['deleted_at'] == ''"
alcove knowledge --kb research_notes delete sources/web/agent-engineering/cleanup-source.md \
  --json > "$fixtures/cleanup-delete-preview.json"
assert_json "cleanup delete preview" "$fixtures/cleanup-delete-preview.json" \
  "payload['status'] == 'preview' and payload['confirm_required']"
alcove knowledge --kb research_notes delete sources/web/agent-engineering/cleanup-source.md \
  --reason "confirmed obsolete from search result" \
  --confirm \
  --json > "$fixtures/cleanup-delete-confirm.json"
assert_json "cleanup delete confirm" "$fixtures/cleanup-delete-confirm.json" \
  "payload['status'] == 'deleted' and payload['deleted_at'] and any(item['action'] == 'deleted_single_source_concept' for item in payload['related_actions'])"
alcove search --kb research_notes "Cleanup obsolete" --json > "$fixtures/cleanup-search-after-delete.json"
assert_json "cleanup default search hides deleted" "$fixtures/cleanup-search-after-delete.json" "payload == []"
alcove search --kb research_notes "Cleanup obsolete" --status deleted --json > "$fixtures/cleanup-search-deleted.json"
assert_json "cleanup deleted audit search" "$fixtures/cleanup-search-deleted.json" \
  "any(row['title'] == 'Cleanup Source' and row['status'] == 'deleted' and row['deleted_at'] for row in payload)"

alcove pin --home "$home" add "Smoke Pin" \
  --summary "Pin summary." \
  --content "Pin body smoke needle." \
  --kind regular \
  --tag smoke \
  --json > "$fixtures/pin-add.json"
assert_json "pin add" "$fixtures/pin-add.json" "payload['pin']['title'] == 'Smoke Pin'"

alcove pin --home "$home" search "smoke needle" --json > "$fixtures/pin-search.json"
assert_json "pin search" "$fixtures/pin-search.json" "payload[0]['title'] == 'Smoke Pin'"

alcove pin --home "$home" add "常用收藏：OKF 知识库采集" \
  --summary "中英混合常用收藏，用于本地个人知识库 OKF 查询和复用。" \
  --content "查一下本地个人知识库 OKF 相关的知识数据。Use Alcove search as candidate discovery, then inspect OKF source refs and connector refs." \
  --kind regular \
  --tag 收藏 \
  --tag okf \
  --json > "$fixtures/multilingual-pin-add.json"
assert_json "multilingual pin add" "$fixtures/multilingual-pin-add.json" \
  "payload['pin']['title'].startswith('常用收藏') and payload['pin']['kind'] == 'regular'"

alcove prompt --home "$home" save "Smoke Prompt" \
  --description "Prompt smoke description." \
  --content "Review this smoke feature for missing tests." \
  --tag smoke \
  --json > "$fixtures/prompt-save.json"
assert_json "prompt save" "$fixtures/prompt-save.json" "payload['prompt']['title'] == 'Smoke Prompt'"

alcove prompt --home "$home" search "missing tests" --json > "$fixtures/prompt-search.json"
assert_json "prompt search" "$fixtures/prompt-search.json" "payload[0]['title'] == 'Smoke Prompt'"

project_dir="$tmp_root/project-alpha"
mkdir -p "$project_dir"
alcove project --home "$home" add project-alpha "$project_dir" --note "Smoke project alias" --json > "$fixtures/project-add.json"
alcove project --home "$home" find alpha --json > "$fixtures/project-find.json"
assert_json "project find" "$fixtures/project-find.json" "payload['projects'][0]['alias'] == 'project-alpha'"

alcove task --home "$home" add "Smoke Task" --notes "Task smoke needle." --tag smoke --priority high --due 2026-07-10 --json > "$fixtures/task-add.json"
alcove task --home "$home" add "TODO：实践 Apple Notes connector 增量更新" \
  --notes "以后找机会细化深入了解 Apple Notes connector 增量更新、删除同步、修改同步。" \
  --tag todo \
  --tag connector \
  --json > "$fixtures/multilingual-task-add.json"
alcove idea --home "$home" add "Smoke Idea" --notes "Idea smoke needle." --tag smoke --json > "$fixtures/idea-add.json"
alcove task --home "$home" routine-add "Smoke Routine" --notes "Routine smoke needle." --tag smoke --every-days 7 --next-due 2026-07-10 --json > "$fixtures/routine-add.json"
alcove task --home "$home" materialize-due --today 2026-07-10 --json > "$fixtures/materialize-due.json"
assert_json "materialize due" "$fixtures/materialize-due.json" "payload['status'] == 'materialized' and len(payload['created']) >= 1"

mount_dir="$tmp_root/mounted-repo"
mkdir -p "$mount_dir/docs"
printf '# Mounted Smoke\n\nMounted search smoke needle.\n' > "$mount_dir/docs/smoke.md"
alcove mount --home "$home" add "$mount_dir" --name mounted-smoke --type local-folder --tag smoke --json > "$fixtures/mount-add.json"
alcove mount --home "$home" scan mounted-smoke --json > "$fixtures/mount-scan.json"
assert_json "mount scan" "$fixtures/mount-scan.json" "payload['items'][0]['title'] == 'Mounted Smoke'"

stars="$fixtures/github-stars.json"
write_json "$stars" '[
  {
    "full_name": "octopusgarage/alcove",
    "html_url": "https://github.com/OctopusGarage/alcove",
    "description": "Local-first smoke knowledge core.",
    "language": "Python",
    "topics": ["smoke", "pkm"],
    "stargazers_count": 123,
    "updated_at": "2026-07-10T00:00:00Z"
  }
]'
alcove connector --home "$home" github-stars index "$stars" --tag smoke --include-items --json > "$fixtures/github-stars-index.json"
assert_json "github stars index" "$fixtures/github-stars-index.json" "payload['scanned'] == 1 and payload['items'][0]['title'] == 'octopusgarage/alcove'"

bookmarks="$fixtures/chrome-bookmarks.json"
write_json "$bookmarks" '{
  "roots": {
    "bookmark_bar": {
      "type": "folder",
      "name": "Bookmarks Bar",
      "children": [
        {
          "type": "url",
          "name": "Smoke Bookmark",
          "url": "https://example.com/smoke-bookmark",
          "date_added": "13300000000000000"
        }
      ]
    }
  }
}'
alcove connector --home "$home" chrome-bookmarks index "$bookmarks" --tag smoke --include-items --json > "$fixtures/chrome-bookmarks-index.json"
assert_json "chrome bookmarks index" "$fixtures/chrome-bookmarks-index.json" "payload['scanned'] == 1 and payload['items'][0]['title'] == 'Smoke Bookmark'"

apple_export="$fixtures/apple-notes-export"
mkdir -p "$apple_export/notes/x-coredata%3A%2F%2Fsmoke-note"
write_json "$apple_export/notes/x-coredata%3A%2F%2Fsmoke-note/note.json" '{
  "id": "x-coredata://smoke-note",
  "title": "Smoke Apple Note",
  "account": "iCloud",
  "folder_path": "iCloud/Smoke",
  "created_at": "2026-07-10T08:00:00Z",
  "updated_at": "2026-07-10T09:00:00Z",
  "plaintext": "Apple Notes smoke needle.",
  "body_html": "<div>Apple Notes smoke needle.</div>"
}'
alcove connector --home "$home" apple-notes index "$apple_export" --tag smoke --include-items --json > "$fixtures/apple-notes-index.json"
assert_json "apple notes index" "$fixtures/apple-notes-index.json" "payload['scanned'] == 1 and payload['items'][0]['title'] == 'Smoke Apple Note'"
alcove search --home "$home" "Apple Notes smoke needle" --json > "$fixtures/apple-notes-search.json"
assert_json "apple notes search" "$fixtures/apple-notes-search.json" "payload[0]['type'] == 'Apple Note' and payload[0]['title'] == 'Smoke Apple Note'"
apple_fetch_ref="$(
  uv run python - "$fixtures/apple-notes-search.json" <<'PY'
import json
import sys
from pathlib import Path

rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(rows[0]["fetch_ref"])
PY
)"
alcove connector --home "$home" fetch "$apple_fetch_ref" --json > "$fixtures/apple-notes-fetch.json"
assert_json "apple notes fetch" "$fixtures/apple-notes-fetch.json" "payload['status'] == 'fetched' and payload['item']['title'] == 'Smoke Apple Note'"

alcove connector --home "$home" fetch "connectors/github-stars#octopusgarage/alcove" --json > "$fixtures/connector-fetch.json"
assert_json "connector fetch" "$fixtures/connector-fetch.json" "payload['item']['title'] == 'octopusgarage/alcove'"

alcove search --home "$home" "smoke bookmark" --json > "$fixtures/chrome-bookmarks-search.json"
assert_json "chrome bookmarks search" "$fixtures/chrome-bookmarks-search.json" "payload[0]['type'] == 'Chrome Bookmark'"

alcove okf --home "$home" catalog build --json > "$fixtures/okf-catalog.json"
assert_json "okf catalog" "$fixtures/okf-catalog.json" \
  "payload['status'] == 'built' and 'search-map.md' in payload['files'] and Path(payload['root'], 'index.md').is_file()"
alcove health --home "$home" --kb research_notes --fix --json > "$fixtures/health.json"
assert_json "health" "$fixtures/health.json" \
  "payload['status'] in {'ok', 'warnings'} and 'issues' in payload and 'actions' in payload"

alcove link --kb research_notes source "connectors/github-stars#octopusgarage/alcove" agent-engineering/smoke \
  --summary "Linked GitHub star smoke item." \
  --json > "$fixtures/link-source.json"
assert_json "link source" "$fixtures/link-source.json" "payload['status'] == 'linked'"

alcove search --home "$home" "smoke needle" --json > "$fixtures/global-search.json"
assert_json "global search" "$fixtures/global-search.json" "len(payload) >= 3"
alcove search --home "$home" "本地个人知识库 OKF" --json > "$fixtures/multilingual-knowledge-search.json"
assert_json "multilingual knowledge search" "$fixtures/multilingual-knowledge-search.json" \
  "any(row.get('type') == 'Pin' and 'OKF' in row.get('title', '') for row in payload) and any(row.get('root') == 'knowledge' and 'OKF' in row.get('title', '') for row in payload)"
alcove search --home "$home" "Apple Notes connector 增量更新" --json > "$fixtures/multilingual-todo-search.json"
assert_json "multilingual todo search" "$fixtures/multilingual-todo-search.json" \
  "any(row.get('type') == 'Task' and 'Apple Notes connector' in row.get('title', '') for row in payload)"
run uv run python - "$fixtures" <<'PY'
import json
import sys
from pathlib import Path

fixtures = Path(sys.argv[1])
examples = {
    "status": "passed",
    "examples": [
        {
            "utterance": "查一下本地的个人知识库，关于OKF相关的知识数据，汇总总结一下",
            "expected_read_path": "Home-wide search first, then AI-led inspection of OKF/source/mount/connector refs.",
            "evidence_fixture": "multilingual-knowledge-search.json",
        },
        {
            "utterance": "这个链接加入常用收藏，后续反复查",
            "expected_write_path": "Search existing pins first, then governed pin add/update.",
            "evidence_fixture": "multilingual-pin-add.json",
        },
        {
            "utterance": "TODO：以后找机会实践 Apple Notes connector 增量更新",
            "expected_write_path": "Governed task add with todo/connector tags.",
            "evidence_fixture": "multilingual-task-add.json",
        },
    ],
}
(fixtures / "intent-routing-examples.json").write_text(
    json.dumps(examples, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

regular="$fixtures/regular.txt"
todo="$fixtures/todo.txt"
printf '# Regular Smoke\n\n## Reference\n\n- regular smoke entry\n' > "$regular"
printf '# Todo\n\n## Practice\n\n- todo smoke entry\n' > "$todo"
alcove dashboard --home "$home" import-pins --regular-file "$regular" --todo-file "$todo" --json > "$fixtures/dashboard-import-pins.json"
alcove okf --home "$home" catalog build --json > "$fixtures/okf-catalog.json"
assert_json "okf catalog after dashboard pin import" "$fixtures/okf-catalog.json" \
  "payload['status'] == 'built' and payload['counts']['pins'] >= 4 and 'search-map.md' in payload['files'] and Path(payload['root'], 'index.md').is_file()"
alcove health --home "$home" --kb research_notes --fix --json > "$fixtures/health.json"
assert_json "health after dashboard pin import" "$fixtures/health.json" \
  "payload['status'] in {'ok', 'warnings'} and payload['counts']['pins'] >= 4"
alcove dashboard --home "$home" build --json > "$fixtures/dashboard-build.json"
assert_json "dashboard build" "$fixtures/dashboard-build.json" "payload['status'] == 'built'"
assert_json "dashboard frontend" "$fixtures/dashboard-build.json" "payload['frontend_mode'] == 'compiled_frontend'"
assert_file_contains "$home/dashboard/snapshot.json" "Regular Smoke"
uv run python - "$home/dashboard/snapshot.json" <<'PY'
import json
import sys

snapshot = json.loads(open(sys.argv[1], encoding="utf-8").read())
usage = snapshot["usage"]
health = snapshot["health"]
assert snapshot["summary"]["counts"]["usage_events"] > 0
assert usage["search"]["total"] > 0
assert usage["search"]["surfaces"].get("cli", 0) > 0
assert usage["actions"]["total"] > 0
assert health["totals"]["managed_kbs"] == 1
assert health["totals"]["mounts"] == 1
assert health["totals"]["connectors"] >= 3
assert health["totals"]["managed_items"] > 0
assert health["totals"]["mount_items"] > 0
assert health["totals"]["connector_items"] > 0
assert health["stats"]["summary_exists"] is True
PY
test -f "$home/stats/summary.json"
test -d "$home/stats/daily"
alcove usage summary --home "$home" --json > "$fixtures/usage-summary.json"
uv run python - "$home/stats/summary.json" <<'PY'
import json
import sys

summary = json.loads(open(sys.argv[1], encoding="utf-8").read())
assert summary["search"]["total"] > 0
assert summary["actions"]["total"] > 0
PY
assert_json "usage summary" "$fixtures/usage-summary.json" "payload['search']['total'] > 0 and payload['actions']['total'] > 0"
uv run python -m alcove.dashboard_render_check \
  --dashboard-root "$home/dashboard" \
  --output-dir "$fixtures/dashboard-render" \
  --json > "$fixtures/dashboard-render.json"
assert_json "dashboard render" "$fixtures/dashboard-render.json" "payload['status'] in {'passed', 'skipped'}"

alcove export --home "$home" all "$export_root/all" --json > "$fixtures/export-all.json"
assert_json "export all" "$fixtures/export-all.json" "payload['type'] == 'all'"
test -f "$export_root/all/global/config.yml"
test -f "$export_root/all/knowledge-bases/research_notes/.alcove/config.yml"

alcove doctor --kb research_notes --json > "$fixtures/doctor.json"
assert_json "doctor" "$fixtures/doctor.json" "payload['status'] in {'ok', 'issues'}"

alcove validate --kb research_notes --json > "$fixtures/validate.json"
assert_json "validate" "$fixtures/validate.json" "'issues' in payload"

run uv run python - "$kb" <<'PY'
from pathlib import Path
import sys

from alcove.markdown import MarkdownDoc, MarkdownRepository

kb = Path(sys.argv[1])
MarkdownRepository().write_doc(
    kb / "knowledge" / "sources" / "web" / "agent-engineering" / "stale-smoke-source.md",
    MarkdownDoc(
        {
            "type": "Source",
            "title": "Stale Smoke Source",
            "topic": "agent-engineering/smoke",
            "status": "active",
            "published_date": "2020-01-01",
            "confidence": 0.2,
            "tags": ["smoke"],
        },
        "# Stale Smoke Source\n\nOld low-confidence source that should be reviewed.\n",
    ),
)
PY
alcove gardener --kb research_notes --json > "$fixtures/gardener.json"
assert_json "gardener" "$fixtures/gardener.json" "'issues' in payload and 'actions' in payload"
assert_json "gardener stale source" "$fixtures/gardener.json" "any(issue.get('kind') == 'stale_source' and issue.get('severity') == 'medium' for issue in payload['issues'])"

run uv run python - "$fixtures" "$report" <<'PY'
import json
import sys
from pathlib import Path

fixtures = Path(sys.argv[1])
report_path = Path(sys.argv[2])
commands = []
for path in sorted(fixtures.glob("*.json")):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        continue
    commands.append({"name": path.stem, "path": str(path), "kind": type(payload).__name__})
report = {
    "status": "passed",
    "fixture_count": len(commands),
    "fixtures": commands,
}
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
PY

printf 'smoke: passed\n'
if [[ "$keep_tmp" == "1" ]]; then
  printf 'smoke: kept tmp root at %s\n' "$tmp_root"
fi
