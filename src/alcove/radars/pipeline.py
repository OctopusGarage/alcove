from __future__ import annotations

from datetime import date
from html import escape, unescape
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from alcove.ai_summary import run_ai_summary
from alcove.notifications import (
    send_feishu_message,
    send_tcb_notification,
    send_telegram_document,
    send_telegram_message,
)
from alcove.notification_delivery import (
    combined_notification_status,
    notification_bool,
    notification_sink_label,
    notification_sinks,
)
from alcove.paths import compact_user_path
from alcove.radars.models import RADAR_RUN_SCHEMA, RadarDefinition, RadarItem, now_iso
from alcove.radars.reporting import render_html, render_markdown, selected_report_items
from alcove.radars.scoring import score_items
from alcove.radars.sources import fetch_source

if TYPE_CHECKING:
    from alcove.radars.module import RadarModule


class RadarPipeline:
    def __init__(self, module: RadarModule) -> None:
        self.module = module

    def run(
        self,
        definition: RadarDefinition,
        *,
        skip_fetch: bool = False,
        force: bool = False,
        ai: bool = False,
        notify: bool = False,
        run_day: str = "",
    ) -> dict[str, Any]:
        run_day = run_day or date.today().isoformat()
        run_path = self.module.runs_root / definition.id / run_day / "run.json"
        if run_path.is_file() and not force:
            existing_run = _json_mapping(run_path)
            if existing_run:
                return existing_run
        cache_dir = self.module.cache_root / definition.id / run_day
        raw_path = cache_dir / "raw.json"
        raw_items, source_results = self._raw_items(
            definition,
            raw_path=raw_path,
            skip_fetch=skip_fetch,
        )
        deduped = _dedupe(raw_items)
        scored = score_items(definition, deduped)
        cache_dir.mkdir(parents=True, exist_ok=True)
        scored_path = cache_dir / "scored.json"
        scored_path.write_text(_json([item.as_dict() for item in scored]), encoding="utf-8")
        reports = self._write_reports(definition, scored, run_day=run_day)
        report_items = selected_report_items(definition, scored)
        run_payload = self._run_payload(
            definition,
            run_day=run_day,
            fetched=len(raw_items),
            deduped=len(deduped),
            scored=len(scored),
            included=len(report_items),
            source_results=source_results,
            reports=reports,
            force=force,
            ai=ai,
        )
        ai_payload = self._maybe_summarize(
            definition,
            scored,
            report_items,
            reports,
            run_day=run_day,
            ai=ai,
        )
        run_payload["ai"] = ai_payload
        notify_payload = self._maybe_notify(
            definition,
            report_items,
            run_payload,
            ai_payload=ai_payload,
            notify=notify,
        )
        run_payload["notify"] = notify_payload
        self._write_run(definition.id, run_day, run_payload)
        self._write_okf_index(definition, run_payload)
        self._append_event(run_payload)
        return run_payload

    def _raw_items(
        self,
        definition: RadarDefinition,
        *,
        raw_path: Path,
        skip_fetch: bool,
    ) -> tuple[list[RadarItem], list[dict[str, Any]]]:
        if skip_fetch:
            if not raw_path.is_file():
                raise FileNotFoundError(f"radar raw cache not found: {compact_user_path(raw_path)}")
            raw_rows = json.loads(raw_path.read_text(encoding="utf-8"))
            if not isinstance(raw_rows, list):
                raise ValueError(f"radar raw cache must be a list: {compact_user_path(raw_path)}")
            return _items_from_json(raw_rows), [{"status": "cached", "count": len(raw_rows)}]
        raw_items, source_results = self._fetch(definition)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(_json([item.as_dict() for item in raw_items]), encoding="utf-8")
        return raw_items, source_results

    def _fetch(self, definition: RadarDefinition) -> tuple[list[RadarItem], list[dict[str, Any]]]:
        items: list[RadarItem] = []
        source_results: list[dict[str, Any]] = []
        for source in definition.sources:
            if not source.enabled:
                source_results.append({"id": source.id, "status": "disabled", "count": 0})
                continue
            try:
                fetched = fetch_source(definition, source)
            except Exception as exc:
                source_results.append(
                    {"id": source.id, "status": "error", "count": 0, "error": str(exc)}
                )
                continue
            items.extend(fetched)
            source_results.append({"id": source.id, "status": "fetched", "count": len(fetched)})
        return items, source_results

    def _write_reports(
        self,
        definition: RadarDefinition,
        scored: list[RadarItem],
        *,
        run_day: str,
    ) -> dict[str, str]:
        formats = _report_formats(definition)
        report_dir = self.module.reports_root / definition.id
        report_dir.mkdir(parents=True, exist_ok=True)
        reports: dict[str, str] = {}
        if "md" in formats:
            md_path = report_dir / f"{run_day}.md"
            md_path.write_text(
                render_markdown(definition, scored, run_day=run_day), encoding="utf-8"
            )
            reports["md"] = compact_user_path(md_path)
        if "html" in formats:
            html_path = report_dir / f"{run_day}.html"
            html_path.write_text(render_html(definition, scored, run_day=run_day), encoding="utf-8")
            reports["html"] = compact_user_path(html_path)
        return reports

    def _run_payload(
        self,
        definition: RadarDefinition,
        *,
        run_day: str,
        fetched: int,
        deduped: int,
        scored: int,
        included: int,
        source_results: list[dict[str, Any]],
        reports: dict[str, str],
        force: bool,
        ai: bool,
    ) -> dict[str, Any]:
        failed_sources = len([row for row in source_results if row.get("status") == "error"])
        return {
            "schema": RADAR_RUN_SCHEMA,
            "id": definition.id,
            "name": definition.name,
            "status": "completed" if failed_sources == 0 else "completed_with_errors",
            "date": run_day,
            "run_at": now_iso(),
            "fetched": fetched,
            "deduped": deduped,
            "scored": scored,
            "included": included,
            "failed_sources": failed_sources,
            "sources": source_results,
            "reports": reports,
            "force": force,
            "ai": {
                "requested": ai,
                "status": "skipped",
                "reason": "AI summary is not enabled for this run",
            },
            "notify": {"status": "skipped", "reason": "notification is not enabled"},
        }

    def _maybe_summarize(
        self,
        definition: RadarDefinition,
        scored: list[RadarItem],
        report_items: list[RadarItem],
        reports: dict[str, str],
        *,
        run_day: str,
        ai: bool,
    ) -> dict[str, Any]:
        policy = dict(definition.ai_summary)
        configured = bool(policy) or bool(policy.get("enabled"))
        requested = ai or bool(policy.get("enabled"))
        if not requested:
            return {
                "requested": False,
                "status": "skipped",
                "reason": "AI summary is not enabled for this run",
            }
        if not configured:
            return {
                "requested": True,
                "status": "skipped",
                "reason": "ai_summary policy is not configured",
            }
        prompt = self._ai_prompt(
            definition,
            report_items,
            reports,
            run_day=run_day,
            policy=policy,
        )
        result = run_ai_summary(prompt=prompt, policy=policy, cwd=self.module.home.root)
        payload = {
            "requested": True,
            "status": result.get("status", "failed"),
            "provider": result.get("provider") or policy.get("provider") or "claude",
        }
        if result.get("fallback_from"):
            payload["fallback_from"] = result["fallback_from"]
        if result.get("summary"):
            summary = str(result["summary"]).strip()
            summary_path = self.module.reports_root / definition.id / f"{run_day}.ai.md"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(summary + "\n", encoding="utf-8")
            reports["ai_summary"] = compact_user_path(summary_path)
            payload["summary"] = summary
            payload["path"] = compact_user_path(summary_path)
        if result.get("reason"):
            payload["reason"] = result["reason"]
        if result.get("error"):
            payload["error"] = result["error"]
        if result.get("returncode") is not None:
            payload["returncode"] = result["returncode"]
        return payload

    def _ai_prompt(
        self,
        definition: RadarDefinition,
        report_items: list[RadarItem],
        reports: dict[str, str],
        *,
        run_day: str,
        policy: dict[str, Any],
    ) -> str:
        report_text = self._report_text(reports)
        max_chars = _positive_int(policy.get("max_input_chars"), default=12000)
        report_text = report_text[:max_chars]
        base_prompt = str(policy.get("prompt") or policy.get("prompt_template") or "").strip()
        if not base_prompt:
            base_prompt = _default_ai_prompt(definition)
        top_lines = [
            f"- {item.title} ({item.source_id}, score {item.score:.2f}): {item.url}"
            for item in report_items[:8]
        ]
        return "\n".join(
            [
                base_prompt,
                "",
                "Radar context:",
                f"- Radar: {definition.name} ({definition.id})",
                f"- Date: {run_day}",
                f"- Report style: {definition.report.get('style') or 'default'}",
                f"- Language: {definition.report.get('language') or 'zh'}",
                "",
                "Top selected items:",
                *(top_lines or ["- No items passed the deterministic threshold."]),
                "",
                "Deterministic report:",
                report_text,
                "",
                "Return a concise core summary suitable for a Telegram notification. "
                "Do not invent facts beyond the report. Do not add translation notes, "
                "English-learning notes, meta commentary, or unrelated coaching. Use plain "
                "Markdown bullets without emoji unless the radar definition explicitly asks for them.",
            ]
        )

    def _report_text(self, reports: dict[str, str]) -> str:
        md_path = reports.get("md")
        if not md_path:
            return ""
        path = Path(str(md_path)).expanduser()
        if not path.is_file():
            return ""
        return path.read_text(encoding="utf-8", errors="replace")

    def _maybe_notify(
        self,
        definition: RadarDefinition,
        report_items: list[RadarItem],
        run_payload: dict[str, Any],
        *,
        ai_payload: dict[str, Any],
        notify: bool,
    ) -> dict[str, Any]:
        policy = dict(definition.notify)
        requested = notify or bool(policy.get("enabled"))
        if not requested:
            return {"status": "skipped", "reason": "notification is not enabled"}
        results: dict[str, dict[str, Any]] = {}
        for sink in notification_sinks(
            policy,
            inheritable_keys=("include_ai_summary", "include_top_links"),
        ):
            sink_type = str(sink.get("type") or "telegram")
            label = notification_sink_label(sink, results, default="telegram")
            if sink_type == "telegram":
                results[label] = self._notify_telegram(
                    definition,
                    sink,
                    report_items,
                    run_payload,
                    ai_payload,
                )
            elif sink_type == "feishu":
                results[label] = self._notify_feishu(
                    definition,
                    sink,
                    report_items,
                    run_payload,
                    ai_payload,
                )
            elif sink_type in {"tcb", "tmux_claude_bot"}:
                results[label] = self._notify_tcb(
                    definition,
                    sink,
                    report_items,
                    run_payload,
                    ai_payload,
                )
            else:
                results[label] = {
                    "status": "skipped",
                    "reason": f"unsupported notification sink: {sink_type}",
                }
        payload = {"status": combined_notification_status(results), "sinks": results}
        if set(results) == {"telegram"}:
            payload.update(results["telegram"])
            payload["sinks"] = results
        return payload

    def _notify_telegram(
        self,
        definition: RadarDefinition,
        sink: dict[str, Any],
        report_items: list[RadarItem],
        run_payload: dict[str, Any],
        ai_payload: dict[str, Any],
    ) -> dict[str, Any]:
        text = self._telegram_message(definition, sink, report_items, run_payload, ai_payload)
        result = send_telegram_message(home=self.module.home, text=text)
        if sink.get("send_document", True):
            documents: dict[str, dict[str, Any]] = {}
            for format_name, path in _report_document_paths(run_payload, sink=sink).items():
                document = send_telegram_document(
                    home=self.module.home,
                    path=path,
                    caption=(
                        f"{definition.name} radar {format_name.upper()} report - "
                        f"{run_payload['date']}"
                    ),
                )
                documents[format_name] = document
            if documents:
                result = {**result, "documents": documents}
                if "html" in documents:
                    result["document"] = documents["html"]
                failed_documents = [
                    document
                    for document in documents.values()
                    if document.get("status") not in {"sent", "skipped"}
                ]
                if result.get("status") == "sent" and failed_documents:
                    result["status"] = "partial"
        return result

    def _notify_feishu(
        self,
        definition: RadarDefinition,
        sink: dict[str, Any],
        report_items: list[RadarItem],
        run_payload: dict[str, Any],
        ai_payload: dict[str, Any],
    ) -> dict[str, Any]:
        return send_feishu_message(
            home=self.module.home,
            sink=sink,
            title=f"Radar: {definition.name}",
            text=self._plain_notification_message(
                definition,
                sink,
                report_items,
                run_payload,
                ai_payload,
            ),
            report_path=None,
        )

    def _notify_tcb(
        self,
        definition: RadarDefinition,
        sink: dict[str, Any],
        report_items: list[RadarItem],
        run_payload: dict[str, Any],
        ai_payload: dict[str, Any],
    ) -> dict[str, Any]:
        attachments = (
            list(_report_document_paths(run_payload, sink=sink).values())
            if sink.get("send_documents", True)
            else []
        )
        return send_tcb_notification(
            sink=sink,
            title=f"Radar: {definition.name}",
            text=self._plain_notification_message(
                definition,
                sink,
                report_items,
                run_payload,
                ai_payload,
            ),
            attachments=attachments,
        )

    def _telegram_message(
        self,
        definition: RadarDefinition,
        sink: dict[str, Any],
        report_items: list[RadarItem],
        run_payload: dict[str, Any],
        ai_payload: dict[str, Any],
    ) -> str:
        lines = [
            f"<b>Radar: {escape(definition.name)}</b>",
            "",
            f"Status: {escape(str(run_payload['status']))}",
            f"Date: {escape(str(run_payload['date']))}",
            f"Included: {escape(str(run_payload['included']))}",
        ]
        include_ai_summary = notification_bool(definition.notify, sink, "include_ai_summary", True)
        include_top_links = notification_bool(definition.notify, sink, "include_top_links", True)
        summary = str(ai_payload.get("summary") or "").strip() if include_ai_summary else ""
        if summary:
            lines.extend(["", f"<b>Core AI Summary</b>\n{escape(_truncate(summary, 1800))}"])
        elif include_ai_summary and _ai_summary_degraded(ai_payload):
            reason = _ai_summary_issue(ai_payload)
            lines.extend(
                [
                    "",
                    "<b>Core Summary</b>",
                    "AI summary unavailable; sending deterministic radar report.",
                    f"AI reason: {escape(_truncate(reason, 400))}",
                ]
            )
        else:
            lines.extend(["", "<b>Core Summary</b>", escape(_deterministic_brief(report_items))])
        top_items = report_items[:5]
        if include_top_links and top_items:
            lines.extend(["", "<b>Top Links</b>"])
            for index, item in enumerate(top_items, start=1):
                title = escape(item.title)
                url = escape(item.url)
                lines.append(f'{index}. <a href="{url}">{title}</a>')
        return _truncate("\n".join(lines), 3900)

    def _plain_notification_message(
        self,
        definition: RadarDefinition,
        sink: dict[str, Any],
        report_items: list[RadarItem],
        run_payload: dict[str, Any],
        ai_payload: dict[str, Any],
    ) -> str:
        lines = [
            f"Status: {run_payload['status']}",
            f"Date: {run_payload['date']}",
            f"Included: {run_payload['included']}",
        ]
        include_ai_summary = notification_bool(definition.notify, sink, "include_ai_summary", True)
        include_top_links = notification_bool(definition.notify, sink, "include_top_links", True)
        summary = str(ai_payload.get("summary") or "").strip() if include_ai_summary else ""
        if summary:
            lines.extend(["", "Core AI Summary", _truncate(summary, 1800)])
        elif include_ai_summary and _ai_summary_degraded(ai_payload):
            reason = _ai_summary_issue(ai_payload)
            lines.extend(
                [
                    "",
                    "Core Summary",
                    "AI summary unavailable; sending deterministic radar report.",
                    f"AI reason: {_truncate(reason, 400)}",
                ]
            )
        else:
            lines.extend(["", "Core Summary", _deterministic_brief(report_items)])
        top_items = report_items[:5]
        if include_top_links and top_items:
            lines.extend(["", "Top Links"])
            for index, item in enumerate(top_items, start=1):
                lines.append(f"{index}. {item.title} - {item.url}")
        return unescape(_truncate("\n".join(lines), 3900))

    def _write_run(self, radar_id: str, run_day: str, run_payload: dict[str, Any]) -> None:
        run_dir = self.module.runs_root / radar_id / run_day
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "run.json").write_text(_json(run_payload), encoding="utf-8")

    def _write_okf_index(self, definition: RadarDefinition, run_payload: dict[str, Any]) -> None:
        okf_dir = self.module.okf_root / definition.id
        okf_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "---",
            "type: Radar Index",
            "schema: okf/radar-index/v1",
            f"radar_id: {definition.id}",
            f"title: {definition.name}",
            f"latest_run: {run_payload['date']}",
            "---",
            "",
            f"# {definition.name}",
            "",
            f"- Status: {run_payload['status']}",
            f"- Included items: {run_payload['included']}",
            f"- Failed sources: {run_payload['failed_sources']}",
        ]
        reports = run_payload.get("reports")
        if isinstance(reports, dict):
            for format_name, path in sorted(reports.items()):
                lines.append(f"- Latest {format_name}: {path}")
        (okf_dir / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append_event(self, run_payload: dict[str, Any]) -> None:
        self.module.events_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "event": "radar.run.completed",
            "radar_id": run_payload["id"],
            "status": run_payload["status"],
            "date": run_payload["date"],
            "run_at": run_payload["run_at"],
            "included": run_payload["included"],
            "failed_sources": run_payload["failed_sources"],
        }
        with self.module.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _dedupe(items: list[RadarItem]) -> list[RadarItem]:
    seen: set[str] = set()
    deduped: list[RadarItem] = []
    for item in items:
        key = _dedupe_key(item)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _dedupe_key(item: RadarItem) -> str:
    if item.url:
        return item.url.strip().lower()
    return f"{item.source_id}:{item.title.strip().lower()}"


