from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_agent_config_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEX_HOME", raising=False)
