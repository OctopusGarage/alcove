from __future__ import annotations

from typing import Any

from alcove.capability_payloads import CapabilityPayloadPresenter
from alcove.runtime import AlcoveRuntime
from alcove.usage import UsageRecorder
from alcove.write_contracts import write_contract


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
