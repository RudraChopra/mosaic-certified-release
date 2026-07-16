"""Cross-field semantic validation for the VERA shared result manifest."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.stats import beta


DATASETS = ("Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB")
RULES = (
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
GATES = (
    "efficacy",
    "sentinel_safety",
    "safe_retention",
    "vector_common_advantage",
)
ABLATIONS = (
    "paired_harm_vs_edited_only_error",
    "balanced_leakage_vs_ordinary_accuracy",
    "attacker_portfolio",
    "iid_vs_shifted_certification",
    "scalar_vs_vector_contracts",
    "common_radius_vs_anisotropic_profile",
    "uniform_vs_prospective_allocation",
    "full_frontier_vs_construction_screen",
    "five_vs_twelve_candidates",
    "one_vs_all_target_environments",
    "evidence_budget",
    "exact_vs_generic_bounds",
    "registered_vs_heldout_attacker",
    "native_eraser_probe_vs_fresh_attackers",
    "no_multiplicity_correction",
    "no_support_check",
)
KAPPAS = (0.75, 1.0, 1.25)
THRESHOLDS = {
    "Waterbirds": (0.10, 0.90),
    "CivilComments-WILDS": (0.075, 0.80),
    "Bios": (0.40, 0.70),
    "GaitPDB": (0.20, 0.55),
}


def close(left: float, right: float, tolerance: float = 1e-12) -> bool:
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= tolerance


def cp_upper(events: int, n: int, alpha: float = 0.05) -> float:
    return 1.0 if events == n else float(beta.ppf(1.0 - alpha, events + 1, n - events))


def validate_fraction(value: Mapping[str, Any], path: str, errors: list[str]) -> None:
    numerator = int(value["numerator"])
    denominator = int(value["denominator"])
    estimate = value["estimate"]
    if numerator < 0 or denominator < 0 or numerator > denominator:
        errors.append(f"{path}: invalid fraction counts")
        return
    expected = None if denominator == 0 else numerator / denominator
    if expected is None:
        if estimate is not None:
            errors.append(f"{path}: zero denominator must have a null estimate")
    elif estimate is None or not close(float(estimate), expected):
        errors.append(f"{path}: fraction estimate disagrees with counts")


def validate_interval(value: Mapping[str, Any], path: str, errors: list[str]) -> None:
    if not close(float(value["level"]), 0.95):
        errors.append(f"{path}: result interval is not 95%")
    lower, upper = value["lower"], value["upper"]
    if lower is not None and upper is not None and float(lower) > float(upper):
        errors.append(f"{path}: interval endpoints are reversed")


def negative_ids(manifest: Mapping[str, Any]) -> list[str]:
    return [str(record["id"]) for record in manifest["negative_results"]]


def validate_primary(manifest: Mapping[str, Any], errors: list[str]) -> None:
    primary = manifest["primary"]
    efficacy = primary["efficacy"]
    test = efficacy["test"]
    positive = int(test["positive_seed_differences"])
    negative = int(test["negative_seed_differences"])
    ties = int(test["ties"])
    nonzero = int(test["nonzero_denominator"])
    if positive + negative != nonzero or nonzero + ties != 64:
        errors.append("primary.efficacy: sign-test counts do not partition 64 seeds")
    effect = efficacy["effect"]
    expected_difference = (
        int(effect["point_violations"]) - int(effect["vector_violations"])
    ) / 256
    if not close(float(effect["paired_difference_estimate"]), expected_difference):
        errors.append("primary.efficacy: paired effect disagrees with violation counts")
    efficacy_pass = positive > negative and float(test["p_value"]) < 0.05
    if (efficacy["status"] == "pass") != efficacy_pass:
        errors.append("primary.efficacy: status disagrees with registered test")

    safety = primary["sentinel_safety"]
    events = int(safety["effect"]["false_acceptances"])
    observed = float(safety["effect"]["observed_rate"])
    upper = float(safety["test"]["upper_bound"])
    if not close(observed, events / 64):
        errors.append("primary.sentinel_safety: observed rate disagrees with count")
    if not close(upper, cp_upper(events, 64), 1e-10):
        errors.append("primary.sentinel_safety: exact upper bound is incorrect")
    safety_pass = events == 0 and upper <= 0.05
    if (safety["status"] == "pass") != safety_pass:
        errors.append("primary.sentinel_safety: status disagrees with registered gate")

    retention = primary["safe_retention"]
    retained = retention["effect"]["retained_opportunities"]
    opportunities = retention["effect"]["safe_opportunities"]
    validate_fraction(retention["effect"]["retention"], "primary.safe_retention.effect", errors)
    fraction = retention["effect"]["retention"]
    if int(fraction["numerator"]) != retained or int(fraction["denominator"]) != opportunities:
        errors.append("primary.safe_retention: effect counts disagree")
    validate_interval(retention["interval"], "primary.safe_retention.interval", errors)
    lower = retention["interval"]["lower"]
    retention_pass = lower is not None and float(lower) >= 0.20
    if (retention["status"] == "pass") != retention_pass:
        errors.append("primary.safe_retention: status disagrees with lower bound")
    sensitivity = retention["zero_opportunity_sensitivity"]
    if (
        int(sensitivity["positive_opportunity_resamples"])
        + int(sensitivity["zero_opportunity_resamples"])
        != 20_000
    ):
        errors.append("primary.safe_retention: bootstrap cases do not sum to 20,000")

    advantage = primary["vector_common_advantage"]
    vector = advantage["effect"]["vector_retention"]
    common = advantage["effect"]["common_retention"]
    validate_fraction(vector, "primary.vector_common.vector", errors)
    validate_fraction(common, "primary.vector_common.common", errors)
    ratio = advantage["effect"]["ratio"]
    status = advantage["effect"]["ratio_status"]
    if common["numerator"] > 0:
        expected_ratio = vector["numerator"] / common["numerator"]
        if ratio is None or not close(float(ratio), expected_ratio):
            errors.append("primary.vector_common: ratio disagrees with retained counts")
        if status != "finite":
            errors.append("primary.vector_common: positive denominator is not finite")
    advantage_pass = status == "finite" and ratio is not None and float(ratio) >= 2.0
    if (advantage["status"] == "pass") != advantage_pass:
        errors.append("primary.vector_common: status disagrees with point ratio")
    cases = advantage["test"]["zero_denominator_cases"]
    total = sum(
        int(cases[key])
        for key in (
            "positive_opportunity_positive_common",
            "positive_opportunity_zero_common_positive_vector",
            "positive_opportunity_zero_common_zero_vector",
            "zero_opportunity",
        )
    )
    if total != 20_000:
        errors.append("primary.vector_common: bootstrap cases do not sum to 20,000")

    expected_failed = [
        gate for gate in GATES if primary[gate]["status"] != "pass"
    ]
    overall = primary["overall"]
    expected_overall = "pass" if not expected_failed else "fail"
    if manifest["analysis_status"] == "invalid":
        expected_overall = "invalid"
        expected_failed = list(GATES)
    if overall["status"] != expected_overall:
        errors.append("primary.overall: status disagrees with component gates")
    if set(overall["failed_gates"]) != set(expected_failed):
        errors.append("primary.overall: failed-gate set is incomplete")
    ids = set(negative_ids(manifest))
    marker = {
        "efficacy": "primary_efficacy_failed",
        "sentinel_safety": "primary_sentinel_safety_failed",
        "safe_retention": "primary_safe_retention_failed",
        "vector_common_advantage": "primary_vector_common_advantage_failed",
    }
    for gate in expected_failed:
        if marker[gate] not in ids:
            errors.append(f"primary.{gate}: mandatory negative result is absent")


def validate_rules(manifest: Mapping[str, Any], errors: list[str]) -> None:
    results = manifest["rule_results"]
    if [row["rule"] for row in results] != list(RULES):
        errors.append("rule_results: order or membership changed")
        return
    for rule in results:
        validate_fraction(rule["deployments"], f"rule_results.{rule['rule']}.deployments", errors)
        validate_fraction(
            rule["violations_all_decisions"],
            f"rule_results.{rule['rule']}.violations_all",
            errors,
        )
        validate_fraction(
            rule["violations_deployed"],
            f"rule_results.{rule['rule']}.violations_deployed",
            errors,
        )
        validate_fraction(
            rule["retained_opportunities"],
            f"rule_results.{rule['rule']}.retention",
            errors,
        )
        if int(rule["deployments"]["numerator"]) != int(
            rule["violations_deployed"]["denominator"]
        ):
            errors.append(f"rule_results.{rule['rule']}: deployment denominators disagree")
        if [row["dataset"] for row in rule["per_dataset"]] != list(DATASETS):
            errors.append(f"rule_results.{rule['rule']}: dataset order changed")
        for dataset in rule["per_dataset"]:
            for field in (
                "deployments",
                "violations_all_decisions",
                "violations_deployed",
                "retained_opportunities",
            ):
                validate_fraction(
                    dataset[field],
                    f"rule_results.{rule['rule']}.{dataset['dataset']}.{field}",
                    errors,
                )
            if int(dataset["deployments"]["numerator"]) != int(
                dataset["violations_deployed"]["denominator"]
            ):
                errors.append(
                    f"rule_results.{rule['rule']}.{dataset['dataset']}: "
                    "deployment denominators disagree"
                )
    safety = manifest["safety_sensitivity"]
    matrix = np.asarray(safety["vector_violation_cooccurrence"], dtype=int)
    if matrix.shape != (4, 4) or not np.array_equal(matrix, matrix.T):
        errors.append("safety_sensitivity: co-occurrence matrix is not symmetric 4-by-4")
        return
    vector = next(row for row in results if row["rule"] == "vera_vector_envelope")
    diagonal = [
        int(row["violations_all_decisions"]["numerator"])
        for row in vector["per_dataset"]
    ]
    if np.diag(matrix).tolist() != diagonal:
        errors.append("safety_sensitivity: matrix diagonal disagrees with events")
    if sum(map(int, safety["vector_violating_dataset_count_by_seed"])) != 64:
        errors.append("safety_sensitivity: violation multiplicities do not sum to 64")


def validate_stress(manifest: Mapping[str, Any], errors: list[str]) -> None:
    stress = manifest["threshold_stress"]
    rates: dict[tuple[float, str, str], float] = {}
    for profile, kappa in zip(stress["profiles"], KAPPAS):
        for dataset in DATASETS:
            observed = profile["thresholds"][dataset]
            tau = kappa * THRESHOLDS[dataset][0]
            leakage = 0.5 + kappa * (THRESHOLDS[dataset][1] - 0.5)
            if not close(float(observed["tau"]), tau) or not close(
                float(observed["lambda"]), leakage
            ):
                errors.append("threshold_stress: transformed threshold changed")
        for rule in profile["rules"]:
            for row in rule["per_dataset"]:
                value = row["violations_all_decisions"]
                validate_fraction(
                    value,
                    f"threshold_stress.{kappa}.{rule['rule']}.{row['dataset']}",
                    errors,
                )
                rates[(kappa, rule["rule"], row["dataset"])] = float(
                    value["estimate"]
                )
    readiness = stress["readiness"]
    always = max(rates[(1.0, "always_deploy", dataset)] for dataset in DATASETS)
    point = max(
        rates[(1.0, "validation_point_selection", dataset)] for dataset in DATASETS
    )
    vera = max(
        rates[(kappa, "vera_vector_envelope", dataset)]
        for kappa in KAPPAS
        for dataset in DATASETS
    )
    if not close(float(readiness["always_deploy_max_registered_rate"]), always):
        errors.append("threshold_stress: always-deploy maximum is incorrect")
    if not close(float(readiness["validation_selection_max_registered_rate"]), point):
        errors.append("threshold_stress: validation maximum is incorrect")
    if not close(float(readiness["vera_max_all_cells_rate"]), vera):
        errors.append("threshold_stress: VERA maximum is incorrect")
    components = (
        always >= 0.20,
        point >= 0.20,
        vera <= 0.05,
        manifest["primary"]["sentinel_safety"]["status"] == "pass",
        manifest["primary"]["safe_retention"]["status"] == "pass",
    )
    passed = all(components)
    if bool(readiness["overall_submission_readiness_support_pass"]) != passed:
        errors.append("threshold_stress: readiness status is inconsistent")
    marker_count = negative_ids(manifest).count("three_rule_threshold_stress_failed")
    if marker_count != int(not passed):
        errors.append("threshold_stress: failure marker presence is inconsistent")


def validate_miscellaneous(manifest: Mapping[str, Any], errors: list[str]) -> None:
    if manifest["analysis_status"] == "complete":
        audit = manifest["receipt_audit"]
        if (audit["valid"], audit["missing"], audit["invalid"], audit["proxy"]) != (
            1280,
            0,
            0,
            0,
        ):
            errors.append("receipt_audit: complete analysis does not have 1,280 valid receipts")
        if any(record["status"] != "complete" for record in manifest["ablations"]):
            errors.append("ablations: complete analysis contains an invalid ablation")
    if [record["id"] for record in manifest["ablations"]] != list(ABLATIONS):
        errors.append("ablations: order or identity changed")
    correction = manifest["candidate_key_correction"]
    if any(
        int(correction[key]) != 0
        for key in (
            "selection_difference_count",
            "row_difference_count",
            "aggregate_difference_count",
            "gate_difference_count",
        )
    ):
        errors.append("candidate_key_correction: scientific difference is nonzero")
    heldout = manifest["heldout_attacker_result"]
    safe = int(heldout["portfolio_safe_deployments"])
    failures = int(heldout["heldout_violation_count"])
    expected = None if safe == 0 else 1.0 - failures / safe
    if failures > safe:
        errors.append("heldout_attacker_result: failures exceed safe deployments")
    elif expected is None and heldout["heldout_safe_fraction"] is not None:
        errors.append("heldout_attacker_result: zero denominator is not null")
    elif expected is not None and not close(float(heldout["heldout_safe_fraction"]), expected):
        errors.append("heldout_attacker_result: safe fraction disagrees with counts")
    gait = manifest["gait_diagnostic"]
    if int(gait["primary_retained_opportunities"]) > int(gait["oracle_safe_candidates"]):
        errors.append("gait_diagnostic: retained opportunities exceed safe candidates")
    if int(gait["doubled_evidence_retained_opportunities"]) > int(
        gait["oracle_safe_candidates"]
    ):
        errors.append("gait_diagnostic: doubled-evidence retention exceeds opportunities")
    figure = manifest["figure_candidate"]
    branch = figure["selection_branch"]
    if branch == "vector_lower_median" and not figure["selected_by_vector"]:
        errors.append("figure_candidate: vector branch is not vector selected")
    if branch == "oracle_safe_fallback" and (
        figure["selected_by_vector"] or not figure["oracle_safe"]
    ):
        errors.append("figure_candidate: oracle fallback flags are inconsistent")
    if branch == "stable_first_fallback" and (
        figure["selected_by_vector"] or figure["oracle_safe"]
    ):
        errors.append("figure_candidate: stable fallback flags are inconsistent")
    allocation_condition = bool(manifest["allocation"]["title_empirical_condition"]) and bool(
        manifest["allocation"]["safety_not_worse"]
    )
    title = manifest["title_decision"]
    if bool(title["allocation_condition"]) != allocation_condition:
        errors.append("title_decision: allocation condition is inconsistent")
    strong = bool(title["literature_condition"]) and allocation_condition
    if (title["title_branch"] == "evidence_efficient") != strong:
        errors.append("title_decision: branch is inconsistent with frozen conditions")
    ids = negative_ids(manifest)
    for required in ("historical_gait_floor_failed", "camelyon17_unsupported_support"):
        if ids.count(required) != 1:
            errors.append(f"negative_results: {required} must appear exactly once")
    cap_differences = manifest["radius_cap_correction"]["primary_gate_differences"]
    if bool(cap_differences) != ("radius_cap_changes_primary_gate" in ids):
        errors.append("radius_cap_correction: gate-difference disclosure is inconsistent")


def validate_semantics(manifest: Mapping[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    validate_primary(manifest, errors)
    validate_rules(manifest, errors)
    validate_stress(manifest, errors)
    validate_miscellaneous(manifest, errors)
    return {
        "schema_version": 1,
        "name": "VERA shared-manifest semantic audit",
        "passed": not errors,
        "errors": errors,
    }
