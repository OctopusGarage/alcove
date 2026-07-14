from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.prompt_quality import has_professional_contract, prompt_record_quality_score
from alcove.prompt_text import prompt_content_hash, prompt_title_key
from alcove.prompts import PROMPT_DEFAULT_KIND, Prompt, PromptsModule
from alcove.workspace import Workspace


@dataclass(frozen=True)
class PromptAuditIssue:
    severity: str
    kind: str
    prompt_id: str
    title: str
    path: str
    message: str
    remediation: str


class PromptAuditModule:
    """Read-only quality audit for the reusable prompt library."""

    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.prompts = PromptsModule(workspace=workspace, home=home)

    def audit(self, *, status: str = "active") -> dict[str, Any]:
        prompts = self.prompts.list(status=status)
        issues: list[PromptAuditIssue] = []
        for prompt in prompts:
            issues.extend(self._prompt_issues(prompt))
        issues.extend(self._duplicate_issues(prompts))
        issue_dicts = [issue_dict(issue) for issue in issues]
        return {
            "status": _status(issue_dicts),
            "counts": self._counts(prompts, issue_dicts),
            "issues": issue_dicts,
            "recommendations": _recommendations(issue_dicts),
        }

    def _prompt_issues(self, prompt: Prompt) -> list[PromptAuditIssue]:
        issues: list[PromptAuditIssue] = []
        quality_score = _quality_score(prompt)
        if len(prompt.content.strip()) < 80:
            issues.append(
                self._issue(
                    "warning",
                    "short_content",
                    prompt,
                    "Prompt content is too short to be safely reusable.",
                    "Expand the prompt with objective, constraints, expected output, and verification notes.",
                )
            )
        if not prompt.description.strip():
            issues.append(
                self._issue(
                    "warning",
                    "missing_description",
                    prompt,
                    "Prompt is missing a concise description.",
                    "Add one sentence describing when to use this prompt.",
                )
            )
        if not prompt.use_cases:
            issues.append(
                self._issue(
                    "warning",
                    "missing_use_cases",
                    prompt,
                    "Prompt has no use cases, making recommendation less reliable.",
                    "Add 1-3 concrete use cases.",
                )
            )
        if prompt.kind == PROMPT_DEFAULT_KIND and not prompt.domain:
            issues.append(
                self._issue(
                    "warning",
                    "missing_domain",
                    prompt,
                    "Full prompt has no domain, making category browsing weak.",
                    "Set a stable domain such as ai-coding, review, prompt-engineering, or knowledge-management.",
                )
            )
        if prompt.kind in {"full_prompt", "playbook", "eval_prompt"} and not prompt.outputs:
            issues.append(
                self._issue(
                    "warning",
                    "missing_outputs",
                    prompt,
                    "Prompt does not state expected outputs.",
                    "Add outputs such as findings, implementation plan, revised prompt, or verification report.",
                )
            )
        if prompt.kind == "style_profile":
            issues.append(
                self._issue(
                    "warning",
                    "non_prompt_style_profile",
                    prompt,
                    "Style profiles and terse-command mappings are behavior rules, not active reusable prompts.",
                    "Archive this record or move it to agent rules unless it is rewritten as a copyable task prompt with a concrete output.",
                )
            )
        if not prompt.surfaces:
            issues.append(
                self._issue(
                    "info",
                    "surface_neutral",
                    prompt,
                    "Prompt has no explicit surfaces; it will be treated as generic.",
                    "Add surfaces only when the prompt is specific to Codex, Claude Code, or another interface.",
                )
            )
        if not has_professional_contract(prompt):
            issues.append(
                self._issue(
                    "warning",
                    "weak_prompt_contract",
                    prompt,
                    "Prompt body is not actionable enough for reliable reuse.",
                    "Rewrite it as a concise prompt with a clear scenario, behavior, output, and boundary; avoid raw history and boilerplate templates.",
                )
            )
        if quality_score < 0.45:
            issues.append(
                self._issue(
                    "warning",
                    "low_quality_score",
                    prompt,
                    f"Prompt quality score is {quality_score:.2f}.",
                    "Add description, use cases, triggers, outputs, domain, and reusable structure.",
                )
            )
        for ref in prompt.source_refs:
            if _is_unportable_ref(ref):
                issues.append(
                    self._issue(
                        "error",
                        "unportable_source_ref",
                        prompt,
                        "Source reference contains an absolute home path.",
                        "Rewrite the source reference with `~` or a stable relative reference.",
                    )
                )
            elif _is_personal_local_ref(ref):
                issues.append(
                    self._issue(
                        "warning",
                        "personal_source_ref",
                        prompt,
                        "Source reference points at a personal local project path.",
                        "Replace it with a stable source label such as `source:prompt-guidelines` or `source:historical-ai-input-archive`.",
                    )
                )
        return issues

    def _duplicate_issues(self, prompts: list[Prompt]) -> list[PromptAuditIssue]:
        issues: list[PromptAuditIssue] = []
        by_content: dict[str, list[Prompt]] = defaultdict(list)
        by_title: dict[str, list[Prompt]] = defaultdict(list)
        for prompt in prompts:
            content_key = _content_fingerprint(prompt.content)
            if content_key:
                by_content[content_key].append(prompt)
            by_title[_title_key(prompt.title)].append(prompt)
        for group in by_content.values():
            if len(group) < 2:
                continue
            ids = ", ".join(prompt.id for prompt in group)
            for prompt in group:
                issues.append(
                    self._issue(
                        "warning",
                        "duplicate_content",
                        prompt,
                        f"Prompt content duplicates another active prompt: {ids}.",
                        "Keep the best reusable record and archive or merge duplicates.",
                    )
                )
        for group in by_title.values():
            if len(group) < 2:
                continue
            ids = ", ".join(prompt.id for prompt in group)
            for prompt in group:
                issues.append(
                    self._issue(
                        "info",
                        "similar_title",
                        prompt,
                        f"Prompt title is very similar to another prompt: {ids}.",
                        "Rename titles to make retrieval intent distinct, or merge overlapping records.",
                    )
                )
        return issues

    def _counts(
        self,
        prompts: list[Prompt],
        issues: list[dict[str, Any]],
    ) -> dict[str, Any]:
        by_kind = Counter(prompt.kind for prompt in prompts)
        by_domain = Counter(prompt.domain or "uncategorized" for prompt in prompts)
        by_issue = Counter(issue["kind"] for issue in issues)
        by_severity = Counter(issue["severity"] for issue in issues)
        scores = [_quality_score(prompt) for prompt in prompts]
        return {
            "prompts": len(prompts),
            "by_kind": dict(sorted(by_kind.items())),
            "by_domain": dict(sorted(by_domain.items())),
            "issues": len(issues),
            "by_issue": dict(sorted(by_issue.items())),
            "by_severity": dict(sorted(by_severity.items())),
            "average_quality_score": round(sum(scores) / len(scores), 3) if scores else 0.0,
            "ready_prompts": sum(1 for score in scores if score >= 0.75),
            "needs_metadata": sum(
                1
                for prompt in prompts
                if not prompt.description
                or not prompt.use_cases
                or not prompt.outputs
                or (prompt.kind == PROMPT_DEFAULT_KIND and not prompt.domain)
            ),
        }

    def _issue(
        self,
        severity: str,
        kind: str,
        prompt: Prompt,
        message: str,
        remediation: str,
    ) -> PromptAuditIssue:
        return PromptAuditIssue(
            severity=severity,
            kind=kind,
            prompt_id=prompt.id,
            title=prompt.title,
            path=compact_user_path(prompt.path),
            message=message,
            remediation=remediation,
        )


