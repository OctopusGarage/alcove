from __future__ import annotations

from typing import Any, Protocol

from alcove.paths import compact_user_path


BLOG_ATTENTION_STATUS = "needs_attention"


class BlogRunHost(Protocol):
    def _load_sources(self) -> list[Any]: ...

    def _is_stale(self, source: Any, timestamp: str) -> bool: ...

    def _discover(self, source: Any) -> list[Any]: ...

    def _load_seen(self, source_id: str) -> set[str]: ...

    def _write_seen(self, source_id: str, urls: set[str], *, timestamp: str) -> None: ...

    def _replace_source(self, source: Any, **changes: str) -> Any: ...

    def _write_source(self, source: Any) -> None: ...

    def _capture_article(self, source: Any, article: Any) -> dict[str, Any]: ...

    def _skipped_capture(self) -> dict[str, str]: ...

    def _summarize(
        self,
        source: Any,
        articles: list[Any],
        captures: list[dict[str, Any]],
    ) -> str: ...

    def _notify(
        self,
        source: Any,
        articles: list[Any],
        captures: list[dict[str, Any]],
        summary: str,
    ) -> dict[str, Any]: ...

    def _notify_failure(self, source: Any, *, stage: str, error: str) -> dict[str, Any]: ...

    def _write_run(
        self,
        source: Any,
        *,
        articles: list[Any],
        captures: list[dict[str, Any]],
        summary: str,
        notify: dict[str, Any],
        timestamp: str,
        stage: str = "",
        error: str = "",
    ) -> Any: ...

    def _record_event(
        self,
        source: Any,
        article: Any,
        capture: dict[str, Any],
        *,
        timestamp: str,
    ) -> None: ...

    def _record_failure_event(
        self,
        source: Any,
        *,
        stage: str,
        error: str,
        timestamp: str,
    ) -> None: ...


class BlogRunModule:
    """Runs blog monitoring checks while keeping storage and adapters behind the host."""

    def __init__(self, host: BlogRunHost) -> None:
        self.host = host

    def check(
        self,
        *,
        source_id: str = "",
        stale_only: bool = False,
        seed_only: bool = False,
        capture_override: bool | None = None,
        summary_override: bool | None = None,
        notify_override: bool | None = None,
        timestamp: str,
    ) -> dict[str, Any]:
        rows = []
        new_count = 0
        captured_count = 0
        errors = 0
        for source in self.host._load_sources():
            if source.status not in {"active", BLOG_ATTENTION_STATUS}:
                continue
            if source_id and source.id != source_id:
                continue
            if stale_only and not self.host._is_stale(source, timestamp):
                rows.append({"id": source.id, "status": "skipped"})
                continue
            result = self._check_one(
                source,
                timestamp=timestamp,
                seed_only=seed_only,
                capture_override=capture_override,
                summary_override=summary_override,
                notify_override=notify_override,
            )
            rows.append(result)
            new_count += int(result.get("new_count") or 0)
            captured_count += int(result.get("captured_count") or 0)
            if result.get("status") in {"error", BLOG_ATTENTION_STATUS}:
                errors += 1
        return {
            "status": "checked",
            "checked": len(rows),
            "new": new_count,
            "captured": captured_count,
            "errors": errors,
            "sources": rows,
        }

    def _check_one(
        self,
        source: Any,
        *,
        timestamp: str,
        seed_only: bool,
        capture_override: bool | None,
        summary_override: bool | None,
        notify_override: bool | None,
    ) -> dict[str, Any]:
        try:
            articles = self.host._discover(source)
        except Exception as exc:  # pragma: no cover - exercised in integration use
            return self._handle_failure(
                source,
                stage="discovery",
                error=str(exc),
                timestamp=timestamp,
                notify_override=notify_override,
            )

        seen = self.host._load_seen(source.id)
        discovered_urls = {article.url for article in articles}
        new_articles = [article for article in articles if article.url not in seen]

        if seed_only:
            self.host._write_seen(source.id, seen | discovered_urls, timestamp=timestamp)
            updated = self.host._replace_source(
                source,
                status="active",
                checked_at=timestamp,
                updated_at=timestamp,
                last_error="",
            )
            self.host._write_source(updated)
            return {
                "id": source.id,
                "status": "seeded",
                "discovered_count": len(articles),
                "new_count": len(new_articles),
            }

        capture_enabled = source.capture.enabled if capture_override is None else capture_override
        summary_enabled = source.summary.enabled if summary_override is None else summary_override
        notify_enabled = source.notify.enabled if notify_override is None else notify_override

        captures = [
            self.host._capture_article(source, article)
            if capture_enabled
            else self.host._skipped_capture()
            for article in new_articles
        ]
        failed_capture = next(
            (
                capture
                for capture in captures
                if str(capture.get("status") or "") in {"failed", "pending"}
            ),
            None,
        )
        if failed_capture is not None:
            error = str(
                failed_capture.get("error") or failed_capture.get("reason") or "capture failed"
            )
            return self._handle_failure(
                source,
                stage="capture",
                error=error,
                timestamp=timestamp,
                notify_override=notify_override,
                articles=new_articles,
                captures=captures,
            )
        self.host._write_seen(source.id, seen | discovered_urls, timestamp=timestamp)
        captured_count = sum(1 for capture in captures if capture.get("status") == "captured")
        summary = self.host._summarize(source, new_articles, captures) if summary_enabled else ""
        notify_payload = (
            self.host._notify(source, new_articles, captures, summary)
            if notify_enabled and new_articles
            else {"status": "skipped"}
        )
        for article, capture in zip(new_articles, captures, strict=True):
            self.host._record_event(source, article, capture, timestamp=timestamp)
        run_path = self.host._write_run(
            source,
            articles=new_articles,
            captures=captures,
            summary=summary,
            notify=notify_payload,
            timestamp=timestamp,
        )
        updated = self.host._replace_source(
            source,
            status="active",
            checked_at=timestamp,
            changed_at=timestamp if new_articles else source.changed_at,
            updated_at=timestamp,
            last_error="",
        )
        self.host._write_source(updated)
        return {
            "id": source.id,
            "status": "changed" if new_articles else "fresh",
            "discovered_count": len(articles),
            "new_count": len(new_articles),
            "captured_count": captured_count,
            "run": compact_user_path(run_path),
            "notify": notify_payload,
            "articles": [article.as_dict() for article in new_articles],
            "captures": captures,
        }

    def _handle_failure(
        self,
        source: Any,
        *,
        stage: str,
        error: str,
        timestamp: str,
        notify_override: bool | None,
        articles: list[Any] | None = None,
        captures: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        notify_enabled = source.notify.enabled if notify_override is None else notify_override
        notify_payload = (
            self.host._notify_failure(source, stage=stage, error=error)
            if notify_enabled
            else {"status": "skipped"}
        )
        run_path = self.host._write_run(
            source,
            articles=articles or [],
            captures=captures or [],
            summary="",
            notify=notify_payload,
            timestamp=timestamp,
            stage=stage,
            error=error,
        )
        self.host._record_failure_event(source, stage=stage, error=error, timestamp=timestamp)
        updated = self.host._replace_source(
            source,
            status=BLOG_ATTENTION_STATUS,
            checked_at=timestamp,
            updated_at=timestamp,
            last_error=error,
        )
        self.host._write_source(updated)
        return {
            "id": source.id,
            "status": BLOG_ATTENTION_STATUS,
            "stage": stage,
            "error": error,
            "run": compact_user_path(run_path),
            "notify": notify_payload,
        }
