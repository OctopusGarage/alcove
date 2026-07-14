from __future__ import annotations

from typing import Any

from alcove.home import AlcoveHome
from alcove.prompt_audit import PromptAuditModule


class PromptHealthAdapter:
    """Translate prompt audit output into generic health rows."""

    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def report(self) -> dict[str, Any]:
        audit = PromptAuditModule(home=self.home).audit()
        counts = audit.get("counts") if isinstance(audit, dict) else {}
        issues: list[dict[str, str]] = []
        for item in audit.get("issues", []):
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity") or "warning")
            if severity == "info":
                continue
            issues.append(
                {
                    "severity": "error" if severity == "error" else "warning",
                    "module": "prompts",
                    "kind": f"prompt_{item.get('kind') or 'quality_issue'}",
                    "path": str(item.get("path") or ""),
                    "message": str(item.get("message") or ""),
                    "remediation": str(item.get("remediation") or "Run `alcove prompt audit`."),
                }
            )
        return {
            "counts": {
                "prompt_ready_prompts": int(counts.get("ready_prompts") or 0)
                if isinstance(counts, dict)
                else 0,
                "prompt_quality_issues": int(counts.get("issues") or 0)
                if isinstance(counts, dict)
                else 0,
                "prompt_needs_metadata": int(counts.get("needs_metadata") or 0)
                if isinstance(counts, dict)
                else 0,
            },
            "issues": issues,
        }
