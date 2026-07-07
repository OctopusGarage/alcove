from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

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
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    taxonomy["tag_aliases"].update(data.get("tag_aliases") or {})
    taxonomy["topic_aliases"].update(data.get("topic_aliases") or {})
    taxonomy["platforms"].update(data.get("platforms") or {})
    for domain, definition in (data.get("domains") or {}).items():
        domain_slug = normalize_slug(domain)
        existing = taxonomy["domains"].setdefault(domain_slug, {"title": domain, "topics": []})
        existing["title"] = definition.get("title") or existing["title"]
        topics = {normalize_topic(topic, taxonomy) for topic in existing.get("topics") or []}
        topics.update(
            normalize_topic(topic, taxonomy) for topic in definition.get("topics") or []
        )
        existing["topics"] = sorted(topics)
    return taxonomy


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
