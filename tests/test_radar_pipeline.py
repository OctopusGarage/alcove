from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

import pytest

from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.radars import RadarDefinition, RadarModule, RadarSource
from alcove.radars import pipeline as radar_pipeline


def test_radar_run_fetches_scores_reports_and_writes_runtime_files(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "LLM open source release",
                    "url": "https://example.test/llm",
                    "summary": "A useful model release",
                    "tags": ["AI"],
                },
                {
                    "title": "Duplicate LLM open source release",
                    "url": "https://example.test/llm",
                    "summary": "Same canonical URL",
                },
                {
                    "title": "Sponsored gambling ad",
                    "url": "https://example.test/ad",
                    "summary": "Advertisement",
                },
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="tech-news",
            name="Tech News",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={
                "interest_tags": ["LLM", "open source"],
                "blocked_keywords": ["gambling"],
                "min_score_threshold": 0.5,
            },
            report={"formats": ["md", "html"], "language": "zh"},
        )
    )

    result = module.run("tech-news", ai=True)

    run_day = result["date"]
    cache_dir = home.root / "radars" / "cache" / "tech-news" / run_day
    report_dir = home.root / "radars" / "reports" / "tech-news"
    run_path = home.root / "radars" / "runs" / "tech-news" / run_day / "run.json"
    okf_path = home.root / "radars" / "okf" / "tech-news" / "index.md"
    events_path = home.root / "radars" / "events.jsonl"

    raw = json.loads((cache_dir / "raw.json").read_text(encoding="utf-8"))
    scored = json.loads((cache_dir / "scored.json").read_text(encoding="utf-8"))
    run_payload = json.loads(run_path.read_text(encoding="utf-8"))
    event = json.loads(events_path.read_text(encoding="utf-8").strip())

    assert result["status"] == "completed"
    assert result["fetched"] == 3
    assert result["deduped"] == 2
    assert result["included"] == 1
    assert result["ai"]["requested"] is True
    assert result["ai"]["status"] == "skipped"
    assert len(raw) == 3
    assert [item["url"] for item in scored] == [
        "https://example.test/llm",
        "https://example.test/ad",
    ]
    assert scored[0]["included"] is True
    assert scored[0]["score"] > 0.5
    assert scored[1]["included"] is False
    assert scored[1]["score_reason"] == "blocked keyword: gambling"
    assert (report_dir / f"{run_day}.md").is_file()
    assert (report_dir / f"{run_day}.html").is_file()
    markdown = (report_dir / f"{run_day}.md").read_text(encoding="utf-8")
    html = (report_dir / f"{run_day}.html").read_text(encoding="utf-8")
    assert "## Brief" in markdown
    assert "## Source Coverage" in markdown
    assert "## Top Signals" in markdown
    assert 'class="hero"' in html
    assert 'class="stats"' in html
    assert 'class="signal-card"' in html
    assert "Top Signals" in html
    assert run_payload == result
    assert okf_path.is_file()
    assert "Tech News" in okf_path.read_text(encoding="utf-8")
    assert event["event"] == "radar.run.completed"
    assert event["radar_id"] == "tech-news"