def issue_dict(issue: PromptAuditIssue) -> dict[str, Any]:
    return {
        "severity": issue.severity,
        "kind": issue.kind,
        "prompt_id": issue.prompt_id,
        "title": issue.title,
        "path": issue.path,
        "message": issue.message,
        "remediation": issue.remediation,
    }


def _status(issues: list[dict[str, Any]]) -> str:
    if any(issue["severity"] == "error" for issue in issues):
        return "issues"
    if any(issue["severity"] == "warning" for issue in issues):
        return "warnings"
    return "ok"


def _recommendations(issues: list[dict[str, Any]]) -> list[str]:
    kinds = {issue["kind"] for issue in issues}
    recommendations: list[str] = []
    if {"missing_use_cases", "missing_outputs", "missing_domain"} & kinds:
        recommendations.append(
            "Backfill metadata for high-value prompts before importing more history."
        )
    if "duplicate_content" in kinds:
        recommendations.append("Merge duplicate prompts so recommendation results stay precise.")
    if "unportable_source_ref" in kinds:
        recommendations.append(
            "Replace absolute source refs with `~` or stable relative references."
        )
    if "personal_source_ref" in kinds:
        recommendations.append(
            "Replace detailed local source refs with stable source labels before treating prompts as polished."
        )
    if "low_quality_score" in kinds:
        recommendations.append(
            "Archive or expand low-quality prompt fragments that are not reusable."
        )
    if "weak_prompt_contract" in kinds:
        recommendations.append(
            "Rewrite weak prompts into concise, actionable prompts before treating them as ready."
        )
    if "non_prompt_style_profile" in kinds:
        recommendations.append(
            "Archive behavior profiles or move them to agent rules instead of keeping them as active prompts."
        )
    return recommendations


def _quality_score(prompt: Prompt) -> float:
    return prompt_record_quality_score(prompt, default_kind=PROMPT_DEFAULT_KIND)


def _content_fingerprint(content: str) -> str:
    return prompt_content_hash(content)


def _title_key(title: str) -> str:
    return prompt_title_key(title)


def _is_unportable_ref(value: str) -> bool:
    text = str(value or "").strip()
    if not text or text.startswith("~"):
        return False
    return text.startswith(str(Path.home()))


def _is_personal_local_ref(value: str) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    return text.startswith("~/programming/") or text.startswith("~/.")
