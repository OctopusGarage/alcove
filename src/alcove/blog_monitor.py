from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import yaml

from alcove.blog_capture import BlogCaptureModule
from alcove.blog_discovery import BlogDiscoveryModule
from alcove.blog_notifications import BlogNotifier
from alcove.blog_run import BLOG_ATTENTION_STATUS, BlogRunModule
from alcove.home import AlcoveHome
from alcove.markdown import normalize_slug
from alcove.paths import compact_user_path


DEFAULT_TTL_HOURS = 24
SOURCE_SCHEMA = "alcove/blog-source/v1"
SEEN_SCHEMA = "alcove/blog-seen/v1"
ATTENTION_STATUS = BLOG_ATTENTION_STATUS


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
        return BlogRunModule(self).check(
            source_id=source_id,
            stale_only=stale_only,
            seed_only=seed_only,
            capture_override=capture_override,
            summary_override=summary_override,
            notify_override=notify_override,
            timestamp=timestamp,
        )

    def _discover(self, source: BlogSource) -> list[BlogArticle]:
        return BlogDiscoveryModule(self).discover(source)

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

    def _article(self, source: BlogSource, *, title: str, url: str, date: str = "") -> BlogArticle:
        return BlogArticle(
            title=title,
            url=url,
            date=date,
            source_id=source.id,
            source_name=source.name,
        )

    def _capture_article(self, source: BlogSource, article: BlogArticle) -> dict[str, Any]:
        return BlogCaptureModule(self).capture(source, article)

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
        return BlogNotifier(self.home).notify(source, articles, captures, summary)

    def _notify_failure(self, source: BlogSource, *, stage: str, error: str) -> dict[str, Any]:
        return BlogNotifier(self.home).notify_failure(source, stage=stage, error=error)

    def _failure_retry_command(self, source: BlogSource) -> str:
        return BlogNotifier(self.home).failure_retry_command(source)

    def _telegram_credential(self, alcove_name: str, generic_name: str) -> str:
        return BlogNotifier(self.home).telegram_credential(alcove_name, generic_name)

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
