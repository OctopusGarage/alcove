from __future__ import annotations

import re
from typing import Any

from alcove.connector_display import connector_display_id
from alcove.external_index import ExternalItemReference


SECRET_LIKE_RE = re.compile(
    r"(?i)(api[_\s-]?key|apikey|password|passwd|密码|token|secret|access[_\s-]?key|bearer|sk-[a-z0-9][a-z0-9_-]{12,})"
)


class ExternalIndexedItemPresenter:
    """User-facing projection for one indexed connector or mount item."""

    def __init__(self, ref: ExternalItemReference, item: dict[str, Any]) -> None:
        self.ref = ref
        self.item = item

    @property
    def title(self) -> str:
        return str(self.item.get("title") or self.ref.relative_path)

    @property
    def text(self) -> str:
        return str(self.item.get("text") or "")

    def display_id(self) -> str:
        if self.ref.kind != "connector":
            return self.ref.path
        return connector_display_id(
            self.ref.source_id,
            title=self.title,
            relative_path=self.ref.relative_path,
        )

    def display_label(self) -> str:
        if self.ref.kind == "connector" and self.ref.source_id == "apple-notes":
            return self.title or "Apple Notes item"
        return self.title or self.display_id()

    def origin_label(self) -> str:
        if self.ref.kind == "connector" and self.ref.source_id == "apple-notes":
            folder = str(self.item.get("folder_path") or "").strip()
            return f"Apple Notes / {folder}" if folder else "Apple Notes"
        return str(
            self.item.get("connector_name") or self.item.get("mount_name") or self.ref.source_id
        )

    def source_label(self) -> str:
        connector_name = str(
            self.item.get("connector_name") or self.item.get("mount_name") or self.ref.source_id
        ).strip()
        account = str(self.item.get("account") or "").strip()
        folder = str(self.item.get("folder_path") or "").strip()
        context = " / ".join(dict.fromkeys(part for part in [account, folder] if part))
        if context:
            return f"{connector_name} · {context}"
        return connector_name or self.origin_label()

    def fetch_command(self) -> str:
        return f"alcove connector fetch {self.ref.path} --json"

    def connector_fields(self) -> dict[str, str]:
        if self.ref.kind != "connector":
            return {}
        return {
            "display_id": self.display_id(),
            "display_label": self.display_label(),
            "source_id": self.ref.source_id,
            "source_label": self.source_label(),
            "origin_label": self.origin_label(),
            "fetch_ref": self.ref.path,
            "fetch_command": self.fetch_command(),
        }

    def dashboard_connector_fields(self) -> dict[str, Any]:
        if self.ref.kind != "connector":
            return {}
        return {
            "display_id": self.display_id(),
            "display_label": self.display_label(),
            "source_id": self.ref.source_id,
            "source_label": self.source_label(),
            "origin_label": self.origin_label(),
            "fetch_ref_available": True,
            "fetch_command_pattern": "alcove connector fetch <fetch_ref> --json",
        }

    def public_item(self) -> dict[str, Any]:
        public = dict(self.item)
        public.pop("path", None)
        return public

    def safe_text(self, max_chars: int | None = None) -> str:
        if self.is_secret_like():
            return "[redacted: secret-like connector content]"
        if max_chars is None:
            return self.text
        return self.text[:max_chars]

    def information_quality(self) -> dict[str, Any]:
        if self.ref.kind != "connector" or self.ref.source_id != "apple-notes":
            return {}
        text = self.text.strip()
        if not text:
            return {
                "status": "empty",
                "reason": "No plaintext was available in the indexed note.",
            }
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        identifier_lines = [line for line in lines if _looks_identifier_heavy(line)]
        natural_lines = [line for line in lines if line not in identifier_lines]
        identifier_ratio = len(identifier_lines) / len(lines) if lines else 0
        natural_preview = " ".join(natural_lines).strip()
        if lines and identifier_ratio >= 0.7:
            return {
                "status": "low-information",
                "reason": "Most plaintext lines look like identifiers or hashes.",
            }
        if identifier_lines and len(natural_lines) <= 1 and len(natural_preview) < 24:
            return {
                "status": "low-information",
                "reason": "The note is mostly identifiers with only a short title-like natural-language fragment.",
            }
        if len(text) < 40 and _looks_identifier_heavy(text):
            return {
                "status": "low-information",
                "reason": "The plaintext is short and identifier-heavy.",
            }
        return {
            "status": "ok",
            "reason": "Plaintext contains natural-language preview content.",
        }

    def is_secret_like(self) -> bool:
        if self.ref.kind != "connector" or self.ref.source_id != "apple-notes":
            return False
        return bool(
            SECRET_LIKE_RE.search(
                "\n".join(
                    str(part)
                    for part in (
                        self.item.get("title"),
                        self.item.get("folder_path"),
                        self.text,
                    )
                    if part
                )
            )
        )


def _looks_identifier_heavy(text: str) -> bool:
    value = re.sub(r"\s+", "", str(text or ""))
    if not value:
        return False
    if re.fullmatch(r"[a-fA-F0-9]{12,}", value):
        return True
    digit_ratio = sum(character.isdigit() for character in value) / len(value)
    return (
        len(value) >= 12
        and re.fullmatch(r"[A-Za-z0-9_:/%.-]+", value) is not None
        and (digit_ratio >= 0.2 or any(marker in value for marker in ("_", ":", "/", "%")))
    )
