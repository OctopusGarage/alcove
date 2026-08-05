from __future__ import annotations

from pathlib import Path
import json

import pytest
import yaml

import alcove.blog_notifications as blog_notifications
from alcove.blog_discovery import _candidate_sitemap_urls
import alcove.notifications as notifications
from alcove.blog_monitor import BlogArticle, BlogMonitorModule
from alcove.cli import main
from alcove.home import AlcoveHome


def _write_html(path: Path, links: list[tuple[str, str]]) -> None:
    anchors = "\n".join(f'<a href="{href}">{title}</a>' for href, title in links)
    path.write_text(f"<html><body>{anchors}</body></html>", encoding="utf-8")


def test_blog_seed_initializes_seen_without_capture(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    _write_html(
        page,
        [
            ("https://example.com/blog/one", "First useful article"),
            ("https://example.com/blog/two", "Second useful article"),
        ],
    )
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url=page.as_uri(),
        source_id="example",
        link_pattern="/blog/",
    )

    result = module.seed(source_id="example")

    seen = json.loads((home.root / "blog-monitor/seen/example.json").read_text())
    assert result["sources"][0]["status"] == "seeded"
    assert result["sources"][0]["discovered_count"] == 2
    assert seen["urls"] == [
        "https://example.com/blog/one",
        "https://example.com/blog/two",
    ]
    assert not (home.root / "blog-monitor/events.jsonl").exists()


def test_blog_seed_rejects_persisted_source_id_path_traversal(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])
    sources = home.root / "blog-monitor" / "sources"
    sources.mkdir(parents=True)
    (sources / "bad.yml").write_text(
        yaml.safe_dump(
            {
                "id": "../../../escaped-blog",
                "name": "Bad Blog",
                "url": page.as_uri(),
                "discover": {"method": "requests", "link_pattern": "/blog/"},
                "status": "active",
            }
        ),
        encoding="utf-8",
    )

    result = BlogMonitorModule(home).seed()

    assert result["errors"] == 1
    assert result["sources"][0]["id"] == "bad"
    assert "Invalid blog source id" in result["sources"][0]["error"]
    assert not (tmp_path / "escaped-blog.yml").exists()
    assert not (tmp_path / "escaped-blog.json").exists()


def test_blog_check_detects_new_article_and_uses_capture_policy(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    home.register_knowledge_base("social_media_posts", kb_root)
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url=page.as_uri(),
        source_id="example",
        link_pattern="/blog/",
        capture_enabled=True,
        kb="social_media_posts",
        inbox_path="inbox/openai",
    )
    module.seed(source_id="example")
    _write_html(
        page,
        [
            ("https://example.com/blog/one", "First useful article"),
            ("https://example.com/blog/two", "Second useful article"),
        ],
    )

    def fake_capture(source, article: BlogArticle):
        assert source.capture.inbox_path == "inbox/openai"
        assert article.url == "https://example.com/blog/two"
        return {
            "status": "captured",
            "adapter": "clipsmith",
            "inbox_path": str(kb_root / "inbox/openai/example"),
        }

    monkeypatch.setattr(module, "_capture_article", fake_capture)

    result = module.check(source_id="example")

    row = result["sources"][0]
    assert row["status"] == "changed"
    assert row["new_count"] == 1
    assert row["captured_count"] == 1
    assert row["captures"][0]["status"] == "captured"
    assert "report" not in row
    assert not (home.root / "blog-monitor/reports").exists()
    assert (home.root / "blog-monitor/events.jsonl").read_text().count("\n") == 1