def test_radar_ai_summary_saves_artifact_and_notifies_success(tmp_path, monkeypatch) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "AI coding agent release",
                    "url": "https://example.test/agent",
                    "summary": "A developer tooling launch for agent teams.",
                    "tags": ["AI", "developer tools"],
                },
                {
                    "title": "AI coding agent release - duplicate discussion",
                    "url": "https://example.test/agent-discussion",
                    "summary": "A duplicate discussion of the same developer tooling launch.",
                    "tags": ["AI", "developer tools"],
                },
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="tech-news",
            name="Tech News",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI", "agent"], "min_score_threshold": 0.5},
            report={"formats": ["md", "html"], "language": "zh", "style": "tech-briefing"},
            ai_summary={
                "enabled": True,
                "provider": "codex",
                "prompt": "技术雷达专用总结提示词",
            },
            notify={"enabled": True, "channel": "telegram"},
        )
    )
    ai_inputs: list[str] = []
    sent_messages: list[str] = []
    sent_documents: list[Path] = []

    def fake_run_ai_summary(*, prompt, policy, cwd=None):
        ai_inputs.append(prompt)
        assert policy["provider"] == "codex"
        return {
            "status": "completed",
            "provider": "codex",
            "summary": "核心AI总结：这个发布值得跟进。",
        }

    def fake_send_telegram(*, home, text):
        sent_messages.append(text)
        return {"status": "sent", "attempts": 1}

    def fake_send_telegram_document(*, home, path, caption=""):
        sent_documents.append(path)
        assert caption in {
            f"Tech News radar MD report - {date.today().isoformat()}",
            f"Tech News radar HTML report - {date.today().isoformat()}",
        }
        return {"status": "sent", "attempts": 1, "path": compact_user_path(path)}

    monkeypatch.setattr(radar_pipeline, "run_ai_summary", fake_run_ai_summary)
    monkeypatch.setattr(radar_pipeline, "send_telegram_message", fake_send_telegram)
    monkeypatch.setattr(radar_pipeline, "send_telegram_document", fake_send_telegram_document)

    result = module.run("tech-news")

    markdown = (home.root / "radars" / "reports" / "tech-news" / f"{result['date']}.md").read_text(
        encoding="utf-8"
    )
    summary_path = home.root / "radars" / "reports" / "tech-news" / f"{result['date']}.ai.md"
    run_payload = json.loads(
        (home.root / "radars" / "runs" / "tech-news" / result["date"] / "run.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["ai"]["status"] == "completed"
    assert result["ai"]["provider"] == "codex"
    assert result["included"] == 1
    assert "技术雷达专用总结提示词" in ai_inputs[0]
    assert "AI coding agent release" in ai_inputs[0]
    assert "duplicate discussion" not in markdown
    assert summary_path.read_text(encoding="utf-8") == "核心AI总结：这个发布值得跟进。\n"
    assert result["reports"]["ai_summary"] == str(summary_path).replace(str(Path.home()), "~")
    assert run_payload["notify"]["status"] == "sent"
    assert run_payload["notify"]["documents"]["md"]["status"] == "sent"
    assert run_payload["notify"]["documents"]["html"]["status"] == "sent"
    assert str(Path.home()) not in run_payload["notify"]["documents"]["md"]["path"]
    assert str(Path.home()) not in run_payload["notify"]["documents"]["html"]["path"]
    assert sent_documents == [
        home.root / "radars" / "reports" / "tech-news" / f"{result['date']}.md",
        home.root / "radars" / "reports" / "tech-news" / f"{result['date']}.html",
    ]
    assert sent_messages
    assert "Included: 1" in sent_messages[0]
    assert "核心AI总结：这个发布值得跟进。" in sent_messages[0]
    assert "AI coding agent release" in sent_messages[0]
    assert "duplicate discussion" not in sent_messages[0]
    assert "md:" not in sent_messages[0]
    assert "html:" not in sent_messages[0]
    assert "Report" not in sent_messages[0]
    for path in sent_documents:
        assert compact_user_path(path) not in sent_messages[0]


def test_radar_notify_supports_multiple_sinks_with_feishu(tmp_path, monkeypatch) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "AI infra signal",
                    "url": "https://example.test/infra",
                    "summary": "Infrastructure update for AI teams.",
                    "tags": ["AI", "infrastructure"],
                }
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="tech-news",
            name="Tech News",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI"], "min_score_threshold": 0.5},
            report={"formats": ["md", "html"]},
            notify={
                "enabled": True,
                "sinks": [
                    {"type": "telegram"},
                    {"type": "feishu", "webhook_env": "ALCOVE_TEST_FEISHU_WEBHOOK"},
                ],
            },
        )
    )
    sent_telegram_messages: list[str] = []
    sent_telegram_documents: list[Path] = []
    sent_feishu: list[dict[str, Any]] = []
    monkeypatch.setenv(
        "ALCOVE_TEST_FEISHU_WEBHOOK", "https://open.feishu.cn/open-apis/bot/v2/hook/test"
    )

    def fake_send_telegram(*, home, text):
        sent_telegram_messages.append(text)
        return {"status": "sent", "attempts": 1}

    def fake_send_telegram_document(*, home, path, caption=""):
        sent_telegram_documents.append(path)
        return {"status": "sent", "attempts": 1, "path": compact_user_path(path)}

    def fake_send_feishu(*, home, sink, title, text, report_path=None):
        sent_feishu.append(
            {
                "sink": sink,
                "title": title,
                "text": text,
                "report_path": report_path,
            }
        )
        return {"status": "sent", "http_status": 200}

    monkeypatch.setattr(radar_pipeline, "send_telegram_message", fake_send_telegram)
    monkeypatch.setattr(radar_pipeline, "send_telegram_document", fake_send_telegram_document)
    monkeypatch.setattr(radar_pipeline, "send_feishu_message", fake_send_feishu, raising=False)

    result = module.run("tech-news", notify=True)

    assert result["notify"]["status"] == "sent"
    assert result["notify"]["sinks"]["telegram"]["status"] == "sent"
    assert result["notify"]["sinks"]["feishu"]["status"] == "sent"
    assert sent_telegram_messages
    assert sent_telegram_documents == [
        home.root / "radars" / "reports" / "tech-news" / f"{result['date']}.md",
        home.root / "radars" / "reports" / "tech-news" / f"{result['date']}.html",
    ]
    assert sent_feishu
    assert sent_feishu[0]["sink"]["webhook_env"] == "ALCOVE_TEST_FEISHU_WEBHOOK"
    assert sent_feishu[0]["title"] == "Radar: Tech News"
    assert "AI infra signal" in sent_feishu[0]["text"]
    assert "Report" not in sent_feishu[0]["text"]
    for path in sent_telegram_documents:
        assert compact_user_path(path) not in sent_feishu[0]["text"]
    assert sent_feishu[0]["report_path"] is None


