from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil

from alcove.home import AlcoveHome
from alcove.workspace import Workspace


GLOBAL_EXPORT_ENTRIES = (
    "config.yml",
    "knowledge-bases",
    "pins",
    "tasks",
    "mounts",
    "connectors",
)
KB_EXPORT_ENTRIES = (
    ".alcove",
    "knowledge",
    "inbox",
    "archive",
    "todo",
)


class ExportModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def export_global(self, output_dir: Path | str) -> dict[str, object]:
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        copied = self._copy_entries(self.home.root, output, GLOBAL_EXPORT_ENTRIES)
        manifest = {
            "schema_version": 1,
            "export_type": "global",
            "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_home": str(self.home.root),
            "entries": copied,
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "exported",
            "output_dir": str(output),
            "entries": copied,
            "manifest": str(output / "manifest.json"),
        }

    def export_kb(self, kb: str, output_dir: Path | str) -> dict[str, object]:
        record = self.home.get_knowledge_base(kb)
        return self.export_workspace(record.path, output_dir, kb_name=record.name)

    def export_workspace(
        self,
        workspace_root: Path | str,
        output_dir: Path | str,
        *,
        kb_name: str = "",
    ) -> dict[str, object]:
        workspace = Workspace.discover(workspace_root)
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        copied = self._copy_entries(workspace.root, output, KB_EXPORT_ENTRIES)
        manifest = {
            "schema_version": 1,
            "export_type": "kb",
            "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "kb": kb_name,
            "source_workspace": str(workspace.root),
            "entries": copied,
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "exported",
            "type": "kb",
            "kb": kb_name,
            "output_dir": str(output),
            "entries": copied,
            "manifest": str(output / "manifest.json"),
        }

    def export_all(self, output_dir: Path | str) -> dict[str, object]:
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        global_report = self.export_global(output / "global")
        kb_reports = [
            self.export_workspace(
                record.path,
                output / "knowledge-bases" / record.name,
                kb_name=record.name,
            )
            for record in self.home.list_knowledge_bases()
        ]
        manifest = {
            "schema_version": 1,
            "export_type": "all",
            "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_home": str(self.home.root),
            "global": global_report,
            "knowledge_bases": kb_reports,
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "exported",
            "type": "all",
            "output_dir": str(output),
            "global": global_report,
            "knowledge_bases": kb_reports,
            "manifest": str(output / "manifest.json"),
        }

    def _copy_entries(
        self,
        source_root: Path,
        output: Path,
        entries: tuple[str, ...],
    ) -> list[str]:
        copied: list[str] = []
        for name in entries:
            source = source_root / name
            if not source.exists():
                continue
            dest = output / name
            if source.is_dir():
                shutil.copytree(source, dest, dirs_exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            copied.append(name)
        return copied
