from __future__ import annotations

from collections.abc import Callable, Iterable
import json
import socket

import alcove.dashboard_server as dashboard_server
from alcove.dashboard import DashboardModule
from alcove.home import AlcoveHome
from alcove.pins import AddPinRequest, PinsModule


def _http_request(
    method: str,
    path: str,
    body: bytes = b"",
    *,
    headers: dict[str, str] | None = None,
) -> bytes:
    header_lines = [
        f"{method} {path} HTTP/1.1",
        "Host: localhost",
        "Connection: close",
    ]
    for key, value in (headers or {}).items():
        header_lines.append(f"{key}: {value}")
    if body:
        header_lines.extend(
            [
                "Content-Type: application/json",
                f"Content-Length: {len(body)}",
            ]
        )
    return ("\r\n".join(header_lines) + "\r\n\r\n").encode("ascii") + body


def _parse_http_response(raw: bytes) -> tuple[str, dict[str, str], bytes]:
    header_blob, _, body = raw.partition(b"\r\n\r\n")
    lines = header_blob.decode("iso-8859-1").splitlines()
    headers = {}
    for line in lines[1:]:
        key, _, value = line.partition(":")
        headers[key.lower()] = value.strip()
    return lines[0], headers, body


def _serve_requests(
    monkeypatch,
    home: AlcoveHome,
    requests: Iterable[bytes],
    *,
    before_request: Callable[[], None] | None = None,
) -> list[bytes]:
    responses: list[bytes] = []

    class FakeServer:
        def __init__(self, server_address, handler_class) -> None:
            self.server_address = server_address
            self.RequestHandlerClass = handler_class
            self.server_name = server_address[0]
            self.server_port = server_address[1]
            self.closed = False

        def serve_forever(self) -> None:
            for raw_request in requests:
                if before_request is not None:
                    before_request()
                server_socket, client_socket = socket.socketpair()
                try:
                    client_socket.sendall(raw_request)
                    client_socket.shutdown(socket.SHUT_WR)
                    self.RequestHandlerClass(server_socket, ("127.0.0.1", 34567), self)
                    server_socket.shutdown(socket.SHUT_WR)
                    chunks = []
                    while chunk := client_socket.recv(65_536):
                        chunks.append(chunk)
                    responses.append(b"".join(chunks))
                finally:
                    server_socket.close()
                    client_socket.close()

        def server_close(self) -> None:
            self.closed = True

    monkeypatch.setattr(dashboard_server, "ThreadingHTTPServer", FakeServer)
    dashboard_server.serve_dashboard(home, host="127.0.0.1", port=0)
    return responses


def test_dashboard_server_snapshot_endpoint_returns_live_no_store_snapshot(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / "home")
    requests = [_http_request("GET", "/snapshot.json")]
    added = False

    def add_pin_after_initial_build() -> None:
        nonlocal added
        if added:
            return
        PinsModule(home=home).add(
            AddPinRequest(
                title="Live Dashboard Pin",
                summary="Added after server startup.",
                content="The server endpoint should read a fresh snapshot.",
            )
        )
        added = True

    responses = _serve_requests(
        monkeypatch,
        home,
        requests,
        before_request=add_pin_after_initial_build,
    )

    status, headers, body = _parse_http_response(responses[0])
    payload = json.loads(body)

    assert status == "HTTP/1.0 200 OK"
    assert headers["content-type"] == "application/json; charset=utf-8"
    assert headers["cache-control"] == "no-store"
    assert any(row["title"] == "Live Dashboard Pin" for row in payload["search_index"])


def test_dashboard_server_records_valid_client_events_and_rejects_bad_json(
    tmp_path,
    monkeypatch,
):
    home = AlcoveHome.init(tmp_path / "home")
    event = {
        "action": "dashboard.route",
        "summary": "Dashboard route viewed",
        "metadata": {"route": "/tasks"},
    }
    requests = [
        _http_request("POST", "/events", json.dumps(event).encode("utf-8")),
        _http_request("POST", "/events", b"{not-json"),
    ]

    responses = _serve_requests(monkeypatch, home, requests)
    success_status, _, success_body = _parse_http_response(responses[0])
    bad_status, _, _ = _parse_http_response(responses[1])
    snapshot = DashboardModule(home=home).snapshot()

    assert success_status == "HTTP/1.0 204 No Content"
    assert success_body == b""
    assert bad_status.startswith("HTTP/1.0 400 ")
    assert snapshot["usage"]["dashboard"]["routes"] == {"/tasks": 1}
    assert all(row.get("area") != "dashboard" for row in snapshot["activity"])


def test_dashboard_server_rejects_foreign_origin_event_posts(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / "home")
    event = {
        "action": "dashboard.route",
        "summary": "Dashboard route viewed",
        "metadata": {"route": "/tasks"},
    }
    requests = [
        _http_request(
            "POST",
            "/events",
            json.dumps(event).encode("utf-8"),
            headers={"Origin": "https://attacker.example"},
        )
    ]

    responses = _serve_requests(monkeypatch, home, requests)
    status, _, _ = _parse_http_response(responses[0])
    snapshot = DashboardModule(home=home).snapshot()

    assert status.startswith("HTTP/1.0 403 ")
    assert snapshot["usage"]["dashboard"]["routes"] == {}


def test_dashboard_server_accepts_same_origin_event_posts(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / "home")
    event = {
        "action": "dashboard.route",
        "summary": "Dashboard route viewed",
        "metadata": {"route": "/tasks"},
    }
    requests = [
        _http_request(
            "POST",
            "/events",
            json.dumps(event).encode("utf-8"),
            headers={"Origin": "http://localhost"},
        )
    ]

    responses = _serve_requests(monkeypatch, home, requests)
    status, _, body = _parse_http_response(responses[0])
    snapshot = DashboardModule(home=home).snapshot()

    assert status == "HTTP/1.0 204 No Content"
    assert body == b""
    assert snapshot["usage"]["dashboard"]["routes"] == {"/tasks": 1}
