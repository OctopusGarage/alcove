#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$repo_root"

root="${ALCOVE_RADAR_REPORTS_DIR:-$repo_root/.tmp/radar-reports}"
home="$root/home"
fixtures="$root/fixtures"
report="$root/radar-reports-report.json"
screenshots="$root/screenshots"

run() {
  local rendered=()
  local arg
  for arg in "$@"; do
    if [[ "$arg" == "$HOME" ]]; then
      rendered+=("~")
    elif [[ "$arg" == "$HOME/"* ]]; then
      rendered+=("~/${arg#"$HOME/"}")
    else
      rendered+=("$arg")
    fi
  done
  printf 'radar-reports: %s\n' "${rendered[*]}" >&2
  "$@"
}

alcove() {
  run uv run alcove "$@"
}

rm -rf "$root"
mkdir -p "$fixtures" "$screenshots"

alcove home init --home "$home" --json > "$fixtures/home-init.json"

run uv run python - "$home" "$fixtures" <<'PY'
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

from alcove.home import AlcoveHome
from alcove.radars import RadarModule, RadarSource

home = AlcoveHome.init(Path(sys.argv[1]))
fixtures = Path(sys.argv[2])
module = RadarModule(home)

samples: dict[str, dict[str, list[dict[str, object]]]] = {
    "tech-news": {
        "hackernews": [
            {
                "title": "Open source coding agent adds MCP orchestration",
                "url": "https://example.test/tech/coding-agent",
                "summary": "A practical release for agentic developer tooling and local workflows.",
                "tags": ["AI", "MCP", "developer tools"],
                "published_at": "2026-07-12T08:00:00+00:00",
            },
            {
                "title": "Open source coding agent adds MCP orchestration - duplicate discussion",
                "url": "https://example.test/tech/coding-agent-discussion",
                "summary": "A duplicate angle that should not crowd the final top list.",
                "tags": ["AI", "MCP"],
                "published_at": "2026-07-12T08:30:00+00:00",
            },
        ],
        "techcrunch": [
            {
                "title": "Database startup ships low-latency vector infrastructure",
                "url": "https://example.test/tech/vector-db",
                "summary": "The launch targets AI retrieval workloads and operational observability.",
                "tags": ["database", "AI", "infrastructure"],
                "published_at": "2026-07-11T10:00:00+00:00",
            }
        ],
        "wired": [
            {
                "title": "Security teams adopt local-first AI review workflows",
                "url": "https://example.test/tech/security-ai-review",
                "summary": "New tooling emphasizes audit trails and constrained write paths.",
                "tags": ["security", "AI"],
                "published_at": "2026-07-10T10:00:00+00:00",
            }
        ],
    },
    "world-news": {
        "bbc-world": [
            {
                "title": "Trade talks resume as energy prices pressure Europe",
                "url": "https://example.test/world/trade-energy",
                "summary": "Negotiators are trying to reduce supply risk before winter demand rises.",
                "tags": ["trade", "energy", "EU"],
                "published_at": "2026-07-12T07:00:00+00:00",
            }
        ],
        "al-jazeera": [
            {
                "title": "Climate funding dispute dominates summit agenda",
                "url": "https://example.test/world/climate-funding",
                "summary": "Developing economies are asking for clearer commitments and faster disbursement.",
                "tags": ["climate", "politics"],
                "published_at": "2026-07-11T09:00:00+00:00",
            }
        ],
        "cnn-world": [
            {
                "title": "Security pact draws regional diplomatic response",
                "url": "https://example.test/world/security-pact",
                "summary": "Officials framed the pact as defensive while rivals warned of escalation.",
                "tags": ["security", "politics"],
                "published_at": "2026-07-10T09:00:00+00:00",
            }
        ],
    },
    "stocks": {
        "marketwatch-top": [
            {
                "title": "NVDA earnings lift semiconductor risk appetite",
                "url": "https://example.test/stocks/nvda-earnings",
                "summary": "Stronger AI accelerator guidance is feeding through chip and cloud names.",
                "tags": ["NVDA", "earnings", "semiconductors", "AI"],
                "published_at": "2026-07-12T06:00:00+00:00",
            }
        ],
        "wsj-markets": [
            {
                "title": "Fed rate path keeps bond yields in focus",
                "url": "https://example.test/stocks/fed-yields",
                "summary": "Macro desks are watching inflation prints, Treasury supply, and equity duration risk.",
                "tags": ["rates", "inflation", "bond yields", "macro"],
                "published_at": "2026-07-11T06:00:00+00:00",
            }
        ],
        "investing-stocks": [
            {
                "title": "AAPL services growth offsets hardware caution",
                "url": "https://example.test/stocks/aapl-services",
                "summary": "Investors are weighing margin resilience against slower device replacement cycles.",
                "tags": ["AAPL", "guidance", "stocks"],
                "published_at": "2026-07-10T06:00:00+00:00",
            }
        ],
    },
    "sports-news": {
        "espn-top": [
            {
                "title": "NBA contenders reshape rotations before playoffs",
                "url": "https://example.test/sports/nba-rotations",
                "summary": "Injuries and defensive matchups are driving lineup changes.",
                "tags": ["NBA", "playoffs", "injuries"],
                "published_at": "2026-07-12T05:00:00+00:00",
            }
        ],
        "formula-one": [
            {
                "title": "F1 title race tightens after qualifying record",
                "url": "https://example.test/sports/f1-qualifying",
                "summary": "A narrow qualifying margin raises the importance of tire strategy.",
                "tags": ["F1", "Formula 1", "record"],
                "published_at": "2026-07-11T05:00:00+00:00",
            }
        ],
        "bbc-sport": [
            {
                "title": "Tennis champion manages injury before semifinal",
                "url": "https://example.test/sports/tennis-injury",
                "summary": "The medical update changes the tactical outlook for the semifinal.",
                "tags": ["tennis", "injuries", "championship"],
                "published_at": "2026-07-10T05:00:00+00:00",
            }
        ],
    },
}

