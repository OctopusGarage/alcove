from __future__ import annotations

from pathlib import Path
from subprocess import CompletedProcess
from types import SimpleNamespace

from alcove.blog_capture import BlogCaptureModule


def _source(*, adapter: str = "clipsmith", kb: str = "kb"):
    return SimpleNamespace(
        id="openai",
        capture=SimpleNamespace(
            kb=kb,
            adapter=adapter,
            inbox_path="inbox/openai",
        ),
    )


def _article():
    return SimpleNamespace(url="https://example.com/post")


def test_blog_capture_requires_kb() -> None:
    host = SimpleNamespace()

    result = BlogCaptureModule(host).capture(_source(kb=""), _article())

    assert result == {
        "status": "failed",
        "error": "capture.kb is required when capture is enabled",
    }


def test_blog_capture_marks_unknown_adapter_pending() -> None:
    host = SimpleNamespace()

    result = BlogCaptureModule(host).capture(_source(adapter="custom"), _article())

    assert result == {
        "status": "pending",
        "adapter": "custom",
        "reason": "capture adapter is not implemented",
    }


def test_blog_capture_reports_missing_clipsmith_runtime(tmp_path, monkeypatch) -> None:
    host = SimpleNamespace(
        home=SimpleNamespace(
            get_knowledge_base=lambda _name: SimpleNamespace(path=tmp_path / "kb")
        ),
        _clipsmith_web_skill_dir=lambda: None,
    )
    monkeypatch.setattr("alcove.blog_capture.shutil.which", lambda _name: None)

    result = BlogCaptureModule(host).capture(_source(), _article())

    assert result["status"] == "pending"
    assert result["adapter"] == "clipsmith"
    assert "clipsmith-web skill" in result["reason"]
    assert "https://example.com/post" in result["capture_command"]


def test_blog_capture_runs_validate_and_sink_sequence(tmp_path, monkeypatch) -> None:
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    bundle_dir = tmp_path / "bundle"
    sink_dir = tmp_path / "kb" / "inbox" / "openai" / "post"
    commands: list[list[str]] = []

    def fake_run_command(command, *, cwd: Path | None, timeout: int):
        commands.append(command)
        if command[:3] == ["npx", "tsx", "scripts/run.ts"]:
            assert cwd == skill_dir
            assert timeout == 180
            return CompletedProcess(command, 0, stdout=f'{{"bundle_dir":"{bundle_dir}"}}')
        if command[:2] == ["clipsmith", "validate-bundle"]:
            assert cwd is None
            assert timeout == 60
            return CompletedProcess(command, 0, stdout="{}")
        if command[:3] == ["clipsmith", "sink", "directory"]:
            assert cwd is None
            assert timeout == 60
            return CompletedProcess(command, 0, stdout=f'{{"path":"{sink_dir}"}}')
        raise AssertionError(f"unexpected command: {command}")

    host = SimpleNamespace(
        home=SimpleNamespace(
            get_knowledge_base=lambda _name: SimpleNamespace(path=tmp_path / "kb")
        ),
        captures_root=tmp_path / "captures",
        _clipsmith_web_skill_dir=lambda: skill_dir,
        _run_command=fake_run_command,
    )
    monkeypatch.setattr("alcove.blog_capture.shutil.which", lambda name: f"/bin/{name}")

    result = BlogCaptureModule(host).capture(_source(), _article())

    assert result == {
        "status": "captured",
        "adapter": "clipsmith",
        "bundle_dir": str(bundle_dir),
        "inbox_path": str(sink_dir),
    }
    assert commands == [
        [
            "npx",
            "tsx",
            "scripts/run.ts",
            "--url",
            "https://example.com/post",
            "--output_dir",
            str(tmp_path / "captures" / "openai"),
        ],
        ["clipsmith", "validate-bundle", str(bundle_dir), "--json"],
        [
            "clipsmith",
            "sink",
            "directory",
            str(bundle_dir),
            str(tmp_path / "kb/inbox/openai"),
            "--json",
        ],
    ]