def test_blog_notify_sends_title_url_and_captured_summary(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    home.register_knowledge_base("social_media_posts", kb_root)
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url=page.as_uri(),
        source_id="example",
        link_pattern="/blog/",
        capture_enabled=True,
        kb="social_media_posts",
        inbox_path="inbox/openai",
        notify_enabled=True,
    )
    module.seed(source_id="example")
    _write_html(
        page,
        [
            ("https://example.com/blog/one", "First useful article"),
            ("https://example.com/blog/two", "Second useful article"),
        ],
    )
    captured_dir = kb_root / "inbox/openai/second-useful-article"
    captured_dir.mkdir(parents=True)
    (captured_dir / "summary.md").write_text(
        "# Summary\n\nThis article explains practical monitoring improvements.\n",
        encoding="utf-8",
    )

    def fake_capture(source, article: BlogArticle):
        return {
            "status": "captured",
            "adapter": "clipsmith",
            "inbox_path": str(captured_dir),
        }

    sent_payloads: list[dict] = []
    original_urlopen = notifications.urlopen

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_urlopen(request, timeout):
        if not str(request.full_url).startswith("https://api.telegram.org/"):
            return original_urlopen(request, timeout=timeout)
        assert timeout == 15
        sent_payloads.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr(module, "_capture_article", fake_capture)
    monkeypatch.setattr(notifications, "urlopen", fake_urlopen)
    monkeypatch.setenv("ALCOVE_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ALCOVE_TELEGRAM_CHAT_ID", "chat")

    result = module.check(source_id="example")

    row = result["sources"][0]
    assert row["notify"]["status"] == "sent"
    assert row["notify"]["messages"][0]["source_id"] == "example"
    assert row["notify"]["messages"][0]["source_name"] == "Example Blog"
    assert row["notify"]["messages"][0]["article_title"] == "Second useful article"
    assert row["notify"]["messages"][0]["article_url"] == "https://example.com/blog/two"
    assert len(sent_payloads) == 1
    assert sent_payloads[0]["chat_id"] == "chat"
    assert sent_payloads[0]["parse_mode"] == "HTML"
    assert "Second useful article" in sent_payloads[0]["text"]
    assert "https://example.com/blog/two" in sent_payloads[0]["text"]
    assert "This article explains practical monitoring improvements." in sent_payloads[0]["text"]


def test_blog_notify_sends_new_article_to_lark_via_tcb(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    home.register_knowledge_base("social_media_posts", kb_root)
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url=page.as_uri(),
        source_id="example",
        link_pattern="/blog/",
        capture_enabled=True,
        kb="social_media_posts",
        inbox_path="inbox/openai",
        notify_enabled=True,
    )
    source_path = home.root / "blog-monitor/sources/example.yml"
    source_payload = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    source_payload["notify"]["channel"] = "lark"
    source_path.write_text(yaml.safe_dump(source_payload, sort_keys=False), encoding="utf-8")
    module.seed(source_id="example")
    _write_html(
        page,
        [
            ("https://example.com/blog/one", "First useful article"),
            ("https://example.com/blog/two", "Second useful article"),
        ],
    )
    captured_dir = kb_root / "inbox/openai/second-useful-article"
    captured_dir.mkdir(parents=True)
    (captured_dir / "summary.md").write_text(
        "# Summary\n\nThis article explains practical monitoring improvements.\n",
        encoding="utf-8",
    )

    def fake_capture(source, article: BlogArticle):
        return {
            "status": "captured",
            "adapter": "clipsmith",
            "inbox_path": str(captured_dir),
        }

    sent_payloads: list[dict] = []

    def fake_tcb_notify(*, sink, title, text, attachments):
        sent_payloads.append(
            {"sink": sink, "title": title, "text": text, "attachments": attachments}
        )
        return {"status": "sent", "deliveries": [{"channel": "lark", "ok": True}]}

    monkeypatch.setattr(module, "_capture_article", fake_capture)
    monkeypatch.setattr(blog_notifications, "send_tcb_notification", fake_tcb_notify)

    result = module.check(source_id="example")

    row = result["sources"][0]
    assert row["notify"]["status"] == "sent"
    assert row["notify"]["messages"][0]["source_id"] == "example"
    assert row["notify"]["messages"][0]["article_title"] == "Second useful article"
    assert len(sent_payloads) == 1
    assert sent_payloads[0]["sink"] == {"type": "tcb", "channel": "lark"}
    assert sent_payloads[0]["title"] == "Blog Monitor: Example Blog"
    assert sent_payloads[0]["attachments"] == []
    text = sent_payloads[0]["text"]
    assert "Blog Monitor: Example Blog" in text
    assert "Second useful article" in text
    assert "https://example.com/blog/two" in text
    assert "This article explains practical monitoring improvements." in text


