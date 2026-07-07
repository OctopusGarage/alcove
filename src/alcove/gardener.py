from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime

from alcove.markdown import MarkdownDoc, MarkdownRepository, normalize_slug
from alcove.validate import ValidateModule
from alcove.workspace import Workspace


@dataclass(frozen=True)
class GardenerReport:
    issues: list[dict]
    actions: list[dict]


class GardenerModule:
    def __init__(self, workspace: Workspace, repo: MarkdownRepository | None = None) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.repo = repo or MarkdownRepository()

    def scan(self) -> list[dict]:
        issues = ValidateModule(self.workspace, self.repo).validate(strict_quality=True)
        docs = self.repo.list_docs(self.paths.knowledge)
        tag_counts: Counter[str] = Counter()
        source_counts: Counter[str] = Counter()
        question_counts: Counter[str] = Counter()
        entity_counts: Counter[str] = Counter()
        for doc in docs:
            doc_type = doc.frontmatter.get("type")
            topic = doc.frontmatter.get("topic")
            if doc_type not in {"Tag", "Topic", "Domain"}:
                for tag in doc.frontmatter.get("tags") or []:
                    tag_counts[str(tag)] += 1
            if doc_type == "Source" and doc.frontmatter.get("status", "active") == "active" and topic:
                source_counts[str(topic)] += 1
            if doc_type == "Question" and doc.frontmatter.get("status", "active") == "active" and topic:
                question_counts[str(topic)] += 1
            if doc_type == "Entity" and doc.frontmatter.get("status", "active") == "active" and topic:
                entity_counts[str(topic)] += 1
            if doc_type == "Source":
                stale = self._stale_source(doc)
                if stale:
                    issues.append(stale)
        for doc in docs:
            if doc.frontmatter.get("type") == "Tag" and doc.path is not None:
                tag = doc.frontmatter.get("tag") or doc.path.stem
                count = tag_counts.get(str(tag), 0)
                if count == 0:
                    issues.append({"kind": "empty_tag", "path": str(doc.path), "message": f"Tag {tag!r} has no references"})
                elif count < 2:
                    issues.append({"kind": "orphan_tag", "path": str(doc.path), "message": f"Tag {tag!r} is used only {count} time(s)"})
        for topic, count in sorted(source_counts.items()):
            if count >= 3 and question_counts.get(topic, 0) == 0:
                issues.append({"kind": "question_backlog", "path": str(self.paths.knowledge / "topics"), "message": f"Topic {topic!r} has {count} active sources but no Question docs"})
            if count >= 3 and entity_counts.get(topic, 0) == 0:
                issues.append({"kind": "entity_backlog", "path": str(self.paths.knowledge / "topics"), "message": f"Topic {topic!r} has {count} active sources but no Entity docs"})
        return issues

    def gardener(self, prune: bool = False) -> GardenerReport:
        issues = self.scan()
        actions: list[dict] = []
        if prune:
            for issue in issues:
                if issue["kind"] == "empty_tag":
                    path = self.paths.knowledge / "tags" / f"{normalize_slug(issue['message'].split()[1].strip(repr('')))}.md"
                    issue_path = issue.get("path")
                    if issue_path:
                        path = type(self.paths.knowledge)(issue_path)
                    if path.exists():
                        path.unlink()
                        actions.append({"action": "deleted_empty_tag", "path": str(path)})
                elif issue["kind"] == "missing_status":
                    path = type(self.paths.knowledge)(issue["path"])
                    if path.exists():
                        doc = self.repo.read_doc(path)
                        self.repo.write_doc(path, MarkdownDoc(frontmatter={**doc.frontmatter, "status": "active"}, body=doc.body))
                        actions.append({"action": "added_status", "path": str(path)})
                elif issue["kind"] == "stale_source":
                    path = type(self.paths.knowledge)(issue["path"])
                    if path.exists():
                        doc = self.repo.read_doc(path)
                        self.repo.write_doc(path, MarkdownDoc(frontmatter={**doc.frontmatter, "status": "stale"}, body=doc.body))
                        actions.append({"action": "marked_stale", "path": str(path)})
        return GardenerReport(issues=issues, actions=actions)

    def _stale_source(self, doc: MarkdownDoc) -> dict | None:
        if doc.path is None or doc.frontmatter.get("status", "active") != "active":
            return None
        published = str(doc.frontmatter.get("published_date") or doc.frontmatter.get("created_at") or "")[:10]
        confidence = float(doc.frontmatter.get("confidence") or 0.5)
        try:
            published_date = datetime.strptime(published, "%Y-%m-%d").date()
        except ValueError:
            return None
        if (date.today() - published_date).days > 365 and confidence < 0.5:
            return {"kind": "stale_source", "path": str(doc.path), "message": f"Published {published}, confidence {confidence}"}
        return None
