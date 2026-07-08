from __future__ import annotations

from alcove.doctor import DoctorModule
from alcove.workspace import Workspace


def test_doctor_reports_ok_workspace_checks(tmp_path):
    workspace = Workspace.init(tmp_path)

    report = DoctorModule(workspace).check()

    checks = {check["name"]: check for check in report["checks"]}
    assert report["status"] == "ok"
    assert checks["workspace"]["status"] == "ok"
    assert checks["knowledge"]["status"] == "ok"
    assert "pins" not in checks
    assert "tasks" not in checks
    assert "mounts" not in checks
    assert checks["validation"]["status"] == "ok"


def test_doctor_reports_missing_data_path_and_validation_issues(tmp_path):
    workspace = Workspace.init(tmp_path)
    (tmp_path / "todo").rmdir()
    broken = tmp_path / "knowledge" / "concepts" / "broken.md"
    broken.parent.mkdir(parents=True)
    broken.write_text(
        "---\n"
        "type: Knowledge Concept\n"
        "title: Broken\n"
        "source_refs:\n"
        "  - /sources/missing.md\n"
        "---\n"
        "# Broken\n",
        encoding="utf-8",
    )

    report = DoctorModule(workspace).check()

    checks = {check["name"]: check for check in report["checks"]}
    assert report["status"] == "issues"
    assert checks["todo"]["status"] == "missing"
    assert checks["validation"]["status"] == "issues"
    assert checks["validation"]["count"] >= 1