def test_blog_notify_reads_telegram_credentials_from_alcove_env_file(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    (home.root / ".env").write_text(
        'ALCOVE_TELEGRAM_BOT_TOKEN="file-token"\nALCOVE_TELEGRAM_CHAT_ID=file-chat\n',
        encoding="utf-8",
    )
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    home.register_knowledge_base("social_media_posts", kb_root)
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url=page.as_uri(),
        source_id="example",
        link_pattern="/blog/",
        capture_enabled=True,
        kb="social_media_posts",
        inbox_path="inbox/openai",
        notify_enabled=True,
    )
    module.seed(source_id="example")
    _write_html(
        page,
        [
            ("https://example.com/blog/one", "First useful article"),
            ("https://example.com/blog/two", "Second useful article"),
        ],
    )
    captured_dir = kb_root / "inbox/openai/second-useful-article"
    captured_dir.mkdir(parents=True)
    (captured_dir / "summary.md").write_text("Captured summary from file env.\n", encoding="utf-8")

    def fake_capture(source, article: BlogArticle):
        return {"status": "captured", "inbox_path": str(captured_dir)}

    sent_requests: list[str] = []
    original_urlopen = notifications.urlopen

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_urlopen(request, timeout):
        if not str(request.full_url).startswith("https://api.telegram.org/"):
            return original_urlopen(request, timeout=timeout)
        sent_requests.append(str(request.full_url))
        return FakeResponse()

    monkeypatch.setattr(module, "_capture_article", fake_capture)
    monkeypatch.setattr(notifications, "urlopen", fake_urlopen)
    monkeypatch.delenv("ALCOVE_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ALCOVE_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)

    result = module.check(source_id="example")

    assert result["sources"][0]["notify"]["status"] == "sent"
    assert sent_requests == ["https://api.telegram.org/botfile-token/sendMessage"]


def test_blog_notify_prefers_alcove_env_file_over_generic_telegram_environment(
    tmp_path, monkeypatch
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    (home.root / ".env").write_text(
        "ALCOVE_TELEGRAM_BOT_TOKEN=file-token\nALCOVE_TELEGRAM_CHAT_ID=file-chat\n",
        encoding="utf-8",
    )
    module = BlogMonitorModule(home)
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "generic-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "generic-chat")
    monkeypatch.delenv("ALCOVE_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ALCOVE_TELEGRAM_CHAT_ID", raising=False)

    assert module._telegram_credential("ALCOVE_TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN") == (
        "file-token"
    )
    assert module._telegram_credential("ALCOVE_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID") == (
        "file-chat"
    )


def test_blog_hn_search_discovery_uses_domain_and_link_pattern(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url="https://example.com/news/",
        source_id="example",
        discover_method="hn-search",
        link_pattern="/index/",
    )
    payload = {
        "hits": [
            {
                "title": "Example infrastructure note",
                "url": "https://example.com/index/infrastructure-note/",
            },
            {
                "title": "Unrelated",
                "url": "https://other.example/index/nope/",
            },
        ]
    }

    monkeypatch.setattr(module, "_fetch_text", lambda _url: json.dumps(payload))

    result = module.seed(source_id="example")

    assert result["sources"][0]["discovered_count"] == 1
    seen = json.loads((home.root / "blog-monitor/seen/example.json").read_text())
    assert seen["urls"] == ["https://example.com/index/infrastructure-note/"]


def test_blog_sitemap_discovery_uses_official_sitemap_urls(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = BlogMonitorModule(home)
    module.add(
        name="OpenAI Engineering",
        url="https://openai.com/sitemap.xml/engineering/",
        source_id="openai",
        discover_method="sitemap",
        link_pattern="/index/",
    )
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://openai.com/index/building-codex-windows-sandbox/</loc>
    <lastmod>2026-07-10T20:02:00.333Z</lastmod>
  </url>
  <url>
    <loc>https://openai.com/about/</loc>
    <lastmod>2026-07-11T20:02:00.333Z</lastmod>
  </url>
  <url>
    <loc>https://example.com/index/nope/</loc>
    <lastmod>2026-07-12T20:02:00.333Z</lastmod>
  </url>
</urlset>
"""

    monkeypatch.setattr(module, "_fetch_text", lambda _url: sitemap)

    result = module.seed(source_id="openai")

    assert result["sources"][0]["discovered_count"] == 1
    seen = json.loads((home.root / "blog-monitor/seen/openai.json").read_text())
    assert seen["urls"] == ["https://openai.com/index/building-codex-windows-sandbox/"]


def test_blog_html_discovery_extracts_article_card_date(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "openai-engineering.html"
    _write_html(
        page,
        [
            (
                "https://openai.com/index/core-dump-epidemiology-data-infrastructure-bug/",
                "Core dump epidemiology: fixing an 18-year-old bug Engineering Jun 30, 2026",
            ),
            (
                "https://openai.com/index/building-codex-windows-sandbox/",
                "Building a safe, effective sandbox to enable Codex on Windows Engineering May 13, 2026",
            ),
        ],
    )
    module = BlogMonitorModule(home)
    module.add(
        name="OpenAI Engineering",
        url=page.as_uri(),
        source_id="openai",
        discover_method="requests",
        link_pattern="/index/",
    )

    articles = module._discover(module._load_sources()[0])

    assert articles[0].title == "Core dump epidemiology: fixing an 18-year-old bug"
    assert articles[0].date == "Jun 30, 2026"
    assert articles[1].title == "Building a safe, effective sandbox to enable Codex on Windows"
    assert articles[1].date == "May 13, 2026"


def test_blog_playwright_discovery_uses_rendered_article_items(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = BlogMonitorModule(home)
    module.add(
        name="OpenAI Engineering",
        url="https://openai.com/news/engineering/",
        source_id="openai",
        discover_method="playwright",
        link_pattern="/index/",
    )

    def fake_extract(source):
        assert source.id == "openai"
        return [
            {
                "title": "Core dump epidemiology: fixing an 18-year-old bug",
                "url": "https://openai.com/index/core-dump-epidemiology-data-infrastructure-bug/",
                "date": "Jun 30, 2026",
            },
            {
                "title": "Ignored about page",
                "url": "https://openai.com/about/",
                "date": "Jul 01, 2026",
            },
        ]

    monkeypatch.setattr(module, "_extract_articles_with_playwright", fake_extract)

    articles = module._discover(module._load_sources()[0])

    assert [article.as_dict() for article in articles] == [
        {
            "title": "Core dump epidemiology: fixing an 18-year-old bug",
            "url": "https://openai.com/index/core-dump-epidemiology-data-infrastructure-bug/",
            "date": "Jun 30, 2026",
            "source_id": "openai",
            "source_name": "OpenAI Engineering",
        }
    ]


def test_blog_playwright_discovery_falls_back_to_html_when_navigation_is_blocked(
    tmp_path, monkeypatch
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = BlogMonitorModule(home)
    module.add(
        name="OpenAI Engineering",
        url="https://openai.com/news/engineering/",
        source_id="openai",
        discover_method="playwright",
        link_pattern="/index/",
    )
    html = """
<html><body>
  <a href="/index/core-dump-epidemiology-data-infrastructure-bug/">
    Core dump epidemiology: fixing an 18-year-old bug Engineering Jun 30, 2026
  </a>
  <a href="/about/">Ignored about page</a>
</body></html>
"""

    def blocked_playwright(_source):
        raise RuntimeError("Navigation failed with HTTP 403")

    monkeypatch.setattr(module, "_extract_articles_with_playwright", blocked_playwright)
    monkeypatch.setattr(module, "_fetch_text", lambda _url: html)

    articles = module._discover(module._load_sources()[0])

    assert [article.as_dict() for article in articles] == [
        {
            "title": "Core dump epidemiology: fixing an 18-year-old bug",
            "url": "https://openai.com/index/core-dump-epidemiology-data-infrastructure-bug/",
            "date": "Jun 30, 2026",
            "source_id": "openai",
            "source_name": "OpenAI Engineering",
        }
    ]


def test_blog_playwright_discovery_falls_back_to_category_sitemap_when_page_is_challenged(
    tmp_path, monkeypatch
):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = BlogMonitorModule(home)
    module.add(
        name="OpenAI Engineering",
        url="https://openai.com/news/engineering/",
        source_id="openai",
        discover_method="playwright",
        link_pattern="/index/",
    )
    challenge_html = """
<html><body>
  <span id="challenge-error-text">Enable JavaScript and cookies to continue</span>
</body></html>
"""
    sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://openai.com/index/core-dump-epidemiology-data-infrastructure-bug/</loc>
    <lastmod>2026-06-30T07:00:00.000Z</lastmod>
  </url>
  <url>
    <loc>https://openai.com/about/</loc>
    <lastmod>2026-07-01T07:00:00.000Z</lastmod>
  </url>
</urlset>
"""
    fetched_urls: list[str] = []

    def blocked_playwright(_source):
        raise RuntimeError("Navigation failed with HTTP 403")

    def fake_fetch(url):
        fetched_urls.append(url)
        if url == "https://openai.com/sitemap.xml/engineering/":
            return sitemap
        return challenge_html

    monkeypatch.setattr(module, "_extract_articles_with_playwright", blocked_playwright)
    monkeypatch.setattr(module, "_fetch_text", fake_fetch)

    articles = module._discover(module._load_sources()[0])

    assert fetched_urls == [
        "https://openai.com/news/engineering/",
        "https://openai.com/sitemap.xml/engineering/",
    ]
    assert [article.as_dict() for article in articles] == [
        {
            "title": "Core Dump Epidemiology Data Infrastructure Bug",
            "url": "https://openai.com/index/core-dump-epidemiology-data-infrastructure-bug/",
            "date": "2026-06-30T07:00:00.000Z",
            "source_id": "openai",
            "source_name": "OpenAI Engineering",
        }
    ]


def test_blog_playwright_discovery_reports_empty_render_and_failed_fallbacks(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = BlogMonitorModule(home)
    module.add(
        name="OpenAI Engineering",
        url="https://openai.com/news/engineering/",
        source_id="openai",
        discover_method="playwright",
        link_pattern="/index/",
    )
    challenge_html = """
<html><body>
  <span id="challenge-error-text">Enable JavaScript and cookies to continue</span>
</body></html>
"""
    empty_sitemap = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://openai.com/about/</loc>
    <lastmod>2026-07-01T07:00:00.000Z</lastmod>
  </url>
</urlset>
"""

    def fake_fetch(url):
        if url == "https://openai.com/sitemap.xml/engineering/":
            return empty_sitemap
        return challenge_html

    monkeypatch.setattr(module, "_extract_articles_with_playwright", lambda _source: [])
    monkeypatch.setattr(module, "_fetch_text", fake_fetch)

    with pytest.raises(RuntimeError) as error:
        module._discover(module._load_sources()[0])

    message = str(error.value)
    assert "Playwright found no article links for https://openai.com/news/engineering/" in message
    assert "HTML fallback found no article links" in message
    assert (
        "sitemap fallback https://openai.com/sitemap.xml/engineering/ found no article links"
        in message
    )


def test_blog_playwright_discovery_reports_html_and_sitemap_fallback_errors(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    module = BlogMonitorModule(home)
    module.add(
        name="OpenAI Engineering",
        url="https://openai.com/news/engineering/",
        source_id="openai",
        discover_method="playwright",
        link_pattern="/index/",
    )

    def fake_fetch(url):
        if url == "https://openai.com/sitemap.xml/engineering/":
            raise RuntimeError("sitemap unavailable")
        raise RuntimeError("html unavailable")

    monkeypatch.setattr(module, "_extract_articles_with_playwright", lambda _source: [])
    monkeypatch.setattr(module, "_fetch_text", fake_fetch)

    with pytest.raises(RuntimeError) as error:
        module._discover(module._load_sources()[0])

    message = str(error.value)
    assert "HTML fallback failed: html unavailable" in message
    assert "sitemap fallback https://openai.com/sitemap.xml/engineering/ failed" in message
    assert "sitemap unavailable" in message


def test_blog_candidate_sitemap_urls_require_news_category_url():
    assert _candidate_sitemap_urls("file:///tmp/blog.html") == []
    assert _candidate_sitemap_urls("https://openai.com/blog/engineering/") == []


def test_blog_discovery_failure_marks_attention_and_sends_alert(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url=page.as_uri(),
        source_id="example",
        link_pattern="/blog/",
        notify_enabled=True,
    )
    sent_payloads: list[dict] = []

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

    def fake_urlopen(request, timeout):
        assert timeout == 15
        sent_payloads.append(json.loads(request.data.decode("utf-8")))
        return FakeResponse()

    monkeypatch.setattr(
        module,
        "_discover",
        lambda _source: (_ for _ in ()).throw(RuntimeError("blocked by challenge")),
    )
    monkeypatch.setattr(notifications, "urlopen", fake_urlopen)
    monkeypatch.setenv("ALCOVE_TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("ALCOVE_TELEGRAM_CHAT_ID", "chat")

    result = module.check(source_id="example", now="2026-07-11T15:00:00+00:00")

    row = result["sources"][0]
    source = module._load_sources()[0]
    assert row["status"] == "needs_attention"
    assert row["stage"] == "discovery"
    assert row["notify"]["status"] == "sent"
    assert row["notify"]["source_id"] == "example"
    assert row["notify"]["stage"] == "discovery"
    assert row["notify"]["error"] == "blocked by challenge"
    assert row["notify"]["retry_command"] == "alcove blog check example --json"
    assert source.status == "needs_attention"
    assert source.last_error == "blocked by challenge"
    assert "Blog Monitor Failed" in sent_payloads[0]["text"]
    assert sent_payloads[0]["text"].index("Error: blocked by challenge") < sent_payloads[0][
        "text"
    ].index("URL:")
    assert "Source ID: example" in sent_payloads[0]["text"]
    assert "alcove blog check example --json" in sent_payloads[0]["text"]
    assert "检查 Example Blog 博客监控失败原因" in sent_payloads[0]["text"]
    run_files = sorted((home.root / "blog-monitor/runs").glob("*-example.json"))
    assert len(run_files) == 1
    payload = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert payload["error"] == "blocked by challenge"
    assert payload["stage"] == "discovery"


def test_blog_discovery_failure_sends_lark_alert_via_tcb(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url=page.as_uri(),
        source_id="example",
        link_pattern="/blog/",
        notify_enabled=True,
    )
    source_path = home.root / "blog-monitor/sources/example.yml"
    source_payload = yaml.safe_load(source_path.read_text(encoding="utf-8"))
    source_payload["notify"]["channel"] = "lark"
    source_path.write_text(yaml.safe_dump(source_payload, sort_keys=False), encoding="utf-8")
    sent_payloads: list[dict] = []

    def fake_tcb_notify(*, sink, title, text, attachments):
        sent_payloads.append(
            {"sink": sink, "title": title, "text": text, "attachments": attachments}
        )
        return {"status": "sent", "deliveries": [{"channel": "lark", "ok": True}]}

    monkeypatch.setattr(
        module,
        "_discover",
        lambda _source: (_ for _ in ()).throw(RuntimeError("blocked by challenge")),
    )
    monkeypatch.setattr(blog_notifications, "send_tcb_notification", fake_tcb_notify)

    result = module.check(source_id="example", now="2026-07-11T15:00:00+00:00")

    row = result["sources"][0]
    assert row["status"] == "needs_attention"
    assert row["notify"]["status"] == "sent"
    assert row["notify"]["source_id"] == "example"
    assert row["notify"]["stage"] == "discovery"
    assert row["notify"]["error"] == "blocked by challenge"
    assert len(sent_payloads) == 1
    assert sent_payloads[0]["sink"] == {"type": "tcb", "channel": "lark"}
    assert sent_payloads[0]["title"] == "Blog Monitor Failed: Example Blog"
    assert sent_payloads[0]["attachments"] == []
    text = sent_payloads[0]["text"]
    assert "Blog Monitor Failed: Example Blog" in text
    assert "Error: blocked by challenge" in text
    assert "alcove blog check example --json" in text


def test_blog_capture_failure_does_not_mark_new_article_seen(tmp_path, monkeypatch):
    home = AlcoveHome.init(tmp_path / ".alcove")
    kb_root = tmp_path / "kb"
    kb_root.mkdir()
    home.register_knowledge_base("social_media_posts", kb_root)
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])
    module = BlogMonitorModule(home)
    module.add(
        name="Example Blog",
        url=page.as_uri(),
        source_id="example",
        link_pattern="/blog/",
        capture_enabled=True,
        kb="social_media_posts",
        inbox_path="inbox/blogs/example",
        notify_enabled=False,
    )

    monkeypatch.setattr(
        module,
        "_capture_article",
        lambda _source, _article: {"status": "failed", "error": "clipsmith failed"},
    )

    result = module.check(source_id="example", now="2026-07-11T15:10:00+00:00")

    row = result["sources"][0]
    assert row["status"] == "needs_attention"
    assert row["stage"] == "capture"
    assert row["error"] == "clipsmith failed"
    assert not (home.root / "blog-monitor/seen/example.json").exists()


def test_cli_blog_add_list_seed_and_check(tmp_path, capsys):
    home = tmp_path / ".alcove"
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])

    add_code = main(
        [
            "blog",
            "add",
            "--home",
            str(home),
            "Example Blog",
            page.as_uri(),
            "--id",
            "example",
            "--link-pattern",
            "/blog/",
            "--json",
        ]
    )
    add_output = capsys.readouterr()
    list_code = main(["blog", "list", "--home", str(home), "--json"])
    list_output = capsys.readouterr()
    seed_code = main(["blog", "seed", "--home", str(home), "example", "--json"])
    seed_output = capsys.readouterr()
    check_code = main(["blog", "check", "--home", str(home), "example", "--json"])
    check_output = capsys.readouterr()

    assert add_code == 0
    assert '"status": "added"' in add_output.out
    assert list_code == 0
    assert '"count": 1' in list_output.out
    assert seed_code == 0
    assert '"status": "seeded"' in seed_output.out
    assert check_code == 0
    assert '"new": 0' in check_output.out


def test_cli_blog_parent_home_is_not_overwritten_by_subcommand_defaults(tmp_path, capsys):
    home = tmp_path / ".alcove"
    page = tmp_path / "blog.html"
    _write_html(page, [("https://example.com/blog/one", "First useful article")])

    add_code = main(
        [
            "blog",
            "--home",
            str(home),
            "add",
            "Example Blog",
            page.as_uri(),
            "--id",
            "example",
            "--link-pattern",
            "/blog/",
            "--json",
        ]
    )
    capsys.readouterr()
    check_code = main(["blog", "--home", str(home), "check", "example", "--json"])
    check_output = capsys.readouterr()

    assert add_code == 0
    assert check_code == 0
    assert '"checked": 1' in check_output.out
