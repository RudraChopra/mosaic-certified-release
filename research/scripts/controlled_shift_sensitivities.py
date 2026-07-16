"""Build outcome-blind VERA safety, bootstrap, and threshold sensitivities."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.stats import beta, binom


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
STRESS_RULES = (
    "always_deploy",
    "validation_point_selection",
    "vera_vector_envelope",
)
SEEDS = tuple(range(45, 109))
KAPPAS = (0.75, 1.0, 1.25)
PRIMARY_GAMMA = 1.1
PRIMARY_BUDGET = 4_000
PRIMARY_ALLOCATION = "targeted_floor_0.15"
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_SEED = 2_027_071_601
GAMMA_CAP = 8.0
THRESHOLDS = {
    "Waterbirds": (0.10, 0.90),
    "CivilComments-WILDS": (0.075, 0.80),
    "Bios": (0.40, 0.70),
    "GaitPDB": (0.20, 0.55),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    estimate = None if denominator == 0 else numerator / denominator
    result: dict[str, Any] = {
        "numerator": int(numerator),
        "denominator": int(denominator),
        "estimate": estimate,
    }
    if denominator == 0:
        result["undefined_reason"] = "zero_denominator"
    return result


def interval(
    lower: float | None,
    upper: float | None,
    *,
    method: str = "whole_seed_percentile_bootstrap",
    unit: str = "whole_seed_four_dataset_cluster",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "level": 0.95,
        "lower": lower,
        "upper": upper,
        "method": method,
        "independent_unit": unit,
    }
    if lower is None or upper is None:
        result["undefined_reason"] = "zero_denominator_in_all_resamples"
    return result


def cp_upper(events: int, n: int, alpha: float = 0.05) -> float:
    if not 0 <= events <= n or n <= 0 or not 0.0 < alpha < 1.0:
        raise ValueError("invalid Clopper-Pearson inputs")
    if events == n:
        return 1.0
    return float(beta.ppf(1.0 - alpha, events + 1, n - events))


def holm(values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(values, key=lambda key: (values[key], key))
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, key in enumerate(ordered):
        running = max(running, min(1.0, (total - rank) * values[key]))
        adjusted[key] = running
    return adjusted


def primary_rows(replay: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in replay["decision_rows"]
        if abs(float(row["requested_gamma"]) - PRIMARY_GAMMA) <= 1e-12
        and int(row["total_budget"]) == PRIMARY_BUDGET
        and row["allocation"] == PRIMARY_ALLOCATION
    ]
    expected = len(SEEDS) * len(DATASETS) * len(RULES)
    if len(rows) != expected:
        raise RuntimeError(f"primary decision shape mismatch: {len(rows)} != {expected}")
    keys = {(int(r["seed"]), r["dataset"], r["rule"]) for r in rows}
    if len(keys) != expected:
        raise RuntimeError("primary decision keys are not unique")
    return rows


def primary_details(replay: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = [
        dict(row)
        for row in replay["candidate_envelope_details"]
        if abs(float(row["requested_gamma"]) - PRIMARY_GAMMA) <= 1e-12
        and int(row["total_budget"]) == PRIMARY_BUDGET
        and row["allocation"] == PRIMARY_ALLOCATION
    ]
    expected = len(SEEDS) * len(DATASETS) * 12
    if len(rows) != expected:
        raise RuntimeError(f"primary candidate shape mismatch: {len(rows)} != {expected}")
    keys = {
        (int(r["seed"]), r["dataset"], r["canonical_candidate_key"])
        for r in rows
    }
    if len(keys) != expected:
        raise RuntimeError("primary candidate keys are not unique")
    return rows


@lru_cache(maxsize=1)
def bootstrap_indices() -> np.ndarray:
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    return rng.integers(
        0, len(SEEDS), size=(BOOTSTRAP_REPLICATES, len(SEEDS)), dtype=np.int16
    )


def quantile_interval(values: np.ndarray) -> tuple[float | None, float | None]:
    finite = values[np.isfinite(values)]
    if not len(finite):
        return None, None
    return float(np.quantile(finite, 0.025)), float(np.quantile(finite, 0.975))


def bootstrap_summary(
    rows: Sequence[Mapping[str, Any]],
    oracle: Mapping[tuple[int, str], Mapping[str, Any]],
    indices: np.ndarray,
) -> dict[str, Any]:
    by_seed: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_seed[int(row["seed"])].append(row)
    if tuple(sorted(by_seed)) != SEEDS:
        raise RuntimeError("bootstrap rows do not contain the exact seed set")
    totals = np.asarray(
        [
            [
                len(by_seed[seed]),
                sum(bool(row["deployed"]) for row in by_seed[seed]),
                sum(bool(row["violation"]) for row in by_seed[seed]),
                sum(bool(row["safe"]) for row in by_seed[seed]),
                sum(
                    bool(oracle[(seed, str(row["dataset"]))]["deployed"])
                    for row in by_seed[seed]
                ),
            ]
            for seed in SEEDS
        ],
        dtype=float,
    )
    sampled = totals[indices].sum(axis=1)
    deployment = sampled[:, 1] / sampled[:, 0]
    violation = sampled[:, 2] / sampled[:, 0]
    conditional = np.divide(
        sampled[:, 2],
        sampled[:, 1],
        out=np.full(len(sampled), np.nan),
        where=sampled[:, 1] > 0,
    )
    retention = np.divide(
        sampled[:, 3],
        sampled[:, 4],
        out=np.full(len(sampled), np.nan),
        where=sampled[:, 4] > 0,
    )
    return {
        "deployment": quantile_interval(deployment),
        "violation": quantile_interval(violation),
        "conditional_violation": quantile_interval(conditional),
        "retention": quantile_interval(retention),
    }


def radius_summary(rows: Sequence[Mapping[str, Any]], rule: str) -> dict[str, Any]:
    applicable = {
        "vera_fixed_profile",
        "vera_vector_envelope",
        "vera_common_radius",
    }
    if rule not in applicable:
        return {
            "status": "not_applicable",
            "median": None,
            "q1": None,
            "q3": None,
            "defined_denominator": 0,
            "right_censored": 0,
            "cap": GAMMA_CAP,
            "undefined_reason": "rule_does_not_return_vera_envelope",
        }
    deployed = [row for row in rows if bool(row["deployed"])]
    if not deployed:
        return {
            "status": "undefined",
            "median": None,
            "q1": None,
            "q3": None,
            "defined_denominator": 0,
            "right_censored": 0,
            "cap": GAMMA_CAP,
            "undefined_reason": "rule_never_deployed",
        }
    values = np.asarray(
        [float(row["certified_common_radius"]) for row in deployed], dtype=float
    )
    return {
        "status": "defined",
        "median": float(np.median(values)),
        "q1": float(np.quantile(values, 0.25)),
        "q3": float(np.quantile(values, 0.75)),
        "defined_denominator": len(deployed),
        "right_censored": sum(
            bool(row["common_radius_right_censored"]) for row in deployed
        ),
        "cap": GAMMA_CAP,
        "undefined_reason": None,
    }


def seed_familywise(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    events = sum(
        any(bool(row["violation"]) for row in rows if int(row["seed"]) == seed)
        for seed in SEEDS
    )
    return {
        "events": events,
        "decisions": len(SEEDS),
        "rate": fraction(events, len(SEEDS)),
        "one_sided_cp95_upper": cp_upper(events, len(SEEDS)),
        "interval_method": "one_sided_clopper_pearson_alpha_0.05",
        "independent_unit": "whole_seed_four_dataset_cluster",
        "can_change_primary_gate": False,
    }


def dataset_safety(
    counts: Mapping[str, int], adjusted: Mapping[str, float], dataset: str
) -> dict[str, Any]:
    events = counts[dataset]
    return {
        "unadjusted_alpha": 0.05,
        "simultaneous_component_alpha": 0.0125,
        "unadjusted_cp95_upper": cp_upper(events, len(SEEDS), 0.05),
        "simultaneous_bonferroni_cp95_upper": cp_upper(
            events, len(SEEDS), 0.0125
        ),
        "threshold_null_rate": 0.05,
        "raw_exact_threshold_p": float(binom.cdf(events, len(SEEDS), 0.05)),
        "holm_adjusted_threshold_p": adjusted[dataset],
        "threshold_alternative": "less",
        "simultaneous_bound_method": "bonferroni_one_sided_clopper_pearson",
        "threshold_test_method": "holm_exact_binomial_lower_tail_at_0.05",
        "can_change_primary_gate": False,
    }


def build_rule_results(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_key = {(int(r["seed"]), str(r["dataset"]), str(r["rule"])): r for r in rows}
    expected = len(SEEDS) * len(DATASETS) * len(RULES)
    if len(by_key) != expected:
        raise RuntimeError("rule table does not have the exact primary key set")
    oracle = {
        (seed, dataset): by_key[(seed, dataset, "external_oracle")]
        for seed in SEEDS
        for dataset in DATASETS
    }
    indices = bootstrap_indices()
    results: list[dict[str, Any]] = []
    vector_events = np.zeros((len(SEEDS), len(DATASETS)), dtype=int)
    for rule in RULES:
        rule_rows = [row for row in rows if row["rule"] == rule]
        counts = {
            dataset: sum(
                bool(row["violation"])
                for row in rule_rows
                if row["dataset"] == dataset
            )
            for dataset in DATASETS
        }
        raw = {
            dataset: float(binom.cdf(counts[dataset], len(SEEDS), 0.05))
            for dataset in DATASETS
        }
        adjusted = holm(raw)
        aggregate_boot = bootstrap_summary(rule_rows, oracle, indices)
        per_dataset: list[dict[str, Any]] = []
        for dataset in DATASETS:
            subset = [row for row in rule_rows if row["dataset"] == dataset]
            boot = bootstrap_summary(subset, oracle, indices)
            deployments = sum(bool(row["deployed"]) for row in subset)
            violations = sum(bool(row["violation"]) for row in subset)
            retained = sum(bool(row["safe"]) for row in subset)
            opportunities = sum(
                bool(oracle[(int(row["seed"]), dataset)]["deployed"])
                for row in subset
            )
            per_dataset.append(
                {
                    "dataset": dataset,
                    "decisions": len(SEEDS),
                    "deployments": fraction(deployments, len(SEEDS)),
                    "violations_all_decisions": fraction(violations, len(SEEDS)),
                    "violations_deployed": fraction(violations, deployments),
                    "safe_opportunities": opportunities,
                    "retained_opportunities": fraction(retained, opportunities),
                    "deployment_interval": interval(*boot["deployment"]),
                    "retention_interval": (
                        None
                        if opportunities == 0
                        else interval(*boot["retention"])
                    ),
                    "common_radius": radius_summary(subset, rule),
                    "safety_sensitivity": dataset_safety(
                        counts, adjusted, dataset
                    ),
                }
            )
        deployments = sum(bool(row["deployed"]) for row in rule_rows)
        violations = sum(bool(row["violation"]) for row in rule_rows)
        retained = sum(bool(row["safe"]) for row in rule_rows)
        opportunities = sum(bool(row["deployed"]) for row in oracle.values())
        results.append(
            {
                "rule": rule,
                "decisions": 256,
                "deployments": fraction(deployments, 256),
                "violations_all_decisions": fraction(violations, 256),
                "violations_deployed": fraction(violations, deployments),
                "safe_opportunities": opportunities,
                "retained_opportunities": fraction(retained, opportunities),
                "deployment_interval": interval(*aggregate_boot["deployment"]),
                "retention_interval": (
                    None
                    if opportunities == 0
                    else interval(*aggregate_boot["retention"])
                ),
                "common_radius": radius_summary(rule_rows, rule),
                "seed_familywise_safety": seed_familywise(rule_rows),
                "per_dataset": per_dataset,
            }
        )
        if rule == "vera_vector_envelope":
            for seed_index, seed in enumerate(SEEDS):
                for dataset_index, dataset in enumerate(DATASETS):
                    vector_events[seed_index, dataset_index] = int(
                        bool(by_key[(seed, dataset, rule)]["violation"])
                    )
    cooccurrence = vector_events.T @ vector_events
    multiplicity = Counter(map(int, vector_events.sum(axis=1)))
    safety = {
        "dataset_bound_method": "bonferroni_one_sided_clopper_pearson",
        "dataset_unadjusted_alpha": 0.05,
        "dataset_bound_familywise_alpha": 0.05,
        "dataset_bound_component_alpha": 0.0125,
        "dataset_threshold_test_method": "holm_exact_binomial_lower_tail_at_0.05",
        "dataset_threshold_null_rate": 0.05,
        "dataset_threshold_alternative": "less",
        "holm_family_size": 4,
        "vector_dataset_order": list(DATASETS),
        "vector_violation_cooccurrence": cooccurrence.astype(int).tolist(),
        "violating_dataset_count_order": [0, 1, 2, 3, 4],
        "vector_violating_dataset_count_by_seed": [
            multiplicity.get(value, 0) for value in range(5)
        ],
        "semantic_consistency_verified": True,
        "can_change_primary_gate": False,
    }
    if sum(safety["vector_violating_dataset_count_by_seed"]) != len(SEEDS):
        raise RuntimeError("vector violation multiplicity does not sum to 64")
    return results, safety


def bootstrap_sensitivities(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_key = {(int(r["seed"]), str(r["dataset"]), str(r["rule"])): r for r in rows}
    per_seed = np.zeros((len(SEEDS), 3), dtype=int)
    for seed_index, seed in enumerate(SEEDS):
        for dataset in DATASETS:
            per_seed[seed_index, 0] += int(
                bool(by_key[(seed, dataset, "external_oracle")]["deployed"])
            )
            per_seed[seed_index, 1] += int(
                bool(by_key[(seed, dataset, "vera_vector_envelope")]["safe"])
            )
            per_seed[seed_index, 2] += int(
                bool(by_key[(seed, dataset, "vera_common_radius")]["safe"])
            )
    totals = per_seed[bootstrap_indices()].sum(axis=1)
    opportunity, vector, common = totals.T
    if np.any(vector > opportunity) or np.any(common > opportunity):
        raise RuntimeError("retained opportunities exceed oracle opportunities")
    cases = {
        "positive_opportunity_positive_common": int(
            np.sum((opportunity > 0) & (common > 0))
        ),
        "positive_opportunity_zero_common_positive_vector": int(
            np.sum((opportunity > 0) & (common == 0) & (vector > 0))
        ),
        "positive_opportunity_zero_common_zero_vector": int(
            np.sum((opportunity > 0) & (common == 0) & (vector == 0))
        ),
        "zero_opportunity": int(np.sum(opportunity == 0)),
    }
    impossible = int(np.sum((opportunity == 0) & ((vector > 0) | (common > 0))))
    cases.update(
        {
            "total_resamples": BOOTSTRAP_REPLICATES,
            "impossible_nonzero_retention_zero_opportunity": impossible,
            "all_resamples_accounted": sum(cases.values()) == BOOTSTRAP_REPLICATES,
        }
    )
    if not cases["all_resamples_accounted"] or impossible:
        raise RuntimeError("vector/common bootstrap cases are not exhaustive")
    completed = np.divide(
        vector,
        opportunity,
        out=np.zeros(BOOTSTRAP_REPLICATES, dtype=float),
        where=opportunity > 0,
    )
    useful_margin = vector - 0.20 * opportunity
    extended = np.zeros(BOOTSTRAP_REPLICATES, dtype=float)
    positive_common = common > 0
    extended[positive_common] = vector[positive_common] / common[positive_common]
    extended[(common == 0) & (vector > 0)] = np.inf
    ratio_quantiles = np.quantile(extended, (0.025, 0.975))
    twofold = np.divide(
        vector - 2 * common,
        opportunity,
        out=np.zeros(BOOTSTRAP_REPLICATES, dtype=float),
        where=opportunity > 0,
    )

    def encode(value: float) -> float | str:
        return "+infinity" if np.isposinf(value) else float(value)

    positive_opportunity = int(np.sum(opportunity > 0))
    zero_opportunity = BOOTSTRAP_REPLICATES - positive_opportunity
    return {
        "usefulness": {
            "resamples": BOOTSTRAP_REPLICATES,
            "seed": BOOTSTRAP_SEED,
            "positive_opportunity_resamples": positive_opportunity,
            "zero_opportunity_resamples": zero_opportunity,
            "impossible_positive_retention_zero_opportunity_resamples": impossible,
            "all_resamples_accounted": True,
            "completed_statistic_interval": interval(
                *quantile_interval(completed)
            ),
            "division_free_margin_interval": interval(
                *quantile_interval(useful_margin)
            ),
            "completed_statistic_lower_target": 0.20,
            "division_free_lower_target": 0,
            "supports_registered_threshold": bool(
                np.quantile(completed, 0.025) >= 0.20
                and np.quantile(useful_margin, 0.025) >= 0.0
            ),
            "can_change_gate": False,
        },
        "vector_common": {
            "zero_denominator_cases": cases,
            "extended_ratio_interval": {
                "level": 0.95,
                "lower": encode(float(ratio_quantiles[0])),
                "upper": encode(float(ratio_quantiles[1])),
                "method": "whole_seed_extended_ratio_percentile_bootstrap",
                "independent_unit": "whole_seed_four_dataset_cluster",
            },
            "division_free_interval": interval(*quantile_interval(twofold)),
        },
    }


def target_upper(curve: Mapping[str, Any], gamma: float) -> float:
    positive = float(curve["positive_probability_upper"])
    negative = float(curve["negative_probability_lower"])
    positive = min(positive, 1.0 - negative)
    zero = max(0.0, 1.0 - negative - positive)
    positive_mass = min(1.0, gamma * positive)
    remaining = 1.0 - positive_mass
    zero_mass = min(remaining, gamma * zero)
    negative_mass = max(0.0, remaining - zero_mass)
    return float(min(1.0, max(-1.0, positive_mass - negative_mass)))


def leakage_upper(
    curve: Mapping[str, Any], profile: Mapping[str, float]
) -> float:
    return float(
        0.5
        * sum(
            min(
                1.0,
                float(profile[source_class])
                * float(curve["classes"][source_class]["probability_upper"]),
            )
            for source_class in ("0", "1")
        )
    )


def profile_lookup(profile: Mapping[str, float], curve_key: str) -> float:
    if curve_key in profile:
        return float(profile[curve_key])
    prefix = "target::environment="
    if curve_key.startswith(prefix):
        environment = curve_key.removeprefix(prefix)
        if environment in profile:
            return float(profile[environment])
    raise KeyError(curve_key)


def vector_eligible(
    candidate: Mapping[str, Any], target_threshold: float, leakage_threshold: float
) -> bool:
    target_profile = candidate["requested_target_profile"]
    source_profile = candidate["requested_source_profile"]
    for key, curve in candidate["curve_parameters"].items():
        if key.startswith("balanced_leakage::"):
            if leakage_upper(curve, source_profile) > leakage_threshold:
                return False
        elif target_upper(curve, profile_lookup(target_profile, key)) > target_threshold:
            return False
    return True


def select_candidate(
    candidates: Sequence[Mapping[str, Any]], rule: str, tau: float, leakage: float
) -> Mapping[str, Any] | None:
    if rule == "always_deploy":
        eligible = list(candidates)
    elif rule == "validation_point_selection":
        eligible = [
            candidate
            for candidate in candidates
            if float(candidate["point_target"]) <= tau
            and float(candidate["point_leakage"]) <= leakage
        ]
    elif rule == "vera_vector_envelope":
        eligible = [
            candidate
            for candidate in candidates
            if vector_eligible(candidate, tau, leakage)
        ]
    elif rule == "external_oracle":
        eligible = [
            candidate
            for candidate in candidates
            if float(candidate["q_target"]) <= tau
            and float(candidate["q_leakage"]) <= leakage
        ]
    else:
        raise ValueError(f"unsupported stress rule: {rule}")
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda candidate: (
            float(candidate["point_leakage"]),
            float(candidate["point_target"]),
            str(candidate["canonical_candidate_key"]),
        ),
    )


def stress_decisions(
    details: Sequence[Mapping[str, Any]], kappa: float
) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in details:
        grouped[(int(row["seed"]), str(row["dataset"]))].append(row)
    expected = {(seed, dataset) for seed in SEEDS for dataset in DATASETS}
    if set(grouped) != expected or any(len(rows) != 12 for rows in grouped.values()):
        raise RuntimeError("threshold-stress candidate grid is incomplete")
    output: list[dict[str, Any]] = []
    for seed in SEEDS:
        for dataset in DATASETS:
            tau0, leakage0 = THRESHOLDS[dataset]
            tau = kappa * tau0
            leakage = 0.5 + kappa * (leakage0 - 0.5)
            candidates = grouped[(seed, dataset)]
            oracle = select_candidate(candidates, "external_oracle", tau, leakage)
            for rule in STRESS_RULES:
                selected = select_candidate(candidates, rule, tau, leakage)
                safe = bool(
                    selected is not None
                    and float(selected["q_target"]) <= tau
                    and float(selected["q_leakage"]) <= leakage
                )
                output.append(
                    {
                        "kappa": kappa,
                        "seed": seed,
                        "dataset": dataset,
                        "rule": rule,
                        "deployed": selected is not None,
                        "violation": selected is not None and not safe,
                        "safe": safe,
                        "oracle_deployed": oracle is not None,
                        "selected_candidate": (
                            ""
                            if selected is None
                            else selected["canonical_candidate_key"]
                        ),
                    }
                )
    return output


def stress_dataset_summary(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if len(rows) != len(SEEDS):
        raise RuntimeError("threshold-stress dataset cell does not have 64 seeds")
    deployments = sum(bool(row["deployed"]) for row in rows)
    violations = sum(bool(row["violation"]) for row in rows)
    opportunities = sum(bool(row["oracle_deployed"]) for row in rows)
    retained = sum(bool(row["safe"]) for row in rows)
    indices = bootstrap_indices()
    values = np.asarray(
        [
            [
                int(bool(row["deployed"])),
                int(bool(row["violation"])),
                int(bool(row["oracle_deployed"])),
                int(bool(row["safe"])),
            ]
            for row in sorted(rows, key=lambda row: int(row["seed"]))
        ],
        dtype=float,
    )
    sampled = values[indices].sum(axis=1)
    deployment = sampled[:, 0] / len(SEEDS)
    violation = sampled[:, 1] / len(SEEDS)
    retention = np.divide(
        sampled[:, 3],
        sampled[:, 2],
        out=np.full(BOOTSTRAP_REPLICATES, np.nan),
        where=sampled[:, 2] > 0,
    )
    return {
        "decisions": len(SEEDS),
        "deployments": fraction(deployments, len(SEEDS)),
        "violations_all_decisions": fraction(violations, len(SEEDS)),
        "violations_deployed": fraction(violations, deployments),
        "safe_opportunities": opportunities,
        "retained_opportunities": fraction(retained, opportunities),
        "deployment_interval": interval(*quantile_interval(deployment)),
        "violation_interval": interval(*quantile_interval(violation)),
        "retention_interval": interval(*quantile_interval(retention)),
    }


def threshold_stress(
    details: Sequence[Mapping[str, Any]], primary_inference: Mapping[str, Any]
) -> dict[str, Any]:
    decisions = [row for kappa in KAPPAS for row in stress_decisions(details, kappa)]
    profiles: list[dict[str, Any]] = []
    rates: dict[tuple[float, str, str], float] = {}
    for kappa in KAPPAS:
        rules: list[dict[str, Any]] = []
        for rule in STRESS_RULES:
            per_dataset = []
            for dataset in DATASETS:
                subset = [
                    row
                    for row in decisions
                    if row["kappa"] == kappa
                    and row["rule"] == rule
                    and row["dataset"] == dataset
                ]
                summary = stress_dataset_summary(subset)
                rates[(kappa, rule, dataset)] = summary[
                    "violations_all_decisions"
                ]["estimate"]
                per_dataset.append({"dataset": dataset, **summary})
            rules.append({"rule": rule, "per_dataset": per_dataset})
        thresholds = {
            dataset: {
                "tau": kappa * THRESHOLDS[dataset][0],
                "lambda": 0.5
                + kappa * (THRESHOLDS[dataset][1] - 0.5),
            }
            for dataset in DATASETS
        }
        profiles.append({"kappa": kappa, "thresholds": thresholds, "rules": rules})
    always_dataset = max(
        DATASETS,
        key=lambda dataset: (
            rates[(1.0, STRESS_RULES[0], dataset)],
            -DATASETS.index(dataset),
        ),
    )
    point_dataset = max(
        DATASETS,
        key=lambda dataset: (
            rates[(1.0, STRESS_RULES[1], dataset)],
            -DATASETS.index(dataset),
        ),
    )
    always_rate = rates[(1.0, STRESS_RULES[0], always_dataset)]
    point_rate = rates[(1.0, STRESS_RULES[1], point_dataset)]
    vera_rate = max(
        rates[(kappa, "vera_vector_envelope", dataset)]
        for kappa in KAPPAS
        for dataset in DATASETS
    )
    sentinel = bool(primary_inference["safety"]["passed"])
    usefulness = bool(primary_inference["usefulness"]["passed"])
    components = (always_rate >= 0.20, point_rate >= 0.20, vera_rate <= 0.05, sentinel, usefulness)
    passed = all(components)
    candidate_manifest = [
        {
            "dataset": row["dataset"],
            "seed": row["seed"],
            "candidate": row["canonical_candidate_key"],
            "audit_npz_sha256": row["audit_npz_sha256"],
        }
        for row in sorted(
            details,
            key=lambda row: (
                row["dataset"], row["seed"], row["canonical_candidate_key"]
            ),
        )
    ]
    stream_manifest = [
        {
            "dataset": row["dataset"],
            "seed": row["seed"],
            "candidate": row["canonical_candidate_key"],
            "indices": row["certification_index_sha256"],
        }
        for row in sorted(
            details,
            key=lambda row: (
                row["dataset"], row["seed"], row["canonical_candidate_key"]
            ),
        )
    ]
    return {
        "kappa_order": list(KAPPAS),
        "rule_order": list(STRESS_RULES),
        "dataset_order": list(DATASETS),
        "registered_candidate_manifest_sha256": canonical_hash(candidate_manifest),
        "registered_certification_stream_manifest_sha256": canonical_hash(
            stream_manifest
        ),
        "registered_objects_reused_across_profiles": True,
        "profiles": profiles,
        "readiness": {
            "always_deploy_max_registered_rate": always_rate,
            "always_deploy_max_registered_dataset": always_dataset,
            "always_deploy_severity_pass": always_rate >= 0.20,
            "validation_selection_max_registered_rate": point_rate,
            "validation_selection_max_registered_dataset": point_dataset,
            "validation_selection_severity_pass": point_rate >= 0.20,
            "vera_max_all_cells_rate": vera_rate,
            "vera_all_cells_measured_safety_pass": vera_rate <= 0.05,
            "registered_vera_sentinel_pass": sentinel,
            "registered_vera_usefulness_pass": usefulness,
            "overall_submission_readiness_support_pass": passed,
            "headline_kappa": 1.0,
            "headline_eligible": passed,
            "negative_result_required": not passed,
            "can_change_primary_gate": False,
        },
        "semantic_consistency_verified": True,
        "can_change_primary_gate": False,
        "decision_rows": decisions,
    }


def validate_fraction(value: Mapping[str, Any], denominator: int) -> None:
    if int(value["denominator"]) != denominator:
        raise RuntimeError("fraction denominator mismatch")
    numerator = int(value["numerator"])
    expected = None if denominator == 0 else numerator / denominator
    if value["estimate"] != expected:
        raise RuntimeError("fraction estimate mismatch")


def validate_report(
    report: Mapping[str, Any], primary: Sequence[Mapping[str, Any]]
) -> None:
    rule_results = report["rule_results"]
    if [row["rule"] for row in rule_results] != list(RULES):
        raise RuntimeError("rule order or membership mismatch")
    for rule in rule_results:
        if int(rule["decisions"]) != 256:
            raise RuntimeError("aggregate decision denominator mismatch")
        validate_fraction(rule["deployments"], 256)
        validate_fraction(rule["violations_all_decisions"], 256)
        if [row["dataset"] for row in rule["per_dataset"]] != list(DATASETS):
            raise RuntimeError("per-dataset order or membership mismatch")
        for dataset in rule["per_dataset"]:
            if int(dataset["decisions"]) != 64:
                raise RuntimeError("per-dataset decision denominator mismatch")
            validate_fraction(dataset["deployments"], 64)
            validate_fraction(dataset["violations_all_decisions"], 64)

    safety = report["safety_sensitivity"]
    matrix = np.asarray(safety["vector_violation_cooccurrence"], dtype=int)
    if matrix.shape != (4, 4) or not np.array_equal(matrix, matrix.T):
        raise RuntimeError("vector co-occurrence matrix is not symmetric 4-by-4")
    vector = next(
        result for result in rule_results if result["rule"] == "vera_vector_envelope"
    )
    diagonal = np.diag(matrix).tolist()
    expected_diagonal = [
        row["violations_all_decisions"]["numerator"]
        for row in vector["per_dataset"]
    ]
    if diagonal != expected_diagonal:
        raise RuntimeError("co-occurrence diagonal disagrees with dataset events")
    multiplicity = safety["vector_violating_dataset_count_by_seed"]
    if len(multiplicity) != 5 or sum(map(int, multiplicity)) != 64:
        raise RuntimeError("violation multiplicity is not an exhaustive seed partition")

    bootstrap = report["bootstrap_sensitivity"]
    useful = bootstrap["usefulness"]
    if (
        int(useful["positive_opportunity_resamples"])
        + int(useful["zero_opportunity_resamples"])
        != BOOTSTRAP_REPLICATES
    ):
        raise RuntimeError("usefulness resamples are not exhaustive")
    cases = bootstrap["vector_common"]["zero_denominator_cases"]
    case_total = sum(
        int(cases[key])
        for key in (
            "positive_opportunity_positive_common",
            "positive_opportunity_zero_common_positive_vector",
            "positive_opportunity_zero_common_zero_vector",
            "zero_opportunity",
        )
    )
    if case_total != BOOTSTRAP_REPLICATES:
        raise RuntimeError("vector/common bootstrap cases are not exhaustive")
    if int(cases["impossible_nonzero_retention_zero_opportunity"]) != 0:
        raise RuntimeError("positive retention appears without an opportunity")

    stress = report["threshold_stress"]
    if stress["kappa_order"] != list(KAPPAS):
        raise RuntimeError("threshold-stress kappa order changed")
    if stress["rule_order"] != list(STRESS_RULES):
        raise RuntimeError("threshold-stress rule order changed")
    if stress["dataset_order"] != list(DATASETS):
        raise RuntimeError("threshold-stress dataset order changed")
    rates: dict[tuple[float, str, str], float] = {}
    for profile, kappa in zip(stress["profiles"], KAPPAS):
        if float(profile["kappa"]) != kappa:
            raise RuntimeError("threshold-stress profile order changed")
        if [rule["rule"] for rule in profile["rules"]] != list(STRESS_RULES):
            raise RuntimeError("threshold-stress profile rule order changed")
        for dataset in DATASETS:
            expected_tau = kappa * THRESHOLDS[dataset][0]
            expected_leakage = 0.5 + kappa * (THRESHOLDS[dataset][1] - 0.5)
            observed = profile["thresholds"][dataset]
            if (
                abs(float(observed["tau"]) - expected_tau) > 1e-12
                or abs(float(observed["lambda"]) - expected_leakage)
                > 1e-12
            ):
                raise RuntimeError("threshold-stress transformed threshold changed")
        for rule in profile["rules"]:
            if [row["dataset"] for row in rule["per_dataset"]] != list(DATASETS):
                raise RuntimeError("threshold-stress dataset order changed")
            for row in rule["per_dataset"]:
                if int(row["decisions"]) != 64:
                    raise RuntimeError("threshold-stress decision denominator changed")
                validate_fraction(row["deployments"], 64)
                validate_fraction(row["violations_all_decisions"], 64)
                rates[(kappa, rule["rule"], row["dataset"])] = row[
                    "violations_all_decisions"
                ]["estimate"]

    readiness = stress["readiness"]
    always_dataset = max(
        DATASETS,
        key=lambda dataset: (
            rates[(1.0, "always_deploy", dataset)],
            -DATASETS.index(dataset),
        ),
    )
    point_dataset = max(
        DATASETS,
        key=lambda dataset: (
            rates[(1.0, "validation_point_selection", dataset)],
            -DATASETS.index(dataset),
        ),
    )
    vera_max = max(
        rates[(kappa, "vera_vector_envelope", dataset)]
        for kappa in KAPPAS
        for dataset in DATASETS
    )
    expected_components = (
        rates[(1.0, "always_deploy", always_dataset)] >= 0.20,
        rates[(1.0, "validation_point_selection", point_dataset)] >= 0.20,
        vera_max <= 0.05,
        bool(readiness["registered_vera_sentinel_pass"]),
        bool(readiness["registered_vera_usefulness_pass"]),
    )
    expected_pass = all(expected_components)
    if (
        bool(readiness["overall_submission_readiness_support_pass"])
        != expected_pass
        or bool(readiness["headline_eligible"]) != expected_pass
        or bool(readiness["negative_result_required"]) == expected_pass
    ):
        raise RuntimeError("threshold-stress readiness logic is inconsistent")

    primary_by_key = {
        (int(row["seed"]), str(row["dataset"]), str(row["rule"])): row
        for row in primary
        if row["rule"] in STRESS_RULES
    }
    registered = {
        (int(row["seed"]), str(row["dataset"]), str(row["rule"])): row
        for row in stress["decision_rows"]
        if float(row["kappa"]) == 1.0
    }
    if set(registered) != set(primary_by_key):
        raise RuntimeError("registered threshold-stress key set changed")
    for key in sorted(registered):
        left = registered[key]
        right = primary_by_key[key]
        for field in ("deployed", "safe", "violation", "selected_candidate"):
            if left[field] != right[field]:
                raise RuntimeError(
                    f"registered threshold-stress decision changed: {key}/{field}"
                )


def analyze(replay: Mapping[str, Any]) -> dict[str, Any]:
    rows = primary_rows(replay)
    details = primary_details(replay)
    rule_results, safety = build_rule_results(rows)
    sensitivity = bootstrap_sensitivities(rows)
    stress = threshold_stress(details, replay["primary_inference"])
    allocations = [
        row
        for row in replay["allocation_records"]
        if abs(float(row["requested_gamma"]) - PRIMARY_GAMMA) <= 1e-12
        and int(row["total_budget"]) == PRIMARY_BUDGET
        and row["allocation"] == PRIMARY_ALLOCATION
    ]
    if len(allocations) != len(SEEDS) * len(DATASETS):
        raise RuntimeError("primary allocation record shape mismatch")
    stress["registered_allocation_manifest_sha256"] = canonical_hash(allocations)
    result = {
        "schema_version": 1,
        "name": "VERA controlled-shift supplementary sensitivities",
        "rule_results": rule_results,
        "safety_sensitivity": safety,
        "bootstrap_sensitivity": sensitivity,
        "threshold_stress": stress,
    }
    validate_report(result, rows)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    replay = json.loads(args.replay.read_text(encoding="utf-8"))
    result = analyze(replay)
    result["input_sha256"] = sha256(args.replay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "output": str(args.output),
                "rule_count": len(result["rule_results"]),
                "threshold_cell_count": 36,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
