from __future__ import annotations

import re
from typing import Any

from alcove.paths import compact_user_paths_in_text


def apple_notes_item_sample(search: Any, fetch: Any) -> dict[str, Any]:
    rows = search if isinstance(search, list) else []
    first = next((row for row in rows if isinstance(row, dict)), None)
    sample: dict[str, Any] = {
        "search_count": len(rows),
        "has_item": first is not None,
    }
    if first is not None:
        sample["search_result"] = _private_connector_search_result_for_eval(first)
        fetch_ref = first.get("fetch_ref") or first.get("path")
        if fetch_ref or first.get("fetch_command"):
            sample["tool_fetch"] = {
                key: value
                for key, value in {
                    "display_ref": _redact_private_text(
                        first.get("display_label") or first.get("title")
                    ),
                    "source_id": first.get("source_id"),
                    "source_label": _redact_private_text(first.get("source_label")),
                    "origin_label": _redact_private_text(first.get("origin_label")),
                    "fetch_ref_available": bool(fetch_ref),
                    "fetch_command_pattern": "alcove connector fetch <fetch_ref> --json"
                    if fetch_ref
                    else "",
                }.items()
                if value not in (None, "")
            }
    if isinstance(fetch, dict) and fetch.get("status") != "skipped":
        detail_value = fetch.get("detail")
        item_value = fetch.get("item")
        detail: dict[str, Any] = detail_value if isinstance(detail_value, dict) else {}
        item: dict[str, Any] = item_value if isinstance(item_value, dict) else {}
        sample["fetch_result"] = {
            key: fetch.get(key)
            for key in (
                "status",
                "connector",
                "display_label",
                "source_id",
                "source_label",
                "origin_label",
            )
            if fetch.get(key) not in (None, "")
        }
        if sample["fetch_result"].get("display_label"):
            sample["fetch_result"]["display_label"] = _redact_private_text(
                sample["fetch_result"]["display_label"]
            )
        if sample["fetch_result"].get("source_label"):
            sample["fetch_result"]["source_label"] = _redact_private_text(
                sample["fetch_result"]["source_label"]
            )
        if sample["fetch_result"].get("origin_label"):
            sample["fetch_result"]["origin_label"] = _redact_private_text(
                sample["fetch_result"]["origin_label"]
            )
        sample["fetch_result"]["item"] = {
            key: value
            for key, value in {
                "title": _redact_private_text(item.get("title")),
                "folder_path_present": bool(item.get("folder_path")),
                "updated_at": item.get("updated_at"),
                "text": _redacted_text_presence(item.get("text")),
            }.items()
            if value not in (None, "")
        }
        plaintext = str(detail.get("plaintext") or item.get("text") or "")
        sample["fetch_result"]["detail"] = {
            key: value
            for key, value in {
                "title": _redact_private_text(detail.get("title")),
                "folder_path_present": bool(detail.get("folder_path")),
                "updated_at": detail.get("updated_at"),
                "plaintext": _redacted_text_presence(detail.get("plaintext")),
                "cleaned_preview": _redacted_text_presence(_cleaned_text_preview(plaintext)),
                "information_quality": _information_quality(plaintext),
            }.items()
            if value not in (None, "")
        }
    return sample


def apple_notes_public_fixture_sample(search: Any, fetch: Any) -> dict[str, Any]:
    sample = _first_search_result_sample(search, connector="apple-notes", public_content=True)
    if not sample:
        return {"has_item": False}
    sample["has_item"] = True
    if isinstance(fetch, dict) and fetch.get("status") == "fetched":
        detail = fetch.get("detail")
        item = fetch.get("item")
        detail_dict = detail if isinstance(detail, dict) else {}
        item_dict = item if isinstance(item, dict) else {}
        plaintext = str(detail_dict.get("plaintext") or item_dict.get("text") or "")
        sample["fetch_result"] = {
            "status": fetch.get("status"),
            "title": str(detail_dict.get("title") or item_dict.get("title") or "")[:160],
            "folder_path": str(
                detail_dict.get("folder_path") or item_dict.get("folder_path") or ""
            )[:160],
            "plaintext_preview": _cleaned_text_preview(plaintext),
            "information_quality": _information_quality(plaintext),
        }
    return sample


