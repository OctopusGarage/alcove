from __future__ import annotations

import os
from pathlib import Path

from alcove import ai_summary


def test_ai_summary_falls_back_to_claude_when_codex_is_missing(monkeypatch, tmp_path) -> None:
    calls: list[list[str]] = []

    def fake_which(command: str) -> str | None:
        if command == "codex":
            return None
        if command == "claude":
            return "/usr/local/bin/claude"
        return None

    class Completed:
        returncode = 0
        stdout = "Core radar summary\n"
        stderr = ""

    def fake_run(command, input, text, capture_output, timeout, check, cwd):
        calls.append(command)
        assert input == "Summarize this"
        assert cwd == str(tmp_path)
        return Completed()

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(ai_summary.shutil, "which", fake_which)
    monkeypatch.setattr(ai_summary.subprocess, "run", fake_run)

    result = ai_summary.run_ai_summary(
        prompt="Summarize this",
        policy={"provider": "codex", "timeout_seconds": 5},
        cwd=Path(tmp_path),
    )

    assert result == {
        "status": "completed",
        "provider": "claude",
        "summary": "Core radar summary",
        "fallback_from": "codex",
    }
    assert calls == [["/usr/local/bin/claude", "-p"]]


def test_ai_summary_reports_all_missing_candidates(monkeypatch) -> None:
    monkeypatch.setenv("HOME", "/tmp/alcove-empty-home-for-test")
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(ai_summary.shutil, "which", lambda command: None)

    result = ai_summary.run_ai_summary(
        prompt="Summarize this",
        policy={"provider": "codex"},
    )

    assert result["status"] == "skipped"
    assert result["provider"] == "codex"
    assert result["reason"] == "codex is not available; claude is not available"


def test_ai_summary_finds_codex_from_nvm_when_path_is_minimal(monkeypatch, tmp_path) -> None:
    nvm_bin = tmp_path / ".nvm" / "versions" / "node" / "v24.13.1" / "bin"
    nvm_bin.mkdir(parents=True)
    codex = nvm_bin / "codex"
    codex.write_text("#!/bin/sh\n", encoding="utf-8")
    codex.chmod(0o755)
    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = "Codex summary\n"
        stderr = ""

    def fake_run(command, input, text, capture_output, timeout, check, cwd):
        calls.append(command)
        return Completed()

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(ai_summary.shutil, "which", lambda command: None)
    monkeypatch.setattr(ai_summary.subprocess, "run", fake_run)

    result = ai_summary.run_ai_summary(
        prompt="Summarize this",
        policy={"provider": "codex"},
    )

    assert result["status"] == "completed"
    assert result["provider"] == "codex"
    assert result["summary"] == "Codex summary"
    assert calls[0][0] == str(codex)


def test_ai_summary_skips_broken_codex_executable(monkeypatch, tmp_path) -> None:
    codex = tmp_path / "codex"
    claude = tmp_path / "claude"
    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = "Claude summary\n"
        stderr = ""

    def fake_run(command, input, text, capture_output, timeout, check, cwd):
        calls.append(command)
        if command == [str(codex), "--version"]:
            raise OSError("spawn vendor/codex ENOENT")
        if command == [str(claude), "--version"]:
            return Completed()
        return Completed()

    def fake_which(command: str) -> str | None:
        if command == "codex":
            return str(codex)
        if command == "claude":
            return str(claude)
        return None

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("PATH", "")
    monkeypatch.setattr(ai_summary.shutil, "which", fake_which)
    monkeypatch.setattr(ai_summary.subprocess, "run", fake_run)

    result = ai_summary.run_ai_summary(
        prompt="Summarize this",
        policy={"provider": "codex"},
    )

    assert result == {
        "status": "completed",
        "provider": "claude",
        "summary": "Claude summary",
        "fallback_from": "codex",
    }
    assert calls == [
        [str(codex), "--version"],
        [str(claude), "-p"],
    ]


def test_ai_summary_tries_later_codex_path_when_first_is_broken(monkeypatch, tmp_path) -> None:
    broken_bin = tmp_path / "broken" / "bin"
    working_bin = tmp_path / "working" / "bin"
    broken_bin.mkdir(parents=True)
    working_bin.mkdir(parents=True)
    broken_codex = broken_bin / "codex"
    working_codex = working_bin / "codex"
    broken_codex.write_text("#!/bin/sh\n", encoding="utf-8")
    working_codex.write_text("#!/bin/sh\n", encoding="utf-8")
    broken_codex.chmod(0o755)
    working_codex.chmod(0o755)
    calls: list[list[str]] = []

    class Completed:
        returncode = 0
        stdout = "Codex summary\n"
        stderr = ""

    def fake_run(command, input, text, capture_output, timeout, check, cwd):
        calls.append(command)
        if command == [str(broken_codex), "--version"]:
            raise OSError("spawn vendor/codex ENOENT")
        return Completed()

    monkeypatch.setenv("PATH", os.pathsep.join([str(broken_bin), str(working_bin)]))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setattr(ai_summary.subprocess, "run", fake_run)

    result = ai_summary.run_ai_summary(
        prompt="Summarize this",
        policy={"provider": "codex"},
    )

    assert result == {
        "status": "completed",
        "provider": "codex",
        "summary": "Codex summary",
    }
    assert calls == [
        [str(broken_codex), "--version"],
        [str(working_codex), "--version"],
        [str(working_codex), "exec", "--skip-git-repo-check", "--ephemeral", "-"],
    ]
