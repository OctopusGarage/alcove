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
alcove hub init "$hub" --home "$home" --default-kb research_notes --target claude --json > "$fixtures/hub-init-claude.json"
assert_json "hub init claude" "$fixtures/hub-init-claude.json" "payload['profile'] == 'hub' and len(payload['files']) >= 2"
alcove hub init "$hub" --home "$home" --default-kb research_notes --target codex --status --json > "$fixtures/hub-status.json"
assert_json "hub status" "$fixtures/hub-status.json" "payload['profile'] == 'hub' and all(item['installed'] and item['workspace_match'] for item in payload['files'])"
alcove hub init "$hub" --home "$home" --default-kb research_notes --target claude --status --json > "$fixtures/hub-status-claude.json"
assert_json "hub status claude" "$fixtures/hub-status-claude.json" "payload['profile'] == 'hub' and all(item['installed'] and item['workspace_match'] for item in payload['files'])"

alcove global install --home "$home" --target codex --print --json > "$fixtures/global-print.json"
assert_json "global install print" "$fixtures/global-print.json" "payload['profile'] == 'global-lite' and 'codex' in payload['configs']"

alcove kb --home "$home" install research_notes --target codex --json > "$fixtures/kb-install.json"
assert_json "kb install" "$fixtures/kb-install.json" "payload['profile'] == 'managed-kb' and len(payload['files']) >= 2"
alcove kb --home "$home" install research_notes --target claude --json > "$fixtures/kb-install-claude.json"
assert_json "kb install claude" "$fixtures/kb-install-claude.json" "payload['profile'] == 'managed-kb' and len(payload['files']) >= 2"
alcove kb --home "$home" install research_notes --target codex --status --json > "$fixtures/kb-status.json"
assert_json "kb install status" "$fixtures/kb-status.json" "payload['profile'] == 'managed-kb' and all(item['installed'] and item['workspace_match'] for item in payload['files'])"
alcove kb --home "$home" install research_notes --target claude --status --json > "$fixtures/kb-status-claude.json"
assert_json "kb install status claude" "$fixtures/kb-status-claude.json" "payload['profile'] == 'managed-kb' and all(item['installed'] and item['workspace_match'] for item in payload['files'])"

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
  "payload['status'] == 'deleted' and payload['deleted_at'] and any(item['action'] in {'deleted_single_source_concept', 'detached_source_ref'} for item in payload['related_actions'])"
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

fake_notes="$fixtures/fake-apple-notes"
ALCOVE_FAKE_APPLE_NOTES_DIR="$fake_notes" \
  alcove publish --home "$home" init apple-notes --root-folder "iCloud/Alcove" --json > "$fixtures/publisher-init.json"
assert_json "publisher init" "$fixtures/publisher-init.json" \
  "payload['status'] == 'initialized' and set(payload['targets']) == {'pins_regular', 'pins_todo', 'planner_digest', 'prompt_library', 'project_registry'}"
ALCOVE_FAKE_APPLE_NOTES_DIR="$fake_notes" \
  alcove publish --home "$home" run apple-notes --json > "$fixtures/publisher-run.json"
assert_json "publisher run" "$fixtures/publisher-run.json" \
  "payload['status'] == 'success' and payload['updated'] == 5 and payload['errors'] == 0"
ALCOVE_FAKE_APPLE_NOTES_DIR="$fake_notes" \
  alcove publish --home "$home" run apple-notes --json > "$fixtures/publisher-run-unchanged.json"
assert_json "publisher run unchanged" "$fixtures/publisher-run-unchanged.json" \
  "payload['status'] == 'success' and payload['skipped'] == 5"
alcove pin --home "$home" add "Service Tick Publisher Pin" \
  --summary "Publisher service tick smoke." \
  --content "Service tick should refresh due publisher mirrors." \
  --kind regular \
  --tag publisher \
  --json > "$fixtures/publisher-service-pin.json"
run uv run python - "$home" <<'PY'
import sys
from pathlib import Path

import yaml

state_path = Path(sys.argv[1]) / "publishers" / "state" / "apple-notes.yml"
payload = yaml.safe_load(state_path.read_text(encoding="utf-8")) or {}
for target in payload.get("targets", {}).values():
    if isinstance(target, dict):
        target["last_synced_at"] = "2000-01-01T00:00:00+00:00"
