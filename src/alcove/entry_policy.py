from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class EntryModePolicy:
    mode: str
    default_toolset: str
    read_scope: str
    write_scope: str
    description: str

    def as_dict(self) -> dict[str, str]:
        return {
            "mode": self.mode,
            "default_toolset": self.default_toolset,
            "read_scope": self.read_scope,
            "write_scope": self.write_scope,
            "description": self.description,
        }


ENTRY_MODE_POLICIES: Final[dict[str, EntryModePolicy]] = {
    "hub": EntryModePolicy(
        mode="hub",
        default_toolset="full",
        read_scope="home-wide",
        write_scope="governed CLI/MCP by routed intent",
        description="Main AI workspace for broad personal knowledge work.",
    ),
    "global": EntryModePolicy(
        mode="global",
        default_toolset="lite",
        read_scope="home-wide",
        write_scope="lightweight governed memory writes only",
        description="Small MCP surface for unrelated projects.",
    ),
    "managed-kb": EntryModePolicy(
        mode="managed-kb",
        default_toolset="kb",
        read_scope="current managed KB plus home-wide search when requested",
        write_scope="managed-KB inbox and OKF writes with explicit confirmation",
        description="Focused capture, inbox, and OKF workflow for one knowledge base.",
    ),
    "service": EntryModePolicy(
        mode="service",
        default_toolset="none",
        read_scope="configured home",
        write_scope="deterministic scheduled maintenance only",
        description="Launchd-backed dashboard and scheduler runtime.",
    ),
}

ENTRY_MODE_ALIASES: Final[dict[str, str]] = {
    "": "hub",
    "full": "hub",
    "hub-full": "hub",
    "global-lite": "global",
    "lite": "global",
    "light": "global",
    "kb": "managed-kb",
    "knowledge-base": "managed-kb",
    "managed": "managed-kb",
    "managed-kb": "managed-kb",
    "scheduler": "service",
    "service": "service",
}


def entry_mode_policy(mode: str | None) -> EntryModePolicy:
    canonical = ENTRY_MODE_ALIASES.get((mode or "").strip().lower(), (mode or "").strip().lower())
    try:
        return ENTRY_MODE_POLICIES[canonical]
    except KeyError as exc:
        choices = ", ".join(sorted(ENTRY_MODE_POLICIES))
        raise ValueError(f"Unknown Alcove entry mode: {mode}. Expected one of: {choices}") from exc


def default_toolset_for_entry(mode: str | None) -> str:
    return entry_mode_policy(mode).default_toolset
