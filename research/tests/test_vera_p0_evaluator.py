from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from vera_p0_evaluator import (  # noqa: E402
    RULES,
    allocation_from_construction,
    candidate_arrays,
    choose_construction_design,
    evaluate_configuration,
    focus_cell_shift,
    validate_shared_metadata,
)


ATTACKERS = ("linear", "boosted_tree")
HELDOUT = "knn_distance"


def raw_arrays(*, edited_errors: np.ndarray, target_harm: np.ndarray) -> dict[str, np.ndarray]:
    environment = np.asarray([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int16)
    source = np.asarray([0, 0, 1, 1, 0, 0, 1, 1], dtype=np.int16)
    target = np.asarray([0, 1, 0, 1, 0, 1, 0, 1], dtype=np.int16)
    arrays: dict[str, np.ndarray] = {}
    for split in ("construction", "certification", "external"):
        arrays[f"target_harm_{split}"] = target_harm.copy()
        arrays[f"source_{split}"] = source.copy()
        arrays[f"environment_{split}"] = environment.copy()
        arrays[f"target_{split}"] = target.copy()
        arrays[f"identity_target_error_{split}"] = np.zeros(8, dtype=np.int8)
        arrays[f"edited_target_error_{split}"] = edited_errors.copy()
        for attacker in ATTACKERS:
            arrays[f"leakage_correct_{split}__{attacker}"] = np.asarray(
                [0, 0, 1, 1, 0, 0, 1, 1], dtype=np.int8
            )
    for split in ("construction", "certification", "external"):
        arrays[f"heldout_leakage_correct_{split}__{HELDOUT}"] = np.asarray(
            [0, 1, 1, 0, 0, 1, 1, 0], dtype=np.int8
        )
    return arrays


def candidate(key: str, errors: np.ndarray, harm: np.ndarray) -> dict[str, object]:
    arrays = raw_arrays(edited_errors=errors, target_harm=harm)
    reference = candidate_arrays(arrays, "certification", ATTACKERS)
    reference[f"heldout::{HELDOUT}"] = arrays[
        f"heldout_leakage_correct_certification__{HELDOUT}"
    ]
    return {
        "candidate": key,
        "method": "test",
        "raw_arrays": arrays,
        "reference": reference,
    }


def test_p0_stress_selection_uses_construction_and_emits_replayable_decisions() -> None:
    candidates = [
        candidate("A", np.ones(8, dtype=np.int8), np.zeros(8, dtype=np.int8)),
        candidate(
            "B",
            np.zeros(8, dtype=np.int8),
            np.asarray([0, 0, 0, 1, 0, 0, 0, 0], dtype=np.int8),
        ),
    ]
    metadata = validate_shared_metadata(candidates, ATTACKERS)
    selected, focus = choose_construction_design(
        candidates,
        metadata["certification"],
        ATTACKERS,
        target_threshold=0.25,
        leakage_threshold=0.75,
        requested_gamma=1.1,
    )
    assert selected == "B"
    probabilities, shift = focus_cell_shift(
        metadata["certification"], focus, requested_gamma=1.1
    )
    assert np.isclose(probabilities.sum(), 1.0)
    assert shift.global_density_ratio_cap <= 1.1 + 1e-12

    construction = candidate_arrays(candidates[1]["raw_arrays"], "construction", ATTACKERS)
    allocation, scores = allocation_from_construction(
        construction,
        shift,
        ATTACKERS,
        target_threshold=0.25,
        leakage_threshold=0.75,
        total_budget=100,
        floor_fraction=0.10,
    )
    assert sum(allocation.values()) == 100
    assert set(scores)
    decisions, details = evaluate_configuration(
        candidates,
        metadata["certification"],
        probabilities,
        shift,
        allocation,
        ATTACKERS,
        fixed_design_candidate=selected,
        rng=np.random.default_rng(7),
        delta=0.1,
        target_threshold=0.25,
        leakage_threshold=0.75,
        gamma_cap=2.0,
        heldout_name=HELDOUT,
    )
    assert set(decisions) == set(RULES)
    assert decisions["always_deploy"]["selected_candidate"] == "B"
    assert len(details) == 2
