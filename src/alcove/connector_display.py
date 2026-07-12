from __future__ import annotations

import re


CONNECTOR_DISPLAY_NAMES = {
    "apple-notes": "Apple Notes",
    "chrome-bookmarks": "Chrome Bookmarks",
    "github-stars": "GitHub Stars",
}


def connector_display_name(connector_id: str) -> str:
    value = connector_id.strip()
    return CONNECTOR_DISPLAY_NAMES.get(value, value)


def connector_display_id(
    connector_id: str,
    *,
    title: str,
    relative_path: str,
    max_len: int = 48,
) -> str:
    label = display_slug(title, max_len=max_len) or display_slug(relative_path, max_len=max_len)
    return f"{connector_id}/{label}" if connector_id and label else label


def display_slug(value: str, *, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:max_len].strip("-")
