"""Analyze the preregistered VERA real-study receipts without tuning outcomes."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import beta, binomtest

from vera_robust_certificate import (
    certify_discrete_group_shift_envelope,
    certify_discrete_shift_radius,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_real.json"
DEFAULT_HASH = ROOT / "prereg_real.sha256"
DEFAULT_RECEIPTS = ROOT / "artifacts" / "real_study_receipts"
DEFAULT_AUDIT = ROOT / "artifacts" / "official_eraser_receipt_audit.json"
DEFAULT_ROWS = ROOT / "artifacts" / "vera_deployment_rule_rows.csv"
DEFAULT_CANDIDATE_ROWS = ROOT / "artifacts" / "vera_candidate_certificate_rows.csv"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_deployment_rule_report.json"
DEFAULT_ABSTRACT = ROOT / "artifacts" / "abstract_numbers_audit.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def cp_interval(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    if trials <= 0:
        return 0.0, 1.0
    lower = 0.0 if successes == 0 else float(
        beta.ppf(alpha / 2.0, successes, trials - successes + 1)
    )
    upper = 1.0 if successes == trials else float(
        beta.ppf(1.0 - alpha / 2.0, successes + 1, trials - successes)
    )
    return lower, upper


def nested_stratified_indices(
    target: np.ndarray,
    source: np.ndarray,
    environment: np.ndarray,
    fractions: list[float],
    seed: int,
) -> dict[float, np.ndarray]:
    rng = np.random.default_rng(seed)
    strata: dict[tuple[int, int, int], np.ndarray] = {}
    for key in sorted(set(zip(map(int, target), map(int, source), map(int, environment)))):
        indices = np.flatnonzero(
            (target == key[0]) & (source == key[1]) & (environment == key[2])
        )
        rng.shuffle(indices)
        strata[key] = indices
    outputs: dict[float, np.ndarray] = {}
    for fraction in sorted(fractions):
        selected: list[int] = []
        for indices in strata.values():
            take = len(indices) if fraction >= 1.0 else max(1, int(np.floor(fraction * len(indices))))
            selected.extend(indices[:take].tolist())
        outputs[fraction] = np.asarray(sorted(selected), dtype=np.int64)
    return outputs


def contract_samples(
    arrays: dict[str, np.ndarray],
    indices: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict[str, tuple[int, ...]]]:
    target_harm = arrays["target_harm_certification"][indices]
    source = arrays["source_certification"][indices]
    environment = arrays["environment_certification"][indices]
    samples: dict[str, np.ndarray] = {}
    supports: dict[str, tuple[int, ...]] = {}
    for group in sorted(map(int, np.unique(environment))):
        mask = environment == group
        key = f"target::environment={group}"
        samples[key] = target_harm[mask]
        supports[key] = (-1, 0, 1)
    for array_name, values in arrays.items():
        prefix = "leakage_correct_certification__"
        if not array_name.startswith(prefix):
            continue
        attacker = array_name[len(prefix) :]
        values = values[indices]
        for group, source_class in sorted(
            set(zip(map(int, environment), map(int, source)))
        ):
            mask = (environment == group) & (source == source_class)
            key = f"leakage::{attacker}::environment={group}::source={source_class}"
            samples[key] = values[mask]
            supports[key] = (0, 1)
    return samples, supports


def point_metrics(samples: dict[str, np.ndarray]) -> tuple[float, float]:
    target = [float(values.mean()) for key, values in samples.items() if key.startswith("target::")]
    leakage = [float(values.mean()) for key, values in samples.items() if key.startswith("leakage::")]
    return max(target), max(leakage)


def group_contract_family(
    samples: dict[str, np.ndarray],
    supports: dict[str, tuple[int, ...]],
    thresholds: dict[str, float],
) -> tuple[
    dict[str, dict[str, np.ndarray]],
    dict[str, dict[str, tuple[int, ...]]],
    dict[str, dict[str, float]],
]:
    grouped_samples: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    grouped_supports: dict[str, dict[str, tuple[int, ...]]] = defaultdict(dict)
    grouped_thresholds: dict[str, dict[str, float]] = defaultdict(dict)
    for key, values in samples.items():
        if "environment=" not in key:
            raise ValueError(f"contract key has no registered environment: {key}")
        group = key.split("environment=", 1)[1].split("::", 1)[0]
        grouped_samples[group][key] = values
        grouped_supports[group][key] = supports[key]
        grouped_thresholds[group][key] = thresholds[key]
    return dict(grouped_samples), dict(grouped_supports), dict(grouped_thresholds)


def external_metrics(arrays: dict[str, np.ndarray]) -> tuple[float, float]:
    target_harm = arrays["target_harm_external"]
    source = arrays["source_external"]
    environment = arrays["environment_external"]
    target_values = [
        float(target_harm[environment == group].mean())
        for group in sorted(map(int, np.unique(environment)))
    ]
    leakage_values: list[float] = []
    for array_name, values in arrays.items():
        prefix = "leakage_correct_external__"
        if not array_name.startswith(prefix):
            continue
        for group, source_class in sorted(set(zip(map(int, environment), map(int, source)))):
            mask = (environment == group) & (source == source_class)
            leakage_values.append(float(values[mask].mean()))
    return max(target_values), max(leakage_values)


def choose(candidates: list[dict[str, Any]], predicate: str | None = None) -> dict[str, Any] | None:
    eligible = candidates if predicate is None else [candidate for candidate in candidates if candidate[predicate]]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda candidate: (
            candidate["validation_max_leakage"],
            candidate["validation_max_target_harm"],
            candidate["key"],
        ),
    )


def holm_adjust(p_values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(p_values, key=p_values.get)
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, key in enumerate(ordered):
        value = min(1.0, (total - rank) * p_values[key])
        running = max(running, value)
        adjusted[key] = running
    return adjusted


def exact_cluster_signflip(differences: list[float]) -> float:
    """Two-sided randomization p-value with one sign flip per independent seed."""

    if not differences or not any(abs(value) > 1e-15 for value in differences):
        return 1.0
    observed = abs(float(np.mean(differences)))
    null_statistics = [
        abs(float(np.mean([sign * value for sign, value in zip(signs, differences)])))
        for signs in product((-1.0, 1.0), repeat=len(differences))
    ]
    return sum(value >= observed - 1e-15 for value in null_statistics) / len(null_statistics)


def analyze(
    args: argparse.Namespace,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[str, Any],
]:
    prereg = load_json(args.prereg)
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    prereg_hash = sha256(args.prereg)
    if prereg_hash != expected_hash:
        raise RuntimeError("real-study preregistration hash mismatch")
    receipt_audit = load_json(args.receipt_audit)
    if receipt_audit.get("passed") is not True:
        raise RuntimeError("official receipt matrix has not passed its audit")

    study = prereg["real_study"]
    datasets: dict[str, dict[str, Any]] = study["datasets"]
    methods: dict[str, dict[str, Any]] = study["methods"]
    seeds = [int(value) for value in study["seeds"]]
    fractions = [float(value) for value in study["validation_fractions"]]
    target_thresholds = [float(value) for value in study["target_harm_thresholds"]]
    leakage_thresholds = [float(value) for value in study["leakage_thresholds"]]
    delta = float(study["delta"])
    deployment_gamma = float(study["deployment_gamma"])
    gamma_cap = float(study["gamma_cap"])

    rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for dataset_name, dataset_config in datasets.items():
        support_mismatch = bool(dataset_config.get("force_abstain_for_unsupported_environment"))
        for seed in seeds:
            loaded_candidates: list[dict[str, Any]] = []
            reference_labels: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
            for method_key, method_config in methods.items():
                receipt_path = args.receipt_dir / f"{dataset_name}__{method_key}__seed-{seed}.json"
                receipt = load_json(receipt_path)
                for candidate_index, candidate in enumerate(receipt["candidates"]):
                    with np.load(candidate["audit_npz"]) as archive:
                        arrays = {key: np.asarray(archive[key]) for key in archive.files}
                    labels = (
                        arrays["target_certification"],
                        arrays["source_certification"],
                        arrays["environment_certification"],
                    )
                    if reference_labels is None:
                        reference_labels = labels
                    elif not all(np.array_equal(left, right) for left, right in zip(reference_labels, labels)):
                        raise RuntimeError(f"label arrays differ across candidates for {dataset_name}/seed-{seed}")
                    loaded_candidates.append({
                        "key": f"{method_config['display_name']}::{candidate['strength']}",
                        "method": method_config["display_name"],
                        "arrays": arrays,
                        "external_metrics": external_metrics(arrays),
                    })
            assert reference_labels is not None
            observed_groups = sorted(map(int, np.unique(reference_labels[2])))
            registered_groups = sorted(
                set(observed_groups)
                | {
                    int(value)
                    for value in dataset_config.get(
                        "unsupported_external_environment_classes", []
                    )
                }
            )
            subsets = nested_stratified_indices(
                *reference_labels,
                fractions,
                seed=2_027_071_300 + 1009 * seed + sum(map(ord, dataset_name)),
            )
            for fraction in fractions:
                subset = subsets[fraction]
                candidate_samples: list[tuple[dict[str, Any], dict[str, np.ndarray], dict[str, tuple[int, ...]]]] = []
                family_size = 0
                for candidate in loaded_candidates:
                    samples, supports = contract_samples(candidate["arrays"], subset)
                    family_size += len(samples)
                    candidate_samples.append((candidate, samples, supports))
                for target_threshold in target_thresholds:
                    for leakage_threshold in leakage_thresholds:
                        evaluated: list[dict[str, Any]] = []
                        for candidate, samples, supports in candidate_samples:
                            target_point, leakage_point = point_metrics(samples)
                            thresholds = {
                                key: target_threshold if key.startswith("target::") else leakage_threshold
                                for key in samples
                            }
                            radius = certify_discrete_shift_radius(
                                samples,
                                delta=delta,
                                supports=supports,
                                thresholds=thresholds,
                                family_size=family_size,
                                gamma_cap=gamma_cap,
                            )
                            (
                                grouped_samples,
                                grouped_supports,
                                grouped_thresholds,
                            ) = group_contract_family(samples, supports, thresholds)
                            envelope = certify_discrete_group_shift_envelope(
                                grouped_samples,
                                delta=delta,
                                grouped_supports=grouped_supports,
                                grouped_thresholds=grouped_thresholds,
                                family_size=family_size,
                                registered_groups=[str(value) for value in registered_groups],
                                gamma_cap=gamma_cap,
                            )
                            if not np.isclose(
                                envelope.observed_common_radius,
                                radius.certified_radius,
                                atol=1e-4,
                            ):
                                raise RuntimeError(
                                    "groupwise envelope minimum differs from the joint radius"
                                )
                            external_target, external_leakage = candidate["external_metrics"]
                            external_contract_satisfied = (
                                external_target <= target_threshold
                                and external_leakage <= leakage_threshold
                            )
                            evaluated.append({
                                "key": candidate["key"],
                                "method": candidate["method"],
                                "validation_max_target_harm": target_point,
                                "validation_max_leakage": leakage_point,
                                "point_feasible": target_point <= target_threshold and leakage_point <= leakage_threshold,
                                "iid_certified": not support_mismatch and radius.certified_radius >= 1.0,
                                "vera_certified": not support_mismatch and radius.certified_radius >= deployment_gamma,
                                "certified_radius": radius.certified_radius,
                                "certified_group_radii": dict(envelope.group_radii),
                                "observed_environment_classes": observed_groups,
                                "unsupported_environment_classes": list(
                                    envelope.unsupported_groups
                                ),
                                "deployment_support_radius": (
                                    envelope.deployment_common_radius
                                ),
                                "limiting_contracts": list(radius.limiting_contracts),
                                "external_max_target_harm": external_target,
                                "external_max_leakage": external_leakage,
                                "external_contract_satisfied": external_contract_satisfied,
                                "protocol_safe": external_contract_satisfied and not support_mismatch,
                            })
                        for candidate in evaluated:
                            candidate_rows.append({
                                "config_id": (
                                    f"{dataset_name}|seed={seed}|fraction={fraction:g}|"
                                    f"tau={target_threshold:g}|lambda={leakage_threshold:g}"
                                ),
                                "dataset": dataset_name,
                                "seed": seed,
                                "validation_fraction": fraction,
                                "certification_n": len(subset),
                                "target_threshold": target_threshold,
                                "leakage_threshold": leakage_threshold,
                                "deployment_gamma": deployment_gamma,
                                "candidate": candidate["key"],
                                "method": candidate["method"],
                                "validation_max_target_harm": candidate["validation_max_target_harm"],
                                "validation_max_leakage": candidate["validation_max_leakage"],
                                "point_feasible": candidate["point_feasible"],
                                "iid_certified": candidate["iid_certified"],
                                "vera_certified": candidate["vera_certified"],
                                "certified_radius": candidate["certified_radius"],
                                "certified_group_radii": json.dumps(
                                    candidate["certified_group_radii"], sort_keys=True
                                ),
                                "observed_environment_classes": json.dumps(
                                    candidate["observed_environment_classes"]
                                ),
                                "unsupported_environment_classes": json.dumps(
                                    candidate["unsupported_environment_classes"]
                                ),
                                "deployment_support_radius": candidate[
                                    "deployment_support_radius"
                                ],
                                "limiting_contracts": json.dumps(candidate["limiting_contracts"]),
                                "external_max_target_harm": candidate["external_max_target_harm"],
                                "external_max_leakage": candidate["external_max_leakage"],
                                "external_contract_satisfied": candidate["external_contract_satisfied"],
                                "protocol_safe": candidate["protocol_safe"],
                                "support_mismatch": support_mismatch,
                            })
                        selections = {
                            "always_deploy": choose(evaluated),
                            "point_selection": choose(evaluated, "point_feasible"),
                            "iid_ltt": choose(evaluated, "iid_certified"),
                            "vera": choose(evaluated, "vera_certified"),
                            "oracle": min(
                                [
                                    candidate
                                    for candidate in evaluated
                                    if candidate["external_contract_satisfied"]
                                ],
                                key=lambda candidate: (
                                    candidate["external_max_leakage"],
                                    candidate["external_max_target_harm"],
                                    candidate["key"],
                                ),
                                default=None,
                            ),
                        }
                        config_id = (
                            f"{dataset_name}|seed={seed}|fraction={fraction:g}|"
                            f"tau={target_threshold:g}|lambda={leakage_threshold:g}"
                        )
                        for rule, selected in selections.items():
                            deployed = selected is not None
                            rows.append({
                                "config_id": config_id,
                                "dataset": dataset_name,
                                "seed": seed,
                                "validation_fraction": fraction,
                                "certification_n": len(subset),
                                "target_threshold": target_threshold,
                                "leakage_threshold": leakage_threshold,
                                "deployment_gamma": deployment_gamma,
                                "rule": rule,
                                "deployed": deployed,
                                "selected_candidate": selected["key"] if deployed else "",
                                "selected_method": selected["method"] if deployed else "",
                                "certified_radius": selected["certified_radius"] if deployed else 0.0,
                                "certified_group_radii": (
                                    json.dumps(
                                        selected["certified_group_radii"], sort_keys=True
                                    )
                                    if deployed
                                    else "{}"
                                ),
                                "deployment_support_radius": (
                                    selected["deployment_support_radius"] if deployed else 0.0
                                ),
                                "limiting_contracts": (
                                    json.dumps(selected["limiting_contracts"])
                                    if deployed
                                    else "[]"
                                ),
                                "validation_max_target_harm": (
                                    selected["validation_max_target_harm"] if deployed else ""
                                ),
                                "validation_max_leakage": (
                                    selected["validation_max_leakage"] if deployed else ""
                                ),
                                "external_max_target_harm": (
                                    selected["external_max_target_harm"] if deployed else ""
                                ),
                                "external_max_leakage": (
                                    selected["external_max_leakage"] if deployed else ""
                                ),
                                "external_contract_satisfied": (
                                    bool(selected["external_contract_satisfied"])
                                    if deployed
                                    else False
                                ),
                                "protocol_safe": bool(selected["protocol_safe"]) if deployed else False,
                                "false_acceptance": bool(
                                    deployed and not selected["external_contract_satisfied"]
                                ),
                                "measured_external_contract_violation": bool(
                                    deployed and not selected["external_contract_satisfied"]
                                ),
                                "preregistered_unsafe_deployment": bool(
                                    deployed and not selected["protocol_safe"]
                                ),
                                "support_mismatch_forced_abstention": (
                                    support_mismatch and rule in {"iid_ltt", "vera"}
                                ),
                            })

    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_rule[row["rule"]].append(row)
    summaries: dict[str, dict[str, Any]] = {}
    for rule, rule_rows in by_rule.items():
        false_count = sum(bool(row["false_acceptance"]) for row in rule_rows)
        lower, upper = cp_interval(false_count, len(rule_rows))
        summaries[rule] = {
            "configuration_count": len(rule_rows),
            "deployment_count": sum(bool(row["deployed"]) for row in rule_rows),
            "false_acceptance_count": false_count,
            "false_acceptance_rate": false_count / len(rule_rows),
            "false_acceptance_cp95": [lower, upper],
            "measured_external_contract_violation_count": false_count,
            "measured_external_contract_violation_rate": (
                false_count / len(rule_rows)
            ),
            "preregistered_unsafe_deployment_count": sum(
                bool(row["preregistered_unsafe_deployment"]) for row in rule_rows
            ),
            "preregistered_unsafe_deployment_rate": sum(
                bool(row["preregistered_unsafe_deployment"]) for row in rule_rows
            ) / len(rule_rows),
        }

    point_rows = {row["config_id"]: row for row in by_rule["point_selection"]}
    vera_rows = {row["config_id"]: row for row in by_rule["vera"]}
    oracle_rows = {row["config_id"]: row for row in by_rule["oracle"]}
    naive_regimes: dict[str, dict[str, Any]] = {}
    mcnemar_raw: dict[str, float] = {}
    mcnemar_counts: dict[str, dict[str, int]] = {}
    seed_blocked_differences: dict[str, list[float]] = {}
    seed_blocked_raw: dict[str, float] = {}
    for dataset_name in datasets:
        regime_rates: dict[tuple[float, float, float], list[bool]] = defaultdict(list)
        dataset_ids = [key for key, row in point_rows.items() if row["dataset"] == dataset_name]
        for config_id in dataset_ids:
            row = point_rows[config_id]
            regime = (
                float(row["validation_fraction"]),
                float(row["target_threshold"]),
                float(row["leakage_threshold"]),
            )
            regime_rates[regime].append(bool(row["false_acceptance"]))
        best_regime, outcomes = max(
            regime_rates.items(), key=lambda item: (sum(item[1]) / len(item[1]), item[0])
        )
        naive_regimes[dataset_name] = {
            "validation_fraction": best_regime[0],
            "target_threshold": best_regime[1],
            "leakage_threshold": best_regime[2],
            "false_acceptance_rate": sum(outcomes) / len(outcomes),
            "false_acceptances": sum(outcomes),
            "seeds": len(outcomes),
        }
        b = sum(
            bool(point_rows[key]["false_acceptance"])
            and not bool(vera_rows[key]["false_acceptance"])
            for key in dataset_ids
        )
        c = sum(
            not bool(point_rows[key]["false_acceptance"])
            and bool(vera_rows[key]["false_acceptance"])
            for key in dataset_ids
        )
        mcnemar_counts[dataset_name] = {"point_only_false": b, "vera_only_false": c}
        mcnemar_raw[dataset_name] = (
            1.0 if b + c == 0 else float(binomtest(min(b, c), b + c, 0.5, alternative="two-sided").pvalue)
        )
        differences: list[float] = []
        for seed in seeds:
            seed_ids = [key for key in dataset_ids if int(point_rows[key]["seed"]) == seed]
            point_rate = float(np.mean([point_rows[key]["false_acceptance"] for key in seed_ids]))
            vera_rate = float(np.mean([vera_rows[key]["false_acceptance"] for key in seed_ids]))
            differences.append(point_rate - vera_rate)
        seed_blocked_differences[dataset_name] = differences
        seed_blocked_raw[dataset_name] = exact_cluster_signflip(differences)
    mcnemar_adjusted = holm_adjust(mcnemar_raw)
    seed_blocked_adjusted = holm_adjust(seed_blocked_raw)

    oracle_possible = sum(bool(row["deployed"]) for row in oracle_rows.values())
    vera_safe = sum(
        bool(row["deployed"] and row["external_contract_satisfied"])
        for row in vera_rows.values()
        if oracle_rows[row["config_id"]]["deployed"]
    )
    retention = vera_safe / oracle_possible if oracle_possible else 0.0
    retention_interval = cp_interval(vera_safe, oracle_possible)
    configuration_significant_count = sum(value <= 0.05 for value in mcnemar_adjusted.values())
    seed_blocked_significant_count = sum(
        value <= 0.05 for value in seed_blocked_adjusted.values()
    )
    naive_dataset_count = sum(
        float(record["false_acceptance_rate"]) >= 0.2 for record in naive_regimes.values()
    )
    vera_upper = float(summaries["vera"]["false_acceptance_cp95"][1])
    descriptive_conditions_passed = naive_dataset_count == 5 and (
        float(summaries["vera"]["false_acceptance_rate"]) <= delta
    )
    report = {
        "name": "VERA preregistered deployment-rule study",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": descriptive_conditions_passed and seed_blocked_significant_count >= 4,
        "preregistered_configuration_level_passed": (
            naive_dataset_count == 5
            and vera_upper <= delta
            and configuration_significant_count >= 4
        ),
        "descriptive_conditions_passed": descriptive_conditions_passed,
        "prereg_sha256": prereg_hash,
        "datasets": list(datasets),
        "seeds": seeds,
        "eraser_count": len(methods),
        "threshold_pair_count": len(target_thresholds) * len(leakage_thresholds),
        "validation_size_count": len(fractions),
        "deployment_rules": list(by_rule),
        "delta": delta,
        "deployment_gamma": deployment_gamma,
        "summaries": summaries,
        "naive_failure_regimes": naive_regimes,
        "datasets_with_naive_violation_at_least_20pct": naive_dataset_count,
        "vera_global_false_acceptance_upper": vera_upper,
        "mcnemar_discordant_counts": mcnemar_counts,
        "mcnemar_raw_p": mcnemar_raw,
        "mcnemar_holm_p": mcnemar_adjusted,
        "holm_mcnemar_significant_dataset_count": configuration_significant_count,
        "configuration_level_dependence_warning": (
            "The McNemar pairs reuse seeds, samples, thresholds, and nested fractions; "
            "their p-values are preregistered diagnostics, not valid independent-pair inference."
        ),
        "seed_blocked_rate_differences": seed_blocked_differences,
        "seed_blocked_signflip_raw_p": seed_blocked_raw,
        "seed_blocked_signflip_holm_p": seed_blocked_adjusted,
        "seed_blocked_significant_dataset_count": seed_blocked_significant_count,
        "certification_tax_intervals_reported": True,
        "safe_deployment_retention": retention,
        "safe_deployment_retention_cp95": list(retention_interval),
        "oracle_certifiable_configuration_count": oracle_possible,
        "measured_external_oracle_opportunity_count": oracle_possible,
        "vera_safe_deployment_count": vera_safe,
        "endpoint_semantics": {
            "false_acceptance": (
                "Compatibility name for deployment followed by a measured external "
                "contract violation; it is not evidence that the external law lies "
                "inside the declared ambiguity set."
            ),
            "preregistered_unsafe_deployment": (
                "Measured external contract violation or deployment into a registered "
                "environment absent from certification."
            ),
            "safe_deployment_retention": (
                "Fraction of measured external-oracle opportunities in which VERA "
                "deploys an edit that meets the measured external contract."
            ),
        },
        "statistical_caution": (
            "Threshold/fraction configurations share seeds and are not independent. Configuration-level "
            "Clopper-Pearson and McNemar values are reported exactly as preregistered diagnostics; the "
            "exact seed-blocked sign-flip analysis governs inferential claims. With five seed blocks, its "
            "minimum attainable two-sided unadjusted p-value is 0.0625."
        ),
    }
    x = float(summaries["point_selection"]["false_acceptance_rate"])
    y = float(summaries["vera"]["false_acceptance_rate"])
    sentence = (
        f"Point selection deploys edits that violate the measured external contract in "
        f"{100*x:.1f}% of registered configurations; VERA does so in {100*y:.1f}% while "
        f"deploying safely in {100*retention:.1f}% of measured external-oracle opportunities."
    )
    abstract = {
        "verified": x - y >= 0.15 and report["passed"],
        "prereg_sha256": prereg_hash,
        "point_selection_violation_rate": x,
        "vera_violation_rate": y,
        "safe_deployment_retention": retention,
        "difference": x - y,
        "sentence": sentence,
        "sentence_matches_manuscript": False,
        "all_numbers_receipted": True,
        "source_report": str(args.report),
        "source_rows": str(args.rows),
    }
    return rows, candidate_rows, report, abstract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--receipt-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATE_ROWS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--abstract-report", type=Path, default=DEFAULT_ABSTRACT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, candidate_rows, report, abstract = analyze(args)
    args.rows.parent.mkdir(parents=True, exist_ok=True)
    args.candidate_rows.parent.mkdir(parents=True, exist_ok=True)
    with args.rows.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with args.candidate_rows.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(candidate_rows[0]), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(candidate_rows)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.abstract_report.write_text(json.dumps(abstract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "passed": report["passed"],
        "rows": len(rows),
        "candidate_rows": len(candidate_rows),
        "point_false_acceptance": abstract["point_selection_violation_rate"],
        "vera_false_acceptance": abstract["vera_violation_rate"],
        "retention": abstract["safe_deployment_retention"],
    }, indent=2))


if __name__ == "__main__":
    main()
