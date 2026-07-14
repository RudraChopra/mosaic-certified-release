"""Analyze the untouched-seed VERA balanced-leakage confirmatory study."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np

from analyze_vera_attacker_ablation import load_candidates
from analyze_vera_balanced_existing import (
    balanced_external_metrics,
    balanced_point_metrics,
    balanced_samples,
    choose,
)
from analyze_vera_real_study import cp_interval, holm_adjust, nested_stratified_indices
from vera_robust_certificate import (
    certify_balanced_iut_fixed_profile,
    certify_balanced_shift_radius,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_confirmatory_balanced.json"
DEFAULT_HASH = ROOT / "prereg_confirmatory_balanced.sha256"
DEFAULT_AUDIT = ROOT / "artifacts" / "confirmatory_balanced_receipt_audit.json"
DEFAULT_RECEIPTS = ROOT / "artifacts" / "confirmatory_balanced_receipts"
DEFAULT_ROWS = ROOT / "artifacts" / "vera_confirmatory_balanced_rule_rows.csv"
DEFAULT_CANDIDATES = ROOT / "artifacts" / "vera_confirmatory_balanced_candidate_rows.csv"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_confirmatory_balanced_report.json"
DEFAULT_ABSTRACT = ROOT / "artifacts" / "vera_confirmatory_abstract_numbers.json"
RULES = (
    "always_deploy_balanced",
    "point_selection_balanced",
    "vera_balanced_iut",
    "vera_balanced_envelope",
    "external_balanced_oracle",
)


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


def exact_one_sided_signflip(differences: list[float]) -> float:
    """Exact seed-blocked randomization p-value for positive mean improvement."""

    if not differences or not any(abs(value) > 1e-15 for value in differences):
        return 1.0
    observed = float(np.mean(differences))
    if observed <= 0.0:
        return 1.0
    null_statistics = [
        float(np.mean([sign * value for sign, value in zip(signs, differences)]))
        for signs in product((-1.0, 1.0), repeat=len(differences))
    ]
    return sum(value >= observed - 1e-15 for value in null_statistics) / len(
        null_statistics
    )


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    estimable = [row for row in rows if row["external_contract_estimable"]]
    deployments = sum(bool(row["deployed"]) for row in rows)
    estimable_deployments = sum(bool(row["deployed"]) for row in estimable)
    violations = sum(bool(row["measured_external_contract_violation"]) for row in estimable)
    safe = sum(
        bool(row["deployed"] and row["external_contract_satisfied"] is True)
        for row in estimable
    )
    denominator = len(estimable)
    return {
        "configuration_count": len(rows),
        "estimable_configuration_count": denominator,
        "deployment_count": deployments,
        "deployment_rate": 0.0 if not rows else deployments / len(rows),
        "estimable_deployment_count": estimable_deployments,
        "safe_deployment_count": safe,
        "measured_external_violation_count": violations,
        "measured_external_violation_rate": (
            None if denominator == 0 else violations / denominator
        ),
        "measured_external_violation_cp95": list(cp_interval(violations, denominator)),
        "violation_rate_conditional_on_estimable_deployment": (
            None if estimable_deployments == 0 else violations / estimable_deployments
        ),
        "procedurally_unsupported_deployment_count": sum(
            bool(row["procedurally_unsupported_deployment"]) for row in rows
        ),
    }


def run_analysis(
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    prereg_hash = sha256(args.prereg)
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    if prereg_hash != expected_hash:
        raise RuntimeError("confirmatory preregistration hash mismatch")
    prereg = load_json(args.prereg)
    if prereg.get("phase") != "untouched_seed confirmatory balanced-leakage study":
        raise RuntimeError("wrong confirmatory preregistration phase")
    audit = load_json(args.receipt_audit)
    if audit.get("passed") is not True or audit.get("prereg_sha256") != prereg_hash:
        raise RuntimeError("confirmatory receipt matrix has not passed its locked audit")

    study = prereg["real_study"]
    datasets: dict[str, dict[str, Any]] = study["datasets"]
    seeds = [int(value) for value in study["seeds"]]
    fractions = [float(value) for value in study["validation_fractions"]]
    primary_fraction = float(study["primary_validation_fraction"])
    target_thresholds = [float(value) for value in study["target_harm_thresholds"]]
    leakage_thresholds = [float(value) for value in study["leakage_thresholds"]]
    delta = float(study["delta"])
    primary_gamma = float(study["deployment_gamma"])
    shifted_gamma = float(study["shifted_sensitivity_gamma"])
    gamma_cap = float(study["gamma_cap"])
    settings = [(fraction, primary_gamma) for fraction in fractions]
    settings.append((primary_fraction, shifted_gamma))

    rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for dataset, dataset_config in datasets.items():
        support_mismatch = bool(
            dataset_config.get("force_abstain_for_unsupported_environment")
        )
        for seed in seeds:
            loaded, labels = load_candidates(args.receipt_dir, study, dataset, seed)
            if len(loaded) != 12:
                raise RuntimeError(f"expected 12 candidates for {dataset}/seed-{seed}")
            for candidate in loaded:
                candidate["balanced_external_metrics"] = balanced_external_metrics(
                    candidate["arrays"]
                )
            subsets = nested_stratified_indices(
                *labels,
                fractions,
                seed=2_027_071_300 + 1009 * seed + sum(map(ord, dataset)),
            )
            for fraction, gamma in settings:
                subset = subsets[fraction]
                prepared = []
                for candidate in loaded:
                    target, leakage, source = balanced_samples(candidate["arrays"], subset)
                    target_point, leakage_point = balanced_point_metrics(
                        target, leakage, source
                    )
                    prepared.append(
                        {
                            **candidate,
                            "target": target,
                            "leakage": leakage,
                            "source": source,
                            "validation_max_target_harm": target_point,
                            "validation_max_balanced_leakage": leakage_point,
                        }
                    )
                family_size = len(prepared) * (
                    len(prepared[0]["target"]) + len(prepared[0]["leakage"])
                )
                tier = (
                    "shifted_sensitivity"
                    if gamma == shifted_gamma
                    else "primary"
                    if fraction == primary_fraction
                    else "learning_curve"
                )
                for target_threshold in target_thresholds:
                    for leakage_threshold in leakage_thresholds:
                        config_id = (
                            f"{tier}|{dataset}|seed={seed}|fraction={fraction:g}|"
                            f"gamma={gamma:g}|tau={target_threshold:g}|"
                            f"lambda={leakage_threshold:g}"
                        )
                        evaluated: list[dict[str, Any]] = []
                        for candidate in prepared:
                            envelope = certify_balanced_shift_radius(
                                candidate["target"],
                                candidate["leakage"],
                                candidate["source"],
                                delta=delta,
                                family_size=family_size,
                                target_threshold=target_threshold,
                                leakage_threshold=leakage_threshold,
                                gamma_cap=gamma_cap,
                            )
                            iut = certify_balanced_iut_fixed_profile(
                                candidate["target"],
                                candidate["leakage"],
                                candidate["source"],
                                gamma=gamma,
                                delta=delta,
                                candidate_count=len(prepared),
                                target_threshold=target_threshold,
                                leakage_threshold=leakage_threshold,
                            )
                            external_target, external_leakage = candidate[
                                "balanced_external_metrics"
                            ]
                            external_estimable = external_leakage is not None
                            external_satisfied = (
                                None
                                if not external_estimable
                                else external_target <= target_threshold
                                and float(external_leakage) <= leakage_threshold
                            )
                            record = {
                                "candidate": candidate["candidate"],
                                "method": candidate["method"],
                                "validation_max_target_harm": candidate[
                                    "validation_max_target_harm"
                                ],
                                "validation_max_balanced_leakage": candidate[
                                    "validation_max_balanced_leakage"
                                ],
                                "point_feasible": (
                                    candidate["validation_max_target_harm"]
                                    <= target_threshold
                                    and candidate["validation_max_balanced_leakage"]
                                    <= leakage_threshold
                                ),
                                "iut_eligible": (
                                    not support_mismatch and iut.decision == "EDIT"
                                ),
                                "envelope_eligible": (
                                    not support_mismatch
                                    and envelope.certified_radius >= gamma
                                ),
                                "envelope_radius": envelope.certified_radius,
                                "iut_limiting_contracts": iut.limiting_contracts,
                                "envelope_limiting_contracts": envelope.limiting_contracts,
                                "external_max_target_harm": external_target,
                                "external_max_balanced_leakage": external_leakage,
                                "external_contract_estimable": external_estimable,
                                "external_contract_satisfied": external_satisfied,
                            }
                            evaluated.append(record)
                            candidate_rows.append(
                                {
                                    "config_id": config_id,
                                    "analysis_tier": tier,
                                    "dataset": dataset,
                                    "seed": seed,
                                    "validation_fraction": fraction,
                                    "certification_n": len(subset),
                                    "gamma": gamma,
                                    "target_threshold": target_threshold,
                                    "leakage_threshold": leakage_threshold,
                                    "family_size": family_size,
                                    "candidate": record["candidate"],
                                    "method": record["method"],
                                    "validation_max_target_harm": record[
                                        "validation_max_target_harm"
                                    ],
                                    "validation_max_balanced_leakage": record[
                                        "validation_max_balanced_leakage"
                                    ],
                                    "point_feasible": record["point_feasible"],
                                    "iut_eligible": record["iut_eligible"],
                                    "envelope_eligible": record["envelope_eligible"],
                                    "envelope_radius": record["envelope_radius"],
                                    "iut_limiting_contracts": json.dumps(
                                        record["iut_limiting_contracts"]
                                    ),
                                    "envelope_limiting_contracts": json.dumps(
                                        record["envelope_limiting_contracts"]
                                    ),
                                    "external_max_target_harm": record[
                                        "external_max_target_harm"
                                    ],
                                    "external_max_balanced_leakage": (
                                        ""
                                        if external_leakage is None
                                        else external_leakage
                                    ),
                                    "external_contract_estimable": external_estimable,
                                    "external_contract_satisfied": (
                                        "NA"
                                        if external_satisfied is None
                                        else external_satisfied
                                    ),
                                    "support_mismatch": support_mismatch,
                                    "confirmatory": True,
                                }
                            )
                        selections = {
                            "always_deploy_balanced": choose(evaluated),
                            "point_selection_balanced": choose(
                                evaluated, "point_feasible"
                            ),
                            "vera_balanced_iut": choose(evaluated, "iut_eligible"),
                            "vera_balanced_envelope": choose(
                                evaluated, "envelope_eligible"
                            ),
                            "external_balanced_oracle": choose(
                                [
                                    candidate
                                    for candidate in evaluated
                                    if candidate["external_contract_satisfied"] is True
                                ]
                            ),
                        }
                        for rule, selected in selections.items():
                            deployed = selected is not None
                            estimable = (
                                bool(selected["external_contract_estimable"])
                                if deployed
                                else not support_mismatch
                            )
                            satisfied = (
                                selected["external_contract_satisfied"]
                                if deployed and estimable
                                else None
                            )
                            rows.append(
                                {
                                    "config_id": config_id,
                                    "analysis_tier": tier,
                                    "dataset": dataset,
                                    "seed": seed,
                                    "validation_fraction": fraction,
                                    "certification_n": len(subset),
                                    "gamma": gamma,
                                    "target_threshold": target_threshold,
                                    "leakage_threshold": leakage_threshold,
                                    "rule": rule,
                                    "deployed": deployed,
                                    "selected_candidate": (
                                        selected["candidate"] if deployed else ""
                                    ),
                                    "selected_method": (
                                        selected["method"] if deployed else ""
                                    ),
                                    "selected_envelope_radius": (
                                        selected["envelope_radius"] if deployed else 0.0
                                    ),
                                    "external_contract_estimable": estimable,
                                    "external_contract_satisfied": (
                                        "NA" if satisfied is None else satisfied
                                    ),
                                    "measured_external_contract_violation": (
                                        False
                                        if satisfied is None
                                        else bool(deployed and not satisfied)
                                    ),
                                    "procedurally_unsupported_deployment": (
                                        deployed and support_mismatch
                                    ),
                                    "support_mismatch_forced_abstention": (
                                        support_mismatch
                                        and rule
                                        in {
                                            "vera_balanced_iut",
                                            "vera_balanced_envelope",
                                        }
                                        and not deployed
                                    ),
                                    "confirmatory": True,
                                }
                            )

    expected_settings = len(fractions) + 1
    expected_configs = (
        len(datasets)
        * len(seeds)
        * expected_settings
        * len(target_thresholds)
        * len(leakage_thresholds)
    )
    if len(rows) != expected_configs * len(RULES):
        raise RuntimeError("confirmatory rule table shape mismatch")
    if len(candidate_rows) != expected_configs * 12:
        raise RuntimeError("confirmatory candidate table shape mismatch")

    primary = [row for row in rows if row["analysis_tier"] == "primary"]
    shifted = [row for row in rows if row["analysis_tier"] == "shifted_sensitivity"]
    supported = [
        dataset
        for dataset, config in datasets.items()
        if not config.get("force_abstain_for_unsupported_environment")
    ]

    def rule_rows(values: list[dict[str, Any]], rule: str) -> list[dict[str, Any]]:
        return [row for row in values if row["rule"] == rule]

    primary_summaries = {
        rule: summarize(rule_rows(primary, rule)) for rule in RULES
    }
    shifted_summaries = {
        rule: summarize(rule_rows(shifted, rule)) for rule in RULES
    }
    primary_by_dataset = {
        dataset: {
            rule: summarize(
                [
                    row
                    for row in primary
                    if row["dataset"] == dataset and row["rule"] == rule
                ]
            )
            for rule in RULES
        }
        for dataset in datasets
    }
    shifted_by_dataset = {
        dataset: {
            rule: summarize(
                [
                    row
                    for row in shifted
                    if row["dataset"] == dataset and row["rule"] == rule
                ]
            )
            for rule in RULES
        }
        for dataset in datasets
    }

    point_primary = rule_rows(primary, "point_selection_balanced")
    iut_primary = rule_rows(primary, "vera_balanced_iut")
    oracle_primary = {
        row["config_id"]: row
        for row in rule_rows(primary, "external_balanced_oracle")
    }
    iut_by_id = {row["config_id"]: row for row in iut_primary}
    oracle_opportunities = sum(bool(row["deployed"]) for row in oracle_primary.values())
    iut_safe_on_opportunity = sum(
        bool(
            iut_by_id[config_id]["deployed"]
            and iut_by_id[config_id]["external_contract_satisfied"] is True
        )
        for config_id, oracle_row in oracle_primary.items()
        if oracle_row["deployed"]
    )
    retention = (
        0.0
        if oracle_opportunities == 0
        else iut_safe_on_opportunity / oracle_opportunities
    )

    naive_regimes: dict[str, dict[str, Any]] = {}
    for dataset in supported:
        regimes: dict[tuple[float, float], list[dict[str, Any]]] = defaultdict(list)
        for row in point_primary:
            if row["dataset"] == dataset:
                regimes[(row["target_threshold"], row["leakage_threshold"])].append(
                    row
                )
        best_key, best_rows = max(
            regimes.items(),
            key=lambda item: (
                np.mean(
                    [row["measured_external_contract_violation"] for row in item[1]]
                ),
                item[0],
            ),
        )
        naive_regimes[dataset] = {
            "target_threshold": best_key[0],
            "leakage_threshold": best_key[1],
            "violation_count": sum(
                bool(row["measured_external_contract_violation"])
                for row in best_rows
            ),
            "seed_count": len(best_rows),
            "measured_external_violation_rate": float(
                np.mean(
                    [row["measured_external_contract_violation"] for row in best_rows]
                )
            ),
        }

    point_by_id = {row["config_id"]: row for row in point_primary}
    seed_differences: dict[str, list[float]] = {}
    raw_p: dict[str, float] = {}
    for dataset in supported:
        differences = []
        for seed in seeds:
            ids = [
                config_id
                for config_id, row in point_by_id.items()
                if row["dataset"] == dataset and row["seed"] == seed
            ]
            point_rate = float(
                np.mean(
                    [
                        point_by_id[config_id][
                            "measured_external_contract_violation"
                        ]
                        for config_id in ids
                    ]
                )
            )
            iut_rate = float(
                np.mean(
                    [
                        iut_by_id[config_id]["measured_external_contract_violation"]
                        for config_id in ids
                    ]
                )
            )
            differences.append(point_rate - iut_rate)
        seed_differences[dataset] = differences
        raw_p[dataset] = exact_one_sided_signflip(differences)
    holm_p = holm_adjust(raw_p)

    stress_lookup = {
        (
            record["dataset"],
            float(record["target_harm_threshold"]),
            float(record["leakage_threshold"]),
        )
        for record in study["headline_stress_family"]["regimes"]
    }
    stress_point = [
        row
        for row in point_primary
        if (row["dataset"], row["target_threshold"], row["leakage_threshold"])
        in stress_lookup
    ]
    stress_iut = [
        row
        for row in iut_primary
        if (row["dataset"], row["target_threshold"], row["leakage_threshold"])
        in stress_lookup
    ]
    if len(stress_point) != 32 or len(stress_iut) != 32:
        raise RuntimeError("headline stress family does not contain 32 configurations")
    stress_point_rate = float(
        np.mean([row["measured_external_contract_violation"] for row in stress_point])
    )
    stress_iut_rate = float(
        np.mean([row["measured_external_contract_violation"] for row in stress_iut])
    )

    primary_iut_global = primary_summaries["vera_balanced_iut"]
    shifted_iut_global = shifted_summaries["vera_balanced_iut"]
    naive_failure_pass = any(
        record["measured_external_violation_rate"] >= 0.20
        for record in naive_regimes.values()
    )
    vera_control_pass = (
        primary_iut_global["measured_external_violation_rate"] <= delta
        and shifted_iut_global["measured_external_violation_rate"] <= delta
        and all(
            primary_by_dataset[dataset]["vera_balanced_iut"][
                "measured_external_violation_rate"
            ]
            <= delta
            and shifted_by_dataset[dataset]["vera_balanced_iut"][
                "measured_external_violation_rate"
            ]
            <= delta
            for dataset in supported
        )
    )
    deployment_datasets = sum(
        primary_by_dataset[dataset]["vera_balanced_iut"]["deployment_count"] > 0
        for dataset in supported
    )
    retention_pass = retention >= 0.30 and deployment_datasets >= 3
    shifted_envelope_datasets = sum(
        shifted_by_dataset[dataset]["vera_balanced_envelope"]["deployment_count"] > 0
        for dataset in supported
    )
    shift_envelope_pass = (
        shifted_summaries["vera_balanced_envelope"][
            "measured_external_violation_count"
        ]
        == 0
        and shifted_envelope_datasets >= 2
    )
    significance_pass = any(value <= 0.05 for value in holm_p.values())
    abstract_gap_pass = stress_point_rate - stress_iut_rate >= 0.15
    camelyon_rows = [
        row
        for row in primary
        if row["dataset"] == "Camelyon17-WILDS"
        and row["rule"] in {"vera_balanced_iut", "vera_balanced_envelope"}
    ]
    camelyon_abstention_pass = bool(camelyon_rows) and all(
        not row["deployed"]
        and row["support_mismatch_forced_abstention"]
        and not row["external_contract_estimable"]
        for row in camelyon_rows
    )
    empirical_pass = all(
        (
            naive_failure_pass,
            vera_control_pass,
            retention_pass,
            shift_envelope_pass,
            significance_pass,
            abstract_gap_pass,
            camelyon_abstention_pass,
        )
    )

    learning_rows = [
        row
        for row in rows
        if row["gamma"] == primary_gamma
        and row["rule"] == "vera_balanced_iut"
    ]
    learning_curve = {}
    for fraction in fractions:
        values = [
            row for row in learning_rows if row["validation_fraction"] == fraction
        ]
        learning_curve[f"{fraction:g}"] = {
            **summarize(values),
            "certification_n_min": min(row["certification_n"] for row in values),
            "certification_n_max": max(row["certification_n"] for row in values),
            "abstention_rate": 1.0
            - sum(bool(row["deployed"]) for row in values) / len(values),
        }

    report = {
        "name": "VERA untouched-seed balanced-leakage confirmatory analysis",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "confirmatory": True,
        "passed": empirical_pass,
        "theory_match_evaluated_elsewhere": True,
        "prereg_sha256": prereg_hash,
        "receipt_audit_sha256": sha256(args.receipt_audit),
        "pilot_seeds_excluded": prereg["parent_pilot"]["seeds"],
        "confirmatory_seeds": seeds,
        "rule_row_count": len(rows),
        "candidate_row_count": len(candidate_rows),
        "primary_summaries": primary_summaries,
        "primary_by_dataset": primary_by_dataset,
        "shifted_sensitivity_summaries": shifted_summaries,
        "shifted_sensitivity_by_dataset": shifted_by_dataset,
        "learning_curve": learning_curve,
        "naive_failure_regimes": naive_regimes,
        "safe_retention": {
            "safe_deployment_count": iut_safe_on_opportunity,
            "external_oracle_opportunity_count": oracle_opportunities,
            "rate": retention,
            "cp95": list(cp_interval(iut_safe_on_opportunity, oracle_opportunities)),
            "supported_datasets_with_deployment": deployment_datasets,
        },
        "seed_blocked_point_minus_iut_differences": seed_differences,
        "seed_blocked_one_sided_signflip_raw_p": raw_p,
        "seed_blocked_one_sided_signflip_holm_p": holm_p,
        "headline_stress_family": {
            "configuration_count": len(stress_point),
            "point_selection_violation_rate": stress_point_rate,
            "vera_iut_violation_rate": stress_iut_rate,
            "gap": stress_point_rate - stress_iut_rate,
        },
        "camelyon_external_balanced_leakage_estimable": False,
        "pass_conditions": {
            "naive_failure": naive_failure_pass,
            "vera_control": vera_control_pass,
            "retention": retention_pass,
            "shift_envelope": shift_envelope_pass,
            "paired_significance": significance_pass,
            "abstract_gap": abstract_gap_pass,
            "camelyon_forced_abstention": camelyon_abstention_pass,
        },
        "selected_method_counts": {
            rule: dict(
                sorted(
                    Counter(
                        row["selected_method"]
                        for row in primary
                        if row["rule"] == rule and row["deployed"]
                    ).items()
                )
            )
            for rule in RULES
        },
        "claim_boundary": (
            "The theorem applies to external laws inside the stated support and "
            "density-ratio model. Measured benchmark violations test outcomes but "
            "do not establish that an external benchmark belongs to that model."
        ),
    }
    sentence = (
        f"Across 32 prespecified stress configurations, validation-only selection "
        f"deployed contract-violating edits in {100 * stress_point_rate:.1f}% of "
        f"configurations versus {100 * stress_iut_rate:.1f}% for VERA, while VERA "
        f"retained {100 * retention:.1f}% of externally certifiable opportunities."
    )
    abstract = {
        "verified": bool(empirical_pass),
        "prereg_sha256": prereg_hash,
        "stress_configuration_count": len(stress_point),
        "point_selection_violation_rate": stress_point_rate,
        "vera_iut_violation_rate": stress_iut_rate,
        "safe_retention": retention,
        "sentence": sentence,
    }
    return rows, candidate_rows, report, abstract


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--receipt-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--abstract", type=Path, default=DEFAULT_ABSTRACT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, candidate_rows, report, abstract = run_analysis(args)
    write_csv(args.rows, rows)
    write_csv(args.candidate_rows, candidate_rows)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.abstract.write_text(
        json.dumps(abstract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "pass_conditions": report["pass_conditions"],
                "abstract": abstract["sentence"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
