from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml

from alcove.health_types import HealthIssue
from alcove.markdown import MarkdownDoc
from alcove.okf import okf_schema_for
from alcove.paths import compact_user_path


class HealthValidationMixin:
    """Reusable file and OKF validation helpers for health checks."""

    def _check_yaml_tree(
        self,
        root: Path,
        module: str,
        issues: list[HealthIssue],
    ) -> int:
        if not root.exists():
            return 0
        count = 0
        for path in sorted(
            [*root.glob("*.yml"), *root.glob("*.yaml")], key=lambda item: item.as_posix()
        ):
            count += 1
            try:
                yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError) as exc:
                self._issue(
                    issues,
                    "error",
                    module,
                    "invalid_yaml",
                    path,
                    f"Could not parse YAML: {exc}",
                    "Repair or recreate the module configuration.",
                )
        return count

    def _check_json_tree(
        self,
        root: Path,
        module: str,
        issues: list[HealthIssue],
    ) -> int:
        if not root.exists():
            return 0
        count = 0
        for path in sorted(root.glob("*.json"), key=lambda item: item.as_posix()):
            count += 1
            self._read_json(path, issues, module)
        return count

    def _check_json_tree_recursive(
        self,
        root: Path,
        module: str,
        issues: list[HealthIssue],
    ) -> int:
        if not root.exists():
            return 0
        count = 0
        for path in sorted(root.rglob("*.json"), key=lambda item: item.as_posix()):
            count += 1
            self._read_json(path, issues, module)
        return count

    def _check_markdown_okf(
        self,
        root: Path,
        *,
        module: str,
        issues: list[HealthIssue],
        counts: dict[str, int],
        allowed_loose_types: set[str] | None = None,
    ) -> None:
        checked = 0
        for path in sorted(root.rglob("*.md"), key=lambda item: item.as_posix()):
            if path.name in {"index.md", "log.md"}:
                continue
            doc = self._read_doc(path, module, issues)
            if doc is None:
                continue
            checked += 1
            doc_type = str(doc.frontmatter.get("type") or "")
            if not doc_type:
                self._issue(
                    issues,
                    "error",
                    module,
                    "missing_okf_type",
                    path,
                    "Markdown OKF document is missing frontmatter type.",
                    "Repair frontmatter or regenerate the derived OKF file.",
                )
            if allowed_loose_types is not None and doc_type not in allowed_loose_types:
                self._check_governed_schema(doc, module, issues)
        counts[f"{module}_okf_docs"] = checked

    def _check_derived_okf_count(
        self,
        root: Path,
        module: str,
        expected_count: int,
        issues: list[HealthIssue],
        remediation: str,
    ) -> None:
        index_path = root / "index.md"
        self._check_markdown_doc(index_path, module, issues)
        item_dir = root / "items"
        item_count = len(list(item_dir.glob("*.md"))) if item_dir.exists() else 0
        if item_count != expected_count:
            self._issue(
                issues,
                "warning",
                module,
                "derived_okf_count_mismatch",
                item_dir,
                f"Derived OKF item count {item_count} does not match JSON index count {expected_count}.",
                remediation,
            )
        self._check_markdown_okf(
            root,
            module=module,
            issues=issues,
            counts={},
            allowed_loose_types=set(),
        )

    def _typed_docs(
        self,
        root: Path,
        type_name: str,
        issues: list[HealthIssue],
        module: str,
    ) -> list[MarkdownDoc]:
        docs: list[MarkdownDoc] = []
        if not root.exists():
            return docs
        for path in sorted(root.glob("*.md"), key=lambda item: item.as_posix()):
            if path.name in {"index.md", "log.md"}:
                continue
            doc = self._read_doc(path, module, issues)
            if doc is None:
                continue
            if doc.frontmatter.get("type") == type_name:
                docs.append(doc)
            elif path.name != "board.html":
                self._issue(
                    issues,
                    "error",
                    module,
                    "unexpected_okf_type",
                    path,
                    f"Expected {type_name} document.",
                    "Repair frontmatter or move the file out of this module.",
                )
        return docs

    def _require_fields(
        self,
        doc: MarkdownDoc,
        fields: tuple[str, ...],
        module: str,
        issues: list[HealthIssue],
    ) -> None:
        path = doc.path or Path(".")
        missing = [field for field in fields if field not in doc.frontmatter]
        if missing:
            self._issue(
                issues,
                "error",
                module,
                "missing_required_fields",
                path,
                f"OKF document is missing required fields: {', '.join(missing)}",
                "Rewrite or update the record through Alcove CLI/MCP.",
            )

    def _require_schema(
        self,
        doc: MarkdownDoc,
        expected: str,
        module: str,
        issues: list[HealthIssue],
    ) -> None:
        path = doc.path or Path(".")
        actual = str(doc.frontmatter.get("schema") or "")
        if actual == expected:
            return
        self._issue(
            issues,
            "error",
            module,
            "invalid_okf_schema",
            path,
            f"Expected schema {expected}, found {actual or '<missing>'}.",
            "Rewrite or update the record through Alcove CLI/MCP.",
        )

    def _check_governed_schema(
        self,
        doc: MarkdownDoc,
        module: str,
        issues: list[HealthIssue],
    ) -> None:
        path = doc.path or Path(".")
        doc_type = str(doc.frontmatter.get("type") or "")
        actual = str(doc.frontmatter.get("schema") or "")
        expected = okf_schema_for(doc_type)
        if expected and actual and actual != expected:
            self._issue(
                issues,
                "warning",
                module,
                "invalid_okf_schema",
                path,
                f"Expected schema {expected}, found {actual}.",
                "Rewrite through Alcove CLI/MCP or update the module schema.",
            )
        elif not actual:
            self._issue(
                issues,
                "warning",
                module,
                "missing_okf_schema",
                path,
                "Alcove-governed OKF document is missing schema.",
                "Rewrite through Alcove CLI/MCP or add the module schema.",
            )

    def _check_json_index_count(
        self,
        path: Path,
        module: str,
        item_key: str,
        expected_count: int,
        issues: list[HealthIssue],
        counts: dict[str, int],
        remediation: str,
    ) -> None:
        payload = self._read_json(path, issues, module)
        items = self._dict_list(payload, item_key)
        counts[f"{module}_index_items"] = len(items)
        if not path.exists():
            self._issue(
                issues,
                "warning",
                module,
                "missing_index",
                path,
                "Module JSON index is missing.",
                remediation,
            )
        elif len(items) != expected_count:
            self._issue(
                issues,
                "warning",
                module,
                "index_count_mismatch",
                path,
                f"JSON index count {len(items)} does not match source count {expected_count}.",
                remediation,
            )

    def _check_json_store(
        self,
        path: Path,
        module: str,
        issues: list[HealthIssue],
        counts: dict[str, int],
    ) -> None:
        payload = self._read_json(path, issues, module)
        if not path.exists():
            counts[module] = 0
            return
        if not isinstance(payload, dict):
            self._issue(
                issues,
                "error",
                module,
                "invalid_json_store",
                path,
                "JSON store is not an object.",
                "Repair or restore the JSON store.",
            )
            return
        if module == "tasks":
            counts["tasks"] = len(self._dict_list(payload, "tasks"))
            counts["ideas"] = len(self._dict_list(payload, "ideas"))
            counts["routines"] = len(self._dict_list(payload, "routines"))
        elif module == "projects":
            projects = self._dict_dict(payload, "projects")
            counts["projects"] = len(projects)

    def _check_markdown_doc(
        self,
        path: Path,
        module: str,
        issues: list[HealthIssue],
        *,
        required_type: str = "",
    ) -> None:
        if not path.is_file():
            self._issue(
                issues,
                "warning",
                module,
                "missing_okf_file",
                path,
                "Derived OKF file is missing.",
                "Refresh or rebuild the affected module.",
            )
            return
        doc = self._read_doc(path, module, issues)
        if doc is None:
            return
        doc_type = str(doc.frontmatter.get("type") or "")
        if not doc_type:
            self._issue(
                issues,
                "error",
                module,
                "missing_okf_type",
                path,
                "Markdown OKF file is missing frontmatter type.",
                "Regenerate the derived OKF file.",
            )
        if required_type and doc_type != required_type:
            self._issue(
                issues,
                "error",
                module,
                "unexpected_okf_type",
                path,
                f"Expected OKF type {required_type}, found {doc_type or '<missing>'}.",
                "Regenerate the module index.",
            )
        self._check_governed_schema(doc, module, issues)

    def _read_doc(
        self: Any,
        path: Path,
        module: str,
        issues: list[HealthIssue],
    ) -> MarkdownDoc | None:
        try:
            return cast(MarkdownDoc, self.repo.read_doc(path))
        except OSError as exc:
            self._issue(
                issues,
                "error",
                module,
                "unreadable_markdown",
                path,
                f"Could not read Markdown file: {exc}",
                "Repair filesystem permissions or restore the file.",
            )
            return None

    def _read_json(
        self,
        path: Path,
        issues: list[HealthIssue],
        module: str,
    ) -> dict[str, Any]:
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            self._issue(
                issues,
                "error",
                module,
                "invalid_json",
                path,
                f"Could not parse JSON: {exc}",
                "Repair or regenerate the JSON file.",
            )
            return {}
        return data if isinstance(data, dict) else {}

    def _json_list(
        self,
        path: Path,
        key: str,
        issues: list[HealthIssue],
        module: str,
    ) -> list[dict[str, Any]]:
        data = self._read_json(path, issues, module)
        rows = self._dict_list(data, key)
        return [row for row in rows if isinstance(row, dict)]

    def _items(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        rows = self._dict_list(payload, "items")
        return [row for row in rows if isinstance(row, dict)]

    def _dict_list(self, data: dict[str, Any], key: str) -> list[Any]:
        value = data.get(key)
        return value if isinstance(value, list) else []

    def _dict_dict(self, data: dict[str, Any], key: str) -> dict[str, Any]:
        value = data.get(key)
        return value if isinstance(value, dict) else {}

    def _issue(
        self,
        issues: list[HealthIssue],
        severity: str,
        module: str,
        kind: str,
        path: Path | str,
        message: str,
        remediation: str = "",
    ) -> None:
        issues.append(
            HealthIssue(
                severity=severity,
                module=module,
                kind=kind,
                path=compact_user_path(path),
                message=message,
                remediation=remediation,
            )
        )

    def _status(self, issues: list[HealthIssue]) -> str:
        if any(issue.severity == "error" for issue in issues):
            return "issues"
        if issues:
            return "warnings"
        return "ok"

    def _dedupe_issues(self, issues: list[HealthIssue]) -> list[HealthIssue]:
        seen: set[tuple[str, str, str, str, str]] = set()
        unique: list[HealthIssue] = []
        for issue in issues:
            key = (
                issue.severity,
                issue.module,
                issue.kind,
                issue.path,
                issue.message,
            )
            if key in seen:
                continue
            seen.add(key)
            unique.append(issue)
        return unique
