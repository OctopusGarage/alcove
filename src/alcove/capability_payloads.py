from __future__ import annotations

from pathlib import Path
from typing import Any

from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime


class CapabilityPayloadPresenter:
    """Internal presenter for adapter-facing capability payloads."""

    def __init__(self, runtime: AlcoveRuntime) -> None:
        self.runtime = runtime

    def scope(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.runtime.scope_payload(payload)

    def compact_path_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        public_rows: list[dict[str, Any]] = []
        for row in rows:
            public = dict(row)
            if "path" in public:
                public["path"] = compact_user_path(str(public["path"]))
            public_rows.append(public)
        return public_rows

    def mount_scan_report(self, report: dict[str, Any]) -> dict[str, Any]:
        public = dict(report)
        mount = public.get("mount")
        if isinstance(mount, dict):
            public["mount"] = self._public_mount(mount)
        return public

    def workspace_relative_path_rows(
        self,
        rows: list[dict[str, Any]],
        workspace_root: Path,
    ) -> list[dict[str, Any]]:
        public_rows: list[dict[str, Any]] = []
        root = workspace_root.resolve()
        for row in rows:
            public = dict(row)
            if "path" in public:
                path = Path(str(public["path"])).expanduser()
                try:
                    public["path"] = path.resolve().relative_to(root).as_posix()
                except (OSError, ValueError):
                    public["path"] = compact_user_path(str(public["path"]))
            public_rows.append(public)
        return public_rows

    def _public_mount(self, mount: dict[str, Any]) -> dict[str, Any]:
        public = dict(mount)
        path = str(public.pop("path", "") or "")
        path_label = Path(path).expanduser().name if path else ""
        if path_label:
            public["path_label"] = path_label
        mount_id = str(public.get("id") or "")
        if mount_id:
            public["index_ref"] = f"mounts/okf/{mount_id}/index.md"
            public["scan_command"] = f"alcove mount scan {mount_id} --json"
        return public
