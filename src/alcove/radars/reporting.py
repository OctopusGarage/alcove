from __future__ import annotations

from html import escape
import re
from urllib.parse import urlparse

from alcove.radars.models import RadarDefinition, RadarItem


def render_markdown(definition: RadarDefinition, items: list[RadarItem], *, run_day: str) -> str:
    included = selected_report_items(definition, items)
    source_counts = _source_counts(items)
    lines = [
        f"# {definition.name} - {run_day}",
        "",
        f"- Radar ID: `{definition.id}`",
        f"- Total scored items: {len(items)}",
        f"- Included items: {len(included)}",
        f"- Active sources represented: {len(source_counts)}",
        "",
        "## Brief",
        "",
        _brief_sentence(definition, included, source_counts),
        "",
        "## Source Coverage",
        "",
        *[f"- `{source_id}`: {count}" for source_id, count in sorted(source_counts.items())],
        "",
        "## Top Signals",
        "",
    ]
    if not included:
        lines.append("- No items passed the threshold.")
    for index, item in enumerate(included, start=1):
        lines.append(
            f"{index}. [{item.title}]({item.url}) - score {item.score:.2f} - {item.score_reason}"
        )
        lines.append(f"  - {_summary(item)}")
        if item.published_at:
            lines.append(f"  - Published: {item.published_at}")
    return "\n".join(lines) + "\n"


def render_html(definition: RadarDefinition, items: list[RadarItem], *, run_day: str) -> str:
    included = selected_report_items(definition, items)
    source_counts = _source_counts(items)
    rows = "\n".join(_item_card(index, item) for index, item in enumerate(included, start=1))
    if not rows:
        rows = '<article class="empty">No items passed the threshold.</article>'
    source_rows = "\n".join(
        f"<li><span>{escape(source_id)}</span><strong>{count}</strong></li>"
        for source_id, count in sorted(source_counts.items())
    )
    if not source_rows:
        source_rows = "<li><span>No sources</span><strong>0</strong></li>"
    profile_terms = ", ".join(_profile_terms(definition)[:10]) or "No explicit profile terms"
    source_count = len(source_counts)
    included_count = len(included)
    total_count = len(items)
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{escape(definition.name)} - {escape(run_day)}</title>"
        f"<style>{_css()}</style>"
        "</head>\n"
        "<body>"
        "<main>"
        '<section class="hero">'
        '<div class="hero-copy">'
        f'<p class="eyebrow">{escape(definition.id)} / radar briefing</p>'
        f"<h1>{escape(definition.name)}</h1>"
        f"<p>{escape(_brief_sentence(definition, included, source_counts))}</p>"
        "</div>"
        '<div class="stats">'
        f"<div><strong>{included_count}</strong><span>signals</span></div>"
        f"<div><strong>{total_count}</strong><span>scored</span></div>"
        f"<div><strong>{source_count}</strong><span>sources</span></div>"
        "</div>"
        "</section>"
        '<section class="meta-grid">'
        '<div class="panel">'
        "<h2>Run</h2>"
        f"<p>{escape(run_day)}</p>"
        "</div>"
        '<div class="panel">'
        "<h2>Profile</h2>"
        f"<p>{escape(profile_terms)}</p>"
        "</div>"
        '<div class="panel">'
        "<h2>Sources</h2>"
        f"<ul>{source_rows}</ul>"
        "</div>"
        "</section>"
        '<section class="signals">'
        "<h2>Top Signals</h2>"
        f"{rows}"
        "</section>"
        "</main>"
        "</body>\n"
        "</html>\n"
    )


