from __future__ import annotations

from alcove.application_capabilities import (
    _ExternalCapabilities,
    _GlobalHomeCapabilities,
    _InboxCapabilities,
    _ManagedKnowledgeCapabilities,
    _SearchCapabilities,
    _SystemCapabilities,
)
from alcove.runtime import AlcoveRuntime


class AlcoveApplication:
    """Stable behavior facade shared by CLI, MCP, and future adapters."""

    def __init__(self, runtime: AlcoveRuntime) -> None:
        self.runtime = runtime
        self.search = _SearchCapabilities(runtime)
        self.system = _SystemCapabilities(runtime)
        self.inbox = _InboxCapabilities(runtime)
        self.knowledge = _ManagedKnowledgeCapabilities(runtime)
        self.global_home = _GlobalHomeCapabilities(runtime)
        self.external = _ExternalCapabilities(runtime)
