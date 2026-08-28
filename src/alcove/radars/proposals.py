from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from alcove.paths import compact_user_path
from alcove.prompts import AddPromptRequest
from alcove.tasks import AddIdeaRequest, AddTaskRequest


PROPOSAL_SCHEMA = "alcove/radar-action-proposal/v1"
PROPOSAL_INDEX_SCHEMA = "alcove/radar-action-proposals-index/v1"
PROPOSAL_STATUSES = {"pending", "accepted", "rejected", "deferred", "duplicate"}
ACTION_TYPES = {"task", "idea", "prompt"}


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class RadarProposalModule:
    """Extract and govern radar actions without mutating radar run artifacts."""

    def __init__(self, home: Any) -> None:
        if home is None:
            raise ValueError("Radar action proposals require Alcove Home")
        self.home = home
        self.root = home.root / "radars" / "proposals"
        self.index_path = self.root / "index.json"

    def generate(
        self,
        radar_id: str,
        run_day: str = "",
        *,
        action_type: str = "idea",
    ) -> dict[str, Any]:
        action_type = _normalize_action_type(action_type)
        run_path = self._run_path(radar_id, run_day)
        run = _read_mapping(run_path)
        if not run:
            raise FileNotFoundError(f"Radar run not found: {compact_user_path(run_path)}")
        effective_day = str(run.get("date") or run_day)
        run_id = str(run.get("run_id") or f"{radar_id}:{effective_day}")
        scored_path = self.home.root / "radars" / "cache" / radar_id / effective_day / "scored.json"
        scored = _read_list(scored_path)
        report_paths = (
            dict(run.get("reports") or {}) if isinstance(run.get("reports"), dict) else {}
        )
        okf_path = self.home.root / "radars" / "okf" / radar_id / "index.md"
        generated: list[dict[str, Any]] = []
        for item in scored:
            if not bool(item.get("included")):
                continue
            source_url = str(item.get("url") or "").strip()
            title = _clean_text(str(item.get("title") or ""))
            if not title:
                continue
            dedup_key = self._dedup_key(action_type, source_url, title)
            proposal_id = _proposal_id(radar_id, run_id, action_type, source_url, title)
            existing = self._read_optional(proposal_id)
            if existing:
                generated.append(existing)
                continue
            duplicate_of = self._find_dedup(dedup_key)
            status = "duplicate" if duplicate_of else "pending"
            proposal = {
                "schema": PROPOSAL_SCHEMA,
                "id": proposal_id,
                "status": status,
                "action_type": action_type,
                "title": title,
                "content": _proposal_content(item, source_url),
                "notes": _proposal_notes(item, source_url, run_id),
                "source_url": source_url,
                "dedup_key": dedup_key,
                "duplicate_of": duplicate_of,
                "provenance": {
                    "radar_id": radar_id,
                    "run_id": run_id,
                    "run_path": compact_user_path(run_path),
                    "scored_path": compact_user_path(scored_path),
                    "report_paths": report_paths,
                    "okf_index_path": compact_user_path(okf_path),
                    "source_id": str(item.get("source_id") or ""),
                    "adapter": str(item.get("adapter") or ""),
                    "published_at": str(item.get("published_at") or ""),
                },
                "created_at": now_iso(),
                "updated_at": now_iso(),
            }
            self._write(proposal)
            generated.append(proposal)
        self._rebuild_index()
        return {
            "status": "generated",
            "radar_id": radar_id,
            "run_id": run_id,
            "count": len(generated),
            "proposals": generated,
            "mutation": "proposal_storage_only",
        }

    def list(self, status: str = "") -> dict[str, Any]:
        rows = [row for row in self._all() if not status or row.get("status") == status]
        return {"count": len(rows), "proposals": rows}

    def get(self, proposal_id: str) -> dict[str, Any]:
        proposal = self._read(proposal_id)
        return proposal

    def resolve(self, proposal_id: str, status: str) -> dict[str, Any]:
        if status not in {"rejected", "deferred"}:
            raise ValueError(f"Unsupported proposal resolution: {status}")
        proposal = self._read(proposal_id)
        if proposal.get("status") == "accepted":
            raise ValueError("Accepted proposals cannot be changed")
        proposal["status"] = status
        proposal["updated_at"] = now_iso()
        self._write(proposal)
        self._rebuild_index()
        return proposal

    def accept(self, proposal_id: str, application: Any) -> dict[str, Any]:
        proposal = self._read(proposal_id)
        if proposal.get("status") == "accepted":
            return {"status": "accepted", "idempotent": True, "proposal": proposal}
        if proposal.get("status") != "pending":
            raise ValueError(f"Proposal is not pending: {proposal_id}")
        action_type = _normalize_action_type(str(proposal.get("action_type") or ""))
        tags = ["radar", str(proposal.get("provenance", {}).get("radar_id") or "")]
        source_url = str(proposal.get("source_url") or "")
        notes = str(proposal.get("notes") or "")
        if source_url:
            notes = f"{notes}\nSource: {source_url}".strip()
        if action_type == "task":
            target = application.task_add_payload(
                AddTaskRequest(title=str(proposal["title"]), notes=notes, tags=tags)
            )
        elif action_type == "idea":
            target = application.idea_add_payload(
                AddIdeaRequest(title=str(proposal["title"]), notes=notes, tags=tags)
            )
        else:
            target = application.prompt_save_payload(
                AddPromptRequest(
                    title=str(proposal["title"]),
                    content=str(proposal.get("content") or ""),
                    description=notes,
                    tags=tags,
                    source_refs=[source_url] if source_url else [],
                ),
                force=True,
            )
        proposal["status"] = "accepted"
        proposal["updated_at"] = now_iso()
        proposal["accepted_at"] = proposal["updated_at"]
        proposal["target"] = _target_receipt(target)
        self._write(proposal)
        self._rebuild_index()
        return {
            "status": "accepted",
            "idempotent": False,
            "proposal": proposal,
            "target": proposal["target"],
            "write_result": target,
        }

    def dashboard_rows(self) -> list[dict[str, Any]]:
        return [
            {
                "id": str(row.get("id") or ""),
                "title": str(row.get("title") or ""),
                "status": str(row.get("status") or ""),
                "action_type": str(row.get("action_type") or ""),
                "source_url": str(row.get("source_url") or ""),
                "run_id": str((row.get("provenance") or {}).get("run_id") or ""),
                "radar_id": str((row.get("provenance") or {}).get("radar_id") or ""),
                "target": row.get("target") or {},
            }
            for row in self._all()
        ]

    def _run_path(self, radar_id: str, run_day: str) -> Path:
        root = self.home.root / "radars" / "runs" / radar_id
        if run_day:
            return root / run_day / "run.json"
        candidates = sorted(root.glob("*/run.json"), reverse=True)
        if not candidates:
            return root / "latest" / "run.json"
        return candidates[0]

    def _dedup_key(self, action_type: str, source_url: str, title: str) -> str:
        basis = source_url.casefold() or _slug_text(title)
        return f"{action_type}:{basis}"

    def _find_dedup(self, dedup_key: str) -> str:
        for row in self._all():
            if row.get("dedup_key") == dedup_key:
                return str(row.get("id") or "")
        return ""

    def _all(self) -> list[dict[str, Any]]:
        if not self.root.is_dir():
            return []
        rows: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            if path.name == self.index_path.name:
                continue
            row = _read_mapping(path)
            if row:
                rows.append(row)
        return rows

    def _read(self, proposal_id: str) -> dict[str, Any]:
        path = self.root / f"{_safe_id(proposal_id)}.json"
        proposal = _read_mapping(path)
        if not proposal:
            raise FileNotFoundError(f"Radar action proposal not found: {proposal_id}")
        return proposal

    def _read_optional(self, proposal_id: str) -> dict[str, Any] | None:
        proposal = _read_mapping(self.root / f"{_safe_id(proposal_id)}.json")
        return proposal or None

    def _write(self, proposal: dict[str, Any]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / f"{proposal['id']}.json"
        _refuse_symlink_write(path, "radar proposal")
        path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _rebuild_index(self) -> None:
        rows = self._all()
        self.root.mkdir(parents=True, exist_ok=True)
        _refuse_symlink_write(self.index_path, "radar proposal index")
        self.index_path.write_text(
            json.dumps(
                {
                    "schema": PROPOSAL_INDEX_SCHEMA,
                    "generated_at": now_iso(),
                    "count": len(rows),
                    "proposals": [
                        {
                            "id": row.get("id"),
                            "status": row.get("status"),
                            "action_type": row.get("action_type"),
                            "title": row.get("title"),
                            "run_id": (row.get("provenance") or {}).get("run_id"),
                            "radar_id": (row.get("provenance") or {}).get("radar_id"),
                        }
                        for row in rows
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


def _proposal_id(radar_id: str, run_id: str, action_type: str, source_url: str, title: str) -> str:
    basis = "|".join([radar_id, run_id, action_type, source_url, title.casefold()])
    return "radar-" + hashlib.sha256(basis.encode("utf-8")).hexdigest()[:20]


def _proposal_content(item: dict[str, Any], source_url: str) -> str:
    summary = _clean_text(str(item.get("summary") or ""))
    title = _clean_text(str(item.get("title") or ""))
    body = f"Track this radar signal: {title}."
    if summary:
        body += f"\n\nContext: {summary}"
    if source_url:
        body += f"\n\nSource: {source_url}"
    return body


def _proposal_notes(item: dict[str, Any], source_url: str, run_id: str) -> str:
    reason = _clean_text(str(item.get("score_reason") or ""))
    text = f"Radar run {run_id}; score {float(item.get('score') or 0):.2f}."
    if reason:
        text += f" {reason}."
    return text


def _target_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    for key in ("task", "idea", "prompt"):
        if isinstance(payload.get(key), dict):
            item = payload[key]
            return {"type": key, "id": item.get("id"), "path": item.get("path")}
    return {"status": payload.get("status")}


def _normalize_action_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ACTION_TYPES:
        raise ValueError(f"action type must be one of: {', '.join(sorted(ACTION_TYPES))}")
    return normalized


def _safe_id(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", value)


def _slug_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _clean_text(value: str) -> str:
    return " ".join(value.split())


def _read_mapping(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(payload) if isinstance(payload, dict) else {}


def _read_list(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    return (
        [dict(row) for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []
    )


def _refuse_symlink_write(path: Path, label: str) -> None:
    if path.is_symlink():
        raise RuntimeError(f"Refusing to write {label} through symlink: {compact_user_path(path)}")
