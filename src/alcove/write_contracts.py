from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WriteContract:
    area: str
    action: str
    target: str = ""
    governed_by: str = "alcove CLI/MCP"
    source_of_truth: str = ""
    confirmation_required: bool = False
    post_write_checks: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, object]:
        return {
            "area": self.area,
            "action": self.action,
            "target": self.target,
            "governed_by": self.governed_by,
            "source_of_truth": self.source_of_truth or self.area,
            "confirmation_required": self.confirmation_required,
            "post_write_checks": list(self.post_write_checks),
        }


DEFAULT_POST_WRITE_CHECKS: dict[str, tuple[str, ...]] = {
    "inbox": ("alcove validate --json",),
    "knowledge": ("alcove validate --json", "alcove okf catalog build --json"),
    "pin": ("alcove pin rebuild-index --json", "alcove okf catalog build --json"),
    "prompt": ("alcove prompt rebuild-index --json", "alcove okf catalog build --json"),
    "project": ("alcove okf catalog build --json",),
    "task": ("alcove health --json",),
    "mount": ("alcove mount scan <mount-id> --json", "alcove okf catalog build --json"),
    "connector": ("alcove connector refresh --connector <connector-id> --json",),
}


def write_contract(
    *,
    area: str,
    action: str,
    target: str = "",
    source_of_truth: str = "",
    confirmation_required: bool = False,
    post_write_checks: tuple[str, ...] | None = None,
) -> dict[str, object]:
    checks = DEFAULT_POST_WRITE_CHECKS.get(area, ())
    if post_write_checks is not None:
        checks = post_write_checks
    return WriteContract(
        area=area,
        action=action,
        target=target,
        source_of_truth=source_of_truth,
        confirmation_required=confirmation_required,
        post_write_checks=checks,
    ).as_dict()
