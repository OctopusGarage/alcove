from __future__ import annotations

import shutil

from alcove.dashboard_render_check import check_dashboard_render


def test_dashboard_render_check_fails_without_compiled_assets(tmp_path):
    root = tmp_path / "dashboard"
    root.mkdir()
    (root / "index.html").write_text("<div id='app'></div>", encoding="utf-8")
    (root / "snapshot.json").write_text("{}", encoding="utf-8")

    payload = check_dashboard_render(root, tmp_path / "out")

    assert payload["status"] == "failed"
    assert "compiled_assets_exist" in payload["failed"]


def test_dashboard_render_check_skips_browser_when_playwright_missing(tmp_path, monkeypatch):
    root = tmp_path / "dashboard"
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text("<div id='app'></div>", encoding="utf-8")
    (root / "snapshot.json").write_text("{}", encoding="utf-8")
    (assets / "index.js").write_text("console.log('ok')", encoding="utf-8")

    real_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name == "playwright":
            return None
        return real_which(name)

    monkeypatch.setattr(shutil, "which", fake_which)

    payload = check_dashboard_render(root, tmp_path / "out")

    assert payload["status"] == "skipped"
    assert payload["reason"] == "playwright CLI is not installed"
