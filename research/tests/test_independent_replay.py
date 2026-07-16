from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


SCRIPTS = Path(
    "/Volumes/Backups/FARO/github_export/vera-edit-or-abstain/research/scripts"
)
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap8_evaluator import evaluate_configuration_cap  # noqa: E402
from independent_replay import (  # noqa: E402
    ATTACKERS,
    construct_shift,
    envelope_geometry,
    evaluate_configuration,
    integer_allocation,
    infer_primary,
    leakage_curve,
    target_curve,
)
from analyze_controlled_shift_confirmatory import primary_inference  # noqa: E402
from vera_controlled_shift import (  # noqa: E402
    allocate_integer_budget,
    design_controlled_shift_from_fold,
)
from vera_robust_certificate import (  # noqa: E402
    certify_balanced_shift_envelope,
    exact_balanced_leakage_profile_certificate,
    exact_discrete_risk_certificate,
)


def assert_close(left, right, tolerance=1e-12):
    assert np.isclose(left, right, atol=tolerance, rtol=tolerance), (left, right)


def test_curves() -> None:
    harm = np.asarray([-1, 0, 0, 1, 0, 1, -1, 0, 0, 0], dtype=np.int8)
    replay = target_curve(harm, 1.7, 0.01)
    locked = exact_discrete_risk_certificate(
        "target::environment=0",
        harm,
        gamma=1.7,
        failure_probability=0.01,
        support=(-1, 0, 1),
    )
    assert_close(replay["upper_confidence_bound"], locked.upper_confidence_bound)
    assert_close(replay["empirical_robust_risk"], locked.empirical_robust_risk)
    source = np.asarray([0] * 10 + [1] * 10, dtype=np.int8)
    correct = np.asarray([1, 0] * 5 + [0, 0, 1, 0, 0, 0, 1, 0, 0, 0], dtype=np.int8)
    profile = {"0": 1.3, "1": 1.8}
    replay_leakage = leakage_curve(correct, source, profile, 0.01)
    locked_leakage = exact_balanced_leakage_profile_certificate(
        "balanced_leakage::linear",
        correct,
        source,
        source_profile=profile,
        failure_probability=0.01,
    )
    assert_close(
        replay_leakage["upper_confidence_bound"],
        locked_leakage.upper_confidence_bound,
    )
    assert_close(
        replay_leakage["empirical_robust_risk"],
        locked_leakage.empirical_robust_risk,
    )


def test_shift_and_allocation() -> None:
    environment = np.repeat(np.asarray([0, 1], dtype=np.int8), 200)
    source = np.tile(np.asarray([0, 1], dtype=np.int8), 200)
    target = np.tile(np.asarray([0, 0, 1, 1], dtype=np.int8), 100)
    design = np.arange(400)
    replay_p, replay_shift = construct_shift(
        environment,
        source,
        target,
        environment[design],
        source[design],
        target[design],
        1.5,
        8,
    )
    locked_p, locked_shift = design_controlled_shift_from_fold(
        environment,
        source,
        target,
        environment[design],
        source[design],
        target[design],
        requested_gamma=1.5,
        minimum_design_cell_count=8,
    )
    assert np.array_equal(replay_p, locked_p)
    assert replay_shift == locked_shift.to_dict()
    scores = {"target::0": 4.0, "target::1": 2.0, "source::0": 1.0, "source::1": 3.0}
    assert integer_allocation(scores, 4000, 600) == allocate_integer_budget(
        scores, total_budget=4000, minimum_per_cell=600
    )


