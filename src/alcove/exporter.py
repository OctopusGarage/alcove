from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import shutil

from alcove.home import AlcoveHome


GLOBAL_EXPORT_ENTRIES = (
    "config.yml",
    "knowledge-bases",
    "pins",
    "tasks",
    "mounts",
    "connectors",
)


class ExportModule:
    def __init__(self, home: AlcoveHome) -> None:
        self.home = home

    def export_global(self, output_dir: Path | str) -> dict[str, object]:
        output = Path(output_dir).expanduser().resolve()
        output.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for name in GLOBAL_EXPORT_ENTRIES:
            source = self.home.root / name
            if not source.exists():
                continue
            dest = output / name
            if source.is_dir():
                shutil.copytree(source, dest, dirs_exist_ok=True)
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            copied.append(name)
        manifest = {
            "schema_version": 1,
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
