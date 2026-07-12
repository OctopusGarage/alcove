#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

root="${ALCOVE_MESSY_INBOX_DIR:-$repo_root/.tmp/messy-inbox}"
home="$root/home"
kb="$root/kb"
fixtures="$root/fixtures"
report="$root/messy-inbox-report.json"

run() {
  printf 'messy-inbox: %s\n' "$*" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
}

rm -rf "$root"
mkdir -p "$fixtures"

export ALCOVE_HOME="$home"
alcove home init --json > "$fixtures/home-init.json"
alcove init "$kb" > "$fixtures/kb-init.txt"
alcove kb add messy_kb "$kb" --json > "$fixtures/kb-add.json"

run uv run python - "$kb" <<'PY'
import json
import sys
from pathlib import Path

kb = Path(sys.argv[1])

def write_bundle(platform: str, name: str, files: dict[str, str], metadata: dict) -> None:
    root = kb / "inbox" / platform / name
    root.mkdir(parents=True, exist_ok=True)
    for rel, text in files.items():
        (root / rel).write_text(text, encoding="utf-8")
    (root / "capture.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

long_body = "# Long Messy Web\n\n" + "\n".join(
    f"Messy long paragraph {index}: agent should keep source context and not lose warning evidence."
    for index in range(90)
) + "\n...[truncated 2048 chars]"
write_bundle(
    "web",
    "long-warning-web",
    {
        "post.md": long_body,
        "summary.md": "Messy long paragraph 0: agent should keep source context and not lose warning evidence.",
    },
    {
        "schema": "clipsmith.capture_bundle.v1",
        "id": "long-warning-web",
        "platform": "web",
        "source_url": "https://example.test/long-warning",
        "title": "Long Warning Web",
        "published_at": "2026-07-10",
        "content_files": [
            {"path": "summary.md", "kind": "summary", "required_for_review": True},
            {"path": "post.md", "kind": "post", "required_for_review": True},
        ],
        "warnings": ["article extraction incomplete", "embedded media skipped"],
        "status": "complete",
    },
)
write_bundle(
    "image-ocr",
    "ocr-duplicate",
    {
        "summary.md": "# Summary\n\nReceipt total should remain visible.",
        "ocr.md": "Receipt OCR text\nTotal: 42\n中文识别测试：知识库采集",
        "post.md": "Receipt OCR text\nTotal: 42\n中文识别测试：知识库采集",
    },
    {
        "schema": "clipsmith.capture_bundle.v1",
        "id": "ocr-duplicate",
        "platform": "image-ocr",
        "source_url": "~/Downloads/receipt.png",
        "title": "OCR Duplicate",
        "captured_at": "2026-07-10T08:00:00Z",
        "content_files": [
            {"path": "summary.md", "kind": "summary", "required_for_review": True},
            {"path": "ocr.md", "kind": "ocr-text", "required_for_review": True},
            {"path": "post.md", "kind": "post", "required_for_review": True},
        ],
        "warnings": [],
        "status": "complete",
    },
)
write_bundle(
    "web",
    "missing-summary",
    {
        "post.md": "# Missing Summary\n\nOnly post content exists, but review still needs useful content.",
    },
    {
        "schema": "clipsmith.capture_bundle.v1",
        "id": "missing-summary",
        "platform": "web",
        "source_url": "https://example.test/missing-summary",
        "title": "Missing Summary",
        "content_files": [{"path": "post.md", "kind": "post", "required_for_review": True}],
        "warnings": ["summary not generated"],
        "status": "partial",
    },
)

platforms = ["web", "x", "xhs", "wechat", "image-ocr", "manual"]
for index in range(24):
    platform = platforms[index % len(platforms)]
    name = f"batch-{index:02d}-{platform}"
    files = {
        "post.md": (
            f"# Batch Item {index:02d}\n\n"
            f"Batch mixed-platform inbox item {index:02d} from {platform}. "
            "This validates that many pending captures keep readable review surfaces."
        )
    }
    content_files = [{"path": "post.md", "kind": "post", "required_for_review": True}]
    warnings = []
    if index % 5 == 0:
        files["summary.md"] = f"Batch summary {index:02d} should be preferred for quick review."
        content_files.insert(
            0,
            {"path": "summary.md", "kind": "summary", "required_for_review": True},
        )
    if platform == "image-ocr":
        files["ocr.md"] = f"Batch OCR text {index:02d}\nTotal: {index * 3}\n批量识别"
        content_files.append({"path": "ocr.md", "kind": "ocr-text", "required_for_review": True})
    if index % 7 == 0:
        warnings.append("batch capture warning kept")
    write_bundle(
        platform,
        name,
        files,
        {
            "schema": "clipsmith.capture_bundle.v1",
            "id": name,
            "platform": platform,
            "source_url": f"https://example.test/batch/{index:02d}",
            "title": f"Batch Item {index:02d}",
            "published_at": "2026-07-10",
            "content_files": content_files,
            "warnings": warnings,
            "status": "partial" if warnings else "complete",
        },
    )
PY

alcove inbox --kb messy_kb read web/long-warning-web --json > "$fixtures/long-warning-web.json"
alcove inbox --kb messy_kb read image-ocr/ocr-duplicate --json > "$fixtures/ocr-duplicate.json"
alcove inbox --kb messy_kb read web/missing-summary --json > "$fixtures/missing-summary.json"
alcove inbox --kb messy_kb read web/batch-00-web --json > "$fixtures/batch-00-web.json"
alcove inbox --kb messy_kb read image-ocr/batch-04-image-ocr --json > "$fixtures/batch-04-image-ocr.json"
alcove inbox --kb messy_kb read wechat/batch-21-wechat --json > "$fixtures/batch-21-wechat.json"

run uv run python - "$fixtures" "$report" <<'PY'
import json
import sys
from pathlib import Path

fixtures = Path(sys.argv[1])
report = Path(sys.argv[2])

long_web = json.loads((fixtures / "long-warning-web.json").read_text(encoding="utf-8"))
ocr = json.loads((fixtures / "ocr-duplicate.json").read_text(encoding="utf-8"))
missing = json.loads((fixtures / "missing-summary.json").read_text(encoding="utf-8"))
batch_web = json.loads((fixtures / "batch-00-web.json").read_text(encoding="utf-8"))
batch_ocr = json.loads((fixtures / "batch-04-image-ocr.json").read_text(encoding="utf-8"))
batch_wechat = json.loads((fixtures / "batch-21-wechat.json").read_text(encoding="utf-8"))

kb = fixtures.parent / "kb"
batch_dirs = [
    path
    for path in (kb / "inbox").glob("*/*")
    if path.is_dir() and path.name.startswith("batch-")
]
platform_counts: dict[str, int] = {}
for path in batch_dirs:
    platform_counts[path.parent.name] = platform_counts.get(path.parent.name, 0) + 1

checks = [
    (
        "long_web_truncation_visible",
        long_web.get("content_truncated") is True
        and long_web.get("content_files", [{}])[1].get("omitted_chars") == 2048,
        "long warning web truncation",
    ),
    (
        "long_web_review_surface",
        "agent should keep source context" in long_web.get("review_content", ""),
        long_web.get("review_content", "")[:160],
    ),
    (
        "long_web_review_outline",
        bool(long_web.get("review_outline", [])),
        json.dumps(long_web.get("review_outline", [])[:1], ensure_ascii=False),
    ),
    (
        "ocr_deduplicated",
        ocr.get("content", "").count("Total: 42") == 1
        and any(row.get("duplicate_of") == "ocr.md" for row in ocr.get("content_files", [])),
        "OCR duplicate post omitted",
    ),
    (
        "ocr_multilingual_visible",
        "中文识别测试" in ocr.get("review_content", ""),
        ocr.get("review_content", ""),
    ),
    (
        "missing_summary_readable",
        "Only post content exists" in missing.get("review_content", "")
        and missing.get("raw_content_available") is not False,
        missing.get("review_content", ""),
    ),
    (
        "capture_warnings_visible",
        long_web.get("capture_status") == "complete"
        and "article extraction incomplete" in long_web.get("capture_warnings", []),
        ", ".join(long_web.get("capture_warnings", [])),
    ),
    (
        "full_content_commands",
        all(
            payload.get("full_content_command")
            for payload in [long_web, ocr, missing, batch_web, batch_ocr, batch_wechat]
        ),
        "full content commands present",
    ),
    (
        "batch_fixture_volume",
        len(batch_dirs) == 24 and len(platform_counts) == 6,
        json.dumps({"batch_count": len(batch_dirs), "platform_counts": platform_counts}, ensure_ascii=False),
    ),
    (
        "batch_samples_readable",
        "Batch mixed-platform inbox item 00" in batch_web.get("review_content", "")
        and "Batch OCR text 04" in batch_ocr.get("review_content", "")
        and "Batch mixed-platform inbox item 21" in batch_wechat.get("review_content", ""),
        "representative batch web/ocr/wechat reads",
    ),
    (
        "batch_warnings_visible",
        "batch capture warning kept" in batch_web.get("capture_warnings", []),
        ", ".join(batch_web.get("capture_warnings", [])),
    ),
]
failed = [name for name, ok, _detail in checks if not ok]
payload = {
    "status": "failed" if failed else "passed",
    "batch": {
        "count": len(batch_dirs),
        "platform_counts": platform_counts,
        "sample_identifiers": [
            batch_web.get("identifier"),
            batch_ocr.get("identifier"),
            batch_wechat.get("identifier"),
        ],
    },
    "items": [
        {
            "identifier": long_web.get("identifier"),
            "title": long_web.get("title"),
            "source": long_web.get("source"),
            "date": long_web.get("date"),
            "capture_status": long_web.get("capture_status"),
            "capture_warnings": long_web.get("capture_warnings", []),
            "content_truncated": long_web.get("content_truncated"),
            "review_summary": long_web.get("review_summary"),
            "review_outline": long_web.get("review_outline", []),
            "content_files": long_web.get("content_files", []),
        },
        {
            "identifier": ocr.get("identifier"),
            "title": ocr.get("title"),
            "source": ocr.get("source"),
            "date": ocr.get("date"),
            "capture_status": ocr.get("capture_status"),
            "capture_warnings": ocr.get("capture_warnings", []),
            "content_source": ocr.get("content_source"),
            "review_summary": ocr.get("review_summary"),
            "review_outline": ocr.get("review_outline", []),
            "content_files": ocr.get("content_files", []),
        },
        {
            "identifier": missing.get("identifier"),
            "title": missing.get("title"),
            "source": missing.get("source"),
            "date": missing.get("date"),
            "capture_status": missing.get("capture_status"),
            "capture_warnings": missing.get("capture_warnings", []),
            "content_source": missing.get("content_source"),
            "review_summary": missing.get("review_summary"),
            "review_outline": missing.get("review_outline", []),
            "content_files": missing.get("content_files", []),
        },
        {
            "identifier": batch_web.get("identifier"),
            "title": batch_web.get("title"),
            "source": batch_web.get("source"),
            "capture_status": batch_web.get("capture_status"),
            "capture_warnings": batch_web.get("capture_warnings", []),
            "review_summary": batch_web.get("review_summary"),
            "content_files": batch_web.get("content_files", []),
        },
        {
            "identifier": batch_ocr.get("identifier"),
            "title": batch_ocr.get("title"),
            "source": batch_ocr.get("source"),
            "capture_status": batch_ocr.get("capture_status"),
            "capture_warnings": batch_ocr.get("capture_warnings", []),
            "content_source": batch_ocr.get("content_source"),
            "review_summary": batch_ocr.get("review_summary"),
            "content_files": batch_ocr.get("content_files", []),
        },
        {
            "identifier": batch_wechat.get("identifier"),
            "title": batch_wechat.get("title"),
            "source": batch_wechat.get("source"),
            "capture_status": batch_wechat.get("capture_status"),
            "capture_warnings": batch_wechat.get("capture_warnings", []),
            "review_summary": batch_wechat.get("review_summary"),
            "content_files": batch_wechat.get("content_files", []),
        },
    ],
    "checks": [
        {"name": name, "status": "passed" if ok else "failed", "detail": detail}
        for name, ok, detail in checks
    ],
    "artifacts": str(report.parent),
}
report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(f"messy inbox smoke failed: {', '.join(failed)}")
PY
