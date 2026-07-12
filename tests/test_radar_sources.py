from __future__ import annotations

import json

from alcove.radars.models import RadarDefinition, RadarSource
from alcove.radars.sources import fetch_source, registered_adapters


def test_fixture_adapter_loads_items_from_json_file(tmp_path) -> None:
    fixture = tmp_path / "items.json"
    fixture.write_text(
        json.dumps(
            [
                {
                    "title": "Useful AI article",
                    "url": "https://example.test/ai",
                    "summary": "Good signal",
                    "tags": ["AI"],
                }
            ]
        ),
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="custom",
        name="Custom",
        sources=[RadarSource(id="fixture", adapter="fixture", params={"path": str(fixture)})],
    )

    items = fetch_source(definition, definition.sources[0])

    assert len(items) == 1
    assert items[0].source_id == "fixture"
    assert items[0].adapter == "fixture"
    assert items[0].title == "Useful AI article"
    assert items[0].summary == "Good signal"
    assert items[0].tags == ["AI"]


def test_rss_adapter_reads_local_rss_and_atom_feeds(tmp_path) -> None:
    rss = tmp_path / "feed.xml"
    rss.write_text(
        """<?xml version="1.0"?>
<rss version="2.0"><channel>
<item><title>First News</title><link>https://example.test/first</link><description><![CDATA[<ol><li><a href="https://example.test/first">Summary</a>&nbsp;&nbsp;<font>Source</font></li></ol><script>ignore()</script>]]></description></item>
</channel></rss>""",
        encoding="utf-8",
    )
    atom = tmp_path / "atom.xml"
    atom.write_text(
        """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Atom News</title><link href="https://example.test/atom" /><summary>Atom summary</summary></entry>
</feed>""",
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="news",
        name="News",
        sources=[
            RadarSource(id="local-rss", adapter="rss", params={"url": rss.as_uri()}),
            RadarSource(id="local-atom", adapter="rss", params={"url": atom.as_uri()}),
        ],
    )

    rss_items = fetch_source(definition, definition.sources[0])
    atom_items = fetch_source(definition, definition.sources[1])

    assert rss_items[0].title == "First News"
    assert rss_items[0].url == "https://example.test/first"
    assert rss_items[0].summary == "Summary Source"
    assert atom_items[0].title == "Atom News"
    assert atom_items[0].url == "https://example.test/atom"


def test_generic_html_adapter_extracts_matching_links(tmp_path) -> None:
    page = tmp_path / "index.html"
    page.write_text(
        '<a href="https://example.test/blog/one">First blog post</a>'
        '<a href="/about">About</a>'
        '<a href="blog/two">Second blog post</a>',
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="html",
        name="HTML",
        sources=[
            RadarSource(
                id="html",
                adapter="generic-html",
                params={"url": page.as_uri(), "link_pattern": "/blog/"},
            )
        ],
    )

    items = fetch_source(definition, definition.sources[0])

    assert [(item.title, item.url) for item in items] == [
        ("First blog post", "https://example.test/blog/one"),
        ("Second blog post", page.parent.as_uri() + "/blog/two"),
    ]


def test_hackernews_adapter_reads_firebase_json(tmp_path) -> None:
    feed_root = tmp_path / "hn"
    item_root = feed_root / "item"
    item_root.mkdir(parents=True)
    (feed_root / "topstories.json").write_text("[101, 102]", encoding="utf-8")
    (item_root / "101.json").write_text(
        '{"id":101,"title":"Useful AI story","url":"https://example.test/ai","by":"alice","score":42,"descendants":7,"time":1760000000}',
        encoding="utf-8",
    )
    (item_root / "102.json").write_text(
        '{"id":102,"title":"Ask HN without URL","by":"bob"}',
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="hn",
        name="HN",
        sources=[
            RadarSource(
                id="hn",
                adapter="hackernews",
                params={"base_url": feed_root.as_uri()},
            )
        ],
    )

    items = fetch_source(definition, definition.sources[0])

    assert len(items) == 1
    assert items[0].title == "Useful AI story"
    assert items[0].url == "https://example.test/ai"
    assert items[0].author == "alice"
    assert items[0].published_at == "2025-10-09T08:53:20+00:00"
    assert items[0].metrics["score"] == 42


def test_github_trending_adapter_extracts_repository_cards(tmp_path) -> None:
    page = tmp_path / "trending.html"
    page.write_text(
        """
<article>
  <h2><a href="/octopus/alcove"> octopus / alcove </a></h2>
  <p>Local-first knowledge workbench.</p>
  <span itemprop="programmingLanguage">Python</span>
  <a href="/octopus/alcove/stargazers">1,234</a>
</article>
<article>
  <h2><a href="/openai/codex"> openai / codex </a></h2>
  <p>Agentic coding in the terminal.</p>
</article>
""",
        encoding="utf-8",
    )
    definition = RadarDefinition(
        id="github",
        name="GitHub",
        sources=[
            RadarSource(
                id="trending",
                adapter="github-trending",
                params={"url": page.as_uri()},
            )
        ],
    )

    items = fetch_source(definition, definition.sources[0])

    assert [(item.title, item.summary) for item in items] == [
        ("octopus/alcove", "Local-first knowledge workbench."),
        ("openai/codex", "Agentic coding in the terminal."),
    ]
    assert items[0].tags == ["Python"]
    assert items[0].metrics["stars"] == 1234


def test_packaged_preset_adapters_are_registered(tmp_path) -> None:
    registered = set(registered_adapters())
    assert {"hackernews", "github-trending", "rss"}.issubset(registered)