state_path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
PY
ALCOVE_FAKE_APPLE_NOTES_DIR="$fake_notes" \
  alcove service tick --home "$home" \
    --skip-connectors \
    --skip-watchers \
    --skip-blogs \
    --skip-radars \
    --skip-automations \
    --skip-health-fix \
    --json > "$fixtures/publisher-service-tick.json"
assert_json "publisher service tick" "$fixtures/publisher-service-tick.json" \
  "payload['status'] == 'ok' and payload['publishers']['ran'] == 1 and payload['publishers']['updated'] >= 1 and payload['publishers']['errors'] == 0"
publisher_failure_home="$tmp_root/publisher-failure-home"
publisher_failure_notes="$fixtures/publisher-failure-notes"
ALCOVE_HOME="$publisher_failure_home" alcove home init --json > "$fixtures/publisher-failure-home.json"
alcove pin --home "$publisher_failure_home" add "Ambiguous Publisher Pin" \
  --summary "Ambiguous target smoke." \
  --kind regular \
  --json > "$fixtures/publisher-failure-pin.json"
ALCOVE_FAKE_APPLE_NOTES_DIR="$publisher_failure_notes" \
  alcove publish --home "$publisher_failure_home" init apple-notes --root-folder "iCloud/Alcove" --json > "$fixtures/publisher-failure-init.json"
run uv run python - "$publisher_failure_notes" <<'PY'
import json
import sys
from pathlib import Path

