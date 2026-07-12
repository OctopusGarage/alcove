from __future__ import annotations

import json

from alcove.cli import main
from alcove.home import AlcoveHome
from alcove.radars import RadarModule


def test_import_social_radar_creates_definitions_and_copies_history(tmp_path, capsys):
    social = tmp_path / ".social_radar"
    home = tmp_path / ".alcove"
    (social / "config").mkdir(parents=True)
    (social / "data/radar").mkdir(parents=True)
    (social / "data/news_radar").mkdir(parents=True)
    (social / "data/stock_radar").mkdir(parents=True)
    (social / "reports/news").mkdir(parents=True)
    (social / "reports/stock").mkdir(parents=True)
    (social / "config/preference_profile.json").write_text(
        json.dumps(
            {
                "interest_tags": ["LLM"],
                "min_score_threshold": 0.6,
                "api_key": "must-not-migrate",
                "nested": {"bot_token": "must-not-migrate"},
            }
        ),
        encoding="utf-8",
    )
    (social / ".env").write_text("TELEGRAM_BOT_TOKEN=must-not-migrate\n", encoding="utf-8")
    (social / "config/news_preference_profile.json").write_text(
        json.dumps({"regions": ["global"], "min_score_threshold": 0.5}),
        encoding="utf-8",
    )
    (social / "config/stock_preference_profile.json").write_text(
        json.dumps({"watched_symbols": ["NVDA"], "min_score_threshold": 0.5}),
        encoding="utf-8",
    )
    (social / "data/radar/all_2026-07-11.json").write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source": "hn",
                        "title": "LLM agent runtime",
                        "url": "https://example.test/llm",
                        "description": "Agent runtime notes",
                        "tags": ["LLM"],
                        "fetched_at": "2026-07-11",
                        "report_score": 0.9,
                        "report_summary": "Useful LLM agent runtime item",
                        "included_in_report": True,
                        "interest_reason": "Matches LLM interests",
                    }
                ],
                "fetched_at": "2026-07-11",
                "scored_at": "2026-07-11",
            }
        ),
        encoding="utf-8",
    )
    (social / "data/news_radar/all_2026-07-11.json").write_text(
        json.dumps({"items": []}),
        encoding="utf-8",
    )
    (social / "data/stock_radar/all_2026-07-11.json").write_text(
        json.dumps({"items": [{"symbol": "NVDA", "title": "NVDA watch"}]}),
        encoding="utf-8",
    )
    (social / "reports/2026-07-11.html").write_text("<html>tech</html>", encoding="utf-8")
    (social / "reports/blogs_2026-07-11.html").write_text(
        "<html>blog report should not be copied</html>", encoding="utf-8"
    )
    (social / "reports/news/2026-07-11.md").write_text("# news", encoding="utf-8")
    (social / "reports/stock/2026-07-11.md").write_text("# stocks", encoding="utf-8")

    code = main(
        [
            "radar",
            "import-social-radar",
            str(social),
            "--home",
            str(home),
            "--json",
        ]
    )
    output = capsys.readouterr()

    assert code == 0
    assert '"status": "imported"' in output.out
    payload = json.loads(output.out)
    tech = next(row for row in payload["radars"] if row["id"] == "tech-news")
    assert tech["target_definition"].endswith("radars/definitions/tech-news.yml")
    assert tech["target_cache"].endswith("radars/cache/tech-news")
    assert tech["target_reports"].endswith("radars/reports/tech-news")
    assert tech["secret_fields_removed"] == 2
    assert payload["scrub"]["env_files_skipped"] == 1
    assert payload["scrub"]["secret_fields_removed"] == 2
    assert payload["scrub"]["blog_reports_skipped"] == 1
    assert (home / "radars/definitions/tech-news.yml").is_file()
    assert (home / "radars/definitions/world-news.yml").is_file()
    assert (home / "radars/definitions/stocks.yml").is_file()
    assert "status: needs_configuration" in (home / "radars/definitions/stocks.yml").read_text(
        encoding="utf-8"
    )
    assert "interest_tags:" in (home / "radars/definitions/tech-news.yml").read_text(
        encoding="utf-8"
    )
    assert "must-not-migrate" not in (home / "radars/definitions/tech-news.yml").read_text(
        encoding="utf-8"
    )
    scored = json.loads(
        (home / "radars/cache/tech-news/2026-07-11/scored.json").read_text(encoding="utf-8")
    )
    assert scored[0]["title"] == "LLM agent runtime"
    assert scored[0]["adapter"] == "social-radar-import"
    assert (home / "radars/cache/tech-news/2026-07-11/legacy.json").is_file()
    assert (home / "radars/reports/tech-news/2026-07-11.html").is_file()
    assert not (home / "radars/reports/tech-news/blogs_2026-07-11.html").exists()
    assert (home / "radars/reports/world-news/2026-07-11.md").is_file()
    assert (home / "radars/reports/stocks/2026-07-11.md").is_file()
    status = RadarModule(AlcoveHome.load(home)).status("stocks")["radars"][0]
    assert status["report_state"] == "historical"
    assert status["report_label"] == "Historical migrated report"


def test_import_social_radar_keeps_existing_definition_without_force(tmp_path, capsys):
    social = tmp_path / ".social_radar"
    home = tmp_path / ".alcove"
    (social / "config").mkdir(parents=True)
    (social / "data/radar").mkdir(parents=True)
    existing = home / "radars/definitions/tech-news.yml"
    existing.parent.mkdir(parents=True)
    existing.write_text(
        "\n".join(
            [
                "schema: alcove/radar-definition/v1",
                "id: tech-news",
                "name: User Edited Radar",
                "sources: []",
                "profile: {}",
                "scoring: {}",
                "report: {}",
                "schedule:",
                "  enabled: false",
                "  ttl_hours: 24",
                "notify: {}",
                "tags: []",
                "status: active",
                "created_at: ''",
                "updated_at: ''",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    code = main(["radar", "import-social-radar", str(social), "--home", str(home), "--json"])
    output = capsys.readouterr()

    assert code == 0
    assert '"definition": "kept"' in output.out
    assert "User Edited Radar" in existing.read_text(encoding="utf-8")