for radar_id, source_rows in samples.items():
    module.init_from_preset(radar_id, radar_id, force=True)
    definition = module.get(radar_id)
    sources: list[RadarSource] = []
    for source_id, rows in source_rows.items():
        path = fixtures / f"{radar_id}-{source_id}.json"
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        sources.append(
            RadarSource(id=source_id, adapter="fixture", limit=20, params={"path": str(path)})
        )
    module.upsert_definition(
        replace(
            definition,
            sources=sources,
            report={**definition.report, "formats": ["md", "html"], "max_items": 8},
        )
    )
PY

for radar_id in tech-news world-news stocks sports-news; do
  alcove radar --home "$home" run "$radar_id" --force --json > "$fixtures/$radar_id-run.json"
done

run uv run python - "$home" "$report" "$screenshots" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any

from alcove.paths import compact_user_path, compact_user_paths_in_text

home = Path(sys.argv[1])
report_path = Path(sys.argv[2])
screenshots = Path(sys.argv[3])
radar_ids = ["tech-news", "world-news", "stocks", "sports-news"]
checks: list[dict[str, Any]] = []
visual_summaries: list[dict[str, Any]] = []
html_paths: dict[str, Path] = {}


def add_check(name: str, ok: bool, detail: str = "") -> None:
    checks.append(
        {
            "name": name,
            "status": "passed" if ok else "failed",
            "detail": compact_user_paths_in_text(detail),
        }
    )


for radar_id in radar_ids:
    runs = sorted((home / "radars" / "runs" / radar_id).glob("*/run.json"))
    run_payload = json.loads(runs[-1].read_text(encoding="utf-8"))
    md_path = Path(run_payload["reports"]["md"]).expanduser()
    html_path = Path(run_payload["reports"]["html"]).expanduser()
    html_paths[radar_id] = html_path
    md = md_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    signal_count = len(re.findall(r"^\d+\. \[", md, flags=re.M))
    add_check(f"{radar_id}_completed", run_payload["status"] == "completed", str(run_payload))
    add_check(f"{radar_id}_enough_signals", signal_count >= 3, md[:800])
    add_check(f"{radar_id}_brief", "## Brief" in md and "## Source Coverage" in md, md[:800])
    add_check(
        f"{radar_id}_html_structure",
        'class="hero"' in html and 'class="signal-card"' in html and "[object Object]" not in html,
        html[:500],
    )

