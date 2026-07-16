from __future__ import annotations

import copy

from controlled_shift_sensitivities import (
    DATASETS,
    PRIMARY_ALLOCATION,
    PRIMARY_BUDGET,
    PRIMARY_GAMMA,
    RULES,
    SEEDS,
    analyze,
    bootstrap_sensitivities,
    cp_upper,
    holm,
    leakage_upper,
    primary_details,
    primary_rows,
    target_upper,
)


HASH = "a" * 64
CANDIDATES = tuple(f"candidate::{index:02d}" for index in range(12))


def candidate(dataset: str, seed: int, key: str) -> dict:
    return {
        "dataset": dataset,
        "seed": seed,
        "requested_gamma": PRIMARY_GAMMA,
        "total_budget": PRIMARY_BUDGET,
        "allocation": PRIMARY_ALLOCATION,
        "canonical_candidate_key": key,
        "audit_npz_sha256": HASH,
        "point_target": 0.01,
        "point_leakage": 0.51,
        "q_target": 0.01,
        "q_leakage": 0.51,
        "requested_target_profile": {"0": 1.1},
        "requested_source_profile": {"0": 1.1, "1": 1.1},
        "curve_parameters": {
            "target::environment=0": {
                "positive_probability_upper": 0.01,
                "negative_probability_lower": 0.10,
            },
            "balanced_leakage::linear": {
                "classes": {
                    "0": {"probability_upper": 0.45},
                    "1": {"probability_upper": 0.45},
                }
            },
        },
        "certification_index_sha256": {
            "target": {"0": HASH},
            "source": {"0": HASH, "1": HASH},
        },
    }


def decision(dataset: str, seed: int, rule: str) -> dict:
    return {
        "dataset": dataset,
        "seed": seed,
        "requested_gamma": PRIMARY_GAMMA,
        "total_budget": PRIMARY_BUDGET,
        "allocation": PRIMARY_ALLOCATION,
        "rule": rule,
        "deployed": True,
        "safe": True,
        "violation": False,
        "certified_common_radius": 2.0,
        "common_radius_right_censored": False,
        "selected_candidate": CANDIDATES[0],
    }


def replay() -> dict:
    details = [
        candidate(dataset, seed, key)
        for dataset in DATASETS
        for seed in SEEDS
        for key in CANDIDATES
    ]
    decisions = [
        decision(dataset, seed, rule)
        for dataset in DATASETS
        for seed in SEEDS
        for rule in RULES
    ]
    allocations = [
        {
            "dataset": dataset,
            "seed": seed,
            "requested_gamma": PRIMARY_GAMMA,
            "total_budget": PRIMARY_BUDGET,
            "allocation": PRIMARY_ALLOCATION,
            "cell_allocation": {"target::0": PRIMARY_BUDGET},
        }
        for dataset in DATASETS
        for seed in SEEDS
    ]
    return {
        "decision_rows": decisions,
        "candidate_envelope_details": details,
        "allocation_records": allocations,
        "primary_inference": {
            "safety": {"passed": True},
            "usefulness": {"passed": True},
        },
    }


def test_math_helpers() -> None:
    assert 0.0 < cp_upper(0, 64) < 0.05
    adjusted = holm({"a": 0.01, "b": 0.04, "c": 0.02, "d": 0.50})
    assert adjusted["a"] <= adjusted["b"] <= adjusted["d"]
    target = target_upper(
        {
            "positive_probability_upper": 0.10,
            "negative_probability_lower": 0.20,
        },
        1.0,
    )
    assert abs(target + 0.10) < 1e-12
    leakage = leakage_upper(
        {
            "classes": {
                "0": {"probability_upper": 0.40},
                "1": {"probability_upper": 0.60},
            }
        },
        {"0": 1.0, "1": 1.0},
    )
    assert abs(leakage - 0.50) < 1e-12


def test_complete_synthetic_report() -> None:
    result = analyze(replay())
    assert len(result["rule_results"]) == 9
    assert [row["rule"] for row in result["rule_results"]] == list(RULES)
    assert result["safety_sensitivity"]["vector_violation_cooccurrence"] == [
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]
    sensitivity = result["bootstrap_sensitivity"]
    assert sensitivity["usefulness"]["positive_opportunity_resamples"] == 20_000
    assert sensitivity["vector_common"]["zero_denominator_cases"][
        "positive_opportunity_positive_common"
    ] == 20_000
    stress = result["threshold_stress"]
    assert len(stress["profiles"]) == 3
    assert sum(
        len(rule["per_dataset"])
        for profile in stress["profiles"]
        for rule in profile["rules"]
    ) == 36
    assert not stress["readiness"]["overall_submission_readiness_support_pass"]
    assert stress["readiness"]["negative_result_required"]


def test_corruptions_fail() -> None:
    base = replay()
    missing = copy.deepcopy(base)
    missing["decision_rows"].pop()
    try:
        primary_rows(missing)
    except RuntimeError:
        pass
    else:
        raise AssertionError("missing decision row passed")

    duplicate = copy.deepcopy(base)
    duplicate["candidate_envelope_details"][-1] = copy.deepcopy(
        duplicate["candidate_envelope_details"][0]
    )
    try:
        primary_details(duplicate)
    except RuntimeError:
        pass
    else:
        raise AssertionError("duplicate candidate row passed")

    bad_retention = primary_rows(base)
    for row in bad_retention:
        if row["rule"] == "external_oracle":
            row["deployed"] = False
    try:
        bootstrap_sensitivities(bad_retention)
    except RuntimeError:
        pass
    else:
        raise AssertionError("retention exceeding opportunity passed")

    report = analyze(base)
    mutations = []
    wrong_denominator = copy.deepcopy(report)
    wrong_denominator["rule_results"][0]["deployments"]["denominator"] = 255
    mutations.append(("wrong denominator", wrong_denominator))
    asymmetric = copy.deepcopy(report)
    asymmetric["safety_sensitivity"]["vector_violation_cooccurrence"][0][1] = 1
    mutations.append(("asymmetric co-occurrence", asymmetric))
    wrong_threshold = copy.deepcopy(report)
    wrong_threshold["threshold_stress"]["profiles"][0]["thresholds"][
        "Bios"
    ]["tau"] += 0.01
    mutations.append(("wrong transformed threshold", wrong_threshold))
    wrong_readiness = copy.deepcopy(report)
    wrong_readiness["threshold_stress"]["readiness"][
        "overall_submission_readiness_support_pass"
    ] = True
    mutations.append(("wrong readiness", wrong_readiness))
    wrong_registered = copy.deepcopy(report)
    first = next(
        row
        for row in wrong_registered["threshold_stress"]["decision_rows"]
        if row["kappa"] == 1.0
    )
    first["selected_candidate"] = "candidate::11"
    mutations.append(("changed registered decision", wrong_registered))
    from controlled_shift_sensitivities import validate_report

    for label, mutation in mutations:
        try:
            validate_report(mutation, primary_rows(base))
        except RuntimeError:
            pass
        else:
            raise AssertionError(f"{label} passed")


def main() -> None:
    test_math_helpers()
    print("PASS exact-bound and curve helpers")
    test_complete_synthetic_report()
    print("PASS complete nine-rule, sensitivity, and 36-cell stress fixture")
    test_corruptions_fail()
    print("PASS missing, duplicate, and impossible-retention corruptions")


if __name__ == "__main__":
    main()
