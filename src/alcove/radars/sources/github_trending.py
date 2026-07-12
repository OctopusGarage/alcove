from __future__ import annotations

from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


GITHUB_TRENDING_URL = "https://github.com/trending"


class GitHubTrendingAdapter:
    adapter_id = "github-trending"

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        url = str(source.params.get("url") or GITHUB_TRENDING_URL)
        language = str(source.params.get("language") or "").strip("/")
        if language and url == GITHUB_TRENDING_URL:
            url = f"{url}/{language}"
        html = _read_html(url)
        parser = _TrendingParser(base_url="https://github.com")
        parser.feed(html)
        rows = parser.items
        limit = source.limit if source.limit > 0 else len(rows)
        return [
            RadarItem(
                source_id=source.id,
                adapter=source.adapter,
                title=str(row["title"]),
                url=str(row["url"]),
                summary=str(row["summary"]),
                author=str(row["author"]),
                tags=[str(row["language"])] if row["language"] else [],
                metrics={"stars": row["stars"]} if row["stars"] else {},
            )
            for row in rows[:limit]
        ]


def _read_html(url: str) -> str:
    request = Request(  # noqa: S310
        url,
        headers={
            "User-Agent": "AlcoveRadar/0.1",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urlopen(request, timeout=20) as response:  # noqa: S310
        content: bytes = response.read(2_000_000)
        return content.decode("utf-8", errors="replace")


class _TrendingParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.items: list[dict[str, Any]] = []
        self._in_article = False
        self._current: dict[str, Any] = {}
        self._capture = ""
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "article":
            self._in_article = True
            self._current = {
                "title": "",
                "url": "",
                "summary": "",
                "author": "",
                "language": "",
                "stars": 0,
            }
            return
        if not self._in_article:
            return
        if tag == "a":
            href = attrs_dict.get("href") or ""
            if href and href.count("/") >= 2 and not self._current.get("url"):
                self._href = href
                self._capture = "repo"
                self._text = []
            elif href.endswith("/stargazers"):
                self._capture = "stars"
                self._text = []
        elif tag == "p":
            self._capture = "summary"
            self._text = []
        elif tag == "span" and attrs_dict.get("itemprop") == "programmingLanguage":
            self._capture = "language"
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._capture:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if not self._in_article:
            return
        if tag == "article":
            if self._current.get("title") and self._current.get("url"):
                self.items.append(dict(self._current))
            self._in_article = False
            self._capture = ""
            self._href = ""
            self._text = []
            return
        if tag not in {"a", "p", "span"} or not self._capture:
            return
        text = " ".join(" ".join(self._text).split())
        if self._capture == "repo" and self._href:
            slug = self._href.strip("/")
            if slug.count("/") == 1:
                self._current["title"] = slug
                self._current["url"] = urljoin(self.base_url, self._href)
                self._current["author"] = slug.split("/", 1)[0]
        elif self._capture == "summary":
            self._current["summary"] = text
        elif self._capture == "language":
            self._current["language"] = text
        elif self._capture == "stars":
            self._current["stars"] = _parse_count(text)
        self._capture = ""
        self._href = ""
        self._text = []


def _parse_count(text: str) -> int:
    normalized = text.replace(",", "").strip().lower()
    multiplier = 1
    if normalized.endswith("k"):
        multiplier = 1000
        normalized = normalized[:-1]
    try:
        return int(float(normalized) * multiplier)
    except ValueError:
        return 0