from dataclasses import replace
from alcove.home import AlcoveHome
from alcove.radars import RadarModule
from alcove.radars import pipeline as radar_pipeline

module = RadarModule(AlcoveHome.init(home))
sent_messages: list[str] = []
sent_documents: list[str] = []
sent_feishu: list[str] = []


def fake_run_ai_summary(*, prompt, policy, cwd=None):
    provider = str(policy.get("provider") or "")
    if "market" in prompt.lower() or "市场雷达" in prompt:
        return {"status": "failed", "provider": provider, "error": "synthetic AI failure"}
    return {
        "status": "completed",
        "provider": provider,
        "summary": "Synthetic core AI summary for radar notification.",
    }


def fake_send_telegram(*, home, text):
    sent_messages.append(text)
    return {"status": "sent", "attempts": 1}


def fake_send_telegram_document(*, home, path, caption=""):
    sent_documents.append(compact_user_path(path))
    return {"status": "sent", "attempts": 1, "path": compact_user_path(path)}


def fake_send_feishu(*, home, sink, title, text, report_path=None):
    rendered_report_path = compact_user_path(report_path) if report_path else ""
    sent_feishu.append(f"{title}\n{text}\n{rendered_report_path}")
    return {"status": "sent", "http_status": 200}


radar_pipeline.run_ai_summary = fake_run_ai_summary
radar_pipeline.send_telegram_message = fake_send_telegram
radar_pipeline.send_telegram_document = fake_send_telegram_document
radar_pipeline.send_feishu_message = fake_send_feishu

