from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
import re

from alcove.radars.models import RadarDefinition, RadarItem


def score_items(definition: RadarDefinition, items: list[RadarItem]) -> list[RadarItem]:
    profile = definition.profile
    blocked = _lower_list(profile.get("blocked_keywords"))
    interests = _interest_terms(profile)
    threshold = _threshold(definition)
    max_age_days = _max_age_days(definition)
    scored: list[RadarItem] = []
    for item in items:
        text = " ".join([item.title, item.summary, " ".join(item.tags)]).lower()
        stale_reason = _stale_reason(item.published_at, max_age_days=max_age_days)
        if stale_reason:
            scored.append(replace(item, score=0.0, score_reason=stale_reason, included=False))
            continue
        blocked_match = next((keyword for keyword in blocked if keyword and keyword in text), "")
        if blocked_match:
            scored.append(
                replace(
                    item,
                    score=0.0,
                    score_reason=f"blocked keyword: {blocked_match}",
                    included=False,
                )
            )
            continue
        matches = [tag for tag in interests if tag and _term_matches(tag, text)]
        source_weight = _source_weight(definition, item.source_id)
        score = min(1.0, 0.35 + source_weight + (0.2 * len(matches)))
        source_cap = _source_cap(definition, item.source_id)
        if source_cap:
            score = min(score, source_cap)
        reason = _score_reason(matches, source_weight, source_cap)
        scored.append(
            replace(item, score=round(score, 4), score_reason=reason, included=score >= threshold)
        )
    return scored


def _lower_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).lower() for item in value]


def _interest_terms(profile: dict[str, object]) -> list[str]:
    fields = [
        "interest_tags",
        "news_categories",
        "watched_symbols",
        "sectors",
        "content_type_preference",
    ]
    terms: list[str] = []
    for field in fields:
        terms.extend(_lower_list(profile.get(field)))
    return list(dict.fromkeys(terms))


def _threshold(definition: RadarDefinition) -> float:
    profile_threshold = definition.profile.get("min_score_threshold")
    scoring_threshold = definition.scoring.get("min_score")
    value = profile_threshold if profile_threshold is not None else scoring_threshold
    try:
        return float(value if value is not None else 0.5)
    except (TypeError, ValueError):
        return 0.5


def _source_weight(definition: RadarDefinition, source_id: str) -> float:
    weights = definition.scoring.get("source_weights")
    if not isinstance(weights, dict):
        return 0.0
    value = weights.get(source_id)
    if value is None:
        return 0.0
    try:
        return max(0.0, min(float(value), 0.25))
    except (TypeError, ValueError):
        return 0.0


def _source_cap(definition: RadarDefinition, source_id: str) -> float:
    caps = definition.scoring.get("source_caps")
    if not isinstance(caps, dict):
        return 0.0
    value = caps.get(source_id)
    if value is None:
        return 0.0
    try:
        return max(0.0, min(float(value), 1.0))
    except (TypeError, ValueError):
        return 0.0


def _score_reason(matches: list[str], source_weight: float, source_cap: float) -> str:
    parts: list[str] = []
    if matches:
        parts.append("matched: " + ", ".join(matches[:5]))
    if source_weight:
        parts.append(f"source weight: {source_weight:.2f}")
    if source_cap:
        parts.append(f"source cap: {source_cap:.2f}")
    return "; ".join(parts) if parts else "baseline source signal"


def _max_age_days(definition: RadarDefinition) -> int:
    value = definition.profile.get("max_age_days")
    try:
        return max(0, int(value)) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _stale_reason(published_at: str, *, max_age_days: int) -> str:
    if not max_age_days or not published_at.strip():
        return ""
    published = _parse_datetime(published_at)
    if published is None:
        return ""
    age_days = (datetime.now(UTC) - published).days
    if age_days > max_age_days:
        return f"stale published_at: {published.date().isoformat()}"
    return ""


def _parse_datetime(value: str) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    try:
        parsed = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError, OverflowError):
        parsed = None
    if parsed is None:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _term_matches(term: str, text: str) -> bool:
    normalized = term.strip().lower()
    if not normalized:
        return False
    if re.fullmatch(r"[a-z0-9+#.-]{1,4}", normalized):
        return re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text) is not None
    return normalized in text
