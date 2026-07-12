from __future__ import annotations

from typing import Protocol

from alcove.radars.models import RadarDefinition, RadarItem, RadarSource


class SourceAdapter(Protocol):
    adapter_id: str

    def fetch(self, definition: RadarDefinition, source: RadarSource) -> list[RadarItem]:
        """Fetch and normalize source rows into radar items."""
