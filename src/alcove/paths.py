from __future__ import annotations

from pathlib import Path
import re


USER_HOME_PATTERN = re.compile(r"(?<![\w.-])(?:/Users|/home)/[^/\s:]+")


def compact_user_path(path: Path | str) -> str:
    """Render paths under the current user home as ~/... for persisted config."""
    value = str(path)
    home = str(Path.home())
    if value == home:
        return "~"
    prefix = f"{home.rstrip('/')}/"
    if value.startswith(prefix):
        return f"~/{value[len(prefix) :]}"
    return value


def compact_user_paths_in_text(text: str) -> str:
    """Render user-home absolute paths inside free text as ~/... ."""
    home = str(Path.home())
    compacted = text.replace(home, "~")
    return USER_HOME_PATTERN.sub("~", compacted)
