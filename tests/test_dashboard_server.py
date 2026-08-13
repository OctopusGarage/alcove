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
    host: str | None = "localhost",
) -> bytes:
    header_lines = [
        f"{method} {path} HTTP/1.1",
        "Connection: close",
    ]
    if host is not None:
        header_lines.insert(1, f"Host: {host}")
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


def test_dashboard_server_head_snapshot_has_fresh_headers_without_body(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / "home")
    requests = [_http_request("HEAD", "/snapshot.json")]

    responses = _serve_requests(monkeypatch, home, requests)
    status, headers, body = _parse_http_response(responses[0])

    assert status == "HTTP/1.0 200 OK"
    assert headers["content-type"] == "application/json; charset=utf-8"
    assert headers["cache-control"] == "no-store"
    assert int(headers["content-length"]) > 0
    assert body == b""


def test_dashboard_server_rejects_non_object_events_and_unknown_post_paths(
    tmp_path,
    monkeypatch,
):
    home = AlcoveHome.init(tmp_path / "home")
    requests = [
        _http_request("POST", "/events", b'["not", "an", "object"]'),
        _http_request("POST", "/unknown", b"{}"),
    ]

    responses = _serve_requests(monkeypatch, home, requests)
    non_object_status, _, _ = _parse_http_response(responses[0])
    unknown_status, _, _ = _parse_http_response(responses[1])
    snapshot = DashboardModule(home=home).snapshot()

    assert non_object_status.startswith("HTTP/1.0 400 ")
    assert unknown_status.startswith("HTTP/1.0 404 ")
    assert snapshot["usage"]["dashboard"]["routes"] == {}


def test_dashboard_server_rejects_event_posts_with_invalid_content_length(
    tmp_path,
    monkeypatch,
):
    home = AlcoveHome.init(tmp_path / "home")
    requests = [
        _http_request(
            "POST",
            "/events",
            b"{}",
            headers={"Content-Length": "not-a-number"},
        )
    ]

    responses = _serve_requests(monkeypatch, home, requests)
    status, _, _ = _parse_http_response(responses[0])
    snapshot = DashboardModule(home=home).snapshot()

    assert status.startswith("HTTP/1.0 400 ")
    assert snapshot["usage"]["dashboard"]["routes"] == {}


def test_dashboard_server_rejects_event_posts_with_negative_content_length(
    tmp_path,
    monkeypatch,
):
    home = AlcoveHome.init(tmp_path / "home")
    requests = [
        _http_request(
            "POST",
            "/events",
            b"{}",
            headers={"Content-Length": "-1"},
        )
    ]

    responses = _serve_requests(monkeypatch, home, requests)
    status, _, _ = _parse_http_response(responses[0])
    snapshot = DashboardModule(home=home).snapshot()

    assert status.startswith("HTTP/1.0 400 ")
    assert snapshot["usage"]["dashboard"]["routes"] == {}


def test_dashboard_server_rejects_browser_origin_when_host_header_is_missing(
    tmp_path,
    monkeypatch,
):
    home = AlcoveHome.init(tmp_path / "home")
    requests = [
        _http_request(
            "POST",
            "/events",
            b"{}",
            headers={"Origin": "http://localhost"},
            host=None,
        )
    ]

    responses = _serve_requests(monkeypatch, home, requests)
    status, _, _ = _parse_http_response(responses[0])
    snapshot = DashboardModule(home=home).snapshot()

    assert status.startswith("HTTP/1.0 403 ")
    assert snapshot["usage"]["dashboard"]["routes"] == {}


def test_dashboard_server_spa_fallback_serves_index_for_unknown_get(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / "home")
    requests = [_http_request("GET", "/missing/client/route?tab=tasks")]

    responses = _serve_requests(monkeypatch, home, requests)
    status, headers, body = _parse_http_response(responses[0])

    assert status == "HTTP/1.0 200 OK"
    assert headers["content-type"].startswith("text/html")
    assert b"Alcove" in body
