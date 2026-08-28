from __future__ import annotations

import json
import shutil
import time
from typing import Any

from alcove.paths import compact_user_path

RETRYABLE_CAPTURE_ERRORS = (
    "Navigation failed with HTTP 403",
    "Navigation failed with HTTP 429",
    "Navigation failed with HTTP 500",
    "Navigation failed with HTTP 502",
    "Navigation failed with HTTP 503",
    "Navigation failed with HTTP 504",
    "net::ERR_HTTP2_PROTOCOL_ERROR",
    "net::ERR_NETWORK_CHANGED",
    "net::ERR_TIMED_OUT",
    "Timeout",
)


class BlogCaptureModule:
    """Captures discovered blog articles into a managed knowledge base inbox."""

    def __init__(self, host: Any) -> None:
        self.host = host

    def capture(self, source: Any, article: Any) -> dict[str, Any]:
        if not source.capture.kb:
            return {"status": "failed", "error": "capture.kb is required when capture is enabled"}
        if source.capture.adapter != "clipsmith":
            return {
                "status": "pending",
                "adapter": source.capture.adapter,
                "reason": "capture adapter is not implemented",
            }
        record = self.host.home.get_knowledge_base(source.capture.kb)
        target_dir = record.path / source.capture.inbox_path
        skill_dir = self.host._clipsmith_web_skill_dir()
        if skill_dir is None or shutil.which("npx") is None or shutil.which("clipsmith") is None:
            return {
                "status": "pending",
                "adapter": "clipsmith",
                "reason": "clipsmith-web skill, npx, or clipsmith command is unavailable",
                "capture_command": (
                    f"Use clipsmith-capture to capture {article.url} and sink it to {target_dir}"
                ),
            }
        output_dir = self.host.captures_root / source.id
        output_dir.mkdir(parents=True, exist_ok=True)
        capture_command = [
            "npx",
            "tsx",
            "scripts/run.ts",
            "--url",
            article.url,
            "--output_dir",
            str(output_dir),
        ]
        capture_result = self._run_capture_with_retry(capture_command, skill_dir)
        if capture_result.returncode != 0:
            return {
                "status": "failed",
                "adapter": "clipsmith",
                "error": capture_result.stderr.strip() or capture_result.stdout.strip(),
            }
        bundle_dir = _json_field(capture_result.stdout, "bundle_dir")
        if not bundle_dir:
            return {
                "status": "failed",
                "adapter": "clipsmith",
                "error": "clipsmith-web did not return bundle_dir",
            }
        validate = self.host._run_command(
            ["clipsmith", "validate-bundle", bundle_dir, "--json"],
            cwd=None,
            timeout=60,
        )
        if validate.returncode != 0:
            return {
                "status": "failed",
                "adapter": "clipsmith",
                "bundle_dir": compact_user_path(bundle_dir),
                "error": validate.stderr.strip() or validate.stdout.strip(),
            }
        sink = self.host._run_command(
            ["clipsmith", "sink", "directory", bundle_dir, str(target_dir), "--json"],
            cwd=None,
            timeout=60,
        )
        if sink.returncode != 0:
            return {
                "status": "failed",
                "adapter": "clipsmith",
                "bundle_dir": compact_user_path(bundle_dir),
                "error": sink.stderr.strip() or sink.stdout.strip(),
            }
        return {
            "status": "captured",
            "adapter": "clipsmith",
            "bundle_dir": compact_user_path(bundle_dir),
            "inbox_path": compact_user_path(_json_field(sink.stdout, "path") or target_dir),
        }

    def _run_capture_with_retry(self, command: list[str], skill_dir: Any) -> Any:
        result = self.host._run_command(command, cwd=skill_dir, timeout=180)
        if result.returncode == 0 or not _is_retryable_capture_error(result):
            return result
        time.sleep(2)
        return self.host._run_command(command, cwd=skill_dir, timeout=180)


def _json_field(text: str, field: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get(field) or "")


def _is_retryable_capture_error(result: Any) -> bool:
    text = f"{getattr(result, 'stderr', '')}\n{getattr(result, 'stdout', '')}"
    return any(marker in text for marker in RETRYABLE_CAPTURE_ERRORS)
