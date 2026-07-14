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


def test_dashboard_render_check_skips_when_playwright_browser_missing(tmp_path, monkeypatch):
    root = _compiled_dashboard_root(tmp_path)
    fake_playwright = tmp_path / "playwright"
    fake_playwright.write_text(
        "#!/usr/bin/env sh\necho 'Please run playwright install' >&2\nexit 1\n"
    )
    fake_playwright.chmod(0o755)
    monkeypatch.setattr(
        shutil, "which", lambda name: str(fake_playwright) if name == "playwright" else None
    )

    payload = check_dashboard_render(root, tmp_path / "out")

    assert payload["status"] == "skipped"
    assert payload["reason"] == "playwright browser binaries are not installed"
    assert payload["checks"][-1]["name"] == "playwright_screenshot"
    assert payload["checks"][-1]["status"] == "skipped"


def test_dashboard_render_check_reports_playwright_screenshot_failure(tmp_path, monkeypatch):
    root = _compiled_dashboard_root(tmp_path)
    fake_playwright = tmp_path / "playwright"
    fake_playwright.write_text("#!/usr/bin/env sh\necho 'navigation timeout' >&2\nexit 1\n")
    fake_playwright.chmod(0o755)
    monkeypatch.setattr(
        shutil, "which", lambda name: str(fake_playwright) if name == "playwright" else None
    )

    payload = check_dashboard_render(root, tmp_path / "out")

    assert payload["status"] == "failed"
    assert payload["checks"][-1] == {
        "name": "playwright_screenshot",
        "status": "failed",
        "detail": str(tmp_path / "out" / "dashboard.png"),
    }
    assert payload["playwright_error"] == "navigation timeout"


def _compiled_dashboard_root(tmp_path):
    root = tmp_path / "dashboard"
    assets = root / "assets"
    assets.mkdir(parents=True)
    (root / "index.html").write_text("<div id='app'></div>", encoding="utf-8")
    (root / "snapshot.json").write_text("{}", encoding="utf-8")
    (assets / "index.js").write_text("console.log('ok')", encoding="utf-8")
    return root