def test_radar_notify_supports_tcb_sink_with_report_attachments(tmp_path, monkeypatch) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "AI infra signal",
                    "url": "https://example.test/infra",
                    "summary": "Infrastructure update for AI teams.",
                    "tags": ["AI", "infrastructure"],
                }
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="tech-news",
            name="Tech News",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI"], "min_score_threshold": 0.5},
            report={"formats": ["md", "html"]},
            notify={
                "enabled": True,
                "sinks": [{"type": "tcb", "channel": "lark"}],
            },
        )
    )
    sent_tcb: list[dict[str, Any]] = []

    def fake_send_tcb(*, sink, title, text, attachments):
        sent_tcb.append(
            {
                "sink": sink,
                "title": title,
                "text": text,
                "attachments": attachments,
            }
        )
        return {"status": "sent", "deliveries": [{"channel": "lark", "ok": True}]}

    monkeypatch.setattr(radar_pipeline, "send_tcb_notification", fake_send_tcb, raising=False)

    result = module.run("tech-news", notify=True)

    assert result["notify"]["status"] == "sent"
    assert result["notify"]["sinks"]["tcb"]["status"] == "sent"
    assert sent_tcb
    assert sent_tcb[0]["sink"]["channel"] == "lark"
    assert sent_tcb[0]["title"] == "Radar: Tech News"
    assert "AI infra signal" in sent_tcb[0]["text"]
    assert sent_tcb[0]["attachments"] == [
        home.root / "radars" / "reports" / "tech-news" / f"{result['date']}.md",
        home.root / "radars" / "reports" / "tech-news" / f"{result['date']}.html",
    ]


def test_radar_notify_respects_summary_and_top_link_options(tmp_path, monkeypatch) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "AI infra signal",
                    "url": "https://example.test/infra",
                    "summary": "Infrastructure update for AI teams.",
                    "tags": ["AI", "infrastructure"],
                }
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="tech-news",
            name="Tech News",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI"], "min_score_threshold": 0.5},
            report={"formats": ["md"]},
            ai_summary={"enabled": True, "provider": "codex"},
            notify={
                "enabled": True,
                "channel": "telegram",
                "include_ai_summary": False,
                "include_top_links": False,
            },
        )
    )
    sent_messages: list[str] = []

    monkeypatch.setattr(
        radar_pipeline,
        "run_ai_summary",
        lambda **_: {
            "status": "completed",
            "provider": "codex",
            "summary": "This AI summary should be hidden.",
        },
    )
    monkeypatch.setattr(
        radar_pipeline,
        "send_telegram_message",
        lambda *, home, text: sent_messages.append(text) or {"status": "sent"},
    )

    result = module.run("tech-news")

    assert result["notify"]["status"] == "sent"
    assert sent_messages
    assert "This AI summary should be hidden." not in sent_messages[0]
    assert "Top Links" not in sent_messages[0]
    assert "https://example.test/infra" not in sent_messages[0]
    assert "Core Summary" in sent_messages[0]


