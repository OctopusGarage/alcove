from __future__ import annotations

from html import escape
from pathlib import Path
import re
from typing import Any

from alcove.notifications import (
    send_feishu_message,
    send_tcb_notification,
    send_telegram_message,
    telegram_credential,
)


class BlogNotifier:
    """Formats and delivers blog monitor notifications."""

    def __init__(self, home: Any) -> None:
        self.home = home

    def notify(
        self,
        source: Any,
        articles: list[Any],
        captures: list[dict[str, Any]],
        summary: str,
    ) -> dict[str, Any]:
        if source.notify.channel not in {"telegram", "feishu", "lark", "tcb", "tmux_claude_bot"}:
            return {"status": "skipped", "reason": "unsupported notification channel"}
        if source.notify.channel == "telegram" and not self._has_telegram_credentials():
            return {"status": "skipped", "reason": "telegram token or chat id missing"}

        statuses = []
        for article, capture in zip(articles, captures, strict=True):
            text = self.article_message(source, article, capture, summary=summary)
            if source.notify.channel == "feishu":
                status = send_feishu_message(
                    home=self.home,
                    sink={},
                    title=f"Blog Monitor: {source.name}",
                    text=text,
                )
            elif source.notify.channel in {"lark", "tcb", "tmux_claude_bot"}:
                status = send_tcb_notification(
                    sink=self._tcb_sink(source),
                    title=f"Blog Monitor: {source.name}",
                    text=text,
                    attachments=[],
                )
            else:
                status = send_telegram_message(home=self.home, text=text)
            status.update(
                {
                    "source_id": source.id,
                    "source_name": source.name,
                    "article_title": article.title,
                    "article_url": article.url,
                }
            )
            statuses.append(status)
            if status.get("status") == "failed":
                return {
                    "status": "failed",
                    "sent_count": sum(1 for item in statuses if item.get("status") == "sent"),
                    "messages": statuses,
                }
        return {"status": "sent", "sent_count": len(statuses), "messages": statuses}

    def notify_failure(self, source: Any, *, stage: str, error: str) -> dict[str, Any]:
        retry_command = self.failure_retry_command(source)
        if source.notify.channel not in {"telegram", "feishu", "lark", "tcb", "tmux_claude_bot"}:
            return {
                "status": "skipped",
                "reason": "unsupported notification channel",
                "source_id": source.id,
                "stage": stage,
                "error": error,
                "retry_command": retry_command,
            }
        if source.notify.channel == "telegram" and not self._has_telegram_credentials():
            return {
                "status": "skipped",
                "reason": "telegram token or chat id missing",
                "source_id": source.id,
                "stage": stage,
                "error": error,
                "retry_command": retry_command,
            }
        text = self.failure_message(source, stage=stage, error=error)
        if source.notify.channel == "feishu":
            result = send_feishu_message(
                home=self.home,
                sink={},
                title=f"Blog Monitor Failed: {source.name}",
                text=text,
            )
        elif source.notify.channel in {"lark", "tcb", "tmux_claude_bot"}:
            result = send_tcb_notification(
                sink=self._tcb_sink(source),
                title=f"Blog Monitor Failed: {source.name}",
                text=text,
                attachments=[],
            )
        else:
            result = send_telegram_message(home=self.home, text=text)
        return {
            **result,
            "source_id": source.id,
            "stage": stage,
            "error": error,
            "retry_command": retry_command,
        }

    def article_message(
        self,
        source: Any,
        article: Any,
        capture: dict[str, Any],
        *,
        summary: str,
    ) -> str:
        message_lines = [
            f"<b>Blog Monitor: {escape(source.name)}</b>",
            "",
            f'<a href="{escape(article.url)}">{escape(article.title)}</a>',
        ]
        article_summary = captured_article_summary(capture)
        if article_summary:
            message_lines.extend(["", f"<b>Summary</b>\n{escape(article_summary)}"])
        elif summary:
            message_lines.extend(["", f"<b>Run Summary</b>\n{escape(summary)}"])
        else:
            status = str(capture.get("status") or "skipped")
            message_lines.extend(["", f"Capture: {escape(status)}"])
        return "\n".join(message_lines)

    def failure_message(self, source: Any, *, stage: str, error: str) -> str:
        action = f"检查 {source.name} 博客监控失败原因，并修复或补采集"
        lines = [
            f"<b>Blog Monitor Failed: {escape(source.name)}</b>",
            "",
            f"Error: {escape(error[:1200])}",
            f"Source ID: {escape(source.id)}",
            f"Stage: {escape(stage)}",
            f"Retry: <code>{escape(self.failure_retry_command(source))}</code>",
            f"URL: {escape(source.url)}",
            "",
            "Suggested action:",
            escape(action),
        ]
        return "\n".join(lines)

    def failure_retry_command(self, source: Any) -> str:
        return f"alcove blog check {source.id} --json"

    def telegram_credential(self, alcove_name: str, generic_name: str) -> str:
        return telegram_credential(self.home, alcove_name, generic_name)

    def _has_telegram_credentials(self) -> bool:
        token = self.telegram_credential("ALCOVE_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
        chat_id = self.telegram_credential("ALCOVE_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID")
        return bool(token and chat_id)

    def _tcb_sink(self, source: Any) -> dict[str, Any]:
        channel = str(source.notify.channel or "").strip()
        if channel == "lark":
            return {"type": "tcb", "channel": "lark"}
        if channel == "tmux_claude_bot":
            return {"type": "tmux_claude_bot"}
        return {"type": "tcb"}


def captured_article_summary(capture: dict[str, Any], max_chars: int = 1200) -> str:
    inbox_path = str(capture.get("inbox_path") or "")
    if not inbox_path:
        return ""
    summary_path = Path(inbox_path).expanduser() / "summary.md"
    if not summary_path.is_file():
        return ""
    text = summary_path.read_text(encoding="utf-8", errors="replace").strip()
    text = re.sub(r"^#\s*Summary\s*", "", text, flags=re.I).strip()
    text = re.sub(r"\n{3,}", "\n\n", text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."