for radar_id, prompt in [
    ("tech-news", "用中文总结技术雷达，突出工程趋势。"),
    ("stocks", "用中文总结市场雷达，突出风险和主线。"),
]:
    definition = module.get(radar_id)
    module.upsert_definition(
        replace(
            definition,
            ai_summary={
                "enabled": True,
                "provider": "codex",
                "prompt": prompt,
                "timeout_seconds": 30,
            },
            notify={
                "enabled": True,
                "sinks": [
                    {"type": "telegram"},
                    {"type": "feishu", "webhook_env": "ALCOVE_TEST_FEISHU_WEBHOOK"},
                ],
            },
        )
    )
    result = module.run(radar_id, skip_fetch=True, force=True, ai=True, notify=True)
    latest_message = sent_messages[-1] if sent_messages else ""
    latest_documents = sent_documents[-2:] if len(sent_documents) >= 2 else sent_documents[:]
    latest_feishu = sent_feishu[-1] if sent_feishu else ""
    add_check(
        f"{radar_id}_ai_notify_contract",
        result["notify"]["status"] == "sent"
        and result["notify"].get("sinks", {}).get("telegram", {}).get("status") == "sent"
        and result["notify"].get("sinks", {}).get("telegram", {}).get("documents", {}).get("md", {}).get("status")
        == "sent"
        and result["notify"].get("sinks", {}).get("telegram", {}).get("documents", {}).get("html", {}).get("status")
        == "sent"
        and result["notify"].get("sinks", {}).get("feishu", {}).get("status") == "sent"
        and len(latest_documents) == 2
        and latest_documents[0].endswith(".md")
        and latest_documents[1].endswith(".html")
        and "html:" not in latest_message
        and "md:" not in latest_message
        and latest_feishu
        and latest_documents[0] not in latest_feishu
        and latest_documents[1] not in latest_feishu
        and latest_documents[0] not in latest_message
        and latest_documents[1] not in latest_message
        and (
            result["ai"]["status"] == "completed"
            or (
                result["ai"]["status"] == "failed"
                and "AI summary failed; sending deterministic radar report." in latest_message
            )
        ),
        json.dumps(
            {
                "ai": result["ai"],
                "notify": result["notify"],
                "message_excerpt": latest_message[:500],
                "documents": latest_documents,
                "feishu_excerpt": latest_feishu[:500],
            },
            ensure_ascii=False,
        ),
    )

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:
    cli = shutil.which("playwright")
    if cli:
        for radar_id, html_path in html_paths.items():
            for label, viewport in [("desktop", "1440,1000"), ("mobile", "390,844")]:
                screenshot = screenshots / f"{radar_id}-{label}.png"
                result = subprocess.run(
                    [
                        cli,
                        "screenshot",
                        "--viewport-size",
                        viewport,
                        "--full-page",
                        html_path.as_uri(),
                        str(screenshot),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                add_check(
                    f"{radar_id}_{label}_cli_screenshot",
                    result.returncode == 0 and screenshot.is_file() and screenshot.stat().st_size > 0,
                    (result.stderr or result.stdout)[-600:],
                )
                visual_summaries.append(
                    {
                        "radar_id": radar_id,
                        "viewport": label,
                        "browser_mode": "playwright-cli",
                        "screenshot": compact_user_path(screenshot),
                    }
                )
        failed = [check for check in checks if check["status"] == "failed"]
        payload = {
            "status": "failed" if failed else "passed",
            "radars": radar_ids,
            "browser_mode": "playwright-cli",
            "python_playwright_unavailable": compact_user_paths_in_text(str(exc)),
            "checks": checks,
            "visual_summaries": visual_summaries,
            "screenshots": compact_user_path(screenshots),
        }
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        if failed:
            raise SystemExit("radar report smoke failed")
        raise SystemExit(0)

    payload = {
        "status": "skipped",
        "reason": compact_user_paths_in_text(
            f"playwright import unavailable and playwright CLI not found: {exc}"
        ),
        "checks": checks,
        "visual_summaries": visual_summaries,
        "screenshots": compact_user_path(screenshots),
    }
    report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0)

with sync_playwright() as p:
    try:
        browser = p.chromium.launch()
    except Exception as exc:
        payload = {
            "status": "skipped",
            "reason": compact_user_paths_in_text(f"playwright browser unavailable: {exc}"),
            "checks": checks,
            "visual_summaries": visual_summaries,
            "screenshots": compact_user_path(screenshots),
        }
        report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        raise SystemExit(0)
    for radar_id in radar_ids:
        run_payload = json.loads(
            sorted((home / "radars" / "runs" / radar_id).glob("*/run.json"))[-1].read_text(
                encoding="utf-8"
            )
        )
        html_path = Path(run_payload["reports"]["html"]).expanduser()
        for label, width, height in [("desktop", 1440, 1000), ("mobile", 390, 844)]:
            page = browser.new_page(viewport={"width": width, "height": height})
            page.goto(html_path.as_uri(), wait_until="networkidle")
            screenshot = screenshots / f"{radar_id}-{label}.png"
            page.screenshot(path=str(screenshot), full_page=True)
            summary = page.evaluate(
                """({radarId, viewport}) => {
                    const main = document.querySelector('main');
                    const text = (main?.innerText || '').replace(/\\s+/g, ' ').trim();
                    return {
                      radar_id: radarId,
                      viewport,
                      text_length: text.length,
                      card_count: document.querySelectorAll('.signal-card').length,
                      panel_count: document.querySelectorAll('.panel').length,
                      horizontal_overflow:
                        document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                      first_screen_excerpt: text.slice(0, 420),
                    };
                }""",
                {"radarId": radar_id, "viewport": label},
            )
            summary["screenshot"] = compact_user_path(screenshot)
            visual_summaries.append(summary)
            add_check(
                f"{radar_id}_{label}_browser_shape",
                summary["card_count"] >= 3 and summary["panel_count"] >= 3,
                json.dumps(summary, ensure_ascii=False),
            )
            add_check(
                f"{radar_id}_{label}_no_horizontal_overflow",
                not summary["horizontal_overflow"],
                json.dumps(summary, ensure_ascii=False),
            )
            add_check(f"{radar_id}_{label}_screenshot", screenshot.stat().st_size > 0, str(screenshot))
            page.close()
    browser.close()

failed = [check for check in checks if check["status"] == "failed"]
payload = {
    "status": "failed" if failed else "passed",
    "radars": radar_ids,
    "checks": checks,
    "visual_summaries": visual_summaries,
    "screenshots": compact_user_path(screenshots),
}
report_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(payload, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit("radar report smoke failed")
PY
