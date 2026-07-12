from __future__ import annotations

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource
from alcove.radars.sources.base import SourceAdapter
from alcove.radars.sources.fixture import FixtureAdapter
from alcove.radars.sources.generic_html import GenericHtmlAdapter
from alcove.radars.sources.github_trending import GitHubTrendingAdapter
from alcove.radars.sources.hackernews import HackerNewsAdapter
from alcove.radars.sources.rss import RssAdapter


_ADAPTERS: dict[str, SourceAdapter] = {
    "fixture": FixtureAdapter(),
    "generic-html": GenericHtmlAdapter(),
    "github-trending": GitHubTrendingAdapter(),
    "hackernews": HackerNewsAdapter(),
    "rss": RssAdapter(),
}


def fetch_source(definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
    adapter = _ADAPTERS.get(source.adapter)
    if adapter is None:
        raise ValueError(f"unsupported radar source adapter: {source.adapter}")
    return adapter.fetch(definition, source)


def registered_adapters() -> list[str]:
    return sorted(_ADAPTERS)
