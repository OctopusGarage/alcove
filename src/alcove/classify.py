from __future__ import annotations

from dataclasses import dataclass

from alcove.inbox import InboxModule, InboxPost
from alcove.lifecycle import score_confidence
from alcove.markdown import MarkdownRepository
from alcove.taxonomy import domain_for_topic, load_taxonomy, normalize_tag, split_domain_topic
from alcove.workspace import Workspace


@dataclass(frozen=True)
class ClassificationDraft:
    post: dict
    topic: str
    suggested_topic: str
    domain: str
    suggested_tags: list[str]
    draft_summary: str
    confidence: float
    confidence_signals: dict[str, float]
    existing_topics: list[str]
    existing_tags: list[str]
    existing_domains: dict


class ClassifyModule:
    def __init__(self, workspace: Workspace, repo: MarkdownRepository | None = None) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.repo = repo or MarkdownRepository()
        self.taxonomy = load_taxonomy(self.paths.knowledge)

    def classify(self, name: str, proposed_topic: str | None = None) -> ClassificationDraft:
        post = InboxModule(self.workspace).read(name)
        if proposed_topic:
            domain, topic = split_domain_topic(proposed_topic, self.taxonomy)
        else:
            topic = self._suggest_topic(post) or "misc"
            domain = domain_for_topic(topic, self.taxonomy)
        confidence = score_confidence(post)
        tags = self.suggest_tags(post, topic)
        return ClassificationDraft(
            post={
                "name": post.name,
                "platform": post.platform,
                "title": post.title,
                "source": post.source or "",
                "date": post.date or "",
            },
            topic=topic,
            suggested_topic=topic,
            domain=domain,
            suggested_tags=tags,
            draft_summary=self._draft_summary(post),
            confidence=confidence.confidence,
            confidence_signals=confidence.signals,
            existing_topics=self.list_topics(),
            existing_tags=self.list_tags(),
            existing_domains=self.taxonomy.get("domains", {}),
        )

    def suggest_tags(self, post: InboxPost, topic: str, max_tags: int = 6) -> list[str]:
        scores: dict[str, int] = {}
        _domain, topic_slug = split_domain_topic(topic, self.taxonomy)
        topic_tag = normalize_tag(topic_slug, self.taxonomy)
        if topic_tag:
            scores[topic_tag] = 100
        platform = normalize_tag(post.platform, self.taxonomy)
        if platform in self.list_tags():
            scores[platform] = max(scores.get(platform, 0), 80)
        text = f"{post.title}\n{post.content}".casefold()
        for tag in set(self.list_tags()) | set(self.taxonomy.get("tag_aliases", {}).values()):
            if not tag:
                continue
            variant = tag.replace("-", " ")
            score = 0
            if tag.casefold() in text:
                score += 20
            if variant.casefold() in text:
                score += 10
            if score:
                scores[tag] = max(scores.get(tag, 0), score)
        return [
            tag
            for tag, _score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[
                :max_tags
            ]
        ]

    def list_topics(self) -> list[str]:
        topics = {
            topic
            for definition in self.taxonomy.get("domains", {}).values()
            for topic in (definition.get("topics") or [])
        }
        topics_dir = self.paths.knowledge / "topics"
        if topics_dir.exists():
            topics.update(path.stem for path in topics_dir.rglob("*.md") if path.name != "index.md")
        return sorted(topics)

    def list_tags(self) -> list[str]:
        tags_dir = self.paths.knowledge / "tags"
        if not tags_dir.exists():
            return []
        return sorted(path.stem for path in tags_dir.glob("*.md") if path.name != "index.md")

    def _suggest_topic(self, post: InboxPost) -> str:
        text = f"{post.title}\n{post.content}".casefold()
        best_topic = ""
        best_score = 0
        for topic in self.list_topics():
            variants = {topic, topic.replace("-", " ")}
            for alias, mapped in self.taxonomy.get("topic_aliases", {}).items():
                if mapped == topic:
                    variants.add(alias)
            score = sum(text.count(variant.casefold()) for variant in variants if variant)
            if score > best_score:
                best_score = score
                best_topic = topic
        return best_topic

    def _draft_summary(self, post: InboxPost, max_chars: int = 500) -> str:
        lines: list[str] = []
        for line in post.content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped.startswith("---"):
                continue
            if stripped.lower().startswith(
                ("source url:", "published at:", "platform:", "date:", "title:", "来源")
            ):
                continue
            lines.append(stripped)
            if len("\n".join(lines)) >= max_chars:
                break
        summary = "\n".join(lines).strip()
        return summary[:max_chars].rstrip()
