from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_controlled_shift_followup_cap8 import (  # noqa: E402
    DATASETS,
    FRESH_SEEDS,
    PRIMARY_BUDGET,
    primary_inference,
)
from prepare_controlled_shift_followup_preregistration import (  # noqa: E402
    FOLLOWUP_SEEDS,
    build_payload,
    load_json,
)


def test_followup_preregistration_records_non_rescue_boundary() -> None:
    parent_path = ROOT / "prereg_controlled_shift.json"
    result_path = ROOT / "maintrack" / "CONTROLLED_SHIFT_RESULT_SUMMARY.json"
    payload = build_payload(
        load_json(parent_path),
        load_json(result_path),
        parent_path=parent_path,
        result_path=result_path,
    )

    assert payload["status"] == "locked_before_claim_grade_runs"
    assert payload["data_policy"]["followup_seeds"] == FOLLOWUP_SEEDS
    assert payload["data_policy"]["seed_blocks_disjoint"]
    assert payload["real_study"]["seeds"] == FOLLOWUP_SEEDS
    assert (
        payload["real_study"]["evidence_allocation"][
            "primary_total_contract_observation_budget"
        ]
        == PRIMARY_BUDGET
    )
    assert payload["calibration_result"]["failed_primary_gates"] == ["usefulness"]
    assert payload["calibration_result"]["may_not_be_pooled_with_followup"]
    assert "not a retroactive pass" in payload["non_rescue_boundary"]


def test_followup_primary_inference_uses_new_seed_block() -> None:
    rows = []
    for seed in FRESH_SEEDS:
        for dataset_index, dataset in enumerate(DATASETS):
            point_violation = seed < 141 and dataset_index == 0
            vector_safe = dataset_index < 2
            common_safe = dataset_index == 0
            shared = {
                "seed": seed,
                "dataset": dataset,
                "certified_common_radius": 1.05,
                "limiting_coordinates": ["source::0"],
                "heldout_stress_violation": False,
            }
            rows.extend(
                [
                    {
                        **shared,
                        "rule": "external_oracle",
                        "deployed": True,
                        "safe": True,
                        "violation": False,
                    },
                    {
                        **shared,
                        "rule": "validation_point_selection",
                        "deployed": True,
                        "safe": not point_violation,
                        "violation": point_violation,
                    },
                    {
                        **shared,
                        "rule": "vera_vector_envelope",
                        "deployed": vector_safe,
                        "safe": vector_safe,
                        "violation": False,
                    },
                    {
                        **shared,
                        "rule": "vera_common_radius",
                        "deployed": common_safe,
                        "safe": common_safe,
                        "violation": False,
                    },
                ]
            )

    inference = primary_inference(rows)

    assert inference["paired_reduction"]["passed"]
    assert inference["safety"]["passed"]
    assert inference["usefulness"]["passed"]
    assert inference["vector_advantage"]["passed"]
    assert inference["overall_confirmatory_success"]
    assert inference["safety"]["sentinel_decision_count"] == len(FRESH_SEEDS)