def connector_failure_samples_for_eval(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    public = dict(payload)
    samples = public.get("samples")
    if not isinstance(samples, list):
        return public
    normalized_samples: list[Any] = []
    for sample in samples:
        if not isinstance(sample, dict):
            normalized_samples.append(sample)
            continue
        normalized = dict(sample)
        stderr = normalized.get("stderr")
        if isinstance(stderr, str):
            normalized["stderr"] = _normalize_eval_stderr(stderr)
        normalized_samples.append(normalized)
    public["samples"] = normalized_samples
    return public


def real_integration_summary_for_eval(integrations: dict[str, Any]) -> dict[str, Any]:
    summary_value = integrations.get("summary")
    summary: dict[str, Any] = dict(summary_value) if isinstance(summary_value, dict) else {}
    summary["live_samples"] = _live_connector_samples(integrations)
    return summary


def _private_connector_search_result_for_eval(row: dict[str, Any]) -> dict[str, Any]:
    notes = row.get("notes")
    result = {
        "title": _redact_private_text(row.get("title")),
        "type": row.get("type"),
        "domain": row.get("domain"),
        "topic": row.get("topic"),
        "platform": row.get("platform"),
        "date": row.get("date"),
        "status": row.get("status"),
        "resource": _redacted_text_presence(row.get("resource")),
        "notes": _redacted_text_presence(notes),
        "display_label": _redact_private_text(row.get("display_label")),
        "source_id": row.get("source_id"),
        "source_label": _redact_private_text(row.get("source_label")),
        "origin_label": _redact_private_text(row.get("origin_label")),
        "fetch_ref_available": bool(row.get("fetch_ref") or row.get("path")),
        "fetch_command_available": bool(row.get("fetch_command")),
        "information_quality": row.get("information_quality"),
    }
    return {key: value for key, value in result.items() if value not in (None, "", {})}


def _normalize_eval_stderr(text: str) -> str:
    compacted = compact_user_paths_in_text(text)
    return re.sub(r"(?:~|/)[^ \n\t'\"`]*\.tmp/[^ \n\t'\"`]*", "<eval-artifact>", compacted)


def _live_connector_samples(integrations: dict[str, Any]) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    github_sample = _first_search_result_sample(
        integrations.get("github_stars_search"),
        connector="github-stars",
        public_content=True,
    )
    if github_sample:
        samples.append(github_sample)
    apple_sample = _first_search_result_sample(
        integrations.get("apple_notes_search"),
        connector="apple-notes",
        public_content=False,
    )
    if apple_sample:
        fetch = integrations.get("apple_notes_fetch")
        if isinstance(fetch, dict) and fetch.get("status") == "fetched":
            detail = fetch.get("detail")
            detail_dict = detail if isinstance(detail, dict) else {}
            plaintext = str(detail_dict.get("plaintext") or "")
            apple_sample["fetch_status"] = "fetched"
            apple_sample["folder_path_present"] = bool(detail_dict.get("folder_path"))
            apple_sample["cleaned_preview"] = _redacted_text_presence(plaintext)
            apple_sample["information_quality"] = _information_quality(plaintext)
        samples.append(apple_sample)
    return samples


def _first_search_result_sample(
    rows: Any,
    *,
    connector: str,
    public_content: bool,
) -> dict[str, Any]:
    if not isinstance(rows, list):
        return {}
    first = next((row for row in rows if isinstance(row, dict)), None)
    if first is None:
        return {}
    title = str(first.get("title") or first.get("display_label") or "").strip()
    notes = str(first.get("notes") or "").strip()
    sample: dict[str, Any] = {
        "connector": connector,
        "type": first.get("type") or "",
        "title": _redact_private_text(title) if not public_content else title[:160],
        "resource": first.get("resource")
        if public_content
        else _redacted_text_presence(first.get("resource")),
        "source_id": first.get("source_id"),
        "source_label": first.get("source_label")
        if public_content
        else _redact_private_text(first.get("source_label")),
        "origin_label": first.get("origin_label")
        if public_content
        else _redact_private_text(first.get("origin_label")),
        "fetch_ref_available": bool(first.get("fetch_ref") or first.get("path")),
        "notes_preview": notes[:240] if public_content else _redacted_text_presence(notes),
    }
    return {key: value for key, value in sample.items() if value not in (None, "")}


def _redact_private_text(text: Any) -> str:
    value = str(text or "").strip()
    if not value:
        return ""
    return f"[redacted {len(value)} chars]"


def _redacted_text_presence(text: Any) -> dict[str, Any]:
    value = str(text or "").strip()
    return {
        "present": bool(value),
        "char_count": len(value),
    }


def _cleaned_text_preview(text: str) -> str:
    lines = [
        line.strip()
        for line in str(text or "").splitlines()
        if line.strip() and not _looks_identifier_heavy(line.strip())
    ]
    return " ".join(lines)[:360]


def _information_quality(text: str) -> dict[str, Any]:
    value = str(text or "").strip()
    if not value:
        return {
            "status": "empty",
            "reason": "No plaintext was available in the fetched note.",
        }
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    identifier_lines = [line for line in lines if _looks_identifier_heavy(line)]
    natural_lines = [line for line in lines if line not in identifier_lines]
    identifier_ratio = len(identifier_lines) / len(lines) if lines else 0
    natural_preview = " ".join(natural_lines).strip()
    if lines and identifier_ratio >= 0.7:
        return {
            "status": "low-information",
            "reason": "Most plaintext lines look like identifiers or hashes; fetch source context before relying on this note.",
        }
    if identifier_lines and len(natural_lines) <= 1 and len(natural_preview) < 24:
        return {
            "status": "low-information",
            "reason": "The note is mostly identifiers with only a short title-like natural-language fragment.",
        }
    if len(value) < 40 and _looks_identifier_heavy(value):
        return {
            "status": "low-information",
            "reason": "The plaintext is short and identifier-heavy.",
        }
    return {
        "status": "ok",
        "reason": "Plaintext contains natural-language preview content.",
    }


def _looks_identifier_heavy(text: str) -> bool:
    value = re.sub(r"\s+", "", str(text or ""))
    if not value:
        return False
    if re.fullmatch(r"[a-fA-F0-9]{12,}", value):
        return True
    digit_ratio = sum(character.isdigit() for character in value) / len(value)
    if (
        len(value) >= 12
        and re.fullmatch(r"[A-Za-z0-9_:/%.-]+", value)
        and (digit_ratio >= 0.2 or any(marker in value for marker in ("_", ":", "/", "%")))
    ):
        return True
    return False