def test_radar_notify_falls_back_to_report_when_ai_summary_fails(tmp_path, monkeypatch) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Market signal for NVDA",
                    "url": "https://example.test/nvda",
                    "summary": "Semiconductor momentum.",
                }
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="stocks",
            name="Stocks",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"watched_symbols": ["NVDA"], "min_score_threshold": 0.5},
            report={"formats": ["md"], "language": "zh", "style": "stocks-briefing"},
            ai_summary={"enabled": True, "provider": "claude"},
            notify={"enabled": True, "channel": "telegram"},
        )
    )
    sent_messages: list[str] = []

    def fake_run_ai_summary(*, prompt, policy, cwd=None):
        return {"status": "failed", "provider": "claude", "error": "model unavailable"}

    def fake_send_telegram(*, home, text):
        sent_messages.append(text)
        return {"status": "sent", "attempts": 1}

    monkeypatch.setattr(radar_pipeline, "run_ai_summary", fake_run_ai_summary)
    monkeypatch.setattr(radar_pipeline, "send_telegram_message", fake_send_telegram)

    result = module.run("stocks")

    assert result["ai"]["status"] == "failed"
    assert result["ai"]["error"] == "model unavailable"
    assert result["notify"]["status"] == "sent"
    assert "AI summary failed; sending deterministic radar report." in sent_messages[0]
    assert "Market signal for NVDA" in sent_messages[0]


def test_radar_run_skip_fetch_reuses_raw_cache_and_status_reports_latest_run(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Important AI research",
                    "url": "https://example.test/research",
                    "summary": "LLM systems",
                }
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="custom-radar",
            name="Custom Radar",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI", "LLM"], "min_score_threshold": 0.5},
        )
    )
    first = module.run("custom-radar")
    fixture.unlink()

    second = module.run("custom-radar", skip_fetch=True, force=True)
    status = module.status("custom-radar")
    all_status = module.status()

    assert second["status"] == "completed"
    assert second["fetched"] == first["fetched"]
    assert status["count"] == 1
    assert status["radars"][0]["id"] == "custom-radar"
    assert status["radars"][0]["last_run"]["status"] == "completed"
    assert status["radars"][0]["last_run"]["included"] == 1
    assert status["radars"][0]["report_state"] == "current"
    assert status["radars"][0]["report_label"] == "Latest run report"
    assert all_status["count"] == 1
    assert all_status["radars"][0]["id"] == "custom-radar"


def test_radar_scoring_uses_generic_profile_interest_fields(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Science policy update",
                    "url": "https://example.test/science",
                    "summary": "Global research funding",
                },
                {
                    "title": "NVDA earnings watch",
                    "url": "https://example.test/nvda",
                    "summary": "Semiconductor market signal",
                },
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="mixed-profile-radar",
            name="Mixed Profile Radar",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={
                "news_categories": ["science"],
                "watched_symbols": ["NVDA"],
                "min_score_threshold": 0.5,
            },
        )
    )

    result = module.run("mixed-profile-radar")

    assert result["included"] == 2


def test_radar_scoring_uses_word_boundaries_and_stale_filter(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Analyst said whether market moves matter",
                    "url": "https://example.test/false-positive",
                    "summary": "Plain finance note without target tokens.",
                },
                {
                    "title": "AI market update for NVDA",
                    "url": "https://example.test/ai",
                    "summary": "AI infrastructure spending.",
                },
                {
                    "title": "AI market update from last year",
                    "url": "https://example.test/stale",
                    "summary": "AI infrastructure spending.",
                    "published_at": "Sat, 01 Jan 2000 10:00:00 GMT",
                },
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="quality-radar",
            name="Quality Radar",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={
                "interest_tags": ["AI", "ETH", "market"],
                "watched_symbols": ["NVDA"],
                "min_score_threshold": 0.55,
                "max_age_days": 14,
            },
        )
    )

    result = module.run("quality-radar")
    run_day = result["date"]
    scored = json.loads(
        (home.root / "radars" / "cache" / "quality-radar" / run_day / "scored.json").read_text(
            encoding="utf-8"
        )
    )

    false_positive = next(row for row in scored if row["url"].endswith("false-positive"))
    useful = next(row for row in scored if row["url"].endswith("/ai"))
    stale = next(row for row in scored if row["url"].endswith("/stale"))

    assert false_positive["score_reason"] == "matched: market"
    assert "ai" not in false_positive["score_reason"]
    assert "eth" not in false_positive["score_reason"]
    assert useful["score_reason"] == "matched: ai, market, nvda"
    assert useful["included"] is True
    assert stale["included"] is False
    assert stale["score_reason"].startswith("stale published_at:")


