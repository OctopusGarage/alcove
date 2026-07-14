from __future__ import annotations

from time import perf_counter
from typing import Any

from alcove.application_base import _Capability
from alcove.application_system import _SystemCapabilities
from alcove.search import SearchModule, SearchRequest
from alcove.usage import UsageRecorder


class _SearchCapabilities(_Capability):
    def search(
        self, request: SearchRequest, *, surface: str = "application"
    ) -> list[dict[str, Any]]:
        started = perf_counter()
        results = SearchModule(self.runtime.workspace, home=self.runtime.home).search(request)
        self._record_search_usage(
            request,
            surface=surface,
            result_count=len(results),
            duration_ms=int((perf_counter() - started) * 1000),
        )
        return results

    def search_payload(
        self,
        request: SearchRequest,
        *,
        surface: str = "application",
    ) -> dict[str, Any]:
        results = self.search(request, surface=surface)
        return self.runtime.scope_payload({"count": len(results), "results": results})

    def search_tags_payload(self) -> dict[str, Any]:
        rows = SearchModule(self.runtime.workspace, home=self.runtime.home).tags()
        return self.runtime.scope_payload({"count": len(rows), "tags": rows})

    def search_tag_doctor_payload(self) -> dict[str, Any]:
        rows = SearchModule(self.runtime.workspace, home=self.runtime.home).tag_doctor()
        return self.runtime.scope_payload({"count": len(rows), "issues": rows})

    def search_recent_payload(self, limit: int = 20) -> dict[str, Any]:
        rows = SearchModule(self.runtime.workspace, home=self.runtime.home).recent(limit)
        return self.runtime.scope_payload({"count": len(rows), "results": rows})

    def search_unindexed_payload(self) -> dict[str, Any]:
        return _SystemCapabilities(self.runtime).validate_payload(strict_quality=False)

    def _record_search_usage(
        self,
        request: SearchRequest,
        *,
        surface: str,
        result_count: int,
        duration_ms: int,
    ) -> None:
        if self.runtime.home is None:
            return
        UsageRecorder(self.runtime.home).record_search(
            surface=surface,
            query=request.query,
            result_count=result_count,
            duration_ms=duration_ms,
            filters={
                "type": request.type_filter,
                "tag": request.tag,
                "topic": request.topic,
                "platform": request.platform,
                "date_from": request.date_from,
                "date_to": request.date_to,
                "min_confidence": request.min_confidence,
                "status": request.status,
            },
        )
