from __future__ import annotations


def deduplicated_search_text(parts: list[str]) -> str:
    """Normalize repeated text lines for search indexes."""
    rows: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for line in part.splitlines() or [part]:
            cleaned = line.strip()
            if not cleaned:
                continue
            key = " ".join(cleaned.casefold().split())
            if not key or key in seen:
                continue
            rows.append(cleaned)
            seen.add(key)
    return "\n".join(rows)
