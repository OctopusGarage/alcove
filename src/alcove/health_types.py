from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HealthIssue:
    severity: str
    module: str
    kind: str
    path: str
    message: str
    remediation: str = ""
