from __future__ import annotations

import json

from alcove.cli import main
from alcove.home import AlcoveHome
from alcove.radars import RadarDefinition, RadarModule, RadarSource
from alcove.radars import pipeline as radar_pipeline


def test_cli_radar_preset_list_and_init(tmp_path, capsys):
    home = tmp_path / ".alcove"

    list_code = main(["radar", "preset", "list", "--home", str(home), "--json"])
    list_output = capsys.readouterr()
    init_code = main(
        [
            "radar",
            "init",
            "tech-news",
            "--home",
            str(home),
            "--from-preset",
            "tech-news",
            "--json",
        ]
    )
    init_output = capsys.readouterr()
    radar_list_code = main(["radar", "list", "--home", str(home), "--json"])
    radar_list_output = capsys.readouterr()

    assert list_code == 0
    assert '"tech-news"' in list_output.out
    assert '"world-news"' in list_output.out
    assert '"stocks"' in list_output.out
    assert '"sports-news"' in list_output.out
    assert init_code == 0
    assert '"status": "saved"' in init_output.out
    assert radar_list_code == 0
    assert '"tech-news"' in radar_list_output.out


def test_cli_radar_init_refuses_to_overwrite_user_definition_without_force(tmp_path, capsys):
    home = tmp_path / ".alcove"
    definition_path = home / "radars" / "definitions" / "tech-news.yml"

    init_code = main(
        [
            "radar",
            "init",
            "tech-news",
            "--home",
            str(home),
            "--from-preset",
            "tech-news",
            "--json",
        ]
    )
    capsys.readouterr()
    definition_path.write_text(
        definition_path.read_text(encoding="utf-8").replace(
            "name: Tech News", "name: User Edited Tech News"
        ),
        encoding="utf-8",
    )

    overwrite_code = main(
        [
            "radar",
            "init",
            "tech-news",
            "--home",
            str(home),
            "--from-preset",
            "tech-news",
            "--json",
        ]
    )
    overwrite_output = capsys.readouterr()

    assert init_code == 0
    assert overwrite_code == 2
    assert "Radar definition already exists" in overwrite_output.out
    assert "name: User Edited Tech News" in definition_path.read_text(encoding="utf-8")

    force_code = main(
        [
            "radar",
            "init",
            "tech-news",
            "--home",
            str(home),
            "--from-preset",
            "tech-news",
            "--force",
            "--json",
        ]
    )
    force_output = capsys.readouterr()

    assert force_code == 0
    assert '"status": "saved"' in force_output.out
    assert "name: Tech News" in definition_path.read_text(encoding="utf-8")


def test_cli_radar_run_and_status_use_generic_definition(tmp_path, capsys):
    home_path = tmp_path / ".alcove"
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Useful AI signal",
                    "url": "https://example.test/ai",
                    "summary": "LLM systems",
                }
            ]
        ),
        encoding="utf-8",
    )
    home = AlcoveHome.init(home_path)
    RadarModule(home).upsert_definition(
        RadarDefinition(
            id="custom-radar",
            name="Custom Radar",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI", "LLM"], "min_score_threshold": 0.5},
            report={"formats": ["md"]},
        )
    )

    run_code = main(["radar", "run", "custom-radar", "--home", str(home_path), "--json"])
    run_output = capsys.readouterr()
    status_code = main(["radar", "status", "custom-radar", "--home", str(home_path), "--json"])
    status_output = capsys.readouterr()

    assert run_code == 0
    assert '"status": "completed"' in run_output.out
    assert '"included": 1' in run_output.out
    assert status_code == 0
    assert '"custom-radar"' in status_output.out
    assert '"last_run"' in status_output.out


def test_cli_radar_run_can_analyze_cached_results_and_notify(tmp_path, capsys, monkeypatch):
    home_path = tmp_path / ".alcove"
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Useful AI signal",
                    "url": "https://example.test/ai",
                    "summary": "LLM systems",
                }
            ]
        ),
        encoding="utf-8",
    )
    home = AlcoveHome.init(home_path)
    RadarModule(home).upsert_definition(
        RadarDefinition(
            id="custom-radar",
            name="Custom Radar",
            sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
            profile={"interest_tags": ["AI", "LLM"], "min_score_threshold": 0.5},
            report={"formats": ["md"]},
            ai_summary={"provider": "codex"},
            notify={"channel": "telegram"},
        )
    )
    first_code = main(["radar", "run", "custom-radar", "--home", str(home_path), "--json"])
    capsys.readouterr()
    fixture.unlink()
    sent_messages: list[str] = []

    monkeypatch.setattr(
        radar_pipeline,
        "run_ai_summary",
        lambda **_: {
            "status": "completed",
            "provider": "codex",
            "summary": "Cached AI summary.",
        },
    )
    monkeypatch.setattr(
        radar_pipeline,
        "send_telegram_message",
        lambda *, home, text: sent_messages.append(text) or {"status": "sent"},
    )

    analyze_code = main(
        [
            "radar",
            "run",
            "custom-radar",
            "--home",
            str(home_path),
            "--skip-fetch",
            "--force",
            "--ai",
            "--notify",
            "--json",
        ]
    )
    analyze_output = capsys.readouterr()

    assert first_code == 0
    assert analyze_code == 0
    assert '"status": "completed"' in analyze_output.out
    assert '"provider": "codex"' in analyze_output.out
    assert sent_messages
    assert "Cached AI summary." in sent_messages[0]
