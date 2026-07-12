from __future__ import annotations

from collections.abc import Sequence
from html import unescape
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


ATOM_NS = "{http://www.w3.org/2005/Atom}"


class RssAdapter:
    adapter_id = "rss"

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        url = str(source.params.get("url") or "")
        summary_mode = str(source.params.get("summary_mode") or "")
        if not url:
            raise ValueError(f"rss radar source requires params.url: {source.id}")
        request = Request(url, headers={"User-Agent": "AlcoveRadar/0.1"})  # noqa: S310
        with urlopen(request, timeout=20) as response:  # noqa: S310
            raw = response.read(2_000_000)
        root = ElementTree.fromstring(raw)  # noqa: S314
        nodes = root.findall(".//item") or root.findall(f".//{ATOM_NS}entry")
        items: list[RadarItem] = []
        limit = source.limit if source.limit > 0 else len(nodes)
        for node in nodes[:limit]:
            title = _first_text(node, ("title", f"{ATOM_NS}title"))
            link = _first_text(node, ("link",))
            atom_link = node.find(f"{ATOM_NS}link")
            if not link and atom_link is not None:
                link = str(atom_link.attrib.get("href") or "")
            summary = _first_text(
                node,
                ("description", "summary", f"{ATOM_NS}summary", "content", f"{ATOM_NS}content"),
            )
            published_at = _first_text(
                node,
                ("pubDate", "published", f"{ATOM_NS}published", "updated", f"{ATOM_NS}updated"),
            )
            if title and link:
                items.append(
                    RadarItem(
                        source_id=source.id,
                        adapter=source.adapter,
                        title=title,
                        url=link,
                        summary=_clean_text(
                            summary,
                            first_list_item=summary_mode == "first-list-item",
                        ),
                        published_at=published_at,
                    )
                )
        return items


def _first_text(node: ElementTree.Element, names: Sequence[str]) -> str:
    for name in names:
        child = node.find(name)
        if child is not None and child.text:
            return child.text.strip()
    return ""


def _clean_text(value: str, max_chars: int = 600, *, first_list_item: bool = False) -> str:
    parser = _TextParser()
    parser.feed(value or "")
    parts = parser.list_items[:1] if first_list_item and parser.list_items else parser.parts
    text = " ".join(unescape(" ".join(parts)).split())
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "..."


class _TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.list_items: list[str] = []
        self._li_parts: list[str] = []
        self._in_li = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        _ = attrs
        if tag in {"script", "style"}:
            self._skip_depth += 1
        if tag == "li":
            self._in_li = True
            self._li_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
        if tag == "li" and self._in_li:
            text = " ".join(self._li_parts).strip()
            if text:
                self.list_items.append(text)
            self._in_li = False
            self._li_parts = []

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and data.strip():
            self.parts.append(data)
            if self._in_li:
                self._li_parts.append(data)
