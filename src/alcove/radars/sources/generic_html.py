from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


class GenericHtmlAdapter:
    adapter_id = "generic-html"

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        url = str(source.params.get("url") or "")
        pattern = str(source.params.get("link_pattern") or "")
        if not url:
            raise ValueError(f"html radar source requires params.url: {source.id}")
        request = Request(url, headers={"User-Agent": "AlcoveRadar/0.1"})  # noqa: S310
        with urlopen(request, timeout=20) as response:  # noqa: S310
            html = response.read(2_000_000).decode("utf-8", errors="replace")
        parser = _AnchorParser(base_url=url)
        parser.feed(html)
        rows: list[RadarItem] = []
        seen: set[str] = set()
        for href, text in parser.links:
            if pattern and pattern not in href:
                continue
            if href in seen:
                continue
            title = " ".join(text.split())
            if len(title) < 4:
                continue
            seen.add(href)
            rows.append(
                RadarItem(source_id=source.id, adapter=source.adapter, title=title, url=href)
            )
            if source.limit > 0 and len(rows) >= source.limit:
                break
        return rows


class _AnchorParser(HTMLParser):
    def __init__(self, *, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.current_href = ""
        self.current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        href = attrs_dict.get("href") or ""
        if href:
            self.current_href = urljoin(self.base_url, href)
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.current_href:
            self.current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current_href:
            self.links.append((self.current_href, " ".join(self.current_text).strip()))
            self.current_href = ""
            self.current_text = []
