from __future__ import annotations

from typing import Any

from alcove.capability_payloads import CapabilityPayloadPresenter
from alcove.runtime import AlcoveRuntime
from alcove.usage import UsageRecorder


class _Capability:
    def __init__(self, runtime: AlcoveRuntime) -> None:
        self.runtime = runtime
        self.payloads = CapabilityPayloadPresenter(runtime)

    def _record_action(
        self,
        *,
        area: str,
        action: str,
        summary: str,
        metrics: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        visible: bool = True,
    ) -> None:
        if self.runtime.home is None:
            return
        UsageRecorder(self.runtime.home).record_action(
            surface="application",
            area=area,
            action=action,
            summary=summary,
            metrics=metrics,
            metadata=metadata,
            visible=visible,
        )
