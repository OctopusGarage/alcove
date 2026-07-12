from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from alcove.connector_sources import ConnectorSourceRegistry, DEFAULT_TTL_HOURS
from alcove.errors import AlcoveError
from alcove.external_index import ExternalIndexItemFactory, ExternalIndexStore
from alcove.home import AlcoveHome
from alcove.paths import compact_user_path
from alcove.runtime import AlcoveRuntime
from alcove.taxonomy import load_taxonomy, normalize_tag
from alcove.workspace import Workspace

from .okf_index import write_connector_okf_index, write_connector_okf_sources


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass(frozen=True)
class GitHubStarsImportRequest:
    export_file: str
    tags: list[str] = field(default_factory=list)
    source_id: str = ""


@dataclass(frozen=True)
class GitHubStarsUrlImportRequest:
    source: str
    export_file: str = ""
    tags: list[str] = field(default_factory=list)
    limit: int = 0
    max_pages: int = 0


class GitHubStarsConnector:
    connector_id = "github-stars"

    def __init__(self, workspace: Workspace | None = None, home: AlcoveHome | None = None) -> None:
        self.runtime = AlcoveRuntime.from_modules(workspace=workspace, home=home)
        self.workspace = self.runtime.workspace
        self.home = self.runtime.home
        self.taxonomy = load_taxonomy(self.runtime.taxonomy_root)
        self.connector_dir = self.runtime.connectors_root / self.connector_id
        self.index_path = self.connector_dir / "index.json"
        self.index_store = ExternalIndexStore(self.runtime.connectors_root)
        self._last_page_etags: dict[int, str] = {}

    def import_export(self, request: GitHubStarsImportRequest) -> dict:
        export_file = Path(request.export_file).expanduser().resolve()
        if not export_file.is_file():
            raise FileNotFoundError(f"GitHub stars export file not found: {export_file}")
        data = json.loads(export_file.read_text(encoding="utf-8"))
        repos = self._repositories(data)
        tags = self._normalize_tags(request.tags)
        items: list[dict] = []
        skipped = 0
        for raw in repos:
            if not isinstance(raw, dict):
                skipped += 1
                continue
            item = self._item(raw, export_file, tags, source_id=request.source_id)
            if item is None:
                skipped += 1
                continue
            items.append(item)
        self._save_index(items, export_file, source_id=request.source_id)
        return {
            "connector": self.connector_id,
            "export_file": compact_user_path(export_file),
            "index_path": compact_user_path(self.index_path),
            "scanned": len(items),
            "skipped": skipped,
            "items": items,
        }

    def import_url(self, request: GitHubStarsUrlImportRequest) -> dict:
        username = self._username_from_source(request.source)
        export_file = self._export_path(username, request.export_file)
        old_repos = self._read_export(export_file)
        repos = self._fetch_starred_repositories(
            username,
            limit=request.limit,
            max_pages=request.max_pages,
        )
        diff = self._diff_repositories(old_repos, repos)
        export_file.parent.mkdir(parents=True, exist_ok=True)
        export_file.write_text(
            json.dumps(repos, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report = self.import_export(
            GitHubStarsImportRequest(
                export_file=str(export_file),
                tags=request.tags,
                source_id=username.lower(),
            )
        )
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_github_stars(
            source_id=username.lower(),
            source=request.source,
            username=username,
            tags=self._normalize_tags(request.tags),
            export_file=export_file,
            index_path=self.index_path,
            item_count=len(repos),
            etag=self._last_page_etags.get(1, ""),
        )
        self._write_okf_sources_from_registry()
        return {
            **report,
            "source": request.source,
            "username": username,
            "exported": len(repos),
            "diff": diff,
        }

    def refresh_sources(
        self,
        *,
        stale_only: bool = False,
        source_id: str = "",
        now: str | None = None,
        default_ttl_hours: int = DEFAULT_TTL_HOURS,
    ) -> dict[str, Any]:
        registry = ConnectorSourceRegistry(self.workspace, home=self.home)
        sources = registry.list(self.connector_id)
        if source_id:
            sources = [source for source in sources if str(source.get("id") or "") == source_id]
        if stale_only:
            stale_ids = {
                str(source.get("id") or "")
                for source in registry.stale_sources(
                    connector=self.connector_id,
                    now=now,
                    default_ttl_hours=default_ttl_hours,
                )
            }
            sources = [source for source in sources if str(source.get("id") or "") in stale_ids]

        reports = []
        for source in sources:
            try:
                report = self._refresh_source(source)
            except Exception as exc:
                report = self._refresh_error(source, exc)
            reports.append(
                {
                    "connector": self.connector_id,
                    "id": str(source.get("id") or report.get("username") or "").lower(),
                    "status": report["status"],
                    "exported": report["exported"],
                    "scanned": report["scanned"],
                    "skipped": report["skipped"],
                    "export_file": report["export_file"],
                    "index_path": report["index_path"],
                    "diff": report["diff"],
                    "error": report.get("error", ""),
                }
            )
        return {
            "connector": self.connector_id,
            "refreshed": sum(1 for report in reports if report["status"] == "refreshed"),
            "skipped": sum(1 for report in reports if report["status"] == "not_modified"),
            "errors": sum(1 for report in reports if report["status"] == "error"),
            "sources": reports,
        }

    def _refresh_source(self, source: dict[str, Any]) -> dict[str, Any]:
        source_text = str(source.get("source") or source.get("username") or "")
        username = self._username_from_source(source_text)
        export_file = self._export_path(username, str(source.get("export_file") or ""))
        tags = [str(tag) for tag in source.get("tags") or []]
        old_repos = self._read_export(export_file)
        refresh = source.get("refresh") if isinstance(source.get("refresh"), dict) else {}
        fetch = self._fetch_starred_repositories_if_changed(
            username,
            etag=str(refresh.get("etag") or ""),
        )
        if fetch["not_modified"]:
            diff = self._not_modified_diff(old_repos)
            self._write_okf_index_from_current_index()
            ConnectorSourceRegistry(self.workspace, home=self.home).upsert_github_stars(
                source_id=str(source.get("id") or username.lower()),
                source=source_text,
                username=username,
                tags=self._normalize_tags(tags),
                export_file=export_file,
                index_path=self.index_path,
                item_count=len(old_repos),
                changed_at=str(refresh.get("last_changed_at") or ""),
                etag=str(fetch.get("etag") or refresh.get("etag") or ""),
            )
            self._write_okf_sources_from_registry()
            return {
                "status": "not_modified",
                "username": username,
                "exported": len(old_repos),
                "scanned": len(old_repos),
                "skipped": 0,
                "export_file": compact_user_path(export_file),
                "index_path": compact_user_path(self.index_path),
                "diff": diff,
            }

        repos = [item for item in fetch["repos"] if isinstance(item, dict)]
        diff = self._diff_repositories(old_repos, repos)
        export_file.parent.mkdir(parents=True, exist_ok=True)
        export_file.write_text(
            json.dumps(repos, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report = self.import_export(
            GitHubStarsImportRequest(
                export_file=str(export_file),
                tags=tags,
                source_id=str(source.get("id") or username.lower()).lower(),
            )
        )
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_github_stars(
            source_id=str(source.get("id") or username.lower()),
            source=source_text,
            username=username,
            tags=self._normalize_tags(tags),
            export_file=export_file,
            index_path=self.index_path,
            item_count=len(repos),
            etag=str(fetch.get("etag") or ""),
        )
        self._write_okf_sources_from_registry()
        return {
            **report,
            "status": "refreshed",
            "username": username,
            "exported": len(repos),
            "diff": diff,
        }

    def _refresh_error(self, source: dict[str, Any], exc: Exception) -> dict[str, Any]:
        source_text = str(source.get("source") or source.get("username") or "")
        username = self._username_from_source(source_text)
        export_file = self._export_path(username, str(source.get("export_file") or ""))
        old_repos = self._read_export(export_file)
        refresh = source.get("refresh") if isinstance(source.get("refresh"), dict) else {}
        ConnectorSourceRegistry(self.workspace, home=self.home).upsert_github_stars(
            source_id=str(source.get("id") or username.lower()),
            source=source_text,
            username=username,
            tags=[str(tag) for tag in source.get("tags") or []],
            export_file=export_file,
            index_path=self.index_path,
            item_count=len(old_repos) or _int_value(refresh.get("item_count"), 0),
            changed_at=str(refresh.get("last_changed_at") or ""),
            status="error",
            error=str(exc),
            etag=str(refresh.get("etag") or ""),
        )
        self._write_okf_sources_from_registry()
        return {
            "status": "error",
            "username": username,
            "exported": len(old_repos),
            "scanned": len(old_repos),
            "skipped": 0,
            "export_file": compact_user_path(export_file),
            "index_path": compact_user_path(self.index_path),
            "diff": self._not_modified_diff(old_repos),
            "error": str(exc),
        }

    def _repositories(self, data: object) -> list:
        if isinstance(data, list):
            return data
        if not isinstance(data, dict):
            return []
        for key in ("repositories", "repos", "items", "nodes"):
            value = data.get(key)
            if isinstance(value, list):
                return value
        return []

    def _read_export(self, export_file: Path) -> list[dict[str, Any]]:
        if not export_file.is_file():
            return []
        try:
            data = json.loads(export_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return []
        return [item for item in self._repositories(data) if isinstance(item, dict)]

    def _diff_repositories(
        self,
        old_repos: list[dict[str, Any]],
        new_repos: list[dict[str, Any]],
    ) -> dict[str, Any]:
        old_by_key = {self._repo_key(repo): repo for repo in old_repos if self._repo_key(repo)}
        new_by_key = {self._repo_key(repo): repo for repo in new_repos if self._repo_key(repo)}
        added = [key for key in new_by_key if key not in old_by_key]
        removed = [key for key in old_by_key if key not in new_by_key]
        updated = [
            key
            for key in new_by_key
            if key in old_by_key
            and self._repo_signature(new_by_key[key]) != self._repo_signature(old_by_key[key])
        ]
        unchanged = len(
            [
                key
                for key in new_by_key
                if key in old_by_key
                and self._repo_signature(new_by_key[key]) == self._repo_signature(old_by_key[key])
            ]
        )
        return {
            "added": added,
            "removed": removed,
            "updated": updated,
            "unchanged": unchanged,
        }

    def _not_modified_diff(self, repos: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "added": [],
            "removed": [],
            "updated": [],
            "unchanged": len([repo for repo in repos if self._repo_key(repo)]),
        }

    def _repo_key(self, raw: dict[str, Any]) -> str:
        return self._string(raw, "full_name", "fullName", "nameWithOwner")

    def _repo_signature(self, raw: dict[str, Any]) -> str:
        return json.dumps(raw, ensure_ascii=False, sort_keys=True, default=str)

    def _item(
        self,
        raw: dict,
        export_file: Path,
        tags: list[str],
        *,
        source_id: str = "",
    ) -> dict | None:
        full_name = self._string(raw, "full_name", "fullName", "nameWithOwner")
        url = self._string(raw, "html_url", "url")
        if not full_name or not url:
            return None
        description = self._string(raw, "description")
        language = self._language(raw)
        topics = self._topics(raw)
        item_tags = self._normalize_tags([*tags, *topics])
        stars = raw.get("stargazers_count", raw.get("stargazerCount", ""))
        text_parts = [
            full_name,
            description,
            language,
            " ".join(topics),
            f"stars: {stars}" if stars != "" else "",
        ]
        return ExternalIndexItemFactory.connector_item(
            connector_id=self.connector_id,
            connector_name="GitHub Stars",
            item_type="GitHub Star",
            title=full_name,
            account="github",
            folder_path=language,
            path=compact_user_path(export_file),
            resource=url,
            relative_path=self._relative_path(source_id, full_name),
            text="\n".join(part for part in text_parts if part),
            tags=item_tags,
            status="active",
            indexed_at=now_iso(),
            extra={
                "stars": stars,
                "language": language,
                "updated_at": self._string(raw, "updated_at", "updatedAt"),
                **({"source_id": source_id} if source_id else {}),
            },
        )

    def _save_index(self, items: list[dict], export_file: Path, *, source_id: str = "") -> None:
        self.connector_dir.mkdir(parents=True, exist_ok=True)
        compact_export_file = compact_user_path(export_file)
        if source_id:
            items = self._merged_source_items(
                source_id=source_id,
                export_file=compact_export_file,
                items=items,
            )
        indexed_at = now_iso()
        self.index_store.write_connector_index(
            self.connector_id,
            {
                "schema_version": 1,
                "connector": self.connector_id,
                "export_file": compact_export_file,
                "indexed_at": indexed_at,
                "items": items,
            },
        )
        self._write_okf_index(items, generated_at=indexed_at)

    def _write_okf_index_from_current_index(self) -> None:
        payload = self.index_store.read_file(self.index_path)
        if payload is None or not isinstance(payload.get("items"), list):
            self._write_okf_index([], generated_at=now_iso())
            return
        items = [item for item in payload["items"] if isinstance(item, dict)]
        self._write_okf_index(items, generated_at=str(payload.get("indexed_at") or now_iso()))

    def _write_okf_index(self, items: list[dict], *, generated_at: str) -> None:
        write_connector_okf_index(
            connector_dir=self.connector_dir,
            connector_id=self.connector_id,
            connector_name="GitHub Stars",
            items=items,
            generated_at=generated_at,
        )

    def _write_okf_sources_from_registry(self) -> None:
        sources = ConnectorSourceRegistry(self.workspace, home=self.home).list(self.connector_id)
        write_connector_okf_sources(
            connector_dir=self.connector_dir,
            connector_id=self.connector_id,
            connector_name="GitHub Stars",
            sources=sources,
            generated_at=now_iso(),
        )

    def _merged_source_items(
        self,
        *,
        source_id: str,
        export_file: str,
        items: list[dict],
    ) -> list[dict]:
        payload = self.index_store.read_file(self.index_path)
        existing = []
        if payload is not None and isinstance(payload.get("items"), list):
            existing = [item for item in payload["items"] if isinstance(item, dict)]
        return [
            item
            for item in existing
            if not self._belongs_to_source(item, source_id=source_id, export_file=export_file)
        ] + items

    def _belongs_to_source(self, item: dict, *, source_id: str, export_file: str) -> bool:
        item_source_id = str(item.get("source_id") or "")
        if item_source_id:
            return item_source_id == source_id
        return str(item.get("path") or "") == export_file

    def _relative_path(self, source_id: str, full_name: str) -> str:
        if source_id:
            return f"{source_id}/{full_name.strip('/')}"
        return full_name

    def _language(self, raw: dict) -> str:
        value = raw.get("language")
        if value:
            return str(value)
        value = raw.get("primaryLanguage")
        if isinstance(value, dict):
            return str(value.get("name") or "")
        return ""

    def _topics(self, raw: dict) -> list[str]:
        value = raw.get("topics")
        if isinstance(value, list):
            return [str(item) for item in value if item]
        value = raw.get("repositoryTopics")
        if isinstance(value, dict):
            nodes = value.get("nodes")
            if isinstance(nodes, list):
                topics = []
                for node in nodes:
                    if not isinstance(node, dict):
                        continue
                    topic = node.get("topic")
                    if isinstance(topic, dict) and topic.get("name"):
                        topics.append(str(topic["name"]))
                return topics
        return []

    def _string(self, raw: dict, *keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if value is not None:
                return str(value)
        return ""

    def _normalize_tags(self, tags: list[str]) -> list[str]:
        normalized = {normalize_tag(tag, self.taxonomy) for tag in tags}
        return sorted(tag for tag in normalized if tag)

    def _export_path(self, username: str, export_file: str) -> Path:
        if export_file:
            return Path(export_file).expanduser().resolve()
        safe_username = re.sub(r"[^A-Za-z0-9_.-]+", "-", username).strip("-") or "github"
        return (self.connector_dir / "exports" / f"{safe_username.lower()}-starred.json").resolve()

    def _username_from_source(self, source: str) -> str:
        value = str(source or "").strip()
        if not value:
            raise ValueError("GitHub Stars source is required")
        if "://" not in value:
            return self._validate_username(value)
        parsed = urlparse(value)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError(f"Unsupported GitHub Stars URL host: {parsed.netloc}")
        parts = [part for part in parsed.path.split("/") if part]
        if not parts:
            raise ValueError(f"GitHub Stars URL has no username: {source}")
        return self._validate_username(parts[0])

    def _validate_username(self, username: str) -> str:
        value = username.strip()
        if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", value):
            raise ValueError(f"Invalid GitHub username: {username}")
        return value

    def _fetch_starred_repositories(
        self,
        username: str,
        *,
        limit: int = 0,
        max_pages: int = 0,
    ) -> list[dict[str, Any]]:
        self._last_page_etags = {}
        repos: list[dict[str, Any]] = []
        per_page = 100
        page = 1
        while True:
            if max_pages and page > max_pages:
                break
            page_items = self._fetch_starred_page(username, page=page, per_page=per_page)
            if not page_items:
                break
            repos.extend(page_items)
            if limit and len(repos) >= limit:
                return repos[:limit]
            if len(page_items) < per_page:
                break
            page += 1
        return repos

    def _fetch_starred_repositories_if_changed(
        self,
        username: str,
        *,
        etag: str = "",
        limit: int = 0,
        max_pages: int = 0,
    ) -> dict[str, Any]:
        if not etag:
            repos = self._fetch_starred_repositories(
                username,
                limit=limit,
                max_pages=max_pages,
            )
            return {
                "not_modified": False,
                "repos": repos,
                "etag": self._last_page_etags.get(1, ""),
            }

        per_page = 100
        first_page = self._fetch_starred_page_response(
            username,
            page=1,
            per_page=per_page,
            etag=etag,
        )
        if first_page["not_modified"]:
            return {
                "not_modified": True,
                "repos": [],
                "etag": first_page["etag"] or etag,
            }

        repos = [item for item in first_page["items"] if isinstance(item, dict)]
        page = 2
        while True:
            if max_pages and page > max_pages:
                break
            page_items = self._fetch_starred_page(username, page=page, per_page=per_page)
            if not page_items:
                break
            repos.extend(page_items)
            if limit and len(repos) >= limit:
                repos = repos[:limit]
                break
            if len(page_items) < per_page:
                break
            page += 1
        return {
            "not_modified": False,
            "repos": repos,
            "etag": first_page["etag"] or etag,
        }

    def _fetch_starred_page(
        self, username: str, *, page: int, per_page: int
    ) -> list[dict[str, Any]]:
        response = self._fetch_starred_page_response(username, page=page, per_page=per_page)
        if response["etag"]:
            self._last_page_etags[page] = str(response["etag"])
        return [item for item in response["items"] if isinstance(item, dict)]

    def _fetch_starred_page_response(
        self,
        username: str,
        *,
        page: int,
        per_page: int,
        etag: str = "",
    ) -> dict[str, Any]:
        url = f"https://api.github.com/users/{username}/starred?per_page={per_page}&page={page}"
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "alcove-github-stars-connector",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if etag:
            headers["If-None-Match"] = etag
        try:
            request = Request(  # noqa: S310 - URL is constructed from a validated GitHub username.
                url,
                headers=headers,
            )
            with urlopen(request, timeout=30) as response:  # noqa: S310
                data = json.loads(response.read().decode("utf-8"))
                response_etag = str(response.headers.get("ETag") or "")
        except HTTPError as exc:
            if exc.code == 304:
                return {
                    "not_modified": True,
                    "items": [],
                    "etag": str(exc.headers.get("ETag") or etag),
                }
            raise AlcoveError(f"GitHub Stars API request failed: HTTP {exc.code}") from exc
        except URLError as exc:
            raise AlcoveError(f"GitHub Stars API request failed: {exc.reason}") from exc
        if not isinstance(data, list):
            raise AlcoveError("GitHub Stars API returned a non-list response")
        return {
            "not_modified": False,
            "items": [item for item in data if isinstance(item, dict)],
            "etag": response_etag,
        }


def _int_value(value: object, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