def selected_report_items(definition: RadarDefinition, items: list[RadarItem]) -> list[RadarItem]:
    """Return the final deduped, limited items shown in radar reports."""

    ranked = sorted(
        (item for item in items if item.included), key=lambda item: item.score, reverse=True
    )
    max_per_source = _max_per_source(definition)
    included: list[RadarItem] = []
    source_counts: dict[str, int] = {}
    topic_keys: list[set[str]] = []
    for item in ranked:
        key = _topic_key(item.title)
        if _is_duplicate_topic(key, topic_keys):
            continue
        if max_per_source:
            count = source_counts.get(item.source_id, 0)
            if count >= max_per_source:
                continue
            source_counts[item.source_id] = count + 1
        included.append(item)
        topic_keys.append(key)
    limit = _report_limit(definition)
    return included[:limit] if limit else included


def _report_limit(definition: RadarDefinition) -> int:
    try:
        return max(0, int(definition.report.get("max_items") or 12))
    except (TypeError, ValueError):
        return 12


def _max_per_source(definition: RadarDefinition) -> int:
    try:
        return max(0, int(definition.report.get("max_per_source") or 0))
    except (TypeError, ValueError):
        return 0


def _topic_key(title: str) -> set[str]:
    text = title.lower()
    text = re.sub(r"\s+-\s+[^-]{2,40}$", "", text)
    tokens = re.findall(r"[a-z0-9]+", text)
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "for",
        "from",
        "how",
        "in",
        "is",
        "it",
        "its",
        "new",
        "of",
        "on",
        "or",
        "the",
        "to",
        "with",
    }
    return {token for token in tokens if len(token) > 2 and token not in stopwords}


def _is_duplicate_topic(key: set[str], existing: list[set[str]]) -> bool:
    if len(key) < 3:
        return False
    for other in existing:
        if len(other) < 3:
            continue
        overlap = len(key & other)
        if overlap / min(len(key), len(other)) >= 0.58:
            return True
    return False


