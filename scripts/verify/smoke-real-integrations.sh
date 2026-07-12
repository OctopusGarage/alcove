#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

root="${ALCOVE_REAL_INTEGRATION_DIR:-$repo_root/.tmp/real-integrations}"
case "$root" in
  /*) ;;
  *) root="$repo_root/$root" ;;
esac
home="$root/home"
kb="$root/kb"
state_dir="$root/clipsmith-state"
web_output="$root/clipsmith-web-output"
web_url="${ALCOVE_REAL_WEB_URL:-https://octopusgarage.github.io/clipsmith/}"
stars_source="${ALCOVE_REAL_GITHUB_STARS_SOURCE:-https://github.com/octocat?tab=stars}"
clipsmith_bin="${ALCOVE_CLIPSMITH_BIN:-clipsmith}"
clipsmith_root="${ALCOVE_CLIPSMITH_ROOT:-}"
if [[ -z "$clipsmith_root" && -d "$repo_root/../clipsmith/skills/clipsmith-web" ]]; then
  clipsmith_root="$(cd "$repo_root/../clipsmith" && pwd)"
fi
clipsmith_web_skill="$clipsmith_root/skills/clipsmith-web"
clipsmith_ocr_skill="$clipsmith_root/skills/clipsmith-ocr"

run() {
  printf 'real-integration: %s\n' "$*" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
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
try:
    ok = bool(eval(code, {"payload": payload, "Path": Path}))
except Exception as exc:
    raise SystemExit(f"{label}: assertion raised {exc!r}") from exc
if not ok:
    raise SystemExit(
        f"{label}: assertion failed: {code}\n"
        f"Payload: {json.dumps(payload, ensure_ascii=False, indent=2)[:4000]}"
    )
PY
}

rm -rf "$root"
mkdir -p "$root" "$state_dir" "$web_output"

if ! command -v "$clipsmith_bin" >/dev/null 2>&1; then
  printf 'real-integration: clipsmith CLI not found; set ALCOVE_CLIPSMITH_BIN or install Clipsmith\n' >&2
  exit 1
fi

if [[ -z "$clipsmith_root" || ! -f "$clipsmith_web_skill/scripts/run.ts" || ! -f "$clipsmith_ocr_skill/scripts/run.ts" ]]; then
  printf 'real-integration: Clipsmith source checkout not found.\n' >&2
  printf 'real-integration: clone it as ../clipsmith or set ALCOVE_CLIPSMITH_ROOT=/path/to/clipsmith\n' >&2
  exit 1
fi

export ALCOVE_HOME="$home"
alcove home init --json > "$root/home-init.json"
alcove init "$kb" > "$root/kb-init.txt"
alcove kb add real_integration_kb "$kb" --json > "$root/kb-add.json"
alcove kb --home "$home" install real_integration_kb --target codex --json > "$root/kb-install.json"

failure_dir="$root/connector-failures"
mkdir -p "$failure_dir"
set +e
alcove connector --home "$home" github-stars import-url "https://example.com/octocat?tab=stars" \
  --json > "$failure_dir/github-stars-invalid-url.stdout" \
  2> "$failure_dir/github-stars-invalid-url.stderr"
github_invalid_status=$?
printf '{"not":"a chrome bookmarks export"\n' > "$failure_dir/malformed-bookmarks.json"
alcove connector --home "$home" chrome-bookmarks index "$failure_dir/malformed-bookmarks.json" \
  --json > "$failure_dir/chrome-bookmarks-malformed.stdout" \
  2> "$failure_dir/chrome-bookmarks-malformed.stderr"
chrome_malformed_status=$?
set -e
run uv run python - "$failure_dir" "$github_invalid_status" "$chrome_malformed_status" "$root/connector-failure-samples.json" <<'PY'
import json
import sys
from pathlib import Path

failure_dir = Path(sys.argv[1])
github_invalid_status = int(sys.argv[2])
chrome_malformed_status = int(sys.argv[3])
report_path = Path(sys.argv[4])

def sample(name: str, exit_code: int) -> dict:
    stdout = (failure_dir / f"{name}.stdout").read_text(encoding="utf-8").strip()
    stderr = (failure_dir / f"{name}.stderr").read_text(encoding="utf-8").strip()
    parsed = None
    try:
        parsed = json.loads(stdout) if stdout else None
    except json.JSONDecodeError:
        parsed = None
    structured = isinstance(parsed, dict) and isinstance(parsed.get("error"), dict)
    return {
        "name": name,
        "exit_code": exit_code,
        "status": "passed"
        if exit_code != 0
        and (
            structured
            or "alcove: " in stderr
        )
        else "failed",
        "structured_json": structured,
        "error": parsed.get("error") if structured else None,
        "stderr": stderr,
        "stdout": stdout,
    }

samples = [
    sample("github-stars-invalid-url", github_invalid_status),
    sample("chrome-bookmarks-malformed", chrome_malformed_status),
]
payload = {
    "status": "passed" if all(item["status"] == "passed" for item in samples) else "failed",
    "samples": samples,
}
report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
if payload["status"] != "passed":
    raise SystemExit("connector failure samples did not return controlled errors")
PY

set +e
alcove connector --home "$home" github-stars import-url "$stars_source" \
  --tag github-stars \
  --json > "$root/github-stars-import.json"
github_status=$?
set -e
if [[ "$github_status" -ne 0 ]]; then
  printf 'real-integration: GitHub Stars live import failed; using local fixture fallback\n' >&2
  github_fallback="$root/github-stars-fallback.json"
  cat > "$github_fallback" <<'JSON'
[
  {
    "full_name": "octopusgarage/alcove",
    "html_url": "https://github.com/OctopusGarage/alcove",
    "description": "Local-first personal knowledge workbench.",
    "language": "Python",
    "topics": ["pkm", "agent"],
    "stargazers_count": 42,
    "updated_at": "2026-07-10T00:00:00Z"
  },
  {
    "full_name": "OctopusGarage/codegraph",
    "html_url": "https://github.com/OctopusGarage/codegraph",
    "description": "Codebase knowledge graph for agentic code exploration.",
    "language": "Python",
    "topics": ["codegraph", "agents"],
    "stargazers_count": 100,
    "updated_at": "2026-07-10T00:00:00Z"
  }
]
JSON
  alcove connector --home "$home" github-stars index "$github_fallback" \
    --tag github-stars \
    --json > "$root/github-stars-import.json"
  run uv run python - "$home" "$stars_source" "$github_fallback" "$root/github-stars-import.json" <<'PY'
import json
import sys
from pathlib import Path

from alcove.connector_sources import ConnectorSourceRegistry
from alcove.home import AlcoveHome

home = AlcoveHome(Path(sys.argv[1]))
source = sys.argv[2]
export_file = Path(sys.argv[3])
report_path = Path(sys.argv[4])
report = json.loads(report_path.read_text(encoding="utf-8"))
scanned = int(report.get("scanned") or 0)
registry = ConnectorSourceRegistry(home=home)
registry.upsert_github_stars(
    source_id="octocat",
    source=source,
    username="octocat",
    tags=["github-stars"],
    export_file=export_file,
    index_path=home.paths().connectors / "github-stars" / "index.json",
    item_count=scanned,
    status="fresh",
    error="live GitHub import failed during smoke; local fixture fallback used",
)
report.update(
    {
        "source": source,
        "username": "octocat",
        "exported": scanned,
        "network_fallback": True,
        "fallback_reason": "live GitHub import failed during smoke",
    }
)
report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
fi
assert_json "github stars import" "$root/github-stars-import.json" \
  "payload['exported'] > 0 and payload['scanned'] > 0"

alcove search --home "$home" --type "GitHub Star" --json \
  > "$root/github-stars-search.json"
assert_json "github stars search" "$root/github-stars-search.json" \
  "len(payload) > 0 and all(row.get('type') == 'GitHub Star' for row in payload)"
github_search_query="$(
  uv run python - "$root/github-stars-search.json" <<'PY'
import json
import sys
from pathlib import Path

rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
title = str(rows[0].get("title") or "").strip()
if not title:
    raise SystemExit("first GitHub Star search result has no title")
print(title)
PY
)"

alcove connector --home "$home" apple-notes import-local \
  --tag apple-notes \
  --json > "$root/apple-notes-import-local.json"
assert_json "apple notes import" "$root/apple-notes-import-local.json" \
  "payload['exported'] >= 0 and payload['scanned'] >= 0"

alcove search --home "$home" --type "Apple Note" --json > "$root/apple-notes-search.json"
assert_json "apple notes search" "$root/apple-notes-search.json" "isinstance(payload, list)"
run uv run python - "$root/apple-notes-search.json" "$root/apple-notes-fetch-target.txt" <<'PY'
import json
import sys
from pathlib import Path

rows = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
target = ""
for row in rows:
    if isinstance(row, dict):
        target = str(row.get("fetch_ref") or row.get("path") or "").strip()
        if target:
            break
Path(sys.argv[2]).write_text(target, encoding="utf-8")
PY
apple_fetch_target="$(cat "$root/apple-notes-fetch-target.txt")"
if [[ -n "$apple_fetch_target" ]]; then
  alcove connector --home "$home" fetch "$apple_fetch_target" --json \
    > "$root/apple-notes-fetch.json"
  assert_json "apple notes fetch" "$root/apple-notes-fetch.json" \
    "payload.get('status') == 'fetched' and payload.get('item')"
else
  printf '{"status":"skipped","reason":"Apple Notes search returned no item to fetch"}\n' \
    > "$root/apple-notes-fetch.json"
fi

web_fallback=0
set +e
"$clipsmith_bin" capture start "$web_url" --state-dir "$state_dir" > "$root/clipsmith-capture-start.json"
capture_start_status=$?
if [[ "$capture_start_status" -eq 0 ]]; then
  (
    cd "$clipsmith_web_skill"
    npx tsx scripts/run.ts --url "$web_url" --output_dir "$web_output" \
      > "$root/clipsmith-web-run.json"
  )
  web_run_status=$?
else
  web_run_status=1
fi
set -e

if [[ "$capture_start_status" -eq 0 && "$web_run_status" -eq 0 ]]; then
  job_id="$(
    uv run python - "$root/clipsmith-capture-start.json" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text())["job_id"])
PY
  )"
  bundle_dir="$(
    uv run python - "$root/clipsmith-web-run.json" <<'PY'
import json
import sys
from pathlib import Path

print(json.loads(Path(sys.argv[1]).read_text())["bundle_dir"])
PY
  )"
else
  printf 'real-integration: web capture failed; using local bundle fallback\n' >&2
  web_fallback=1
  bundle_dir="$web_output/fallback-web-bundle"
  mkdir -p "$bundle_dir"
  cat > "$bundle_dir/summary.md" <<'MD'
# Clipsmith Web Fallback

Fallback web capture bundle for Alcove real integration smoke.
MD
  cat > "$bundle_dir/post.md" <<MD
# Clipsmith Web Fallback

Source: $web_url

Fallback web capture content verifies that Clipsmith-compatible bundles can still be validated, written to an Alcove inbox, and read through the managed knowledge-base workflow when live web capture is unavailable.
MD
  run uv run python - "$bundle_dir" "$web_url" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

bundle = Path(sys.argv[1])
source = sys.argv[2]
payload = {
    "schema": "clipsmith.capture_bundle.v1",
    "id": "clipsmith-web-fallback",
    "platform": "web",
    "source_url": source,
    "title": "Clipsmith Web Fallback",
    "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
    "content_files": [
        {"path": "summary.md", "kind": "summary", "required_for_review": True},
        {"path": "post.md", "kind": "post", "required_for_review": True},
    ],
    "assets": [],
    "warnings": ["live web capture failed during real integration smoke; local fallback used"],
    "status": "complete",
}
(bundle / "capture.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
  printf '{"status":"fallback","live_verified":false,"fallback_reason":"live web capture failed during smoke"}\n' \
    > "$root/clipsmith-finalize.json"
fi

run "$clipsmith_bin" validate-bundle "$bundle_dir" --json > "$root/clipsmith-validate.json"
assert_json "clipsmith web validate" "$root/clipsmith-validate.json" \
  "payload.get('issues') == []"
if [[ "$web_fallback" == "0" ]]; then
  run "$clipsmith_bin" capture finalize "$job_id" "$bundle_dir" --state-dir "$state_dir" \
    > "$root/clipsmith-finalize.json"
  assert_json "clipsmith finalize" "$root/clipsmith-finalize.json" "payload['status'] == 'done'"
fi
printf '{"status":"%s","live_verified":%s,"fallback_reason":"%s"}\n' \
  "$([[ "$web_fallback" == "1" ]] && printf fallback || printf live)" \
  "$([[ "$web_fallback" == "1" ]] && printf false || printf true)" \
  "$([[ "$web_fallback" == "1" ]] && printf 'live web capture failed during smoke' || printf '')" \
  > "$root/web-capture-status.json"
run "$clipsmith_bin" sink inbox "$bundle_dir" "$kb" --json > "$root/clipsmith-sink-inbox.json"
assert_json "clipsmith sink inbox" "$root/clipsmith-sink-inbox.json" \
  "payload['status'] == 'written'"

alcove inbox --kb real_integration_kb peek --json > "$root/alcove-inbox-peek-clipsmith.json"
inbox_item="$(
  uv run python - "$root/alcove-inbox-peek-clipsmith.json" <<'PY'
import json
import sys
from pathlib import Path

payload = json.loads(Path(sys.argv[1]).read_text())
print(f"{payload['platform']}/{payload['name']}")
PY
)"
alcove inbox --kb real_integration_kb read "$inbox_item" --json \
  > "$root/alcove-inbox-read-clipsmith.json"
assert_json "alcove read clipsmith inbox" "$root/alcove-inbox-read-clipsmith.json" \
  "len(payload.get('content', '')) > 0 and payload.get('source')"

if ! command -v magick >/dev/null 2>&1; then
  printf 'real-integration: ImageMagick magick is required for OCR smoke\n' >&2
  exit 1
fi

ocr_dir="$root/ocr"
ocr_bundle="$root/ocr-bundle"
mkdir -p "$ocr_dir" "$ocr_bundle"
ocr_image="$ocr_dir/ocr-source.png"
run magick -size 1200x420 xc:white \
  -font /System/Library/Fonts/Supplemental/Arial.ttf \
  -fill '#111111' \
  -pointsize 52 -annotate +70+130 'Clipsmith OCR smoke test' \
  -pointsize 46 -annotate +70+235 'OCR result should be saved to ocr.md' \
  -pointsize 42 -annotate +70+330 '中文识别测试：知识库采集' \
  "$ocr_image"

run npx tsx "$clipsmith_ocr_skill/scripts/run.ts" \
  --image_path "$ocr_image" \
  --output_text "$ocr_dir/ocr.txt" \
  --languages "zh-Hans,zh-Hant,en" \
  --recognition_level accurate > "$root/clipsmith-ocr-run.txt"

cp "$ocr_dir/ocr.txt" "$ocr_bundle/ocr.md"
cp "$ocr_dir/ocr.txt" "$ocr_bundle/post.md"
printf '# Summary\n\nLocal OCR smoke bundle generated from `%s`.\n' \
  "$(basename "$ocr_image")" > "$ocr_bundle/summary.md"
cp "$ocr_image" "$ocr_bundle/ocr-source.png"

run uv run python - "$ocr_bundle" "$ocr_image" <<'PY'
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

bundle = Path(sys.argv[1])
image = Path(sys.argv[2])
ocr = (bundle / "ocr.md").read_text(encoding="utf-8").strip()
if "OCR result should be saved to ocr.md" not in ocr:
    raise SystemExit(f"OCR text did not contain expected phrase: {ocr!r}")
payload = {
    "schema": "clipsmith.capture_bundle.v1",
    "id": "ocr-bundle",
    "platform": "image-ocr",
    "source_url": str(image.resolve()),
    "title": "Clipsmith OCR smoke test",
    "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
    "content_files": [
        {"path": "summary.md", "kind": "summary", "required_for_review": True},
        {"path": "ocr.md", "kind": "ocr-text", "required_for_review": True},
        {"path": "post.md", "kind": "post", "required_for_review": True},
    ],
    "assets": [{"path": "ocr-source.png", "kind": "ocr-image"}],
    "warnings": [],
    "status": "complete",
}
(bundle / "capture.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY

run "$clipsmith_bin" validate-bundle "$ocr_bundle" --json > "$root/clipsmith-ocr-validate.json"
assert_json "clipsmith ocr validate" "$root/clipsmith-ocr-validate.json" \
  "payload.get('issues') == []"
run "$clipsmith_bin" sink inbox "$ocr_bundle" "$kb" --json > "$root/clipsmith-ocr-sink-inbox.json"
assert_json "clipsmith ocr sink" "$root/clipsmith-ocr-sink-inbox.json" \
  "payload['status'] == 'written'"
alcove inbox --kb real_integration_kb read image-ocr/ocr-bundle --json \
  > "$root/alcove-inbox-read-ocr.json"
assert_json "alcove read ocr inbox" "$root/alcove-inbox-read-ocr.json" \
  "'OCR result should be saved to ocr.md' in payload.get('content', '') and 'ocr.md' in payload.get('content_source', '')"

run uv run python - "$home" "$kb" "$root/mcp-stdio-report.json" "$github_search_query" <<'PY'
import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client
from fastmcp.client.transports import StdioTransport

home = Path(sys.argv[1])
kb = Path(sys.argv[2])
report = Path(sys.argv[3])
github_search_query = sys.argv[4]


async def main() -> None:
    transport = StdioTransport(
        command="uv",
        args=[
            "run",
            "alcove",
            "serve",
            "--mcp",
            "--home",
            str(home),
            "--workspace",
            str(kb),
        ],
        cwd=str(Path.cwd()),
        log_file=report.with_name("mcp-stdio-server.log"),
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)
        search = await client.call_tool(
            "alcove_search",
            {
                "query": github_search_query,
                "home": str(home),
                "type_filter": "GitHub Star",
            },
        )
        inbox = await client.call_tool("alcove_inbox_peek", {"workspace": str(kb)})
        connectors = await client.call_tool("alcove_connector_status", {"home": str(home)})
        payload = {
            "tool_count": len(tool_names),
            "has_required_tools": all(
                name in tool_names
                for name in [
                    "alcove_search",
                    "alcove_inbox_peek",
                    "alcove_connector_status",
                ]
            ),
            "search": search.structured_content,
            "inbox": inbox.structured_content,
            "connectors": connectors.structured_content,
        }
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not payload["has_required_tools"]:
        raise SystemExit("MCP required tools missing")
    if payload["search"].get("count", 0) < 1:
        raise SystemExit("MCP search did not return live connector result")
    if len(payload["connectors"].get("sources", [])) < 2:
        raise SystemExit("MCP connector status did not return both sources")


asyncio.run(main())
PY

run uv run python - "$root" <<'PY'
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
github = json.loads((root / "github-stars-import.json").read_text(encoding="utf-8"))
apple = json.loads((root / "apple-notes-import-local.json").read_text(encoding="utf-8"))
mcp = json.loads((root / "mcp-stdio-report.json").read_text(encoding="utf-8"))
ocr = json.loads((root / "alcove-inbox-read-ocr.json").read_text(encoding="utf-8"))
web = json.loads((root / "web-capture-status.json").read_text(encoding="utf-8"))
failures = json.loads((root / "connector-failure-samples.json").read_text(encoding="utf-8"))
github_fallback = bool(github.get("network_fallback"))
summary = {
    "status": "degraded" if github_fallback or web.get("status") == "fallback" else "passed",
    "github_stars": github.get("scanned", 0),
    "github_stars_live_verified": not github_fallback,
    "github_stars_status": "fallback" if github_fallback else "live",
    "github_stars_fallback_reason": github.get("fallback_reason", "") if github_fallback else "",
    "web_capture_status": web.get("status"),
    "web_capture_live_verified": bool(web.get("live_verified")),
    "web_capture_fallback_reason": web.get("fallback_reason", ""),
    "connector_failure_samples_status": failures.get("status"),
    "connector_failure_samples": len(failures.get("samples", [])),
    "apple_notes": apple.get("scanned", 0),
    "mcp_tool_count": mcp.get("tool_count", 0),
    "ocr_content_source": ocr.get("content_source"),
    "artifacts": str(root),
}
(root / "real-integrations-summary.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY

printf 'real-integration: completed\n'
