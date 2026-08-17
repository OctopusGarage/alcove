from __future__ import annotations

import base64
import hashlib
import hmac
import json
import subprocess
from types import SimpleNamespace

from alcove import notifications
from alcove.notification_delivery import (
    combined_notification_status,
    notification_bool,
    notification_sink_label,
    notification_sinks,
)


def test_feishu_signature_matches_custom_bot_contract() -> None:
    expected = base64.b64encode(
        hmac.new(b"1234567890\nsecret", b"", digestmod=hashlib.sha256).digest()
    ).decode("utf-8")

    assert notifications.feishu_signature(timestamp="1234567890", secret="secret") == expected  # noqa: S106


def test_notification_delivery_policy_normalizes_sinks_and_status() -> None:
    policy = {
        "channel": "telegram",
        "include_ai_summary": False,
        "sinks": [
            {"type": "feishu", "name": "Team Bot"},
            {"type": "feishu", "name": "Team Bot", "include_ai_summary": True},
        ],
    }

    sinks = notification_sinks(policy, inheritable_keys=("include_ai_summary",))
    assert sinks == [
        {"include_ai_summary": False, "type": "feishu", "name": "Team Bot"},
        {"include_ai_summary": True, "type": "feishu", "name": "Team Bot"},
    ]
    assert notification_bool(policy, sinks[0], "include_ai_summary", True) is False
    assert notification_bool(policy, sinks[1], "include_ai_summary", False) is True

    results: dict[str, dict[str, object]] = {}
    first = notification_sink_label(sinks[0], results)
    results[first] = {"status": "sent"}
    second = notification_sink_label(sinks[1], results)
    results[second] = {"status": "failed"}

    assert first == "team-bot"
    assert second == "team-bot-2"
    assert combined_notification_status(results) == "partial"


def test_send_feishu_message_posts_text_payload_with_optional_signature(
    monkeypatch, tmp_path
) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"code":0}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr(notifications, "urlopen", fake_urlopen)
    monkeypatch.setattr(notifications.time, "time", lambda: 1234567890)
    home = SimpleNamespace(root=tmp_path)
    report_path = tmp_path / "report.html"
    report_path.write_text("<html></html>", encoding="utf-8")

    result = notifications.send_feishu_message(
        home=home,
        sink={
            "type": "feishu",
            "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/test",
            "secret": "secret",
        },
        title="Radar: Tech News",
        text="Core summary",
        report_path=report_path,
    )

    assert result["status"] == "sent"
    assert captured["url"] == "https://open.feishu.cn/open-apis/bot/v2/hook/test"
    assert captured["timeout"] == 15
    body = captured["body"]
    assert body["msg_type"] == "text"
    assert body["timestamp"] == "1234567890"
    assert body["sign"] == notifications.feishu_signature(
        timestamp="1234567890",
        secret="secret",  # noqa: S106
    )
    assert "Radar: Tech News" in body["content"]["text"]
    assert "Core summary" in body["content"]["text"]
    assert "HTML report:" not in body["content"]["text"]
    assert ".html" not in body["content"]["text"]


def test_send_feishu_message_reports_remote_error_code(monkeypatch, tmp_path) -> None:
    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def read(self) -> bytes:
            return b'{"code":19022,"msg":"signature mismatch"}'

    monkeypatch.setattr(notifications, "urlopen", lambda request, timeout: FakeResponse())

    result = notifications.send_feishu_message(
        home=SimpleNamespace(root=tmp_path),
        sink={"type": "feishu", "webhook": "https://open.feishu.cn/open-apis/bot/v2/hook/test"},
        title="Radar failed",
        text="Core summary",
    )

    assert result["status"] == "failed"
    assert result["http_status"] == 200
    assert result["remote_code"] == 19022
    assert "signature mismatch" in result["response"]


def test_send_telegram_document_reports_missing_attachment(tmp_path) -> None:
    home = SimpleNamespace(root=tmp_path)
    (tmp_path / ".env").write_text(
        "ALCOVE_TELEGRAM_BOT_TOKEN=token\nALCOVE_TELEGRAM_CHAT_ID=chat\n",
        encoding="utf-8",
    )

    result = notifications.send_telegram_document(
        home=home,
        path=tmp_path / "missing-report.md",
        caption="Radar report",
    )

    assert result["status"] == "failed"
    assert "telegram document not found:" in result["error"]
    assert "missing-report.md" in result["error"]


