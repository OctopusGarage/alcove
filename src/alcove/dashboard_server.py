from __future__ import annotations

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from typing import Any

from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome


def serve_dashboard(home: AlcoveHome, host: str = "127.0.0.1", port: int = 8765) -> None:
    result = DashboardModule(home=home).build()
    root = Path(result["root"])

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, directory=str(root), **kwargs)

        def _apply_spa_fallback(self) -> None:
            requested = root / self.path.lstrip("/").split("?", 1)[0]
            if self.path not in {"/", ""} and not requested.exists():
                self.path = "/index.html"

        def do_GET(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] == "/snapshot.json":
                self._send_dynamic_snapshot(include_body=True)
                return
            self._apply_spa_fallback()
            super().do_GET()

        def do_HEAD(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] == "/snapshot.json":
                self._send_dynamic_snapshot(include_body=False)
                return
            self._apply_spa_fallback()
            super().do_HEAD()

        def do_POST(self) -> None:  # noqa: N802
            if self.path.split("?", 1)[0] != "/events":
                self.send_error(404)
                return
            self._record_client_event()

        def _send_dynamic_snapshot(self, *, include_body: bool) -> None:
            body = json.dumps(
                DashboardModule(home=home).snapshot(),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if include_body:
                self.wfile.write(body)

        def _record_client_event(self) -> None:
            length = int(self.headers.get("Content-Length") or "0")
            raw = self.rfile.read(min(length, 16_384)) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except json.JSONDecodeError:
                self.send_error(400)
                return
            if not isinstance(payload, dict):
                self.send_error(400)
                return
            action = str(payload.get("action") or "dashboard.event")
            summary = str(payload.get("summary") or action)
            metadata = payload.get("metadata")
            DashboardModule(home=home)._record_event(
                action,
                summary,
                metadata if isinstance(metadata, dict) else {},
                visible=False,
            )
            self.send_response(204)
            self.end_headers()

    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Alcove dashboard: http://{host}:{port}/")
    try:
        server.serve_forever()
    finally:
        server.server_close()
