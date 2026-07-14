from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from alcove.paths import compact_user_paths_in_text


PACKET_REVIEW_FIELD_MAX = 5000


def compact_packet(value: Any, *, max_string: int = 1200, max_list: int = 40) -> Any:
    if isinstance(value, str):
        text = _sanitize_packet_text(compact_user_paths_in_text(value))
        if len(text) <= max_string:
            return text
        return text[:max_string] + f"...[truncated {len(text) - max_string} chars]"
    if isinstance(value, list):
        return [
            compact_packet(item, max_string=max_string, max_list=max_list)
            for item in value[:max_list]
        ]
    if isinstance(value, dict):
        compacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            field_max_string = _field_max_string(key_text, max_string)
            compacted[key_text] = compact_packet(
                item,
                max_string=field_max_string,
                max_list=max_list,
            )
            if isinstance(item, str):
                compacted.update(_packet_truncation_fields(key_text, item, field_max_string))
            if isinstance(item, list) and len(item) > max_list:
                compacted[f"{key_text}_truncated_count"] = len(item) - max_list
        if isinstance(value.get("content"), str) and str(value.get("review_content") or ""):
            compacted["content"] = (
                "[raw content omitted from AI eval packet; review_content is the "
                "default agent review surface]"
            )
            compacted["content_preview"] = compact_packet(
                str(value.get("review_content") or ""),
                max_string=_field_max_string("review_content", max_string),
                max_list=max_list,
            )
            compacted.update(
                _packet_truncation_fields(
                    "content_preview",
                    str(value.get("review_content") or ""),
                    _field_max_string("review_content", max_string),
                )
            )
            compacted["raw_content_available"] = True
        if (
            "content" in value
            and "content_truncated" in value
            and isinstance(value.get("content"), str)
            and len(value["content"]) > max_string
            and not str(value.get("review_content") or "")
        ):
            compacted["packet_truncated"] = True
            compacted["packet_truncation_note"] = (
                "The AI eval packet shortened this content field for review size. "
                "Use content_truncated to interpret the underlying Alcove read payload."
            )
        return compacted
    return value


def doctor_for_eval(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    public = dict(payload)
    checks = public.get("checks")
    if isinstance(checks, list):
        clean_checks: list[dict[str, Any]] = []
        for check in checks:
            if not isinstance(check, dict):
                continue
            clean_checks.append(
                {
                    key: value
                    for key, value in check.items()
                    if key not in {"path", "detail_path", "debug_path"}
                }
            )
        public["checks"] = clean_checks
        public["diagnostic_paths_omitted"] = True
    return public


def dashboard_browser_for_eval(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    public = dict(payload)
    checks = public.get("checks")
    if not isinstance(checks, list):
        return public
    public["check_rollup_by_viewport"] = _dashboard_check_rollup_by_viewport(checks)
    public["checks"] = _balanced_dashboard_checks(checks)
    layout_summaries = public.get("layout_summaries")
    if isinstance(layout_summaries, list):
        public["layout_summaries"] = _balanced_dashboard_layouts(layout_summaries)
    return public


def project_health_evidence(check_log: Path, warnings: list[str]) -> dict[str, Any]:
    text = _read_text(check_log, warnings)
    return {
        "check_status": "passed" if "All checks passed!" in text else "unknown",
        "pytest": "passed" if " passed" in text else "unknown",
        "gitleaks": "passed" if "no leaks found" in text else "unknown",
        "pip_audit": "passed" if "No known vulnerabilities found" in text else "unknown",
        "coverage": _line_containing(text, "Required test coverage"),
        "summary_tail": "\n".join(text.splitlines()[-12:]),
    }


def _dashboard_check_rollup_by_viewport(checks: list[Any]) -> dict[str, dict[str, int]]:
    rollup: dict[str, dict[str, int]] = {}
    for check in checks:
        if not isinstance(check, dict):
            continue
        name = str(check.get("name") or "")
        viewport = name.split("_", 1)[0] if "_" in name else "global"
        if viewport not in {"desktop", "mobile"}:
            viewport = "global"
        bucket = rollup.setdefault(viewport, {"total": 0, "passed": 0, "failed": 0})
        bucket["total"] += 1
        if check.get("status") == "failed":
            bucket["failed"] += 1
        else:
            bucket["passed"] += 1
    return rollup


def _balanced_dashboard_checks(checks: list[Any], *, per_viewport: int = 24) -> list[Any]:
    failed = [
        check for check in checks if isinstance(check, dict) and check.get("status") == "failed"
    ]
    desktop = [
        check
        for check in checks
        if isinstance(check, dict) and str(check.get("name") or "").startswith("desktop_")
    ]
    mobile = [
        check
        for check in checks
        if isinstance(check, dict) and str(check.get("name") or "").startswith("mobile_")
    ]
    global_checks = [
        check
        for check in checks
        if isinstance(check, dict)
        and not str(check.get("name") or "").startswith(("desktop_", "mobile_"))
    ]
    return _dedupe_checks(
        [
            *failed,
            *desktop[:per_viewport],
            *mobile[:per_viewport],
            *global_checks[:8],
        ]
    )


def _balanced_dashboard_layouts(layouts: list[Any], *, per_viewport: int = 8) -> list[Any]:
    desktop = [
        row
        for row in layouts
        if isinstance(row, dict) and str(row.get("viewport") or "") == "desktop"
    ][:per_viewport]
    mobile = [
        row
        for row in layouts
        if isinstance(row, dict) and str(row.get("viewport") or "") == "mobile"
    ][:per_viewport]
    return [*desktop, *mobile]


def _dedupe_checks(checks: list[Any]) -> list[Any]:
    seen: set[str] = set()
    result: list[Any] = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        key = str(check.get("name") or json.dumps(check, sort_keys=True, ensure_ascii=False))
        if key in seen:
            continue
        seen.add(key)
        result.append(check)
    return result


def _field_max_string(key: str, default: int) -> int:
    if key in {
        "review_content",
        "content_preview",
        "review_excerpt",
        "tail_excerpt",
        "notes_excerpt",
    }:
        return PACKET_REVIEW_FIELD_MAX
    return default


def _sanitize_packet_text(text: str) -> str:
    return re.sub(r"""file://~/[^\s"']*/\.tmp/[^\s"']+""", "fixture://local-file", text)


def _packet_truncation_fields(key: str, value: str, max_string: int) -> dict[str, Any]:
    text = _sanitize_packet_text(compact_user_paths_in_text(value))
    if len(text) <= max_string:
        return {}
    return {
        f"{key}_packet_truncated": True,
        f"{key}_packet_omitted_chars": len(text) - max_string,
    }


def _read_text(path: Path, warnings: list[str]) -> str:
    if not path.is_file():
        warnings.append(f"missing artifact: {path.name}")
        return ""
    return path.read_text(encoding="utf-8")


def _line_containing(text: str, needle: str) -> str:
    for line in text.splitlines():
        if needle in line:
            return line
    return ""
