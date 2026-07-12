from __future__ import annotations

from datetime import UTC, datetime
import json
from urllib.request import Request, urlopen

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


BASE_FIREBASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsAdapter:
    adapter_id = "hackernews"

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        base_url = str(source.params.get("base_url") or BASE_FIREBASE).rstrip("/")
        story_ids = _json_get(f"{base_url}/topstories.json")
        if not isinstance(story_ids, list):
            raise ValueError("hackernews topstories response must be a JSON list")
        limit = source.limit if source.limit > 0 else len(story_ids)
        items: list[RadarItem] = []
        for story_id in story_ids[:limit]:
            story = _json_get(f"{base_url}/item/{story_id}.json")
            if not isinstance(story, dict):
                continue
            title = str(story.get("title") or "").strip()
            url = str(story.get("url") or "").strip()
            if not title or not url:
                continue
            published_at = _story_time(story.get("time"))
            items.append(
                RadarItem(
                    source_id=source.id,
                    adapter=source.adapter,
                    title=title,
                    url=url,
                    author=str(story.get("by") or ""),
                    published_at=published_at,
                    metrics={
                        "hn_id": story.get("id"),
                        "score": story.get("score"),
                        "comment_count": story.get("descendants"),
                    },
                )
            )
        return items


def _json_get(url: str) -> object:
    request = Request(url, headers={"User-Agent": "AlcoveRadar/0.1"})  # noqa: S310
    with urlopen(request, timeout=20) as response:  # noqa: S310
        return json.loads(response.read(2_000_000).decode("utf-8"))


def _story_time(value: object) -> str:
    if not isinstance(value, str | int | float):
        return ""
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return ""
    return datetime.fromtimestamp(timestamp, UTC).isoformat(timespec="seconds")
