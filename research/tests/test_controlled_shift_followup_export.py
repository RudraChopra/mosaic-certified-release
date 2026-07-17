from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from export_controlled_shift_followup_paper_artifacts import (  # noqa: E402
    PRIMARY_ALLOCATION,
    PRIMARY_BUDGET,
    PRIMARY_GAMMA,
    aggregate_budget_rows,
    count_ratio,
    followup_budget_table,
    followup_results_table,
    summarize_rule_rows,
)


RULE_VALUES = {
    "always_deploy": (256, 128, 183),
    "validation_point_selection": (186, 24, 183),
    "iid_ltt": (109, 0, 183),
    "robust_point_estimate": (98, 3, 183),
    "generic_scalar_robust_certificate": (256, 126, 183),
    "vera_fixed_profile": (67, 0, 183),
    "vera_vector_envelope": (59, 0, 183),
    "vera_common_radius": (11, 0, 183),
    "external_oracle": (183, 0, 183),
}


def summary_row(
    *,
    rule: str,
    deploy: int,
    viol: int,
    oracle: int,
    allocation: str = PRIMARY_ALLOCATION,
    budget: int = PRIMARY_BUDGET,
) -> dict[str, object]:
    return {
        "requested_gamma": PRIMARY_GAMMA,
        "total_budget": budget,
        "allocation": allocation,
        "rule": rule,
        "deployment_count": deploy,
        "violation_count": viol,
        "oracle_opportunity_count": oracle,
    }


def test_followup_export_summarizes_primary_table() -> None:
    cap8 = {
        "summaries": [
            summary_row(rule=rule, deploy=deploy, viol=viol, oracle=oracle)
            for rule, (deploy, viol, oracle) in RULE_VALUES.items()
        ]
    }
    primary = {
        "common_radius_distribution_on_vector_deployments": {
            "median": 1.0400009,
        }
    }

    rows = summarize_rule_rows(cap8)
    table = followup_results_table(rows, primary)

    assert "Validation selection & 186/256 (72.7\\%) & 24/186" in table
    assert "VERA vector envelope & 59/256 (23.0\\%) & 0/59" in table
    assert "59/183 (32.2\\%) & 1.04" in table


def test_followup_budget_table_uses_clean_zero_deployment_ratio() -> None:
    cap8 = {
        "summaries": [
            summary_row(
                rule="vera_vector_envelope",
                deploy=0,
                viol=0,
                oracle=183,
                allocation="uniform",
                budget=1000,
            ),
            summary_row(
                rule="vera_common_radius",
                deploy=0,
                viol=0,
                oracle=183,
                allocation="uniform",
                budget=1000,
            ),
        ]
    }

    rows = aggregate_budget_rows(cap8)
    table = followup_budget_table(rows)

    assert count_ratio(0, 0) == "--"
    assert "uniform & 1,000 & 0/183 (0.0\\%) & -- & 0/183" in table
