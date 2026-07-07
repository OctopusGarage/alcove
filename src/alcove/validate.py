from __future__ import annotations

from dataclasses import dataclass

from alcove.markdown import MarkdownRepository
from alcove.workspace import Workspace


@dataclass(frozen=True)
class ValidationIssue:
    kind: str
    path: str
    message: str


class ValidateModule:
    def __init__(self, workspace: Workspace, repo: MarkdownRepository | None = None) -> None:
        self.workspace = workspace
        self.paths = workspace.paths()
        self.repo = repo or MarkdownRepository()

    def validate(self, strict_quality: bool = False) -> list[dict]:
        issues: list[ValidationIssue] = []
        for name in ("knowledge", "inbox", "archive", "todo"):
            path = getattr(self.paths, name)
            if not path.exists():
                issues.append(ValidationIssue("missing_path", str(path), f"Missing {name} path"))
        for doc in self.repo.list_docs(self.paths.knowledge):
            if doc.path is None:
                continue
            doc_type = doc.frontmatter.get("type")
            if not doc_type:
                issues.append(ValidationIssue("missing_type", str(doc.path), "Markdown doc lacks frontmatter type"))
            if strict_quality and doc_type in {"Source", "Knowledge Concept"} and "status" not in doc.frontmatter:
                issues.append(ValidationIssue("missing_status", str(doc.path), "OKF doc lacks status"))
            if doc_type == "Knowledge Concept":
                for ref in doc.frontmatter.get("source_refs") or []:
                    ref_path = self.paths.knowledge / str(ref).lstrip("/")
                    if not ref_path.exists():
                        issues.append(ValidationIssue("dead_source_ref", str(doc.path), f"Missing source ref {ref}"))
        return [issue.__dict__ for issue in issues]