def test_local_env_values_ignores_comments_malformed_and_invalid_names(tmp_path) -> None:
    (tmp_path / ".env").write_text(
        "\n"
        "# local secrets\n"
        "ALCOVE_TELEGRAM_BOT_TOKEN=' quoted-token '\n"
        'TELEGRAM_CHAT_ID="chat-123"\n'
        "NOT A KEY=value\n"
        "MISSING_EQUALS\n"
        "=empty-name\n",
        encoding="utf-8",
    )

    assert notifications.local_env_values(tmp_path) == {
        "ALCOVE_TELEGRAM_BOT_TOKEN": "quoted-token",
        "TELEGRAM_CHAT_ID": "chat-123",
    }


def test_send_tcb_notification_uses_notify_attach_protocol(monkeypatch, tmp_path) -> None:
    calls: list[dict[str, object]] = []
    report_md = tmp_path / "report.md"
    report_html = tmp_path / "report.html"
    report_md.write_text("# Report\n", encoding="utf-8")
    report_html.write_text("<html></html>\n", encoding="utf-8")

    class Completed:
        returncode = 0
        stdout = '{"status":"sent","deliveries":[{"channel":"lark","ok":true}]}\n'
        stderr = ""

    def fake_run(command, input, text, capture_output, timeout, check):
        calls.append(
            {
                "command": command,
                "input": input,
                "text": text,
                "capture_output": capture_output,
                "timeout": timeout,
                "check": check,
            }
        )
        return Completed()

    monkeypatch.setattr(notifications.subprocess, "run", fake_run)

    result = notifications.send_tcb_notification(
        sink={"type": "tcb", "channel": "lark"},
        title="Radar: Tech News",
        text="Core summary",
        attachments=[report_md, report_html],
    )

    assert result["status"] == "sent"
    assert result["deliveries"] == [{"channel": "lark", "ok": True}]
    assert calls
    command = calls[0]["command"]
    assert command[:2] == ["tcb", "notify"]
    assert "--stdin" in command
    assert "--json" in command
    assert "--channel" in command
    assert "lark" in command
    assert command.count("--attach") == 2
    assert str(report_md) in command
    assert str(report_html) in command
    assert calls[0]["input"] == "Core summary"


def test_send_tcb_notification_reports_timeout(monkeypatch) -> None:
    def fake_run(command, input, text, capture_output, timeout, check):
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(notifications.subprocess, "run", fake_run)

    result = notifications.send_tcb_notification(
        sink={"type": "tcb", "timeout_seconds": "2"},
        title="Radar ready",
        text="Core summary",
        attachments=[],
    )

    assert result == {"status": "failed", "error": "tcb notify timed out after 2s"}


def test_send_tcb_notification_compacts_user_path_in_non_json_stdout(monkeypatch) -> None:
    class Completed:
        returncode = 0
        stdout = "queued notification for /Users/alice/AlcoveHub/reports/radar.md\n"
        stderr = ""

    monkeypatch.setattr(notifications.subprocess, "run", lambda *args, **kwargs: Completed())

    result = notifications.send_tcb_notification(
        sink={"type": "tcb"},
        title="Radar ready",
        text="Core summary",
        attachments=[],
    )

    assert result["status"] == "sent"
    assert result["attachment_count"] == 0
    assert result["output"] == "queued notification for ~/AlcoveHub/reports/radar.md"


def test_send_tcb_notification_routes_to_explicit_session(monkeypatch) -> None:
    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = '{"status":"sent"}\n'
        stderr = ""

    def fake_run(command, input, text, capture_output, timeout, check):
        calls.append(command)
        return Completed()

    monkeypatch.setattr(notifications.subprocess, "run", fake_run)

    notifications.send_tcb_notification(
        sink={
            "type": "tcb",
            "channel": "lark",
            "session": "tmux_proj_alcovehub",
        },
        title="Radar ready",
        text="Core summary",
        attachments=[],
    )

    assert calls[0][0:2] == ["tcb", "notify"]
    assert calls[0][calls[0].index("--session") + 1] == "tmux_proj_alcovehub"


def test_send_tcb_notification_normalizes_failed_deliveries(monkeypatch) -> None:
    class Completed:
        returncode = 0
        stdout = '{"status":"sent","deliveries":[{"channel":"lark","ok":false}]}\n'
        stderr = ""

    def fake_run(command, input, text, capture_output, timeout, check):
        return Completed()

    monkeypatch.setattr(notifications.subprocess, "run", fake_run)

    result = notifications.send_tcb_notification(
        sink={"type": "tcb", "channel": "lark"},
        title="Radar: Tech News",
        text="Core summary",
        attachments=[],
    )

    assert result["status"] == "failed"
    assert result["deliveries"] == [{"channel": "lark", "ok": False}]
