from __future__ import annotations

import base64
import hashlib
import hmac
import json
from mimetypes import guess_type
import os
from pathlib import Path
import re
import subprocess
import time
from typing import Any
from urllib.request import Request, urlopen

from alcove.paths import compact_user_path, compact_user_paths_in_text


def send_telegram_message(*, home: Any, text: str) -> dict[str, Any]:
    token = telegram_credential(home, "ALCOVE_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    chat_id = telegram_credential(home, "ALCOVE_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"status": "skipped", "reason": "telegram token or chat id missing"}
    return send_telegram_message_with_credentials(token=token, chat_id=chat_id, text=text)


def send_telegram_document(*, home: Any, path: Path, caption: str = "") -> dict[str, Any]:
    token = telegram_credential(home, "ALCOVE_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
    chat_id = telegram_credential(home, "ALCOVE_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"status": "skipped", "reason": "telegram token or chat id missing"}
    if not path.is_file():
        return {
            "status": "failed",
            "error": f"telegram document not found: {compact_user_path(path)}",
        }
    return send_telegram_document_with_credentials(
        token=token,
        chat_id=chat_id,
        path=path,
        caption=caption,
    )


def send_feishu_message(
    *,
    home: Any,
    sink: dict[str, Any],
    title: str,
    text: str,
    report_path: Path | None = None,
) -> dict[str, Any]:
    webhook = _sink_secret(home, sink, "webhook", "webhook_env", "ALCOVE_FEISHU_WEBHOOK_URL")
    if not webhook:
        return {"status": "skipped", "reason": "feishu webhook missing"}
    secret = _sink_secret(home, sink, "secret", "secret_env", "ALCOVE_FEISHU_SECRET")
    return send_feishu_message_with_webhook(
        webhook=webhook,
        title=title,
        text=text,
        secret=secret,
    )


def send_tcb_notification(
    *,
    sink: dict[str, Any],
    title: str,
    text: str,
    attachments: list[Path],
) -> dict[str, Any]:
    command = str(sink.get("command") or "tcb")
    args = [command, "notify", "--title", title, "--stdin", "--json"]
    channel = str(sink.get("channel") or "").strip()
    if channel:
        args.extend(["--channel", channel])
    level = str(sink.get("level") or "").strip()
    if level:
        args.extend(["--level", level])
    source = str(sink.get("source") or "alcove").strip()
    if source:
        args.extend(["--source", source])
    for attachment in attachments:
        args.extend(["--attach", str(attachment)])
    timeout = _positive_int(sink.get("timeout_seconds"), default=60)
    try:
        completed = subprocess.run(  # noqa: S603 - local tcb executable, no shell expansion
            args,
            input=text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return {"status": "skipped", "reason": f"{command} command not found"}
    except subprocess.TimeoutExpired as exc:
        return {"status": "failed", "error": f"{command} notify timed out after {exc.timeout}s"}
    stdout = completed.stdout.strip()
    stderr = compact_user_paths_in_text(completed.stderr.strip())
    if completed.returncode != 0:
        return {
            "status": "failed",
            "exit_code": completed.returncode,
            "error": stderr or f"{command} notify failed",
            "attachment_count": len(attachments),
        }
    if stdout:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            payload = {"status": "sent", "output": compact_user_paths_in_text(stdout)}
    else:
        payload = {"status": "sent"}
    if isinstance(payload, dict):
        payload.setdefault("status", "sent")
        payload["attachment_count"] = len(attachments)
        return payload
    return {"status": "sent", "attachment_count": len(attachments)}


def send_telegram_message_with_credentials(
    *,
    token: str,
    chat_id: str,
    text: str,
) -> dict[str, Any]:
    body = json.dumps(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
    ).encode("utf-8")
    request = Request(  # noqa: S310
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    last_error = ""
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310
                status = response.status
            return {
                "status": "sent" if status < 400 else "failed",
                "http_status": status,
                "attempts": attempt,
            }
        except Exception as exc:  # pragma: no cover - network failure depends on environment
            last_error = str(exc)
            if attempt < 3:
                time.sleep(1.5 * attempt)
    return {"status": "failed", "error": last_error, "attempts": 3}


def send_telegram_document_with_credentials(
    *,
    token: str,
    chat_id: str,
    path: Path,
    caption: str = "",
) -> dict[str, Any]:
    boundary = f"----alcove-{int(time.time() * 1000)}"
    body = _multipart_form_data(
        boundary=boundary,
        fields={"chat_id": chat_id, "caption": caption},
        files={
            "document": {
                "filename": path.name,
                "content_type": guess_type(path.name)[0] or "application/octet-stream",
                "content": path.read_bytes(),
            }
        },
    )
    request = Request(  # noqa: S310
        f"https://api.telegram.org/bot{token}/sendDocument",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    last_error = ""
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310
                status = response.status
            return {
                "status": "sent" if status < 400 else "failed",
                "http_status": status,
                "attempts": attempt,
                "path": compact_user_path(path),
            }
        except Exception as exc:  # pragma: no cover - network failure depends on environment
            last_error = str(exc)
            if attempt < 3:
                time.sleep(1.5 * attempt)
    return {"status": "failed", "error": last_error, "attempts": 3, "path": compact_user_path(path)}


def send_feishu_message_with_webhook(
    *,
    webhook: str,
    title: str,
    text: str,
    secret: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "msg_type": "text",
        "content": {"text": f"{title}\n\n{text}"},
    }
    if secret:
        timestamp = str(int(time.time()))
        payload["timestamp"] = timestamp
        payload["sign"] = feishu_signature(timestamp=timestamp, secret=secret)
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(  # noqa: S310
        webhook,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    last_error = ""
    for attempt in range(1, 4):
        try:
            with urlopen(request, timeout=15) as response:  # noqa: S310
                status = response.status
                response_body = response.read().decode("utf-8", errors="replace")
            remote_code = _feishu_response_code(response_body)
            sent = status < 400 and remote_code in {None, 0}
            result = {
                "status": "sent" if sent else "failed",
                "http_status": status,
                "attempts": attempt,
            }
            if remote_code is not None:
                result["remote_code"] = remote_code
            if not sent and response_body:
                result["response"] = response_body[:500]
            return result
        except Exception as exc:  # pragma: no cover - network failure depends on environment
            last_error = str(exc)
            if attempt < 3:
                time.sleep(1.5 * attempt)
    return {"status": "failed", "error": last_error, "attempts": 3}


def feishu_signature(*, timestamp: str, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}".encode("utf-8")
    digest = hmac.new(string_to_sign, b"", digestmod=hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def telegram_credential(home: Any, alcove_name: str, generic_name: str) -> str:
    value = os.environ.get(alcove_name)
    if value:
        return value
    env_values = local_env_values(Path(home.root))
    value = env_values.get(alcove_name) or env_values.get(generic_name)
    if value:
        return value
    return os.environ.get(generic_name) or ""


def _sink_secret(
    home: Any,
    sink: dict[str, Any],
    value_name: str,
    env_name: str,
    default_env_name: str,
) -> str:
    value = sink.get(value_name)
    if value:
        return str(value)
    env_var = str(sink.get(env_name) or default_env_name)
    return named_credential(home, env_var)


def named_credential(home: Any, name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    return local_env_values(Path(home.root)).get(name, "")


def local_env_values(home_root: Path) -> dict[str, str]:
    env_path = home_root / ".env"
    if not env_path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
            continue
        values[key] = parse_env_value(value.strip())
    return values


def parse_env_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        value = value[1:-1]
    return value.strip()


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _multipart_form_data(
    *,
    boundary: str,
    fields: dict[str, str],
    files: dict[str, dict[str, Any]],
) -> bytes:
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode("utf-8"),
                b"\r\n",
            ]
        )
    for name, payload in files.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{payload["filename"]}"\r\n'
                ).encode(),
                f"Content-Type: {payload['content_type']}\r\n\r\n".encode(),
                bytes(payload["content"]),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks)


def _feishu_response_code(response_body: str) -> int | None:
    try:
        payload = json.loads(response_body)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    value = payload.get("code", payload.get("StatusCode"))
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
