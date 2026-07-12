from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any

from alcove.home import AlcoveHome
from alcove.workspace import Workspace


GLOBAL_EXPORT_ENTRIES = (
    "config.yml",
    "knowledge-bases",
    "projects",
    "prompts",
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
        entry_details = self._entry_details(output, copied)
        manifest = {
            "schema_version": 1,
            "export_type": "global",
            "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_home": str(self.home.root),
            "entries": copied,
            "entry_details": entry_details,
            "summary": self._summary(entry_details),
            "readback": self._readback(output, copied),
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return {
            "status": "exported",
            "output_dir": str(output),
            "entries": copied,
            "summary": manifest["summary"],
            "readback": manifest["readback"],
            "manifest": str(output / "manifest.json"),
            "manifest_excerpt": self._manifest_excerpt(manifest),
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
        entry_details = self._entry_details(output, copied)
        manifest = {
            "schema_version": 1,
            "export_type": "kb",
            "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "kb": kb_name,
            "source_workspace": str(workspace.root),
            "entries": copied,
            "entry_details": entry_details,
            "summary": self._summary(entry_details),
            "readback": self._readback(output, copied),
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
            "summary": manifest["summary"],
            "readback": manifest["readback"],
            "manifest": str(output / "manifest.json"),
            "manifest_excerpt": self._manifest_excerpt(manifest),
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
        entries = ["global"]
        if kb_reports:
            entries.append("knowledge-bases")
        entry_details = self._entry_details(output, entries)
        manifest = {
            "schema_version": 1,
            "export_type": "all",
            "exported_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "source_home": str(self.home.root),
            "global": global_report,
            "knowledge_bases": kb_reports,
            "entries": entries,
            "entry_details": entry_details,
            "summary": self._summary(entry_details),
            "readback": self._readback(output, entries),
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
            "summary": manifest["summary"],
            "readback": manifest["readback"],
            "manifest": str(output / "manifest.json"),
            "manifest_excerpt": self._manifest_excerpt(manifest),
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

    def _entry_details(self, output: Path, entries: list[str]) -> list[dict[str, Any]]:
        return [
            self._entry_detail(output / name, name) for name in entries if (output / name).exists()
        ]

    def _entry_detail(self, path: Path, name: str) -> dict[str, Any]:
        if path.is_file():
            data = path.read_bytes()
            return {
                "name": name,
                "type": "file",
                "file_count": 1,
                "byte_count": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        files = [
            item
            for item in sorted(path.rglob("*"), key=lambda item: item.as_posix())
            if item.is_file()
        ]
        digest = hashlib.sha256()
        byte_count = 0
        for file_path in files:
            relative = file_path.relative_to(path).as_posix()
            data = file_path.read_bytes()
            byte_count += len(data)
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(hashlib.sha256(data).hexdigest().encode("ascii"))
            digest.update(b"\0")
        return {
            "name": name,
            "type": "directory",
            "file_count": len(files),
            "byte_count": byte_count,
            "sha256": digest.hexdigest(),
        }

    def _summary(self, entry_details: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "entry_count": len(entry_details),
            "file_count": sum(int(entry.get("file_count") or 0) for entry in entry_details),
            "byte_count": sum(int(entry.get("byte_count") or 0) for entry in entry_details),
        }

    def _readback(self, output: Path, entries: list[str]) -> dict[str, Any]:
        missing = [name for name in entries if not (output / name).exists()]
        return {
            "status": "passed" if not missing else "failed",
            "checked_entries": len(entries),
            "missing": missing,
        }

    def _manifest_excerpt(self, manifest: dict[str, Any]) -> dict[str, Any]:
        excerpt: dict[str, Any] = {
            "export_type": manifest.get("export_type"),
            "summary": manifest.get("summary", {}),
            "readback": manifest.get("readback", {}),
            "entry_details": manifest.get("entry_details", [])[:8],
        }
        if manifest.get("global"):
            global_report = manifest["global"]
            excerpt["global"] = {
                "summary": global_report.get("summary", {}),
                "readback": global_report.get("readback", {}),
                "entries": global_report.get("entries", [])[:8],
                "entry_details": global_report.get("manifest_excerpt", {}).get("entry_details", [])[
                    :8
                ],
            }
        if manifest.get("knowledge_bases"):
            excerpt["knowledge_bases"] = [
                {
                    "kb": kb_report.get("kb", ""),
                    "summary": kb_report.get("summary", {}),
                    "readback": kb_report.get("readback", {}),
                    "entries": kb_report.get("entries", [])[:8],
                    "entry_details": kb_report.get("manifest_excerpt", {}).get("entry_details", [])[
                        :8
                    ],
                }
                for kb_report in manifest.get("knowledge_bases", [])[:8]
            ]
        return excerpt
