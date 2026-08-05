from __future__ import annotations

import json

import pytest

from alcove.application import AlcoveApplication
from alcove.home import AlcoveHome
from alcove.radars import RadarModule
from alcove.runtime import AlcoveRuntime


def _write_run(home, *, radar_id="custom", day="2026-08-05"):
    root = home.root / "radars"
    run_path = root / "runs" / radar_id / day / "run.json"
    scored_path = root / "cache" / radar_id / day / "scored.json"
    okf_path = root / "okf" / radar_id / "index.md"
    report_path = root / "reports" / radar_id / f"{day}.md"
    for path in (run_path, scored_path, report_path, okf_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    run_path.write_text(
        json.dumps(
            {
                "schema": "alcove/radar-run/v1",
                "id": radar_id,
                "run_id": f"{radar_id}:{day}",
                "date": day,
                "reports": {"md": str(report_path)},
            }
        ),
        encoding="utf-8",
    )
    scored_path.write_text(
        json.dumps(
            [
                {
                    "source_id": "fixture",
                    "adapter": "fixture",
                    "title": "Useful Radar Signal",
                    "url": "https://example.test/signal",
                    "summary": "A durable signal worth tracking.",
                    "score": 0.91,
                    "score_reason": "matched profile",
                    "included": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    return run_path


def test_radar_proposals_preserve_provenance_and_are_idempotent(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    _write_run(home)
    module = RadarModule(home)

    first = module.proposal_generate("custom", "2026-08-05", action_type="idea")
    second = module.proposal_generate("custom", "2026-08-05", action_type="idea")

    assert first["mutation"] == "proposal_storage_only"
    assert first["count"] == second["count"] == 1
    proposal = first["proposals"][0]
    assert proposal["status"] == "pending"
    assert proposal["provenance"]["run_id"] == "custom:2026-08-05"
    assert proposal["provenance"]["scored_path"].endswith(
        "radars/cache/custom/2026-08-05/scored.json"
    )
    assert proposal["source_url"] == "https://example.test/signal"
    assert (home.root / "radars" / "proposals" / f"{proposal['id']}.json").is_file()


def test_radar_proposal_acceptance_uses_existing_idea_contract_and_is_idempotent(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    _write_run(home)
    module = RadarModule(home)
    proposal = module.proposal_generate("custom", "2026-08-05", action_type="idea")["proposals"][0]
    app = AlcoveApplication(AlcoveRuntime.from_modules(home=home))

    accepted = app.global_home.radar_proposal_accept_payload(proposal["id"])
    repeated = app.global_home.radar_proposal_accept_payload(proposal["id"])

    assert accepted["status"] == "accepted"
    assert accepted["idempotent"] is False
    assert accepted["target"]["type"] == "idea"
    assert repeated["idempotent"] is True
    assert len(app.global_home.idea_list_payload()["ideas"]) == 1


@pytest.mark.parametrize("action_type", ["task", "prompt"])
def test_radar_proposal_acceptance_routes_task_and_prompt_contracts(tmp_path, action_type):
    home = AlcoveHome.init(tmp_path / ".alcove")
    _write_run(home)
    proposal = RadarModule(home).proposal_generate("custom", "2026-08-05", action_type=action_type)[
        "proposals"
    ][0]
    app = AlcoveApplication(AlcoveRuntime.from_modules(home=home))

    accepted = app.global_home.radar_proposal_accept_payload(proposal["id"])
    repeated = app.global_home.radar_proposal_accept_payload(proposal["id"])

    assert accepted["target"]["type"] == action_type
    assert repeated["idempotent"] is True


def test_radar_proposal_lifecycle_supports_deferred_rejected_and_duplicate(tmp_path):
    home = AlcoveHome.init(tmp_path / ".alcove")
    _write_run(home)
    module = RadarModule(home)
    first = module.proposal_generate("custom", "2026-08-05", action_type="task")["proposals"][0]
    duplicate_run = home.root / "radars" / "runs" / "custom" / "2026-08-06" / "run.json"
    duplicate_run.parent.mkdir(parents=True)
    duplicate_run.write_text(
        json.dumps({"id": "custom", "run_id": "custom:2026-08-06", "date": "2026-08-06"}),
        encoding="utf-8",
    )
    scored = home.root / "radars" / "cache" / "custom" / "2026-08-06" / "scored.json"
    scored.parent.mkdir(parents=True)
    scored.write_text(
        json.dumps(
            [
                {
                    "title": "Useful Radar Signal",
                    "url": "https://example.test/signal",
                    "included": True,
                }
            ]
        ),
        encoding="utf-8",
    )
    duplicate = module.proposal_generate("custom", "2026-08-06", action_type="task")["proposals"][0]

    assert first["status"] == "pending"
    assert duplicate["status"] == "duplicate"
    assert duplicate["duplicate_of"] == first["id"]
    assert module.proposal_resolve(first["id"], "deferred")["status"] == "deferred"
    assert module.proposal_resolve(duplicate["id"], "rejected")["status"] == "rejected"
