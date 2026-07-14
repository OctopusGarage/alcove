from __future__ import annotations

from typing import Any

from alcove.capability_payloads import CapabilityPayloadPresenter
from alcove.publisher_dirty import mark_publisher_source_dirty
from alcove.runtime import AlcoveRuntime
from alcove.usage import UsageRecorder
from alcove.write_contracts import write_contract


_PUBLISHER_SOURCES_BY_WRITE_AREA = {
    "pin": "pins",
    "prompt": "prompts",
    "project": "projects",
    "task": "tasks",
}


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

    def _governed_write(
        self,
        payload: dict[str, Any],
        *,
        area: str,
        action: str,
        target: str = "",
        source_of_truth: str = "",
        confirmation_required: bool = False,
        post_write_checks: tuple[str, ...] | None = None,
    ) -> dict[str, Any]:
        if "write_contract" in payload:
            return payload
        self._mark_publisher_dirty(area=area, confirmation_required=confirmation_required)
        return {
            **payload,
            "write_contract": write_contract(
                area=area,
                action=action,
                target=target,
                source_of_truth=source_of_truth,
                confirmation_required=confirmation_required,
                post_write_checks=post_write_checks,
            ),
        }

    def _mark_publisher_dirty(self, *, area: str, confirmation_required: bool) -> None:
        if confirmation_required or self.runtime.home is None:
            return
        source = _PUBLISHER_SOURCES_BY_WRITE_AREA.get(area)
        if source is None:
            return
        try:
            mark_publisher_source_dirty(self.runtime.home, source)
        except OSError:
            return
