from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

from alcove.dashboard_snapshot import DashboardSnapshotBuilder
from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.pins_import import PinsMarkdownImportModule
from alcove.usage import UsageRecorder

DASHBOARD_SNAPSHOT_VERSION = 1


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class DashboardModule:
    snapshot_version = DASHBOARD_SNAPSHOT_VERSION
    now_iso = staticmethod(now_iso)

    def __init__(self, home: AlcoveHome | None = None) -> None:
        self.home = home or AlcoveHome.init()
        self.root = self.home.root / "dashboard"

    def snapshot(self) -> dict[str, Any]:
        return DashboardSnapshotBuilder(self).snapshot()

    def _dashboard_usage_summary(self) -> dict[str, Any]:
        summary = UsageRecorder(self.home).summary()
        recent = summary.get("recent") if isinstance(summary.get("recent"), list) else []
        summary["recent"] = [
            self._dashboard_usage_event(event) for event in recent if isinstance(event, dict)
        ]
        return summary

    @staticmethod
    def _dashboard_usage_event(event: dict[str, Any]) -> dict[str, Any]:
        metrics = event.get("metrics") if isinstance(event.get("metrics"), dict) else {}
        display_metrics: dict[str, Any] = {}
        if "result_count" in metrics:
            display_metrics["result_count"] = metrics.get("result_count")
        return {
            "timestamp": str(event.get("timestamp") or ""),
            "surface": str(event.get("surface") or ""),
            "area": str(event.get("area") or ""),
            "action": str(event.get("action") or ""),
            "outcome": str(event.get("outcome") or ""),
            "summary": str(event.get("summary") or ""),
            "metrics": display_metrics,
        }

    def _home_label(self) -> str:
        return f"Alcove Home · {self.home.root.name or compact_user_path(self.home.root)}"

    def build(
        self,
        output_dir: str | Path | None = None,
        *,
        build_frontend: bool = True,
    ) -> dict[str, Any]:
        self._record_event("dashboard.build", "Built Alcove dashboard", visible=False)
        root = Path(output_dir).expanduser() if output_dir else self.root
        root.mkdir(parents=True, exist_ok=True)
        snapshot = self.snapshot()
        snapshot_path = root / "snapshot.json"
        snapshot_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        frontend = self._frontend_dir()
        frontend_built = False
        if build_frontend and frontend.is_dir():
            self._build_frontend(frontend, root)
            frontend_built = True
            snapshot_path.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        return {
            "status": "built",
            "root": str(root),
            "index": str(root / "index.html"),
            "snapshot": str(snapshot_path),
            "frontend_built": frontend_built,
            "frontend_mode": ("compiled_frontend" if frontend_built else "static_snapshot"),
            "frontend_note": (
                "Frontend build was skipped or unavailable; static index.html and snapshot.json "
                "were written for local dashboard use."
                if not frontend_built
                else ""
            ),
        }

    def import_pins(
        self,
        regular_file: str | Path | None = None,
        todo_file: str | Path | None = None,
    ) -> dict[str, Any]:
        result = PinsMarkdownImportModule(home=self.home).import_pins(
            regular_file=regular_file,
            todo_file=todo_file,
        )
        self._record_event(
            "dashboard.import_pins",
            "Imported regular/todo theme pin files",
            result,
        )
        return result

    def _record_event(
        self,
        action: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
        visible: bool = True,
    ) -> None:
        self._record_usage_event(action, summary, metadata or {})
        log_path = self.home.paths().logs / "activity.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "type": "event",
            "area": "dashboard",
            "action": action,
            "summary": summary,
            "metadata": metadata or {},
            "visible": visible,
            "updated_at": now_iso(),
        }
        with log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _record_usage_event(
        self,
        action: str,
        summary: str,
        metadata: dict[str, Any],
    ) -> None:
        recorder = UsageRecorder(self.home)
        if action == "dashboard.search":
            result_count = int(metadata.get("result_count") or 0)
            query_length = int(metadata.get("query_length") or 0)
            query_preview = str(metadata.get("query_preview") or "").strip()
            metrics: dict[str, Any] = {
                "query_length": max(query_length, 0),
                "result_count": max(result_count, 0),
            }
            if query_preview:
                metrics["query_preview"] = query_preview
            recorder.record_usage(
                surface="dashboard",
                area="search",
                action="search.run",
                summary=f"Search: {query_preview}" if query_preview else summary,
                outcome="empty" if result_count == 0 else "success",
                metrics=metrics,
                metadata={"filters": {}},
                privacy={
                    "query_stored": False,
                    "query_preview_stored": bool(query_preview),
                    "content_stored": False,
                },
            )
            return
        if action == "dashboard.route":
            recorder.record_usage(
                surface="dashboard",
                area="dashboard",
                action=action,
                summary=summary,
                metadata={"route": str(metadata.get("route") or "")},
                privacy={"query_stored": False, "content_stored": False},
            )
            return
        if action == "dashboard.result_open":
            recorder.record_usage(
                surface="dashboard",
                area="dashboard",
                action=action,
                summary=summary,
                metadata={
                    "type": str(metadata.get("type") or ""),
                    "href": str(metadata.get("href") or ""),
                    "title_length": int(metadata.get("title_length") or 0),
                },
                privacy={"query_stored": False, "content_stored": False},
            )

    def _frontend_dir(self) -> Path:
        return Path(__file__).resolve().parents[2] / "frontend" / "dashboard"

    def _build_frontend(self, frontend: Path, output_dir: Path) -> None:
        package_json = frontend / "package.json"
        if not package_json.is_file():
            return
        npm = shutil.which("npm")
        if npm is None:
            raise FileNotFoundError("npm is required to build the dashboard frontend")
        if not (frontend / "node_modules").is_dir():
            subprocess.run(  # noqa: S603
                [npm, "install"],
                cwd=frontend,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        subprocess.run(  # noqa: S603
            [npm, "run", "build"],
            cwd=frontend,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        dist = frontend / "dist"
        if not dist.is_dir():
            raise FileNotFoundError(f"Dashboard frontend build did not create {dist}")
        for stale in output_dir.iterdir():
            if stale.name == "snapshot.json":
                continue
            if stale.is_dir():
                shutil.rmtree(stale)
            else:
                stale.unlink()
        for path in dist.iterdir():
            target = output_dir / path.name
            if target.exists():
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
            if path.is_dir():
                shutil.copytree(path, target)
            else:
                shutil.copy2(path, target)
