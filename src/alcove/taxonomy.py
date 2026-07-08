from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from alcove.errors import TaxonomyError
from alcove.markdown import normalize_slug


DEFAULT_TAXONOMY = {
    "tag_aliases": {
        "知识库": "knowledge-base",
        "ai工具": "ai-tools",
        "工具": "tools",
        "代码图谱": "code-intelligence",
    },
    "topic_aliases": {
        "知识库": "knowledge-base",
        "工具": "tools",
    },
    "domains": {
        "agent-engineering": {
            "title": "Agent Engineering",
            "topics": ["agent", "agent-harness", "claude-code", "codex", "eval"],
        },
        "ai-knowledge": {
            "title": "AI Knowledge Systems",
            "topics": ["knowledge-base", "rag", "search-ranking", "ai-visibility"],
        },
        "software-engineering": {
            "title": "Software Engineering",
            "topics": ["architecture", "design-system", "go", "tools", "git"],
        },
        "misc": {"title": "Misc", "topics": ["misc"]},
    },
    "platforms": {
        "xhs": {"title": "XiaoHongShu", "inbox": "inbox/xhs"},
        "x": {"title": "X / Twitter", "inbox": "inbox/x"},
        "wechat": {"title": "WeChat", "inbox": "inbox/wechat"},
        "web": {"title": "Generic Web", "inbox": "inbox/web"},
        "anthropic": {"title": "Anthropic", "inbox": "inbox/anthropic"},
    },
}


def load_taxonomy(knowledge_root: Path) -> dict[str, Any]:
    taxonomy = {
        "tag_aliases": dict(DEFAULT_TAXONOMY["tag_aliases"]),
        "topic_aliases": dict(DEFAULT_TAXONOMY["topic_aliases"]),
        "domains": {key: dict(value) for key, value in DEFAULT_TAXONOMY["domains"].items()},
        "platforms": {key: dict(value) for key, value in DEFAULT_TAXONOMY["platforms"].items()},
    }
    path = knowledge_root / "taxonomy.yml"
    if not path.exists():
        return taxonomy
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise _taxonomy_error(path, f"could not parse YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise _taxonomy_error(path, "top-level document must be a mapping")
    tag_aliases = _mapping_section(data, path, "tag_aliases")
    topic_aliases = _mapping_section(data, path, "topic_aliases")
    platforms = _mapping_section(data, path, "platforms")
    domains = _mapping_section(data, path, "domains")

    taxonomy["tag_aliases"].update(_normalize_aliases(tag_aliases))
    taxonomy["topic_aliases"].update(_normalize_aliases(topic_aliases))
    taxonomy["platforms"].update(platforms)
    for domain, definition in domains.items():
        if not isinstance(definition, dict):
            raise _taxonomy_error(path, f"domains.{domain} must be a mapping")
        domain_slug = normalize_slug(domain)
        existing = taxonomy["domains"].setdefault(domain_slug, {"title": domain, "topics": []})
        existing["title"] = definition.get("title") or existing["title"]
        topics_value = definition.get("topics")
        if topics_value is None:
            topics_value = []
        if not isinstance(topics_value, list):
            raise _taxonomy_error(path, f"domains.{domain}.topics must be a list")
        topics = {normalize_topic(topic, taxonomy) for topic in existing.get("topics") or []}
        topics.update(normalize_topic(topic, taxonomy) for topic in topics_value)
        existing["topics"] = sorted(topics)
    return taxonomy


def _mapping_section(data: dict[str, Any], path: Path, section: str) -> dict[str, Any]:
    value = data.get(section)
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _taxonomy_error(path, f"{section} must be a mapping")
    return value


def _taxonomy_error(path: Path, message: str) -> TaxonomyError:
    return TaxonomyError(f"Invalid taxonomy at {path}: {message}")


def _normalize_aliases(aliases: dict[str, Any]) -> dict[str, str]:
    return {
        str(alias).lower().replace("_", " ").strip(): normalize_slug(target)
        for alias, target in aliases.items()
    }


def normalize_tag(tag: str, taxonomy: dict[str, Any]) -> str:
    raw = str(tag or "").strip()
    key = raw.lower().replace("_", " ").strip()
    if key in taxonomy.get("tag_aliases", {}):
        return taxonomy["tag_aliases"][key]
    if raw in taxonomy.get("tag_aliases", {}):
        return taxonomy["tag_aliases"][raw]
    return normalize_slug(key or raw)


def normalize_topic(topic: str, taxonomy: dict[str, Any]) -> str:
    raw = str(topic or "").strip()
    key = raw.lower().replace("_", " ").strip()
    if key in taxonomy.get("topic_aliases", {}):
        return taxonomy["topic_aliases"][key]
    return normalize_tag(raw, taxonomy)


def split_domain_topic(value: str, taxonomy: dict[str, Any]) -> tuple[str, str]:
    raw = str(value or "").strip()
    if "/" in raw:
        domain, _, topic = raw.partition("/")
        return normalize_slug(domain), normalize_topic(topic, taxonomy)
    topic = normalize_topic(raw, taxonomy)
    return domain_for_topic(topic, taxonomy), topic


def domain_for_topic(topic: str, taxonomy: dict[str, Any]) -> str:
    topic_slug = normalize_topic(topic, taxonomy)
    for domain, definition in taxonomy.get("domains", {}).items():
        if topic_slug in set(definition.get("topics") or []):
            return domain
    return "misc"
