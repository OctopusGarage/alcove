from __future__ import annotations

import base64
import hashlib
import hmac
import json
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