def _source_counts(items: list[RadarItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.source_id] = counts.get(item.source_id, 0) + 1
    return counts


def _brief_sentence(
    definition: RadarDefinition,
    included: list[RadarItem],
    source_counts: dict[str, int],
) -> str:
    if not included:
        return (
            f"{definition.name} found no high-confidence signals from "
            f"{len(source_counts)} source groups on this run."
        )
    top = included[0]
    return (
        f"{definition.name} surfaced {len(included)} ranked signals from "
        f"{len(source_counts)} source groups. The strongest lead is "
        f"'{top.title}' from {top.source_id}."
    )


def _item_card(index: int, item: RadarItem) -> str:
    host = urlparse(item.url).netloc or item.source_id
    summary = _summary(item)
    published = f"<span>{escape(item.published_at)}</span>" if item.published_at else ""
    return (
        '<article class="signal-card">'
        '<div class="rank">'
        f"<span>{index:02d}</span>"
        f"<strong>{item.score:.2f}</strong>"
        "</div>"
        '<div class="signal-body">'
        f'<a href="{escape(item.url, quote=True)}">{escape(item.title)}</a>'
        f"<p>{escape(summary)}</p>"
        '<div class="signal-meta">'
        f"<span>{escape(item.source_id)}</span>"
        f"<span>{escape(host)}</span>"
        f"<span>{escape(item.score_reason)}</span>"
        f"{published}"
        "</div>"
        "</div>"
        "</article>"
    )


def _profile_terms(definition: RadarDefinition) -> list[str]:
    terms: list[str] = []
    for field in [
        "interest_tags",
        "news_categories",
        "watched_symbols",
        "sectors",
        "content_type_preference",
    ]:
        value = definition.profile.get(field)
        if isinstance(value, list):
            terms.extend(str(item) for item in value if str(item).strip())
    return list(dict.fromkeys(terms))


def _summary(item: RadarItem) -> str:
    if item.summary.strip():
        return _excerpt(item.summary.strip(), max_chars=320)
    return f"Source summary unavailable; selected because {item.score_reason}."


def _excerpt(text: str, *, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "..."


def _css() -> str:
    return """
:root {
  color-scheme: light;
  --paper: #f7f8fb;
  --ink: #151922;
  --muted: #667085;
  --line: #d9dee8;
  --panel: #ffffff;
  --blue: #2457d6;
  --teal: #087f83;
  --ruby: #b42318;
  --amber: #c58518;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 15px/1.55 Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
main {
  width: min(1120px, calc(100% - 32px));
  margin: 0 auto;
  padding: 48px 0 56px;
}
.hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 380px);
  gap: 28px;
  align-items: stretch;
  border-bottom: 3px solid var(--ink);
  padding-bottom: 28px;
}
.eyebrow {
  margin: 0 0 12px;
  color: var(--teal);
  font: 700 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
  letter-spacing: 0;
  text-transform: uppercase;
}
h1 {
  margin: 0;
  max-width: 760px;
  font-size: 76px;
  line-height: .92;
  letter-spacing: 0;
}
.hero p:not(.eyebrow) {
  max-width: 720px;
  margin: 20px 0 0;
  color: #384252;
  font-size: 18px;
}
.stats {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border: 1px solid var(--line);
  background: var(--panel);
}
.stats div {
  display: flex;
  min-height: 150px;
  flex-direction: column;
  justify-content: flex-end;
  padding: 18px;
  border-left: 1px solid var(--line);
}
.stats div:first-child { border-left: 0; }
.stats strong {
  font-size: 42px;
  line-height: 1;
}
.stats span {
  margin-top: 8px;
  color: var(--muted);
  font: 700 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
  text-transform: uppercase;
}
.meta-grid {
  display: grid;
  grid-template-columns: 1fr 1.5fr 1.2fr;
  gap: 16px;
  margin: 24px 0 34px;
}
.panel {
  border: 1px solid var(--line);
  background: var(--panel);
  padding: 18px;
}
h2 {
  margin: 0 0 12px;
  font-size: 15px;
  text-transform: uppercase;
}
.panel p, .panel ul {
  margin: 0;
  color: var(--muted);
}
.panel ul {
  padding: 0;
  list-style: none;
}
.panel li {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  border-top: 1px solid var(--line);
  padding: 8px 0;
}
.panel li:first-child { border-top: 0; padding-top: 0; }
.signals {
  display: grid;
  gap: 12px;
}
.signals > h2 {
  margin-bottom: 2px;
}
.signal-card {
  display: grid;
  grid-template-columns: 84px minmax(0, 1fr);
  gap: 18px;
  border: 1px solid var(--line);
  background: var(--panel);
  padding: 18px;
}
.rank {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  border-right: 3px solid var(--blue);
  padding-right: 16px;
  color: var(--blue);
}
.rank span {
  font: 700 13px/1 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.rank strong {
  font-size: 28px;
  line-height: 1;
}
.signal-body a {
  color: var(--ink);
  font-size: 21px;
  font-weight: 750;
  line-height: 1.2;
  text-decoration-color: var(--amber);
  text-decoration-thickness: 2px;
  text-underline-offset: 4px;
}
.signal-body p {
  margin: 10px 0 12px;
  color: #384252;
}
.signal-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.signal-meta span {
  border: 1px solid var(--line);
  color: var(--muted);
  padding: 3px 7px;
  font: 600 12px/1.2 ui-monospace, SFMono-Regular, Menlo, monospace;
}
.empty {
  border: 1px dashed var(--line);
  background: var(--panel);
  color: var(--muted);
  padding: 24px;
}
@media (max-width: 820px) {
  main { width: min(100% - 24px, 1120px); padding-top: 28px; }
  .hero, .meta-grid { grid-template-columns: 1fr; }
  h1 { font-size: 44px; }
  .stats div { min-height: 110px; }
  .signal-card { grid-template-columns: 1fr; }
  .rank {
    flex-direction: row;
    border-right: 0;
    border-bottom: 3px solid var(--blue);
    padding: 0 0 12px;
  }
}
"""
