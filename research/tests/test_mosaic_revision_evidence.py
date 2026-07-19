from __future__ import annotations

from summarize_mosaic_revision_evidence import outcome


def test_outcome_ignores_an_unestimable_diagnostic() -> None:
    assert outcome(
        {
            "decision": "deploy",
            "diagnostic_estimable": False,
            "false_acceptance": True,
        }
    ) == {
        "deployments": 1,
        "estimable_deployments": 0,
        "diagnostic_violations": 0,
    }


def test_outcome_records_an_estimable_violation() -> None:
    assert outcome(
        {
            "decision": "deploy",
            "diagnostic_estimable": True,
            "false_acceptance": True,
        }
    )["diagnostic_violations"] == 1
