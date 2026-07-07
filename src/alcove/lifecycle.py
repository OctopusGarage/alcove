from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re

from alcove.markdown import MarkdownDoc, MarkdownRepository, normalize_slug
from alcove.taxonomy import load_taxonomy, normalize_topic, split_domain_topic
from alcove.workspace import Workspace


PLATFORM_CONFIDENCE = {
    "anthropic": 0.95,
    "wechat": 0.75,
    "web": 0.60,
    "x": 0.55,
    "xhs": 0.45,
    "unknown": 0.30,
}


@dataclass(frozen=True)
class ConfidenceScore:
    confidence: float
    signals: dict[str, float]
    details: dict[str, int]


@dataclass(frozen=True)
class SimilarSource:
    path: str
    rel: str
    title: str
    confidence: float
    similarity: float


def normalize_for_similarity(text: str) -> str:
    text = (text or "").casefold()
    text = re.sub(r"[^一-鿿\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def jaccard_similarity(a: str, b: str, k: int = 3) -> float:
    def kgrams(value: str) -> set[str]:
        return {value[i : i + k] for i in range(max(0, len(value) - k + 1))}

    left = kgrams(a)
    right = kgrams(b)
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def source_signature(title: str, summary: str) -> str:
    return normalize_for_similarity(f"{title or ''} {(summary or '')[:600]}")


def score_confidence(post_or_mapping: object) -> ConfidenceScore:
    getter = post_or_mapping.get if isinstance(post_or_mapping, dict) else lambda key, default=None: getattr(post_or_mapping, key, default)
    title = getter("title", "") or ""
    content = getter("content", "") or ""
    platform = (getter("platform", "unknown") or "unknown").lower()
    date = getter("date", "") or ""
    text = f"{title}\n{content}"

    platform_score = PLATFORM_CONFIDENCE.get(platform, 0.50)
    verify_score, details = _verifiability_score(text)
    recency_score = _recency_score(date)
    confidence = platform_score * 0.35 + verify_score * 0.45 + recency_score * 0.20
    return ConfidenceScore(
        confidence=round(min(max(confidence, 0.0), 1.0), 2),
        signals={
            "platform": round(platform_score, 2),
            "verifiability": round(verify_score, 2),
            "recency": round(recency_score, 2),
        },
        details=details,
    )


def _verifiability_score(text: str) -> tuple[float, dict[str, int]]:
    details = {
        "urls": len(re.findall(r"https?://[^\s\]\)\>\"'`]+", text or "")),
        "code_blocks": len(re.findall(r"```[\s\S]*?```", text or "")),
        "inline_code": len(re.findall(r"`[^`]+`", text or "")),
        "numbers": len(re.findall(r"\b\d+(?:\.\d+)?(?:\s*%|\s*x|\s*K|\s*M|\s*stars?)?\b", text or "", flags=re.I)),
        "commands": len(re.findall(r"\b(uv run|npm|npx|git|pytest|python|bash|curl|gh)\b", text or "", flags=re.I)),
        "quoted": len(re.findall(r"[「\"'`].+?[」\"'`]", text or "")),
    }
    score = 0.0
    if details["urls"]:
        score += min(details["urls"] * 0.10, 0.25)
    if details["code_blocks"]:
        score += min(details["code_blocks"] * 0.10, 0.20)
    if details["inline_code"]:
        score += min(details["inline_code"] * 0.03, 0.10)
    if details["numbers"] > 2:
        score += min((details["numbers"] - 2) * 0.02, 0.15)
    if details["commands"]:
        score += min(details["commands"] * 0.05, 0.15)
    if details["quoted"]:
        score += min(details["quoted"] * 0.03, 0.10)
    return min(score, 1.0), details


def _recency_score(date: str) -> float:
    if not date:
        return 0.50
    try:
        value = datetime.strptime(str(date)[:10], "%Y-%m-%d")
    except ValueError:
        return 0.50
    age_days = (datetime.now() - value).days
    if age_days < 0:
        return 0.50
    if age_days <= 30:
        return 1.0
    if age_days <= 90:
        return 0.85
    if age_days <= 180:
        return 0.70
    if age_days <= 365:
        return 0.55
    return 0.40


class LifecycleModule:
    def __init__(self, workspace: Workspace, repo: MarkdownRepository | None = None) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.knowledge_root = self.paths.knowledge
        self.repo = repo or MarkdownRepository()
        self.taxonomy = load_taxonomy(self.knowledge_root)

    def find_similar_sources(
        self,
        topic: str,
        title: str,
        summary: str,
        threshold: float = 0.75,
    ) -> list[SimilarSource]:
        _domain, topic_slug = split_domain_topic(topic, self.taxonomy)
        signature = source_signature(title, summary)
        if not signature:
            return []
        similar: list[SimilarSource] = []
        for doc in self.repo.list_docs(self.knowledge_root, type_filter="Source"):
            if doc.path is None or doc.frontmatter.get("topic") != topic_slug:
                continue
            if doc.frontmatter.get("status", "active") != "active":
                continue
            existing_summary = _summary_from_body(doc.body)
            existing_signature = source_signature(str(doc.frontmatter.get("title") or ""), existing_summary)
            score = jaccard_similarity(signature, existing_signature)
            if score >= threshold:
                rel = doc.path.relative_to(self.knowledge_root).as_posix()
                similar.append(
                    SimilarSource(
                        path=str(doc.path),
                        rel=rel,
                        title=str(doc.frontmatter.get("title") or ""),
                        confidence=float(doc.frontmatter.get("confidence") or 0.5),
                        similarity=round(score, 2),
                    )
                )
        return sorted(similar, key=lambda item: item.similarity, reverse=True)

    def mark_superseded(self, rel_paths: list[str], superseded_by: str) -> list[str]:
        changed: list[str] = []
        ref = superseded_by if superseded_by.startswith("/") else f"/{superseded_by}"
        for rel in rel_paths:
            path = self.knowledge_root / rel.lstrip("/")
            if not path.exists():
                continue
            doc = self.repo.read_doc(path)
            frontmatter = {
                **doc.frontmatter,
                "status": "superseded",
                "superseded_by": ref,
            }
            self.repo.write_doc(path, MarkdownDoc(frontmatter=frontmatter, body=doc.body))
            changed.append(rel)
        return changed

    def refresh_topic(self, topic: str, in_place: bool = False, summary: str = "") -> dict:
        domain, topic_slug = split_domain_topic(topic, self.taxonomy)
        sources = [
            doc
            for doc in self.repo.list_docs(self.knowledge_root, type_filter="Source")
            if doc.frontmatter.get("topic") == topic_slug
            and doc.frontmatter.get("status", "active") == "active"
            and doc.path is not None
        ]
        if not sources:
            raise ValueError(f"No active sources found for topic '{topic_slug}'")
        source_refs = [f"/{doc.path.relative_to(self.knowledge_root).as_posix()}" for doc in sources if doc.path]
        tags = sorted({str(tag) for doc in sources for tag in (doc.frontmatter.get("tags") or [])})
        final_summary = summary or _composite_summary(sources)

        concepts = [
            doc
            for doc in self.repo.list_docs(self.knowledge_root, type_filter="Knowledge Concept")
            if doc.frontmatter.get("topic") == topic_slug and doc.path is not None
        ]
        superseded: list[str] = []
        if in_place and concepts:
            target = concepts[0]
            assert target.path is not None
            frontmatter = {
                **target.frontmatter,
                "source_refs": source_refs,
                "tags": tags,
                "status": "active",
                "last_verified": datetime.now().date().isoformat(),
            }
            self.repo.write_doc(target.path, MarkdownDoc(frontmatter=frontmatter, body=target.body))
            path = target.path
        else:
            for concept in concepts:
                if concept.path is None or concept.frontmatter.get("status") != "active":
                    continue
                doc = self.repo.read_doc(concept.path)
                self.repo.write_doc(
                    concept.path,
                    MarkdownDoc(
                        frontmatter={**doc.frontmatter, "status": "superseded"},
                        body=doc.body,
                    ),
                )
                superseded.append(f"/{concept.path.relative_to(self.knowledge_root).as_posix()}")
            path = self.repo.unique_path(
                self.knowledge_root / "concepts" / domain / topic_slug,
                f"{topic_slug}-refresh",
            )
            self.repo.write_doc(
                path,
                MarkdownDoc(
                    frontmatter={
                        "type": "Knowledge Concept",
                        "title": f"{topic_slug} refresh",
                        "domain": domain,
                        "topic": topic_slug,
                        "tags": tags,
                        "source_refs": source_refs,
                        "status": "active",
                        "last_verified": datetime.now().date().isoformat(),
                    },
                    body=f"# {topic_slug} refresh\n\n{final_summary}\n",
                ),
            )
        return {
            "status": "refreshed",
            "topic": f"{domain}/{topic_slug}",
            "path": str(path),
            "source_refs": source_refs,
            "superseded": superseded,
        }


def _summary_from_body(body: str) -> str:
    match = re.search(r"^#+\s*摘要\s*\n(?P<summary>.*?)(?:\n#+\s|\Z)", body or "", flags=re.S | re.M)
    if match:
        return match.group("summary").strip()
    lines = [line.strip() for line in (body or "").splitlines() if line.strip() and not line.startswith("#")]
    return "\n".join(lines[:3])


def _composite_summary(sources: list[MarkdownDoc], max_sources: int = 8) -> str:
    lines = ["## 来源汇总", ""]
    for doc in sources[:max_sources]:
        title = doc.frontmatter.get("title") or (doc.path.stem if doc.path else "source")
        confidence = float(doc.frontmatter.get("confidence") or 0.5)
        summary = _summary_from_body(doc.body).splitlines()[0] if _summary_from_body(doc.body) else ""
        lines.append(f"- **{title}** (conf {confidence:.2f}): {summary}")
    if len(sources) > max_sources:
        lines.append(f"\n_另有 {len(sources) - max_sources} 条来源未列出。_")
    return "\n".join(lines)
