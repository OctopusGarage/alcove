from __future__ import annotations

import argparse
from contextlib import suppress
from functools import partial
import http.server
import json
from pathlib import Path
import shutil
import socketserver
import subprocess
import threading
from typing import Any


def check_dashboard_render(dashboard_root: Path, output_dir: Path) -> dict[str, Any]:
    dashboard_root = dashboard_root.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    index = dashboard_root / "index.html"
    snapshot = dashboard_root / "snapshot.json"
    assets = dashboard_root / "assets"

    checks = [
        {
            "name": "index_html_exists",
            "status": "passed" if index.is_file() else "failed",
            "detail": str(index),
        },
        {
            "name": "snapshot_json_exists",
            "status": "passed" if snapshot.is_file() else "failed",
            "detail": str(snapshot),
        },
        {
            "name": "compiled_assets_exist",
            "status": "passed" if _has_compiled_assets(assets) else "failed",
            "detail": str(assets),
        },
    ]
    failed = [check["name"] for check in checks if check["status"] == "failed"]
    if failed:
        return {
            "status": "failed",
            "mode": "compiled_dashboard",
            "checks": checks,
            "failed": failed,
        }

    playwright = shutil.which("playwright")
    if playwright is None:
        return {
            "status": "skipped",
            "mode": "compiled_dashboard",
            "reason": "playwright CLI is not installed",
            "checks": checks,
        }

    screenshot = output_dir / "dashboard.png"
    with _serve_directory(dashboard_root) as url:
        command = [playwright, "screenshot", "--timeout", "15000", url, str(screenshot)]
        completed = subprocess.run(command, text=True, capture_output=True, check=False)  # noqa: S603

    screenshot_ok = (
        completed.returncode == 0 and screenshot.is_file() and screenshot.stat().st_size > 0
    )
    playwright_error = (completed.stderr or completed.stdout).strip()
    if completed.returncode != 0 and _missing_playwright_browser(playwright_error):
        checks.append(
            {
                "name": "playwright_screenshot",
                "status": "skipped",
                "detail": "playwright browser binaries are not installed",
            }
        )
        return {
            "status": "skipped",
            "mode": "compiled_dashboard",
            "reason": "playwright browser binaries are not installed",
            "checks": checks,
        }
    checks.append(
        {
            "name": "playwright_screenshot",
            "status": "passed" if screenshot_ok else "failed",
            "detail": str(screenshot),
        }
    )
    payload: dict[str, Any] = {
        "status": "passed" if screenshot_ok else "failed",
        "mode": "compiled_dashboard",
        "checks": checks,
        "screenshot": str(screenshot) if screenshot.is_file() else "",
        "screenshot_bytes": screenshot.stat().st_size if screenshot.is_file() else 0,
    }
    if completed.returncode != 0:
        payload["playwright_error"] = playwright_error[-1200:]
    return payload


def _has_compiled_assets(assets: Path) -> bool:
    return assets.is_dir() and any(path.suffix == ".js" for path in assets.iterdir())


def _missing_playwright_browser(error: str) -> bool:
    lower = error.lower()
    return "playwright install" in lower or "executable doesn't exist" in lower


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        return


class _ThreadingTCPServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


class _serve_directory:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.server: _ThreadingTCPServer | None = None
        self.thread: threading.Thread | None = None

    def __enter__(self) -> str:
        handler = partial(_QuietHandler, directory=str(self.root))
        self.server = _ThreadingTCPServer(("127.0.0.1", 0), handler)
        host, port = self.server.server_address
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return f"http://{host}:{port}/"

    def __exit__(self, *exc: object) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            with suppress(RuntimeError):
                self.thread.join(timeout=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify Alcove dashboard browser render output.")
    parser.add_argument("--dashboard-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    payload = check_dashboard_render(
        dashboard_root=Path(args.dashboard_root),
        output_dir=Path(args.output_dir),
    )
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"dashboard render: {payload['status']}")
    return 1 if payload["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