def test_decisions_and_geometry() -> None:
    n = 400
    source = np.tile(np.asarray([0, 1], dtype=np.int8), n // 2)
    environment = np.repeat(np.asarray([0, 1], dtype=np.int8), n // 2)
    target = np.tile(np.asarray([0, 1, 1, 0], dtype=np.int8), n // 4)
    reference = {
        "target_harm": np.zeros(n, dtype=np.int8),
        "source": source,
        "environment": environment,
        "target": target,
    }
    for attacker in ATTACKERS:
        reference[f"leakage::{attacker}"] = np.zeros(n, dtype=np.int8)
    cap_candidate = {
        "candidate": "LEACE::closed_form",
        "legacy_cap4_candidate_key": "LEACE::closed_form",
        "method": "LEACE",
        "reference": reference,
        "q_metrics": (0.0, 0.0),
        "evaluation_metrics": (0.0, 0.0),
    }
    replay_candidate = {
        "canonical_candidate_key": "LEACE::closed_form",
        "legacy_cap4_candidate_key": "LEACE::closed_form",
        "method": "LEACE",
        "certification": reference,
        "q_metrics": (0.0, 0.0),
        "evaluation_metrics": (0.0, 0.0),
        "audit_npz_sha256": "a" * 64,
        "receipt_certification_split_sha256": "b" * 64,
    }
    metadata = {"source": source, "environment": environment, "target": target}
    target_profile = {"0": 1.1, "1": 1.1}
    source_profile = {"0": 1.1, "1": 1.1}
    allocation = {
        "target::0": 200,
        "target::1": 200,
        "source::0": 200,
        "source::1": 200,
    }
    shared = {"delta": 0.05, "target_threshold": 0.2, "leakage_threshold": 0.2}
    cap_decisions, cap_details = evaluate_configuration_cap(
        [cap_candidate],
        metadata,
        np.full(n, 1.0 / n),
        target_profile,
        source_profile,
        allocation,
        rng=np.random.default_rng(2027),
        gamma_cap=8.0,
        **shared,
    )
    replay_decisions, replay_details = evaluate_configuration(
        [replay_candidate],
        metadata,
        target_profile,
        source_profile,
        allocation,
        np.random.default_rng(2027),
        **shared,
    )
    for rule in cap_decisions:
        for key in (
            "deployed",
            "safe",
            "violation",
            "selected_candidate",
            "q_target",
            "q_leakage",
            "target_environment_radii",
            "source_class_radii",
            "limiting_coordinates",
            "common_limiting_contracts",
            "common_radius_right_censored",
        ):
            assert replay_decisions[rule][key] == cap_decisions[rule][key], (rule, key)
        assert_close(
            replay_decisions[rule]["certified_common_radius"],
            cap_decisions[rule]["certified_common_radius"],
            tolerance=1e-4,
        )
    assert replay_details[0]["target_sufficient_statistics"] == cap_details[0][
        "target_sufficient_statistics"
    ]
    assert replay_details[0]["leakage_sufficient_statistics"] == cap_details[0][
        "leakage_sufficient_statistics"
    ]
    assert_close(
        replay_details[0]["coupled_common_radius"],
        cap_details[0]["coupled_common_radius"],
        tolerance=1e-4,
    )


def geometry_fixture(positive_count: int, cap: float):
    n = 4000
    values = np.zeros(n, dtype=np.int8)
    values[:positive_count] = 1
    target = {
        "target::environment=0": values.copy(),
        "target::environment=1": values.copy(),
    }
    source = np.asarray([0] * (n // 2) + [1] * (n // 2), dtype=np.int8)
    leakage = {attacker: np.zeros(n, dtype=np.int8) for attacker in ATTACKERS}
    replay = envelope_geometry(
        target,
        leakage,
        source,
        {"0": 1.1, "1": 1.1},
        {"0": 1.1, "1": 1.1},
        alpha=0.05 / 72,
        target_threshold=0.2,
        leakage_threshold=0.2,
        cap=cap,
    )
    locked = certify_balanced_shift_envelope(
        target,
        leakage,
        source,
        delta=0.05,
        family_size=72,
        target_threshold=0.2,
        leakage_threshold=0.2,
        registered_target_environments=(0, 1),
        gamma_cap=cap,
    )
    assert_close(
        replay["coupled_common_radius"], locked.observed_common_radius, tolerance=1e-4
    )
    return replay


def test_cap_regimes() -> None:
    below4_at4 = geometry_fixture(160, 4.0)
    below4_at8 = geometry_fixture(160, 8.0)
    assert 1.0 < below4_at4["coupled_common_radius"] < 4.0
    assert_close(
        below4_at4["coupled_common_radius"],
        below4_at8["coupled_common_radius"],
        tolerance=1e-4,
    )
    between_at4 = geometry_fixture(100, 4.0)
    between_at8 = geometry_fixture(100, 8.0)
    assert between_at4["coupled_common_radius"] == 4.0
    assert between_at4["common_radius_right_censored"]
    assert 4.0 < between_at8["coupled_common_radius"] < 8.0
    assert not between_at8["common_radius_right_censored"]
    above8 = geometry_fixture(20, 8.0)
    assert above8["coupled_common_radius"] == 8.0
    assert above8["common_radius_right_censored"]

    n = 4000
    moderate = np.zeros(n, dtype=np.int8)
    moderate[:100] = 1
    low = np.zeros(n, dtype=np.int8)
    low[:20] = 1
    target = {
        "target::environment=0": moderate,
        "target::environment=1": low,
    }
    source = np.asarray([0] * 2000 + [1] * 2000, dtype=np.int8)
    leakage = {attacker: np.zeros(n, dtype=np.int8) for attacker in ATTACKERS}
    anisotropic = envelope_geometry(
        target,
        leakage,
        source,
        {"0": 5.0, "1": 7.0},
        {"0": 1.0, "1": 1.0},
        alpha=0.05 / 72,
        target_threshold=0.2,
        leakage_threshold=0.2,
        cap=8.0,
    )
    assert anisotropic["requested_profile_in_envelope"]
    common5 = envelope_geometry(
        {
            "target::environment=0": moderate,
            "target::environment=1": moderate.copy(),
        },
        leakage,
        source,
        {"0": 5.0, "1": 5.0},
        {"0": 5.0, "1": 5.0},
        alpha=0.05 / 72,
        target_threshold=0.2,
        leakage_threshold=0.2,
        cap=8.0,
    )
    assert common5["requested_common_profile_in_envelope"]


def compare_nested(left, right, path="root") -> None:
    if isinstance(right, dict):
        assert isinstance(left, dict), path
        assert set(left) == set(right), (path, sorted(left), sorted(right))
        for key, value in right.items():
            compare_nested(left[key], value, f"{path}.{key}")
    elif isinstance(right, list):
        assert len(left) == len(right), path
        for index, value in enumerate(right):
            compare_nested(left[index], value, f"{path}[{index}]")
    elif isinstance(right, float):
        assert_close(left, right, tolerance=1e-12)
    else:
        assert left == right, (path, left, right)


def test_primary_inference() -> None:
    datasets = ("Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB")
    rules = (
        "always_deploy",
        "validation_point_selection",
        "iid_ltt",
        "robust_point_estimate",
        "generic_scalar_robust_certificate",
        "vera_fixed_profile",
        "vera_vector_envelope",
        "vera_common_radius",
        "external_oracle",
    )
    rows = []
    for seed in range(45, 109):
        for dataset_index, dataset in enumerate(datasets):
            point_violation = seed < 77 and dataset_index == 0
            for rule in rules:
                deployed = False
                safe = False
                violation = False
                if rule == "external_oracle":
                    deployed = safe = True
                elif rule == "validation_point_selection":
                    deployed = True
                    violation = point_violation
                    safe = not violation
                elif rule == "vera_vector_envelope":
                    deployed = safe = dataset_index < 2
                elif rule == "vera_common_radius":
                    deployed = safe = dataset_index == 0
                rows.append(
                    {
                        "seed": seed,
                        "dataset": dataset,
                        "rule": rule,
                        "deployed": deployed,
                        "safe": safe,
                        "violation": violation,
                        "certified_common_radius": 1.05,
                        "limiting_coordinates": ["source::0"],
                        "common_limiting_contracts": [
                            "balanced_leakage::linear"
                        ],
                        "heldout_stress_violation": False,
                    }
                )
    replay = infer_primary(rows)
    locked = primary_inference(rows)
    assert set(replay) == set(locked) | {"common_limiting_contract_counts"}
    common_limiting = replay.pop("common_limiting_contract_counts")
    assert common_limiting == {"balanced_leakage::linear": 128}
    compare_nested(replay, locked)


def main() -> None:
    test_curves()
    print("PASS independent exact curves")
    test_shift_and_allocation()
    print("PASS independent shift and allocation")
    test_decisions_and_geometry()
    print("PASS independent nine-rule decisions and cap-8 geometry")
    test_cap_regimes()
    print("PASS below-4, between-4-and-8, above-8, anisotropic, and common fixtures")
    test_primary_inference()
    print("PASS independent primary inference and 20,000-cluster bootstrap")


if __name__ == "__main__":
    main()