def test_radar_report_limits_source_dominance_and_duplicate_topics(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture_a = tmp_path / "items-a.json"
    fixture_a.write_text(
        json.dumps(
            [
                {
                    "title": "OpenAI launches agent orchestration for coding teams",
                    "url": "https://example.test/openai-agent-a",
                    "summary": "AI agent developer tooling.",
                    "tags": ["AI", "agent", "developer tools"],
                },
                {
                    "title": "OpenAI launches agent orchestration for coding teams - analysis",
                    "url": "https://example.test/openai-agent-b",
                    "summary": "Duplicate topic that should be collapsed in the report.",
                    "tags": ["AI", "agent", "developer tools"],
                },
                {
                    "title": "AI database indexing improves retrieval infrastructure",
                    "url": "https://example.test/ai-db",
                    "summary": "Database infrastructure for retrieval.",
                    "tags": ["AI", "database", "infrastructure"],
                },
                {
                    "title": "Cloud security teams adopt AI review gates",
                    "url": "https://example.test/ai-security",
                    "summary": "Security workflow signal.",
                    "tags": ["AI", "security"],
                },
            ]
        ),
        encoding="utf-8",
    )
    fixture_b = tmp_path / "items-b.json"
    fixture_b.write_text(
        json.dumps(
            [
                {
                    "title": "Developer tools market shifts toward local-first agents",
                    "url": "https://example.test/local-agents",
                    "summary": "Developer tools and agents.",
                    "tags": ["developer tools", "agentic"],
                }
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="report-quality",
            name="Report Quality",
            sources=[
                RadarSource(id="source-a", adapter="fixture", params={"path": str(fixture_a)}),
                RadarSource(id="source-b", adapter="fixture", params={"path": str(fixture_b)}),
            ],
            profile={
                "interest_tags": ["AI", "agent", "developer tools", "database", "security"],
                "min_score_threshold": 0.55,
            },
            report={"formats": ["md", "html"], "max_items": 4, "max_per_source": 2},
        )
    )

    result = module.run("report-quality")
    markdown = (
        home.root / "radars" / "reports" / "report-quality" / f"{result['date']}.md"
    ).read_text(encoding="utf-8")

    assert "OpenAI launches agent orchestration for coding teams" in markdown
    assert "OpenAI launches agent orchestration for coding teams - analysis" not in markdown
    assert markdown.count("source-a") <= 3
    assert "Developer tools market shifts toward local-first agents" in markdown


def test_radar_run_reuses_same_day_run_until_forced(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Original AI item",
                    "url": "https://example.test/original",
                    "summary": "LLM",
                }
            ]
        ),
        encoding="utf-8",
    )
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="refreshable-radar",
            name="Refreshable Radar",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI", "LLM"], "min_score_threshold": 0.5},
        )
    )

    first = module.run("refreshable-radar")
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Replacement AI item",
                    "url": "https://example.test/replacement",
                    "summary": "LLM",
                },
                {
                    "title": "Second replacement AI item",
                    "url": "https://example.test/replacement-2",
                    "summary": "LLM",
                },
            ]
        ),
        encoding="utf-8",
    )

    reused = module.run("refreshable-radar")
    refreshed = module.run("refreshable-radar", force=True)

    assert reused == first
    assert refreshed["fetched"] == 2
    assert refreshed["force"] is True


def test_radar_skip_fetch_requires_existing_raw_cache(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="offline-radar",
            name="Offline Radar",
            sources=[
                RadarSource(
                    id="missing-fixture",
                    adapter="fixture",
                    params={"path": str(tmp_path / "missing.json")},
                )
            ],
        )
    )

    with pytest.raises(FileNotFoundError, match="radar raw cache not found"):
        module.run("offline-radar", skip_fetch=True)


def test_radar_status_skips_malformed_latest_run(tmp_path) -> None:
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = RadarModule(home)
    module.upsert_definition(
        RadarDefinition(
            id="status-radar",
            name="Status Radar",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": "unused.json"})],
        )
    )
    run_root = home.root / "radars" / "runs" / "status-radar"
    good_run = run_root / "2026-01-01" / "run.json"
    bad_run = run_root / "2099-01-01" / "run.json"
    good_run.parent.mkdir(parents=True)
    bad_run.parent.mkdir(parents=True)
    good_run.write_text(
        json.dumps({"status": "completed", "included": 1, "date": "2026-01-01"}),
        encoding="utf-8",
    )
    bad_run.write_text("{broken", encoding="utf-8")

    status = module.status("status-radar")

    assert status["radars"][0]["last_run"]["date"] == "2026-01-01"