notes_root = Path(sys.argv[1]) / "notes"
notes_root.mkdir(parents=True, exist_ok=True)
for note_id in ["dup-a", "dup-b"]:
    (notes_root / f"{note_id}.json").write_text(
        json.dumps(
            {
                "note_id": note_id,
                "folder_path": "iCloud/Alcove/pins",
                "title": "Regular Pins",
                "body": "",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
PY
ALCOVE_FAKE_APPLE_NOTES_DIR="$publisher_failure_notes" \
  alcove publish --home "$publisher_failure_home" run apple-notes --target pins_regular --json > "$fixtures/publisher-run-ambiguous.json"
assert_json "publisher ambiguous target" "$fixtures/publisher-run-ambiguous.json" \
  "payload['status'] == 'partial' and payload['errors'] == 1 and payload['targets'][0]['status'] == 'failed' and payload['targets'][0]['error_code'] == 'TARGET_AMBIGUOUS' and 'Multiple notes match' in payload['targets'][0]['error'] and payload['targets'][0]['remediation_hint'] and len(payload['targets'][0]['details']['candidates']) == 2 and payload['targets'][0]['details']['candidates'][0]['note_id']"
test -f "$home/publishers/renders/pins_regular.md"
test -f "$home/publishers/renders/pins_todo.md"
test -f "$home/publishers/renders/planner_digest.md"
test -f "$home/publishers/renders/prompt_library.md"
test -f "$home/publishers/renders/project_registry.md"
assert_file_contains "$home/publishers/renders/pins_regular.md" "Smoke Pin"
assert_file_contains "$home/publishers/renders/planner_digest.md" "Planner Digest"
assert_file_contains "$home/publishers/renders/prompt_library.md" "Prompt Library"
assert_file_contains "$home/publishers/renders/project_registry.md" "Project Registry"
test -f "$home/publishers/state/apple-notes.yml"
test "$(find "$fake_notes/notes" -type f -name '*.json' | wc -l | tr -d ' ')" -eq 5
run uv run python - "$home" "$fixtures/publisher-render-quality.json" <<'PY'
import json
import sys
from pathlib import Path

from alcove.publishers import _markdown_as_html

home = Path(sys.argv[1])
output = Path(sys.argv[2])
targets = [
    "pins_regular",
    "pins_todo",
    "planner_digest",
    "prompt_library",
    "project_registry",
]
emoji_headers = {
    "pins_regular": "# 📌 Regular Pins",
    "pins_todo": "# ✅ TODO Pins",
    "planner_digest": "# 🧭 Planner Digest",
    "prompt_library": "# 🧰 Prompt Library",
    "project_registry": "# 🗂 Project Registry",
}
checks = []
for target in targets:
    markdown = (home / "publishers" / "renders" / f"{target}.md").read_text(encoding="utf-8")
    html = _markdown_as_html(markdown)
    legacy_noise = [
        "Summary: 📝",
        "Content: 📄",
        "Description: 📝",
        "Use cases: 🎯",
        "Tags: 🏷️",
        "Path: 📍",
        "Exists: ✅",
        "Note: 📝",
    ]
    checks.append(
        {
            "target": target,
            "markdown_has_sections": "## " in markdown or "No active" in markdown or "No registered" in markdown,
            "html_has_heading_style": "font-size: 24px" in html,
            "html_has_section_style": "font-size: 18px" in html or "No active" in markdown or "No registered" in markdown,
            "html_has_item_blocks": "margin: 8px 0 4px 0" in html or "No active" in markdown or "No registered" in markdown,
            "html_has_indented_details": "margin-left: 22px" in html or "No active" in markdown or "No registered" in markdown,
            "html_has_emphasis": "<b>" in html,
            "raw_markdown_heading_absent": "# " not in html and "## " not in html,
            "has_emoji_header": emoji_headers[target] in markdown,
            "has_divider_blocks": "\n---\n" in markdown and "────────────" in html,
            "pins_avoid_detail_dump": not target.startswith("pins_") or "Detail:" not in markdown,
            "pins_content_block": target != "pins_regular" or "Notes" in markdown,
            "pins_no_table_spam": not target.startswith("pins_") or "Table:" not in markdown,
            "pins_preserve_long_details": not target.startswith("pins_")
            or "Outline  " not in markdown
            or "Full notes" in markdown,
            "no_legacy_field_noise": not any(token in markdown for token in legacy_noise),
            "line_count": len(markdown.splitlines()),
        }
    )
payload = {
    "status": "passed"
    if all(
        item["markdown_has_sections"]
        and item["html_has_heading_style"]
        and item["html_has_section_style"]
        and item["html_has_item_blocks"]
        and item["html_has_indented_details"]
        and item["html_has_emphasis"]
        and item["raw_markdown_heading_absent"]
        and item["has_emoji_header"]
        and item["has_divider_blocks"]
        and item["pins_avoid_detail_dump"]
        and item["pins_content_block"]
        and item["pins_no_table_spam"]
        and item["pins_preserve_long_details"]
        and item["no_legacy_field_noise"]
        for item in checks
    )
    else "failed",
    "checks": checks,
}
output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
if payload["status"] != "passed":
    raise SystemExit(json.dumps(payload, ensure_ascii=False, indent=2))
PY

alcove pin --home "$home" add "常用收藏：OKF 知识库采集" \
  --summary "中英混合常用收藏，用于本地个人知识库 OKF 查询和复用。" \
  --content "查一下本地个人知识库 OKF 相关的知识数据。Use Alcove search as candidate discovery, then inspect OKF source refs and connector refs." \
  --kind regular \
  --tag 收藏 \
  --tag okf \
  --json > "$fixtures/multilingual-pin-add.json"
assert_json "multilingual pin add" "$fixtures/multilingual-pin-add.json" \
  "payload['pin']['title'].startswith('常用收藏') and payload['pin']['kind'] == 'regular'"

alcove prompt --home "$home" propose "Smoke Prompt" \
  --description "Review a smoke-tested feature for missing verification and regression risk." \
  --content "Review this smoke-tested feature for correctness, missing tests, regression risk, and unclear user-facing behavior. Use the current diff, smoke artifacts, and expected workflow as evidence before reporting findings." \
  --kind eval_prompt \
  --domain testing \
  --intent review \
  --surface codex \
  --surface claude-code \
  --trigger "missing tests" \
  --input "diff" \
  --input "smoke artifacts" \
  --output "findings" \
  --output "verification gaps" \
  --use-case "Smoke regression review" \
  --tag smoke \
  --json > "$fixtures/prompt-propose.json"
assert_json "prompt propose" "$fixtures/prompt-propose.json" \
  "payload['request']['title'] == 'Smoke Prompt' and payload['action'] in {'create_new', 'create_new_after_review'} and payload['similar'] == []"
proposal_id="$(uv run python - "$fixtures/prompt-propose.json" <<'PY'
import json
import sys
print(json.loads(open(sys.argv[1], encoding="utf-8").read())["id"])
PY
)"
alcove prompt --home "$home" proposal "$proposal_id" \
  --json > "$fixtures/prompt-proposal.json"
assert_json "prompt proposal" "$fixtures/prompt-proposal.json" \
  "payload['id'] and payload['request']['outputs']"
alcove prompt --home "$home" save --proposal-id "$proposal_id" \
  --json > "$fixtures/prompt-save.json"
assert_json "prompt save" "$fixtures/prompt-save.json" \
  "payload['prompt']['title'] == 'Smoke Prompt' and payload['prompt']['domain'] == 'testing' and payload['prompt']['outputs']"

alcove prompt --home "$home" search "missing tests" --json > "$fixtures/prompt-search.json"
assert_json "prompt search" "$fixtures/prompt-search.json" "payload[0]['title'] == 'Smoke Prompt'"
alcove prompt --home "$home" recommend "review this smoke-tested feature for missing tests" --json > "$fixtures/prompt-recommend.json"
assert_json "prompt recommend" "$fixtures/prompt-recommend.json" \
  "payload[0]['prompt']['title'] == 'Smoke Prompt' and payload[0]['score'] > 0"
alcove prompt --home "$home" compose "review this smoke-tested feature for missing tests" --json > "$fixtures/prompt-compose.json"
assert_json "prompt compose" "$fixtures/prompt-compose.json" \
  "payload['sources'][0]['title'] == 'Smoke Prompt' and 'Smoke Prompt' in payload['prompt']"

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
alcove task --home "$home" digest --today 2026-07-12 --json > "$fixtures/task-digest.json"
assert_json "task digest readable" "$fixtures/task-digest.json" \
  "payload['counts']['tasks'] >= 2 and payload['counts']['ideas'] >= 1 and payload['counts']['routines'] >= 1 and payload['title'] not in payload['text'] and '[task:' not in payload['text'] and '[idea:' not in payload['text'] and '[routine:' not in payload['text'] and '✅ Pending tasks' in payload['text'] and '💡 Ideas' in payload['text'] and '🔁 Active routines' in payload['text'] and 'Overdue:' in payload['text']"

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

radar_fixture="$fixtures/radar-items.json"
write_json "$radar_fixture" '[
  {
    "title": "Sports analytics smoke radar",
    "url": "https://example.test/sports-radar",
    "summary": "NBA tactical analysis for radar smoke.",
    "tags": ["NBA", "analytics"]
  }
]'
run uv run python - "$home" "$radar_fixture" <<'PY'
import sys
from pathlib import Path

from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSource

home = AlcoveHome.init(Path(sys.argv[1]))
fixture = Path(sys.argv[2])
RadarModule(home).upsert_definition(
    RadarDefinition(
        id="sports-news",
        name="Sports News",
        sources=[
            RadarSource(
                id="fixture",
                adapter="fixture",
                params={"path": str(fixture)},
            )
        ],
        profile={"interest_tags": ["NBA", "analytics"], "min_score_threshold": 0.5},
        report={"formats": ["md"]},
    )
)
PY
alcove radar --home "$home" list --json > "$fixtures/radar-list.json"
assert_json "radar list" "$fixtures/radar-list.json" "any(row['id'] == 'sports-news' for row in payload['definitions'])"
alcove radar --home "$home" run sports-news --json > "$fixtures/radar-run.json"
assert_json "radar run" "$fixtures/radar-run.json" "payload['status'] == 'completed' and payload['included'] == 1 and payload['reports']['md']"
alcove radar --home "$home" status sports-news --json > "$fixtures/radar-status.json"
assert_json "radar status" "$fixtures/radar-status.json" "payload['radars'][0]['id'] == 'sports-news' and payload['radars'][0]['last_run']"

run uv run python - "$home" "$kb" "$fixtures" <<'PY'
import json
import re
import sys
from pathlib import Path
from types import MethodType

from alcove.blog_monitor import BlogMonitorModule
from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug

home = AlcoveHome.init(Path(sys.argv[1]))
kb = Path(sys.argv[2])
fixtures = Path(sys.argv[3])
module = BlogMonitorModule(home)
page = (fixtures / "blog-monitor.html").resolve()


def write_page(links):
    anchors = "\n".join(f'<a href="{href}">{title}</a>' for href, title in links)
    page.write_text(f"<html><body>{anchors}</body></html>", encoding="utf-8")


write_page([("https://example.test/blog/one", "First Blog Article")])
module.add(
    name="Blog Smoke Success",
    url=page.as_uri(),
    source_id="blog-success",
    link_pattern="/blog/",
    capture_enabled=True,
    kb="research_notes",
    inbox_path="inbox/blog-smoke",
    notify_enabled=True,
)
module.seed(source_id="blog-success")
write_page(
    [
        ("https://example.test/blog/one", "First Blog Article"),
        ("https://example.test/blog/two", "Second Blog Article"),
    ]
)


def fake_capture(self, source, article):
    target = kb / source.capture.inbox_path / normalize_slug(article.title)
    target.mkdir(parents=True, exist_ok=True)
    (target / "summary.md").write_text(
        "# Summary\n\nSecond article summary for blog monitor smoke.\n",
        encoding="utf-8",
    )
    return {
        "status": "captured",
        "adapter": "fixture",
        "inbox_path": str(target),
        "summary_file": str(target / "summary.md"),
    }


def fake_article_notify(self, source, articles, captures, summary):
    messages = []
    for article in articles:
        messages.append(
            {
                "status": "sent",
                "http_status": 200,
                "attempts": 1,
                "source_id": source.id,
                "source_name": source.name,
                "article_title": article.title,
                "article_url": article.url,
            }
        )
    return {"status": "sent", "sent_count": len(messages), "messages": messages}


def fake_failure_notify(self, source, *, stage, error):
    text = f"Error: {error}\nSource ID: {source.id}\nStage: {stage}\nRetry: <code>alcove blog check {source.id} --json</code>"

    def code_value(label):
        match = re.search(rf"{label}: <code>([^<]+)</code>", text)
        return match.group(1) if match else ""

    def line_value(label):
        match = re.search(rf"{label}: ([^\n]+)", text)
        return match.group(1).strip() if match else ""

    return {
        "status": "sent",
        "http_status": 200,
        "attempts": 1,
        "text_excerpt": text[:180],
        "source_id": line_value("Source ID"),
        "stage": line_value("Stage"),
        "error": line_value("Error"),
        "retry_command": code_value("Retry"),
    }


module._capture_article = MethodType(fake_capture, module)
module._notify = MethodType(fake_article_notify, module)
module._notify_failure = MethodType(fake_failure_notify, module)
(home.root / ".env").write_text(
    "ALCOVE_TELEGRAM_BOT_TOKEN=smoke-token\nALCOVE_TELEGRAM_CHAT_ID=smoke-chat\n",
    encoding="utf-8",
)
success = module.check(source_id="blog-success", now="2026-07-12T00:00:00+00:00")

module.add(
    name="Blog Smoke Failure",
    url=page.as_uri(),
    source_id="blog-failure",
    link_pattern="/blog/",
    notify_enabled=True,
)
original_discover = module._discover


def fake_discover(self, source):
    if source.id == "blog-failure":
        raise RuntimeError("fixture discovery failed")
    return original_discover(source)


module._discover = MethodType(fake_discover, module)
failure = module.check(source_id="blog-failure", now="2026-07-12T00:05:00+00:00")

payload = {
    "status": "passed",
    "success": success,
    "failure": failure,
    "events": [
        json.loads(line)
        for line in (home.root / "blog-monitor/events.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ],
    "run_files": sorted(
        str(path.relative_to(home.root))
        for path in (home.root / "blog-monitor/runs").glob("*.json")
    ),
}
(fixtures / "blog-monitor-smoke.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
assert_json "blog monitor success and failure" "$fixtures/blog-monitor-smoke.json" \
  "payload['success']['sources'][0]['status'] == 'changed' and payload['success']['captured'] == 1 and payload['success']['sources'][0]['notify']['status'] == 'sent' and payload['failure']['errors'] == 1 and payload['failure']['sources'][0]['stage'] == 'discovery'"

alcove okf --home "$home" catalog build --json > "$fixtures/okf-catalog.json"
assert_json "okf catalog" "$fixtures/okf-catalog.json" \
  "payload['status'] == 'built' and 'search-map.md' in payload['files'] and (Path(payload['root']).expanduser() / 'index.md').is_file()"
alcove health --home "$home" --kb research_notes --fix --fixture-context --json > "$fixtures/health.json"
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
  "payload['status'] == 'built' and payload['counts']['pins'] >= 4 and 'search-map.md' in payload['files'] and (Path(payload['root']).expanduser() / 'index.md').is_file()"
alcove health --home "$home" --kb research_notes --fix --fixture-context --json > "$fixtures/health.json"
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
