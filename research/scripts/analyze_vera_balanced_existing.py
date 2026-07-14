"""Exploratory seeds 0-4 analysis of the locked balanced-leakage estimand."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from analyze_vera_attacker_ablation import load_candidates
from analyze_vera_real_study import (
    cp_interval,
    exact_cluster_signflip,
    holm_adjust,
    nested_stratified_indices,
)
from analyze_vera_secondary_ablations import load_json, sha256
from vera_robust_certificate import (
    certify_balanced_iut_fixed_profile,
    certify_balanced_shift_radius,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_real.json"
DEFAULT_HASH = ROOT / "prereg_real.sha256"
DEFAULT_BALANCED_PREREG = ROOT / "prereg_balanced_leakage_extension.json"
DEFAULT_BALANCED_HASH = ROOT / "prereg_balanced_leakage_extension.sha256"
DEFAULT_AUDIT = ROOT / "artifacts" / "official_eraser_receipt_audit.json"
DEFAULT_RECEIPTS = ROOT / "artifacts" / "real_study_receipts"
DEFAULT_ROWS = ROOT / "artifacts" / "vera_balanced_existing_rule_rows.csv"
DEFAULT_CANDIDATES = ROOT / "artifacts" / "vera_balanced_existing_candidate_rows.csv"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_balanced_existing_report.json"


RULES = (
    "always_deploy_balanced",
    "point_selection_balanced",
    "vera_balanced_envelope",
    "vera_balanced_iut",
    "external_balanced_oracle",
)


def expected_hash(path: Path) -> str:
    return path.read_text(encoding="utf-8").split()[0]


def balanced_accuracy(correct: np.ndarray, source: np.ndarray) -> float | None:
    classes = set(map(int, np.unique(source)))
    if classes != {0, 1}:
        return None
    return 0.5 * (
        float(correct[source == 0].mean()) + float(correct[source == 1].mean())
    )


def balanced_samples(
    arrays: dict[str, np.ndarray], indices: np.ndarray
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray]:
    environment = arrays["environment_certification"][indices]
    target_harm = arrays["target_harm_certification"][indices]
    source = arrays["source_certification"][indices]
    target = {
        f"target::environment={group}": target_harm[environment == group]
        for group in sorted(map(int, np.unique(environment)))
    }
    leakage = {
        name.removeprefix("leakage_correct_certification__"): values[indices]
        for name, values in arrays.items()
        if name.startswith("leakage_correct_certification__")
    }
    return target, leakage, source


def balanced_point_metrics(
    target: dict[str, np.ndarray],
    leakage: dict[str, np.ndarray],
    source: np.ndarray,
) -> tuple[float, float]:
    target_max = max(float(values.mean()) for values in target.values())
    attacker_values = [balanced_accuracy(values, source) for values in leakage.values()]
    if any(value is None for value in attacker_values):
        raise ValueError("certification is missing a registered source class")
    return target_max, max(float(value) for value in attacker_values if value is not None)


def balanced_external_metrics(
    arrays: dict[str, np.ndarray]
) -> tuple[float, float | None]:
    environment = arrays["environment_external"]
    target_harm = arrays["target_harm_external"]
    source = arrays["source_external"]
    target_max = max(
        float(target_harm[environment == group].mean())
        for group in sorted(map(int, np.unique(environment)))
    )
    attacker_values = [
        balanced_accuracy(values, source)
        for name, values in arrays.items()
        if name.startswith("leakage_correct_external__")
    ]
    if not attacker_values or any(value is None for value in attacker_values):
        return target_max, None
    return target_max, max(float(value) for value in attacker_values if value is not None)


def choose(
    candidates: list[dict[str, Any]], predicate: str | None = None
) -> dict[str, Any] | None:
    eligible = candidates if predicate is None else [
        candidate for candidate in candidates if candidate[predicate]
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda candidate: (
            candidate["validation_max_balanced_leakage"],
            candidate["validation_max_target_harm"],
            candidate["candidate"],
        ),
    )


def analyze(
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    parent_hash = sha256(args.prereg)
    balanced_hash = sha256(args.balanced_prereg)
    if parent_hash != expected_hash(args.hash_file):
        raise RuntimeError("parent preregistration hash mismatch")
    if balanced_hash != expected_hash(args.balanced_hash_file):
        raise RuntimeError("balanced-leakage extension hash mismatch")
    receipt_audit = load_json(args.receipt_audit)
    if receipt_audit.get("passed") is not True:
        raise RuntimeError("official receipt matrix has not passed its audit")
    balanced_prereg = load_json(args.balanced_prereg)
    if balanced_prereg.get("status") != (
        "locked_after_primary_and_iut_diagnostics_before_balanced_leakage_analysis_or_new_runs"
    ):
        raise RuntimeError("balanced-leakage extension is not locked")
    prereg = load_json(args.prereg)
    study = prereg["real_study"]
    fractions = [float(value) for value in study["validation_fractions"]]
    target_thresholds = [float(value) for value in study["target_harm_thresholds"]]
    leakage_thresholds = [float(value) for value in study["leakage_thresholds"]]
    delta = float(study["delta"])
    gamma = float(study["deployment_gamma"])
    gamma_cap = float(study["gamma_cap"])
    rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for dataset, dataset_config in study["datasets"].items():
        support_mismatch = bool(
            dataset_config.get("force_abstain_for_unsupported_environment")
        )
        for seed in map(int, study["seeds"]):
            loaded, labels = load_candidates(args.receipt_dir, study, dataset, seed)
            for candidate in loaded:
                candidate["balanced_external_metrics"] = balanced_external_metrics(
                    candidate["arrays"]
                )
            candidate_count = len(loaded)
            subsets = nested_stratified_indices(
                *labels,
                fractions,
                seed=2_027_071_300 + 1009 * seed + sum(map(ord, dataset)),
            )
            for fraction in fractions:
                subset = subsets[fraction]
                candidate_samples = []
                for candidate in loaded:
                    target, leakage, source = balanced_samples(candidate["arrays"], subset)
                    candidate_samples.append((candidate, target, leakage, source))
                contract_count = len(candidate_samples[0][1]) + len(
                    candidate_samples[0][2]
                )
                family_size = candidate_count * contract_count
                for target_threshold in target_thresholds:
                    for leakage_threshold in leakage_thresholds:
                        evaluated = []
                        config_id = (
                            f"{dataset}|seed={seed}|fraction={fraction:g}|"
                            f"tau={target_threshold:g}|lambda={leakage_threshold:g}"
                        )
                        for candidate, target, leakage, source in candidate_samples:
                            target_point, leakage_point = balanced_point_metrics(
                                target, leakage, source
                            )
                            envelope = certify_balanced_shift_radius(
                                target,
                                leakage,
                                source,
                                delta=delta,
                                family_size=family_size,
                                target_threshold=target_threshold,
                                leakage_threshold=leakage_threshold,
                                gamma_cap=gamma_cap,
                            )
                            iut = certify_balanced_iut_fixed_profile(
                                target,
                                leakage,
                                source,
                                gamma=gamma,
                                delta=delta,
                                candidate_count=candidate_count,
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
                                "validation_max_target_harm": target_point,
                                "validation_max_balanced_leakage": leakage_point,
                                "point_feasible": (
                                    target_point <= target_threshold
                                    and leakage_point <= leakage_threshold
                                ),
                                "envelope_radius": envelope.certified_radius,
                                "envelope_eligible": (
                                    not support_mismatch
                                    and envelope.certified_radius >= gamma
                                ),
                                "iut_eligible": (
                                    not support_mismatch and iut.decision == "EDIT"
                                ),
                                "envelope_limiting_contracts": envelope.limiting_contracts,
                                "iut_limiting_contracts": iut.limiting_contracts,
                                "external_max_target_harm": external_target,
                                "external_max_balanced_leakage": external_leakage,
                                "external_contract_estimable": external_estimable,
                                "external_contract_satisfied": external_satisfied,
                            }
                            evaluated.append(record)
                            candidate_rows.append({
                                "config_id": config_id,
                                "dataset": dataset,
                                "seed": seed,
                                "validation_fraction": fraction,
                                "certification_n": len(subset),
                                "target_threshold": target_threshold,
                                "leakage_threshold": leakage_threshold,
                                "deployment_gamma": gamma,
                                "family_size": family_size,
                                "candidate": record["candidate"],
                                "method": record["method"],
                                "validation_max_target_harm": target_point,
                                "validation_max_balanced_leakage": leakage_point,
                                "point_feasible": record["point_feasible"],
                                "envelope_radius": envelope.certified_radius,
                                "envelope_eligible": record["envelope_eligible"],
                                "iut_eligible": record["iut_eligible"],
                                "envelope_limiting_contracts": json.dumps(
                                    envelope.limiting_contracts
                                ),
                                "iut_limiting_contracts": json.dumps(
                                    iut.limiting_contracts
                                ),
                                "external_max_target_harm": external_target,
                                "external_max_balanced_leakage": (
                                    "" if external_leakage is None else external_leakage
                                ),
                                "external_contract_estimable": external_estimable,
                                "external_contract_satisfied": (
                                    "NA" if external_satisfied is None else external_satisfied
                                ),
                                "support_mismatch": support_mismatch,
                                "post_primary_exploratory": True,
                            })
                        selections = {
                            "always_deploy_balanced": choose(evaluated),
                            "point_selection_balanced": choose(evaluated, "point_feasible"),
                            "vera_balanced_envelope": choose(evaluated, "envelope_eligible"),
                            "vera_balanced_iut": choose(evaluated, "iut_eligible"),
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
                            estimable = bool(
                                selected["external_contract_estimable"]
                                if deployed
                                else rule != "external_balanced_oracle"
                                and dataset != "Camelyon17-WILDS"
                            )
                            satisfied = (
                                selected["external_contract_satisfied"]
                                if deployed and estimable
                                else None
                            )
                            rows.append({
                                "config_id": config_id,
                                "dataset": dataset,
                                "seed": seed,
                                "validation_fraction": fraction,
                                "certification_n": len(subset),
                                "target_threshold": target_threshold,
                                "leakage_threshold": leakage_threshold,
                                "deployment_gamma": gamma,
                                "rule": rule,
                                "deployed": deployed,
                                "selected_candidate": selected["candidate"] if deployed else "",
                                "selected_method": selected["method"] if deployed else "",
                                "external_contract_estimable": estimable,
                                "external_contract_satisfied": (
                                    "NA" if satisfied is None else satisfied
                                ),
                                "measured_external_contract_violation": (
                                    "NA"
                                    if satisfied is None
                                    else bool(deployed and not satisfied)
                                ),
                                "procedurally_unsupported_deployment": (
                                    deployed and support_mismatch
                                ),
                                "support_mismatch_forced_abstention": (
                                    support_mismatch
                                    and rule in {
                                        "vera_balanced_envelope",
                                        "vera_balanced_iut",
                                    }
                                ),
                                "post_primary_exploratory": True,
                            })

    expected_configs = (
        len(study["datasets"])
        * len(study["seeds"])
        * len(fractions)
        * len(target_thresholds)
        * len(leakage_thresholds)
    )
    if len(rows) != expected_configs * len(RULES):
        raise RuntimeError("balanced rule table shape mismatch")
    if len(candidate_rows) != expected_configs * 12:
        raise RuntimeError("balanced candidate table shape mismatch")

    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_rule[row["rule"]].append(row)
    summaries = {}
    for rule, rule_rows in by_rule.items():
        estimable = [
            row for row in rule_rows if row["external_contract_estimable"]
        ]
        violations = sum(
            row["measured_external_contract_violation"] is True for row in estimable
        )
        deployments = sum(row["deployed"] for row in rule_rows)
        estimable_deployments = sum(row["deployed"] for row in estimable)
        summaries[rule] = {
            "configuration_count": len(rule_rows),
            "estimable_configuration_count": len(estimable),
            "deployment_count": deployments,
            "deployment_rate": deployments / len(rule_rows),
            "estimable_deployment_count": estimable_deployments,
            "measured_external_violation_count": violations,
            "measured_external_violation_rate": violations / len(estimable),
            "violation_rate_conditional_on_estimable_deployment": (
                None if estimable_deployments == 0 else violations / estimable_deployments
            ),
            "configuration_cp95": list(cp_interval(violations, len(estimable))),
            "procedurally_unsupported_deployment_count": sum(
                row["procedurally_unsupported_deployment"] for row in rule_rows
            ),
        }

    oracle = {
        row["config_id"]: row for row in by_rule["external_balanced_oracle"]
    }
    retention = {}
    for rule in ("vera_balanced_envelope", "vera_balanced_iut"):
        selected = {row["config_id"]: row for row in by_rule[rule]}
        opportunities = sum(row["deployed"] for row in oracle.values())
        safe = sum(
            selected[config_id]["deployed"]
            and selected[config_id]["external_contract_satisfied"] is True
            for config_id, oracle_row in oracle.items()
            if oracle_row["deployed"]
        )
        retention[rule] = {
            "safe_deployment_count": safe,
            "oracle_opportunity_count": opportunities,
            "safe_deployment_retention": 0.0 if opportunities == 0 else safe / opportunities,
            "cp95": list(cp_interval(safe, opportunities)),
        }

    point = {
        row["config_id"]: row for row in by_rule["point_selection_balanced"]
    }
    seed_tests = {}
    for rule in ("vera_balanced_envelope", "vera_balanced_iut"):
        selected = {row["config_id"]: row for row in by_rule[rule]}
        differences_by_dataset = {}
        raw = {}
        for dataset in study["datasets"]:
            if dataset == "Camelyon17-WILDS":
                continue
            differences = []
            for seed in map(int, study["seeds"]):
                ids = [
                    config_id
                    for config_id, row in point.items()
                    if row["dataset"] == dataset and int(row["seed"]) == seed
                ]
                point_rate = float(np.mean([
                    point[config_id]["measured_external_contract_violation"] is True
                    for config_id in ids
                ]))
                rule_rate = float(np.mean([
                    selected[config_id]["measured_external_contract_violation"] is True
                    for config_id in ids
                ]))
                differences.append(point_rate - rule_rate)
            differences_by_dataset[dataset] = differences
            raw[dataset] = exact_cluster_signflip(differences)
        seed_tests[rule] = {
            "point_minus_rule_seed_differences": differences_by_dataset,
            "raw_p": raw,
            "holm_p": holm_adjust(raw),
        }

    supported_deployment_datasets = {
        rule: sum(
            any(row["deployed"] for row in by_rule[rule] if row["dataset"] == dataset)
            for dataset, config in study["datasets"].items()
            if not config.get("force_abstain_for_unsupported_environment")
        )
        for rule in ("vera_balanced_envelope", "vera_balanced_iut")
    }
    external_ok = {
        rule: summaries[rule]["measured_external_violation_rate"] <= delta
        for rule in ("vera_balanced_envelope", "vera_balanced_iut")
    }
    report = {
        "name": "VERA balanced-leakage existing-seed exploratory diagnostic",
        "passed": True,
        "confirmatory": False,
        "post_primary_exploratory": True,
        "parent_prereg_sha256": parent_hash,
        "balanced_prereg_sha256": balanced_hash,
        "receipt_audit_sha256": sha256(args.receipt_audit),
        "row_count": len(rows),
        "candidate_row_count": len(candidate_rows),
        "delta": delta,
        "deployment_gamma": gamma,
        "summaries": summaries,
        "retention": retention,
        "supported_datasets_with_deployment": supported_deployment_datasets,
        "measured_external_violation_below_delta": external_ok,
        "seed_blocked_tests": seed_tests,
        "selected_method_counts": {
            rule: dict(sorted(Counter(
                row["selected_method"] for row in by_rule[rule] if row["deployed"]
            ).items()))
            for rule in RULES
        },
        "camelyon_external_balanced_leakage_estimable": False,
        "scientific_power_gate_pass": any(
            supported_deployment_datasets[rule] >= 3
            and retention[rule]["safe_deployment_retention"] >= 0.30
            and external_ok[rule]
            for rule in ("vera_balanced_envelope", "vera_balanced_iut")
        ),
        "timing_disclosure": balanced_prereg["timing_disclosure"],
        "claim_boundary": (
            "Seeds 0-4 are exploratory for this corrected estimand. Camelyon17 "
            "external balanced leakage is NA because center 2 contains one source class."
        ),
    }
    return rows, candidate_rows, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--balanced-prereg", type=Path, default=DEFAULT_BALANCED_PREREG)
    parser.add_argument("--balanced-hash-file", type=Path, default=DEFAULT_BALANCED_HASH)
    parser.add_argument("--receipt-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, candidate_rows, report = analyze(args)
    args.rows.parent.mkdir(parents=True, exist_ok=True)
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
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "confirmatory": report["confirmatory"],
        "power_gate": report["scientific_power_gate_pass"],
        "envelope": report["summaries"]["vera_balanced_envelope"],
        "iut": report["summaries"]["vera_balanced_iut"],
        "retention": report["retention"],
    }, indent=2))


if __name__ == "__main__":
    main()
