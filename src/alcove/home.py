from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError
import yaml

from alcove.paths import compact_user_path


DEFAULT_HOME = "~/.alcove"


@dataclass(frozen=True)
class AlcoveHomePaths:
    root: Path
    config: Path
    okf: Path
    projects: Path
    prompts: Path
    pins: Path
    tasks: Path
    mounts: Path
    mount_indexes: Path
    connectors: Path
    knowledge_bases: Path
    logs: Path
    stats: Path


@dataclass(frozen=True)
class KnowledgeBaseRecord:
    name: str
    path: Path
    config_path: Path


class KnowledgeBaseConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int = 1
    name: str
    path: str


@dataclass(frozen=True)
class AlcoveHome:
    root: Path

    @classmethod
    def default_root(cls) -> Path:
        return Path(os.environ.get("ALCOVE_HOME", DEFAULT_HOME)).expanduser()

    @classmethod
    def init(cls, root: Path | str | None = None) -> "AlcoveHome":
        root_path = Path(root).expanduser() if root is not None else cls.default_root()
        root_path = root_path.resolve()
        paths = cls(root_path).paths()
        paths.root.mkdir(parents=True, exist_ok=True)
        paths.projects.mkdir(exist_ok=True)
        paths.prompts.mkdir(exist_ok=True)
        paths.pins.mkdir(exist_ok=True)
        paths.tasks.mkdir(exist_ok=True)
        paths.mounts.mkdir(exist_ok=True)
        paths.mount_indexes.mkdir(parents=True, exist_ok=True)
        paths.connectors.mkdir(exist_ok=True)
        paths.knowledge_bases.mkdir(exist_ok=True)
        paths.logs.mkdir(exist_ok=True)
        paths.stats.mkdir(exist_ok=True)
        (paths.stats / "daily").mkdir(exist_ok=True)
        if not paths.config.exists():
            paths.config.write_text(
                yaml.safe_dump(
                    {
                        "version": 1,
                        "home": {"name": "alcove"},
                    },
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
        return cls(root_path)

    @classmethod
    def load(cls, root: Path | str | None = None) -> "AlcoveHome":
        root_path = Path(root).expanduser() if root is not None else cls.default_root()
        return cls(root_path.resolve())

    def paths(self) -> AlcoveHomePaths:
        return AlcoveHomePaths(
            root=self.root,
            config=self.root / "config.yml",
            okf=self.root / "okf",
            projects=self.root / "projects",
            prompts=self.root / "prompts",
            pins=self.root / "pins",
            tasks=self.root / "tasks",
            mounts=self.root / "mounts",
            mount_indexes=self.root / "mounts" / "indexes",
            connectors=self.root / "connectors",
            knowledge_bases=self.root / "knowledge-bases",
            logs=self.root / "logs",
            stats=self.root / "stats",
        )

    def load_config(self) -> dict[str, Any]:
        if not self.paths().config.is_file():
            return {}
        return yaml.safe_load(self.paths().config.read_text(encoding="utf-8")) or {}

    def register_knowledge_base(
        self,
        name: str,
        path: Path | str,
    ) -> KnowledgeBaseRecord:
        paths = self.paths()
        paths.knowledge_bases.mkdir(parents=True, exist_ok=True)
        slug = _slug(name)
        kb_path = Path(path).expanduser().resolve()
        config_path = paths.knowledge_bases / f"{slug}.yml"
        config = KnowledgeBaseConfig(version=1, name=slug, path=compact_user_path(kb_path))
        config_path.write_text(
            yaml.safe_dump(config.model_dump(), sort_keys=False),
            encoding="utf-8",
        )
        return KnowledgeBaseRecord(name=slug, path=kb_path, config_path=config_path)

    def list_knowledge_bases(self) -> list[KnowledgeBaseRecord]:
        records = []
        for path in sorted(self.paths().knowledge_bases.glob("*.yml")):
            record = self._read_knowledge_base(path)
            if record is not None:
                records.append(record)
        return records

    def get_knowledge_base(self, name: str) -> KnowledgeBaseRecord:
        path = self.paths().knowledge_bases / f"{_slug(name)}.yml"
        record = self._read_knowledge_base(path)
        if record is None:
            raise FileNotFoundError(f"Knowledge base not registered: {name}")
        return record

    def _read_knowledge_base(self, path: Path) -> KnowledgeBaseRecord | None:
        if not path.is_file():
            return None
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            return None
        try:
            config = KnowledgeBaseConfig.model_validate(data)
        except ValidationError:
            return None
        return KnowledgeBaseRecord(
            name=config.name or path.stem,
            path=Path(config.path).expanduser().resolve(),
            config_path=path,
        )


def _slug(value: str) -> str:
    return str(value or "").strip().lower().replace(" ", "_")
