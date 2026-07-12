from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from html import escape, unescape
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from typing import Any
from urllib.parse import urlencode, urljoin, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

import yaml

from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path


DEFAULT_TTL_HOURS = 24
SOURCE_SCHEMA = "alcove/blog-source/v1"
SEEN_SCHEMA = "alcove/blog-seen/v1"
ATTENTION_STATUS = "needs_attention"


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class BlogArticle:
    title: str
    url: str
    date: str = ""
    source_id: str = ""
    source_name: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DiscoverPolicy:
    method: str = "requests"
    link_pattern: str = ""
    days_back: int = 30

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CapturePolicy:
    enabled: bool = False
    adapter: str = "clipsmith"
    kb: str = ""
    inbox_path: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SummaryPolicy:
    enabled: bool = False
    provider: str = "claude"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NotifyPolicy:
    enabled: bool = False
    channel: str = "telegram"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SchedulePolicy:
    ttl_hours: int = DEFAULT_TTL_HOURS

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class BlogSource:
    id: str
    name: str
    url: str
    discover: DiscoverPolicy = field(default_factory=DiscoverPolicy)
    capture: CapturePolicy = field(default_factory=CapturePolicy)
    summary: SummaryPolicy = field(default_factory=SummaryPolicy)
    notify: NotifyPolicy = field(default_factory=NotifyPolicy)
    schedule: SchedulePolicy = field(default_factory=SchedulePolicy)
    tags: list[str] = field(default_factory=list)
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""
    checked_at: str = ""
    changed_at: str = ""
    last_error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SOURCE_SCHEMA,
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "discover": self.discover.as_dict(),
            "capture": self.capture.as_dict(),
            "summary": self.summary.as_dict(),
            "notify": self.notify.as_dict(),
            "schedule": self.schedule.as_dict(),
            "tags": self.tags,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "checked_at": self.checked_at,
            "changed_at": self.changed_at,
            "last_error": self.last_error,
        }


class BlogMonitorModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home
        self.root = home.root / "blog-monitor"
        self.sources_root = self.root / "sources"
        self.seen_root = self.root / "seen"
        self.captures_root = self.root / "captures"
        self.runs_root = self.root / "runs"
        self.events_path = self.root / "events.jsonl"

    def add(
        self,
        *,
        name: str,
        url: str,
        source_id: str = "",
        discover_method: str = "requests",
        link_pattern: str = "",
        days_back: int = 30,
        capture_enabled: bool = False,
        capture_adapter: str = "clipsmith",
        kb: str = "",
        inbox_path: str = "",
        summary_enabled: bool = False,
        notify_enabled: bool = False,
        tags: list[str] | None = None,
        ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> dict[str, Any]:
        source_slug = normalize_slug(source_id or name or url) or "blog"
        if kb:
            self.home.get_knowledge_base(kb)
        timestamp = now_iso()
        source = BlogSource(
            id=source_slug,
            name=name.strip() or source_slug,
            url=url.strip(),
            discover=DiscoverPolicy(
                method=self._normalize_discover_method(discover_method),
                link_pattern=link_pattern.strip(),
                days_back=max(days_back, 1),
            ),
            capture=CapturePolicy(
                enabled=capture_enabled,
                adapter=normalize_slug(capture_adapter or "clipsmith") or "clipsmith",
                kb=kb.strip(),
                inbox_path=self._normalize_inbox_path(inbox_path, source_slug),
            ),
            summary=SummaryPolicy(enabled=summary_enabled),
            notify=NotifyPolicy(enabled=notify_enabled),
            schedule=SchedulePolicy(ttl_hours=max(ttl_hours, 1)),
            tags=[tag.strip() for tag in tags or [] if tag.strip()],
            created_at=timestamp,
            updated_at=timestamp,
        )
        self._write_source(source)
        return {"status": "added", "source": self._public_source(source)}

    def list_sources(self, *, status: str = "active") -> dict[str, Any]:
        sources = [
            self._public_source(source)
            for source in self._load_sources()
            if not status or source.status == status
        ]
        return {"count": len(sources), "sources": sources}

    def seed(self, *, source_id: str = "") -> dict[str, Any]:
        return self.check(
            source_id=source_id,
            seed_only=True,
            capture_override=False,
            summary_override=False,
            notify_override=False,
        )

    def check(
        self,
        *,
        source_id: str = "",
        stale_only: bool = False,
        seed_only: bool = False,
        capture_override: bool | None = None,
        summary_override: bool | None = None,
        notify_override: bool | None = None,
        now: str | None = None,
    ) -> dict[str, Any]:
        timestamp = now or now_iso()
        rows = []
        new_count = 0
        captured_count = 0
        errors = 0
        for source in self._load_sources():
            if source.status not in {"active", ATTENTION_STATUS}:
                continue
            if source_id and source.id != source_id:
                continue
            if stale_only and not self._is_stale(source, timestamp):
                rows.append({"id": source.id, "status": "skipped"})
                continue
            result = self._check_one(
                source,
                timestamp=timestamp,
                seed_only=seed_only,
                capture_override=capture_override,
                summary_override=summary_override,
                notify_override=notify_override,
            )
            rows.append(result)
            new_count += int(result.get("new_count") or 0)
            captured_count += int(result.get("captured_count") or 0)
            if result.get("status") in {"error", ATTENTION_STATUS}:
                errors += 1
        return {
            "status": "checked",
            "checked": len(rows),
            "new": new_count,
            "captured": captured_count,
            "errors": errors,
            "sources": rows,
        }

    def _check_one(
        self,
        source: BlogSource,
        *,
        timestamp: str,
        seed_only: bool,
        capture_override: bool | None,
        summary_override: bool | None,
        notify_override: bool | None,
    ) -> dict[str, Any]:
        try:
            articles = self._discover(source)
        except Exception as exc:  # pragma: no cover - exercised in integration use
            return self._handle_failure(
                source,
                stage="discovery",
                error=str(exc),
                timestamp=timestamp,
                notify_override=notify_override,
            )

        seen = self._load_seen(source.id)
        discovered_urls = {article.url for article in articles}
        new_articles = [article for article in articles if article.url not in seen]

        if seed_only:
            self._write_seen(source.id, seen | discovered_urls, timestamp=timestamp)
            updated = self._replace_source(
                source,
                status="active",
                checked_at=timestamp,
                updated_at=timestamp,
                last_error="",
            )
            self._write_source(updated)
            return {
                "id": source.id,
                "status": "seeded",
                "discovered_count": len(articles),
                "new_count": len(new_articles),
            }

        capture_enabled = source.capture.enabled if capture_override is None else capture_override
        summary_enabled = source.summary.enabled if summary_override is None else summary_override
        notify_enabled = source.notify.enabled if notify_override is None else notify_override

        captures = [
            self._capture_article(source, article) if capture_enabled else self._skipped_capture()
            for article in new_articles
        ]
        failed_capture = next(
            (
                capture
                for capture in captures
                if str(capture.get("status") or "") in {"failed", "pending"}
            ),
            None,
        )
        if failed_capture is not None:
            error = str(
                failed_capture.get("error") or failed_capture.get("reason") or "capture failed"
            )
            return self._handle_failure(
                source,
                stage="capture",
                error=error,
                timestamp=timestamp,
                notify_override=notify_override,
                articles=new_articles,
                captures=captures,
            )
        self._write_seen(source.id, seen | discovered_urls, timestamp=timestamp)
        captured_count = sum(1 for capture in captures if capture.get("status") == "captured")
        summary = self._summarize(source, new_articles, captures) if summary_enabled else ""
        notify_payload = (
            self._notify(source, new_articles, captures, summary)
            if notify_enabled and new_articles
            else {"status": "skipped"}
        )
        for article, capture in zip(new_articles, captures, strict=True):
            self._record_event(source, article, capture, timestamp=timestamp)
        run_path = self._write_run(
            source,
            articles=new_articles,
            captures=captures,
            summary=summary,
            notify=notify_payload,
            timestamp=timestamp,
        )
        updated = self._replace_source(
            source,
            status="active",
            checked_at=timestamp,
            changed_at=timestamp if new_articles else source.changed_at,
            updated_at=timestamp,
            last_error="",
        )
        self._write_source(updated)
        return {
            "id": source.id,
            "status": "changed" if new_articles else "fresh",
            "discovered_count": len(articles),
            "new_count": len(new_articles),
            "captured_count": captured_count,
            "run": compact_user_path(run_path),
            "notify": notify_payload,
            "articles": [article.as_dict() for article in new_articles],
            "captures": captures,
        }

    def _handle_failure(
        self,
        source: BlogSource,
        *,
        stage: str,
        error: str,
        timestamp: str,
        notify_override: bool | None,
        articles: list[BlogArticle] | None = None,
        captures: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        notify_enabled = source.notify.enabled if notify_override is None else notify_override
        notify_payload = (
            self._notify_failure(source, stage=stage, error=error)
            if notify_enabled
            else {"status": "skipped"}
        )
        run_path = self._write_run(
            source,
            articles=articles or [],
            captures=captures or [],
            summary="",
            notify=notify_payload,
            timestamp=timestamp,
            stage=stage,
            error=error,
        )
        self._record_failure_event(source, stage=stage, error=error, timestamp=timestamp)
        updated = self._replace_source(
            source,
            status=ATTENTION_STATUS,
            checked_at=timestamp,
            updated_at=timestamp,
            last_error=error,
        )
        self._write_source(updated)
        return {
            "id": source.id,
            "status": ATTENTION_STATUS,
            "stage": stage,
            "error": error,
            "run": compact_user_path(run_path),
            "notify": notify_payload,
        }

    def _discover(self, source: BlogSource) -> list[BlogArticle]:
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

    def _discover_html(self, source: BlogSource) -> list[BlogArticle]:
        html = self._fetch_text(source.url)
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
            articles.append(self._article(source, title=title, url=href, date=date))
        return articles

    def _discover_playwright(self, source: BlogSource) -> list[BlogArticle]:
        raw_items = self._extract_articles_with_playwright(source)
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
            articles.append(self._article(source, title=title, url=href, date=date))
        if not articles:
            raise RuntimeError(f"Playwright found no article links for {source.url}")
        return articles

    def _extract_articles_with_playwright(self, source: BlogSource) -> list[dict[str, str]]:
        node = shutil.which("node")
        node_path = self._playwright_node_path()
        if node is None or node_path is None:
            raise RuntimeError(
                "Playwright discovery requires node and the clipsmith-web Playwright runtime"
            )
        script = self._playwright_discover_script()
        with tempfile.NamedTemporaryFile(
            "w", suffix=".cjs", delete=False, encoding="utf-8"
        ) as handle:
            handle.write(script)
            script_path = Path(handle.name)
        env = os.environ.copy()
        env["NODE_PATH"] = node_path
        try:
            result = subprocess.run(  # noqa: S603
                [
                    node,
                    str(script_path),
                    source.url,
                    source.discover.link_pattern,
                ],
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
                env=env,
            )
        finally:
            script_path.unlink(missing_ok=True)
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(error or "Playwright discovery failed")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Playwright discovery returned invalid JSON") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Playwright discovery returned non-object JSON")
        if payload.get("manual_action"):
            reason = str(payload.get("reason") or "manual action page detected")
            raise RuntimeError(reason)
        items = payload.get("items")
        if not isinstance(items, list):
            raise RuntimeError("Playwright discovery response missing items")
        return [
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "date": str(item.get("date") or ""),
            }
            for item in items
            if isinstance(item, dict)
        ]

    def _discover_feed(self, source: BlogSource) -> list[BlogArticle]:
        raw = self._fetch_text(source.url)
        root = ElementTree.fromstring(raw)  # noqa: S314
        articles: list[BlogArticle] = []
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
                    articles.append(self._article(source, title=title, url=href, date=date))
            return articles
        for item in root.findall(".//item"):
            title = _element_text(item, "title")
            href = _element_text(item, "link")
            date = _element_text(item, "pubDate")
            if title and href:
                articles.append(self._article(source, title=title, url=href, date=date))
        return articles

    def _discover_sitemap(self, source: BlogSource) -> list[BlogArticle]:
        raw = self._fetch_text(source.url)
        root = ElementTree.fromstring(raw)  # noqa: S314
        source_domain = urlparse(source.url).netloc
        rows: list[tuple[datetime | None, BlogArticle]] = []
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
                    self._article(
                        source,
                        title=_title_from_url(href),
                        url=href,
                        date=lastmod,
                    ),
                )
            )
        rows.sort(key=lambda row: row[0] or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [article for _, article in rows]

    def _discover_hn(self, source: BlogSource) -> list[BlogArticle]:
        domain = urlparse(source.url).netloc
        timestamp = int(datetime.now(UTC).timestamp()) - source.discover.days_back * 86400
        query = urlencode(
            {
                "query": domain,
                "tags": "story",
                "numericFilters": f"created_at_i>{timestamp}",
            }
        )
        data = json.loads(self._fetch_text(f"https://hn.algolia.com/api/v1/search?{query}"))
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
            articles.append(self._article(source, title=title, url=url))
        return articles

    def _article(self, source: BlogSource, *, title: str, url: str, date: str = "") -> BlogArticle:
        return BlogArticle(
            title=title,
            url=url,
            date=date,
            source_id=source.id,
            source_name=source.name,
        )

    def _capture_article(self, source: BlogSource, article: BlogArticle) -> dict[str, Any]:
        if not source.capture.kb:
            return {"status": "failed", "error": "capture.kb is required when capture is enabled"}
        if source.capture.adapter != "clipsmith":
            return {
                "status": "pending",
                "adapter": source.capture.adapter,
                "reason": "capture adapter is not implemented",
            }
        record = self.home.get_knowledge_base(source.capture.kb)
        target_dir = record.path / source.capture.inbox_path
        skill_dir = self._clipsmith_web_skill_dir()
        if skill_dir is None or shutil.which("npx") is None or shutil.which("clipsmith") is None:
            return {
                "status": "pending",
                "adapter": "clipsmith",
                "reason": "clipsmith-web skill, npx, or clipsmith command is unavailable",
                "capture_command": f"Use clipsmith-capture to capture {article.url} and sink it to {target_dir}",
            }
        output_dir = self.captures_root / source.id
        output_dir.mkdir(parents=True, exist_ok=True)
        capture_result = self._run_command(
            [
                "npx",
                "tsx",
                "scripts/run.ts",
                "--url",
                article.url,
                "--output_dir",
                str(output_dir),
            ],
            cwd=skill_dir,
            timeout=180,
        )
        if capture_result.returncode != 0:
            return {
                "status": "failed",
                "adapter": "clipsmith",
                "error": capture_result.stderr.strip() or capture_result.stdout.strip(),
            }
        bundle_dir = _json_field(capture_result.stdout, "bundle_dir")
        if not bundle_dir:
            return {
                "status": "failed",
                "adapter": "clipsmith",
                "error": "clipsmith-web did not return bundle_dir",
            }
        validate = self._run_command(
            ["clipsmith", "validate-bundle", bundle_dir, "--json"],
            cwd=None,
            timeout=60,
        )
        if validate.returncode != 0:
            return {
                "status": "failed",
                "adapter": "clipsmith",
                "bundle_dir": compact_user_path(bundle_dir),
                "error": validate.stderr.strip() or validate.stdout.strip(),
            }
        sink = self._run_command(
            ["clipsmith", "sink", "directory", bundle_dir, str(target_dir), "--json"],
            cwd=None,
            timeout=60,
        )
        if sink.returncode != 0:
            return {
                "status": "failed",
                "adapter": "clipsmith",
                "bundle_dir": compact_user_path(bundle_dir),
                "error": sink.stderr.strip() or sink.stdout.strip(),
            }
        return {
            "status": "captured",
            "adapter": "clipsmith",
            "bundle_dir": compact_user_path(bundle_dir),
            "inbox_path": compact_user_path(_json_field(sink.stdout, "path") or target_dir),
        }

    def _run_command(
        self,
        command: list[str],
        *,
        cwd: Path | None,
        timeout: int,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603
            command,
            cwd=str(cwd) if cwd is not None else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    def _clipsmith_web_skill_dir(self) -> Path | None:
        candidates = [
            os.environ.get("CLIPSMITH_WEB_SKILL_DIR", ""),
            str(Path.home() / ".codex" / "skills" / "clipsmith-web"),
            str(Path.home() / ".agents" / "skills" / "clipsmith-web"),
        ]
        for candidate in candidates:
            if not candidate:
                continue
            path = Path(candidate).expanduser()
            if (path / "scripts" / "run.ts").is_file():
                return path
        return None

    def _playwright_node_path(self) -> str | None:
        explicit = os.environ.get("ALCOVE_PLAYWRIGHT_NODE_PATH", "")
        if explicit and Path(explicit).expanduser().is_dir():
            return str(Path(explicit).expanduser())
        skill_dir = self._clipsmith_web_skill_dir()
        if skill_dir is not None and (skill_dir / "node_modules" / "playwright").is_dir():
            return str(skill_dir / "node_modules")
        return None

    def _playwright_discover_script(self) -> str:
        return r"""
const { chromium } = require('playwright');

const [url, linkPattern] = process.argv.slice(2);

function hasManualActionText(text) {
  const normalized = String(text || '').toLowerCase();
  return [
    'enable javascript and cookies',
    'verify you are human',
    'checking if the site connection is secure',
    'access denied',
    'cloudflare',
  ].some((hint) => normalized.includes(hint));
}

(async () => {
  let browser;
  try {
    browser = await chromium.launch({
      headless: true,
    });
    const page = await browser.newPage({
      viewport: { width: 1365, height: 900 },
      userAgent:
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
        'Chrome/126.0.0.0 Safari/537.36',
    });
    const response = await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45_000 });
    const status = response ? response.status() : 0;
    if (status >= 400) {
      throw new Error(`Navigation failed with HTTP ${status}`);
    }
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => undefined);
    await page.evaluate(async () => {
      let y = 0;
      const step = Math.max(300, Math.floor(window.innerHeight * 0.75));
      while (y < document.body.scrollHeight) {
        y += step;
        window.scrollTo(0, y);
        await new Promise((resolve) => setTimeout(resolve, 80));
      }
      window.scrollTo(0, 0);
    });
    await page.waitForTimeout(500);
    const payload = await page.evaluate((pattern) => {
      const dateRe = /\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b/;
      const links = Array.from(document.querySelectorAll('a[href]'));
      const seen = new Set();
      const items = [];
      for (const anchor of links) {
        const href = new URL(anchor.getAttribute('href') || '', window.location.href).toString();
        if (pattern && !href.includes(pattern)) continue;
        if (seen.has(href)) continue;
        seen.add(href);
        const card = anchor.closest('article, li, section, [class*="card"], [class*="Card"]') || anchor;
        const anchorText = (anchor.innerText || anchor.textContent || '').replace(/\s+/g, ' ').trim();
        const cardText = (card.innerText || card.textContent || anchorText).replace(/\s+/g, ' ').trim();
        const date = (anchorText.match(dateRe) || cardText.match(dateRe) || [''])[0];
        let title = anchorText || cardText;
        if (date && title.includes(date)) {
          title = title.slice(0, title.indexOf(date)).trim();
        }
        title = title.replace(/\b(Engineering|Research|Product|Company|Safety|Security|Business)\s*$/i, '').trim();
        if (title.length < 6) continue;
        items.push({ title, url: href, date });
      }
      return {
        title: document.title || '',
        text: (document.body && document.body.innerText ? document.body.innerText : '').slice(0, 2000),
        items,
      };
    }, linkPattern || '');
    if (payload.items.length === 0 && hasManualActionText(payload.text)) {
      console.log(JSON.stringify({
        manual_action: true,
        reason: 'Playwright reached a manual action or anti-bot challenge page',
        items: [],
      }));
      return;
    }
    console.log(JSON.stringify({ items: payload.items }));
  } catch (error) {
    console.error(error instanceof Error ? error.message : String(error));
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close().catch(() => undefined);
  }
})();
"""

    def _summarize(
        self,
        source: BlogSource,
        articles: list[BlogArticle],
        captures: list[dict[str, Any]],
    ) -> str:
        claude_path = shutil.which("claude")
        if not articles or source.summary.provider != "claude" or claude_path is None:
            return ""
        lines = [
            "Summarize these newly discovered blog articles in 2-3 concise sentences.",
            "Focus on common themes and practical importance. Do not invent details.",
            "",
        ]
        for article, capture in zip(articles, captures, strict=True):
            lines.append(f"Title: {article.title}")
            lines.append(f"URL: {article.url}")
            if capture.get("inbox_path"):
                lines.append(f"Captured: {capture['inbox_path']}")
            lines.append("")
        try:
            result = subprocess.run(  # noqa: S603
                [claude_path, "-p"],
                input="\n".join(lines),
                text=True,
                capture_output=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return ""
        return result.stdout.strip() if result.returncode == 0 else ""

    def _notify(
        self,
        source: BlogSource,
        articles: list[BlogArticle],
        captures: list[dict[str, Any]],
        summary: str,
    ) -> dict[str, Any]:
        if source.notify.channel != "telegram":
            return {"status": "skipped", "reason": "unsupported notification channel"}
        token = self._telegram_credential("ALCOVE_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
        chat_id = self._telegram_credential("ALCOVE_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return {"status": "skipped", "reason": "telegram token or chat id missing"}
        statuses = []
        for article, capture in zip(articles, captures, strict=True):
            message = self._telegram_article_message(
                source,
                article,
                capture,
                summary=summary,
            )
            status = self._send_telegram_message(token=token, chat_id=chat_id, text=message)
            statuses.append(status)
            if status.get("status") == "failed":
                return {
                    "status": "failed",
                    "sent_count": sum(1 for item in statuses if item.get("status") == "sent"),
                    "messages": statuses,
                }
        return {
            "status": "sent",
            "sent_count": len(statuses),
            "messages": statuses,
        }

    def _notify_failure(self, source: BlogSource, *, stage: str, error: str) -> dict[str, Any]:
        retry_command = self._failure_retry_command(source)
        if source.notify.channel != "telegram":
            return {
                "status": "skipped",
                "reason": "unsupported notification channel",
                "source_id": source.id,
                "stage": stage,
                "error": error,
                "retry_command": retry_command,
            }
        token = self._telegram_credential("ALCOVE_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN")
        chat_id = self._telegram_credential("ALCOVE_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return {
                "status": "skipped",
                "reason": "telegram token or chat id missing",
                "source_id": source.id,
                "stage": stage,
                "error": error,
                "retry_command": retry_command,
            }
        message = self._telegram_failure_message(source, stage=stage, error=error)
        result = self._send_telegram_message(token=token, chat_id=chat_id, text=message)
        return {
            **result,
            "source_id": source.id,
            "stage": stage,
            "error": error,
            "retry_command": retry_command,
        }

    def _telegram_article_message(
        self,
        source: BlogSource,
        article: BlogArticle,
        capture: dict[str, Any],
        *,
        summary: str,
    ) -> str:
        message_lines = [
            f"<b>Blog Monitor: {escape(source.name)}</b>",
            "",
            f'<a href="{escape(article.url)}">{escape(article.title)}</a>',
        ]
        article_summary = self._captured_article_summary(capture)
        if article_summary:
            message_lines.extend(["", f"<b>Summary</b>\n{escape(article_summary)}"])
        elif summary:
            message_lines.extend(["", f"<b>Run Summary</b>\n{escape(summary)}"])
        else:
            status = str(capture.get("status") or "skipped")
            message_lines.extend(["", f"Capture: {escape(status)}"])
        return "\n".join(message_lines)

    def _telegram_failure_message(self, source: BlogSource, *, stage: str, error: str) -> str:
        action = f"检查 {source.name} 博客监控失败原因，并修复或补采集"
        lines = [
            f"<b>Blog Monitor Failed: {escape(source.name)}</b>",
            "",
            f"Error: {escape(error[:1200])}",
            f"Source ID: {escape(source.id)}",
            f"Stage: {escape(stage)}",
            f"Retry: <code>{escape(self._failure_retry_command(source))}</code>",
            f"URL: {escape(source.url)}",
            "",
            "Suggested action:",
            escape(action),
        ]
        return "\n".join(lines)

    def _failure_retry_command(self, source: BlogSource) -> str:
        return f"alcove blog check {source.id} --json"

    def _captured_article_summary(self, capture: dict[str, Any], max_chars: int = 1200) -> str:
        inbox_path = str(capture.get("inbox_path") or "")
        if not inbox_path:
            return ""
        summary_path = Path(inbox_path).expanduser() / "summary.md"
        if not summary_path.is_file():
            return ""
        text = summary_path.read_text(encoding="utf-8", errors="replace").strip()
        text = re.sub(r"^#\s*Summary\s*", "", text, flags=re.I).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 1].rstrip() + "…"

    def _send_telegram_message(self, *, token: str, chat_id: str, text: str) -> dict[str, Any]:
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

    def _env_value(self, *names: str) -> str:
        for name in names:
            value = os.environ.get(name)
            if value:
                return value
        env_values = self._local_env_values()
        for name in names:
            value = env_values.get(name)
            if value:
                return value
        return ""

    def _telegram_credential(self, alcove_name: str, generic_name: str) -> str:
        value = os.environ.get(alcove_name)
        if value:
            return value
        env_values = self._local_env_values()
        value = env_values.get(alcove_name) or env_values.get(generic_name)
        if value:
            return value
        return os.environ.get(generic_name) or ""

    def _local_env_values(self) -> dict[str, str]:
        env_path = self.home.root / ".env"
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
            values[key] = self._parse_env_value(value.strip())
        return values

    def _parse_env_value(self, value: str) -> str:
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        return value.strip()

    def _write_run(
        self,
        source: BlogSource,
        *,
        articles: list[BlogArticle],
        captures: list[dict[str, Any]],
        summary: str,
        notify: dict[str, Any],
        timestamp: str,
        stage: str = "",
        error: str = "",
    ) -> Path:
        self.runs_root.mkdir(parents=True, exist_ok=True)
        path = self.runs_root / f"{timestamp.replace(':', '-')}-{source.id}.json"
        payload = {
            "schema": "alcove/blog-run/v1",
            "timestamp": timestamp,
            "source_id": source.id,
            "articles": [article.as_dict() for article in articles],
            "captures": captures,
            "summary": summary,
            "notify": notify,
        }
        if stage:
            payload["stage"] = stage
        if error:
            payload["error"] = error
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def _record_event(
        self,
        source: BlogSource,
        article: BlogArticle,
        capture: dict[str, Any],
        *,
        timestamp: str,
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "type": "blog.article.discovered",
            "timestamp": timestamp,
            "source_id": source.id,
            "source_name": source.name,
            "title": article.title,
            "url": article.url,
            "capture": capture,
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _record_failure_event(
        self,
        source: BlogSource,
        *,
        stage: str,
        error: str,
        timestamp: str,
    ) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event = {
            "type": "blog.monitor.failed",
            "timestamp": timestamp,
            "source_id": source.id,
            "source_name": source.name,
            "stage": stage,
            "url": source.url,
            "error": error,
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _fetch_text(self, url: str) -> str:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        request = Request(  # noqa: S310
            url,
            headers=headers,
        )
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310
                raw: bytes = response.read(3_000_000)
        except (HTTPError, URLError) as error:
            curl = shutil.which("curl")
            if curl is None:
                raise error
            result = subprocess.run(  # noqa: S603
                [
                    curl,
                    "-L",
                    "--max-time",
                    "30",
                    "-A",
                    headers["User-Agent"],
                    "-H",
                    f"Accept: {headers['Accept']}",
                    "-H",
                    f"Accept-Language: {headers['Accept-Language']}",
                    "-sS",
                    url,
                ],
                text=False,
                capture_output=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(
                    result.stderr.decode("utf-8", errors="replace").strip()
                ) from error
            raw = result.stdout[:3_000_000]
        return raw.decode("utf-8", errors="replace")

    def _load_sources(self) -> list[BlogSource]:
        if not self.sources_root.is_dir():
            return []
        sources = []
        for path in sorted(self.sources_root.glob("*.yml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                sources.append(self._source(data))
        return sources

    def _write_source(self, source: BlogSource) -> None:
        self.sources_root.mkdir(parents=True, exist_ok=True)
        path = self.sources_root / f"{source.id}.yml"
        path.write_text(
            yaml.safe_dump(source.as_dict(), allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

    def _source(self, payload: dict[str, Any]) -> BlogSource:
        discover = _dict_value(payload, "discover")
        capture = _dict_value(payload, "capture")
        summary = _dict_value(payload, "summary")
        notify = _dict_value(payload, "notify")
        schedule = _dict_value(payload, "schedule")
        source_id = str(payload.get("id") or "")
        return BlogSource(
            id=source_id,
            name=str(payload.get("name") or source_id),
            url=str(payload.get("url") or ""),
            discover=DiscoverPolicy(
                method=self._normalize_discover_method(str(discover.get("method") or "requests")),
                link_pattern=str(discover.get("link_pattern") or ""),
                days_back=max(_int(discover.get("days_back"), 30), 1),
            ),
            capture=CapturePolicy(
                enabled=bool(capture.get("enabled")),
                adapter=normalize_slug(str(capture.get("adapter") or "clipsmith")) or "clipsmith",
                kb=str(capture.get("kb") or ""),
                inbox_path=self._normalize_inbox_path(
                    str(capture.get("inbox_path") or ""), source_id
                ),
            ),
            summary=SummaryPolicy(
                enabled=bool(summary.get("enabled")),
                provider=str(summary.get("provider") or "claude"),
            ),
            notify=NotifyPolicy(
                enabled=bool(notify.get("enabled")),
                channel=str(notify.get("channel") or "telegram"),
            ),
            schedule=SchedulePolicy(ttl_hours=max(_int(schedule.get("ttl_hours"), 24), 1)),
            tags=[str(tag) for tag in _list_value(payload, "tags")],
            status=str(payload.get("status") or "active"),
            created_at=str(payload.get("created_at") or ""),
            updated_at=str(payload.get("updated_at") or ""),
            checked_at=str(payload.get("checked_at") or ""),
            changed_at=str(payload.get("changed_at") or ""),
            last_error=str(payload.get("last_error") or ""),
        )

    def _replace_source(self, source: BlogSource, **changes: str) -> BlogSource:
        payload = source.as_dict()
        payload.update(changes)
        return self._source(payload)

    def _public_source(self, source: BlogSource) -> dict[str, Any]:
        payload = source.as_dict()
        capture = payload.get("capture")
        if isinstance(capture, dict) and capture.get("kb"):
            capture["kb"] = str(capture["kb"])
        return payload

    def _load_seen(self, source_id: str) -> set[str]:
        path = self.seen_root / f"{source_id}.json"
        if not path.is_file():
            return set()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return set()
        urls = _list_value(data, "urls") if isinstance(data, dict) else []
        return {str(url) for url in urls if str(url)}

    def _write_seen(self, source_id: str, urls: set[str], *, timestamp: str) -> None:
        self.seen_root.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema": SEEN_SCHEMA,
            "source_id": source_id,
            "updated_at": timestamp,
            "urls": sorted(urls),
        }
        (self.seen_root / f"{source_id}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _is_stale(self, source: BlogSource, timestamp: str) -> bool:
        if not source.checked_at:
            return True
        checked_at = _parse_time(source.checked_at)
        current = _parse_time(timestamp)
        if checked_at is None or current is None:
            return True
        return current >= checked_at + timedelta(hours=max(source.schedule.ttl_hours, 1))

    def _normalize_discover_method(self, method: str) -> str:
        normalized = normalize_slug(method or "requests")
        if normalized not in {"requests", "rss", "atom", "hn-search", "playwright", "sitemap"}:
            raise ValueError(f"Unsupported blog discover method: {method}")
        return normalized

    def _normalize_inbox_path(self, inbox_path: str, source_id: str) -> str:
        value = inbox_path.strip().strip("/")
        if not value:
            value = f"inbox/blogs/{source_id}"
        parts = [part for part in value.split("/") if part not in {"", ".", ".."}]
        if not parts or parts[0] != "inbox":
            parts.insert(0, "inbox")
        return "/".join(parts)

    def _skipped_capture(self) -> dict[str, str]:
        return {"status": "skipped"}

    def storage_summary(self) -> dict[str, str]:
        return {
            "root": compact_user_path(self.root),
            "sources": compact_user_path(self.sources_root),
            "seen": compact_user_path(self.seen_root),
            "events": compact_user_path(self.events_path),
        }


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


def _json_field(text: str, field: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    return str(data.get(field) or "")


def _parse_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _list_value(payload: dict[str, Any], key: str) -> list[Any]:
    value = payload.get(key)
    return value if isinstance(value, list) else []
