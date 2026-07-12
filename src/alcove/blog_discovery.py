from __future__ import annotations

from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
import json
import re
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from xml.etree import ElementTree


class BlogDiscoveryModule:
    """Discovers candidate articles for a blog source."""

    def __init__(self, host: Any) -> None:
        self.host = host

    def discover(self, source: Any) -> list[Any]:
        method = source.discover.method
        if method == "requests":
            return self._discover_html(source)
        if method == "playwright":
            return self._discover_playwright(source)
        if method in {"rss", "atom"}:
            return self._discover_feed(source)
        if method == "sitemap":
            return self._discover_sitemap(source)
        if method == "hn-search":
            return self._discover_hn(source)
        raise ValueError(f"Unsupported blog discover method: {method}")

    def _discover_html(self, source: Any) -> list[Any]:
        html = self.host._fetch_text(source.url)
        parser = _AnchorParser(source.url)
        parser.feed(html)
        articles = []
        seen: set[str] = set()
        for href, text in parser.links:
            if not _matches_link_pattern(href, source.discover.link_pattern):
                continue
            if href in seen or href.rstrip("/") == source.url.rstrip("/"):
                continue
            title, date = _extract_article_card_date(_clean_title(text))
            if len(title) < 6:
                continue
            seen.add(href)
            articles.append(self.host._article(source, title=title, url=href, date=date))
        return articles

    def _discover_playwright(self, source: Any) -> list[Any]:
        raw_items = self.host._extract_articles_with_playwright(source)
        articles = []
        seen: set[str] = set()
        for item in raw_items:
            href = str(item.get("url") or "")
            if not href or href in seen:
                continue
            if not _matches_link_pattern(href, source.discover.link_pattern):
                continue
            title = _clean_title(str(item.get("title") or ""))
            date = _clean_title(str(item.get("date") or ""))
            if not title:
                title = _title_from_url(href)
            title, extracted_date = _extract_article_card_date(title)
            date = date or extracted_date
            if len(title) < 6:
                continue
            seen.add(href)
            articles.append(self.host._article(source, title=title, url=href, date=date))
        if not articles:
            raise RuntimeError(f"Playwright found no article links for {source.url}")
        return articles

    def _discover_feed(self, source: Any) -> list[Any]:
        raw = self.host._fetch_text(source.url)
        root = ElementTree.fromstring(raw)  # noqa: S314
        articles = []
        if source.discover.method == "atom":
            for entry in root.findall(".//{*}entry"):
                title = _element_text(entry, "{*}title")
                href = ""
                for link in entry.findall("{*}link"):
                    href = str(link.attrib.get("href") or "")
                    if href:
                        break
                date = _element_text(entry, "{*}updated") or _element_text(entry, "{*}published")
                if title and href:
                    articles.append(self.host._article(source, title=title, url=href, date=date))
            return articles
        for item in root.findall(".//item"):
            title = _element_text(item, "title")
            href = _element_text(item, "link")
            date = _element_text(item, "pubDate")
            if title and href:
                articles.append(self.host._article(source, title=title, url=href, date=date))
        return articles

    def _discover_sitemap(self, source: Any) -> list[Any]:
        raw = self.host._fetch_text(source.url)
        root = ElementTree.fromstring(raw)  # noqa: S314
        source_domain = urlparse(source.url).netloc
        rows: list[tuple[datetime | None, Any]] = []
        seen: set[str] = set()
        for url_node in root.findall(".//{*}url"):
            href = _element_text(url_node, "{*}loc")
            if not href or href in seen:
                continue
            parsed = urlparse(href)
            if parsed.netloc and parsed.netloc != source_domain:
                continue
            if not _matches_link_pattern(href, source.discover.link_pattern):
                continue
            seen.add(href)
            lastmod = _element_text(url_node, "{*}lastmod")
            rows.append(
                (
                    _parse_time(lastmod),
                    self.host._article(
                        source,
                        title=_title_from_url(href),
                        url=href,
                        date=lastmod,
                    ),
                )
            )
        rows.sort(key=lambda row: row[0] or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [article for _, article in rows]

    def _discover_hn(self, source: Any) -> list[Any]:
        domain = urlparse(source.url).netloc
        timestamp = int(datetime.now(UTC).timestamp()) - source.discover.days_back * 86400
        query = urlencode(
            {
                "query": domain,
                "tags": "story",
                "numericFilters": f"created_at_i>{timestamp}",
            }
        )
        data = json.loads(self.host._fetch_text(f"https://hn.algolia.com/api/v1/search?{query}"))
        hits = data.get("hits") if isinstance(data, dict) else []
        articles = []
        seen: set[str] = set()
        for hit in hits if isinstance(hits, list) else []:
            if not isinstance(hit, dict):
                continue
            url = str(hit.get("url") or "")
            story_text = str(hit.get("story_text") or "")
            if domain not in url and domain not in story_text:
                continue
            if domain not in url and story_text:
                match = re.search(
                    rf'href=["\']([^"\']*{re.escape(domain)}[^"\']*)["\']',
                    unescape(story_text),
                )
                url = match.group(1) if match else url
            if not url or url in seen:
                continue
            if not _matches_link_pattern(url, source.discover.link_pattern):
                continue
            title = _clean_title(str(hit.get("title") or ""))
            if not title:
                continue
            seen.add(url)
            articles.append(self.host._article(source, title=title, url=url))
        return articles


class _AnchorParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.links: list[tuple[str, str]] = []
        self._href = ""
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        href = dict(attrs).get("href") or ""
        if not href or href.startswith("#") or href.startswith("mailto:"):
            return
        self._href = urljoin(self.base_url, href)
        self._text = []

    def handle_data(self, data: str) -> None:
        if self._href:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        self.links.append((self._href, " ".join(self._text)))
        self._href = ""
        self._text = []


def _element_text(parent: ElementTree.Element, selector: str) -> str:
    found = parent.find(selector)
    return _clean_title(found.text or "") if found is not None else ""


def _clean_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _matches_link_pattern(url: str, pattern: str) -> bool:
    if not pattern:
        return True
    if pattern.startswith("/"):
        return urlparse(url).path.startswith(pattern)
    return pattern in url


def _extract_article_card_date(value: str) -> tuple[str, str]:
    match = re.search(
        r"\b(?:Engineering|Research|Product|Company|Safety|Security|Business)?\s*"
        r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4})\b",
        value,
    )
    if match is None:
        return value, ""
    date = match.group(1)
    title = value[: match.start()].strip()
    title = re.sub(
        r"\b(?:Engineering|Research|Product|Company|Safety|Security|Business)\s*$",
        "",
        title,
    ).strip()
    return title or value, date


def _title_from_url(url: str) -> str:
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    title = slug.replace("-", " ").strip()
    return title.title() if title else url


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