def _items_from_json(rows: list[Any]) -> list[RadarItem]:
    items: list[RadarItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        tags = row.get("tags") or []
        metrics = row.get("metrics") or {}
        items.append(
            RadarItem(
                source_id=str(row.get("source_id") or ""),
                adapter=str(row.get("adapter") or ""),
                title=str(row.get("title") or ""),
                url=str(row.get("url") or ""),
                summary=str(row.get("summary") or ""),
                author=str(row.get("author") or ""),
                published_at=str(row.get("published_at") or ""),
                tags=[str(tag) for tag in tags] if isinstance(tags, list) else [],
                metrics=dict(metrics) if isinstance(metrics, dict) else {},
                score=float(row.get("score") or 0.0),
                score_reason=str(row.get("score_reason") or ""),
                included=bool(row.get("included", False)),
            )
        )
    return items


def _report_formats(definition: RadarDefinition) -> set[str]:
    formats = definition.report.get("formats")
    if not isinstance(formats, list):
        return {"md"}
    normalized = {str(format_name).lower() for format_name in formats}
    return normalized or {"md"}


def _default_ai_prompt(definition: RadarDefinition) -> str:
    language = str(definition.report.get("language") or "zh")
    style = str(definition.report.get("style") or "")
    if "stock" in definition.id or "stock" in style or "market" in style:
        return (
            f"Use {language}. Analyze this market radar as a concise investor briefing. "
            "Highlight actionable themes, notable risks, noisy signals to ignore, and why the "
            "top items matter. Avoid financial advice and do not invent prices or facts."
        )
    if "world" in definition.id or "news" in style:
        return (
            f"Use {language}. Analyze this news radar as a concise situational briefing. "
            "Group related developments, call out geopolitical or economic implications, and "
            "separate durable signals from ordinary headline churn."
        )
    if "sport" in definition.id or "sport" in style:
        return (
            f"Use {language}. Analyze this sports radar as a concise fan briefing. "
            "Focus on match outcomes, roster or injury implications, and storylines worth "
            "tracking next."
        )
    return (
        f"Use {language}. Analyze this technology radar as a concise technical briefing. "
        "Surface the strongest engineering, AI, infrastructure, or developer-tooling signals, "
        "explain why they matter, and call out low-value noise."
    )


def _deterministic_brief(report_items: list[RadarItem]) -> str:
    if not report_items:
        return "No items passed the deterministic radar threshold."
    top = report_items[0]
    return f"{len(report_items)} items passed the deterministic threshold. Top signal: {top.title}."


def _ai_summary_degraded(ai_payload: dict[str, Any]) -> bool:
    return str(ai_payload.get("status") or "") in {"failed", "skipped"} and bool(
        ai_payload.get("requested")
    )


def _ai_summary_issue(ai_payload: dict[str, Any]) -> str:
    return str(
        ai_payload.get("error")
        or ai_payload.get("reason")
        or f"{ai_payload.get('provider') or 'AI provider'} unavailable"
    )


def _report_document_paths(run_payload: dict[str, Any], *, sink: dict[str, Any]) -> dict[str, Path]:
    reports = run_payload.get("reports")
    if not isinstance(reports, dict):
        return {}
    configured_formats = sink.get("document_formats")
    if isinstance(configured_formats, list) and configured_formats:
        wanted = [str(format_name).lower() for format_name in configured_formats]
    else:
        wanted = ["md", "html"]
    paths: dict[str, Path] = {}
    for format_name in wanted:
        report_path = reports.get(format_name)
        if report_path:
            paths[format_name] = Path(str(report_path)).expanduser()
    return paths


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _positive_int(value: Any, *, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return number if number > 0 else default


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _json_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}
