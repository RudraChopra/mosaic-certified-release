"""Exploratory existing-seed analysis of the post-primary VERA-IUT rule."""

from __future__ import annotations

import argparse
import csv
import hashlib
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
    contract_samples,
    point_metrics,
)
from analyze_vera_secondary_ablations import as_bool, load_json, read_csv, sha256
from vera_robust_certificate import certify_discrete_iut_fixed_profile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_real.json"
DEFAULT_HASH = ROOT / "prereg_real.sha256"
DEFAULT_IUT_PREREG = ROOT / "prereg_iut_power_extension.json"
DEFAULT_IUT_HASH = ROOT / "prereg_iut_power_extension.sha256"
DEFAULT_AUDIT = ROOT / "artifacts" / "official_eraser_receipt_audit.json"
DEFAULT_RECEIPTS = ROOT / "artifacts" / "real_study_receipts"
DEFAULT_PRIMARY_ROWS = ROOT / "artifacts" / "vera_deployment_rule_rows.csv"
DEFAULT_ROWS = ROOT / "artifacts" / "vera_iut_existing_rows.csv"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_iut_existing_report.json"


def expected_hash(path: Path) -> str:
    return path.read_text(encoding="utf-8").split()[0]


def choose(candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [candidate for candidate in candidates if candidate["eligible"]]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda candidate: (
            candidate["validation_max_leakage"],
            candidate["validation_max_target_harm"],
            candidate["candidate"],
        ),
    )


def analyze(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parent_hash = sha256(args.prereg)
    iut_hash = sha256(args.iut_prereg)
    if parent_hash != expected_hash(args.hash_file):
        raise RuntimeError("parent preregistration hash mismatch")
    if iut_hash != expected_hash(args.iut_hash_file):
        raise RuntimeError("IUT extension hash mismatch")
    receipt_audit = load_json(args.receipt_audit)
    if receipt_audit.get("passed") is not True:
        raise RuntimeError("official receipt matrix has not passed its audit")
    iut_prereg = load_json(args.iut_prereg)
    if iut_prereg.get("status") != "locked_after_primary_analysis_before_iut_analysis_or_new_runs":
        raise RuntimeError("IUT extension is not in the locked post-primary state")
    prereg = load_json(args.prereg)
    study = prereg["real_study"]
    fractions = [float(value) for value in study["validation_fractions"]]
    target_thresholds = [float(value) for value in study["target_harm_thresholds"]]
    leakage_thresholds = [float(value) for value in study["leakage_thresholds"]]
    gamma = float(study["deployment_gamma"])
    delta = float(study["delta"])
    rows: list[dict[str, Any]] = []

    for dataset, dataset_config in study["datasets"].items():
        support_mismatch = bool(
            dataset_config.get("force_abstain_for_unsupported_environment")
        )
        for seed in map(int, study["seeds"]):
            loaded, labels = load_candidates(
                args.receipt_dir, study, dataset, seed
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
                    samples, supports = contract_samples(candidate["arrays"], subset)
                    candidate_samples.append((candidate, samples, supports))
                for target_threshold in target_thresholds:
                    for leakage_threshold in leakage_thresholds:
                        evaluated = []
                        for candidate, samples, supports in candidate_samples:
                            thresholds = {
                                key: (
                                    target_threshold
                                    if key.startswith("target::")
                                    else leakage_threshold
                                )
                                for key in samples
                            }
                            certificate = certify_discrete_iut_fixed_profile(
                                samples,
                                gamma=gamma,
                                delta=delta,
                                candidate_count=candidate_count,
                                supports=supports,
                                thresholds=thresholds,
                            )
                            target_point, leakage_point = point_metrics(samples)
                            external_target, external_leakage = candidate[
                                "external_metrics"
                            ]
                            evaluated.append({
                                "candidate": candidate["candidate"],
                                "method": candidate["method"],
                                "validation_max_target_harm": target_point,
                                "validation_max_leakage": leakage_point,
                                "eligible": (
                                    not support_mismatch
                                    and certificate.decision == "EDIT"
                                ),
                                "limiting_contracts": certificate.limiting_contracts,
                                "external_max_target_harm": external_target,
                                "external_max_leakage": external_leakage,
                                "external_contract_satisfied": (
                                    external_target <= target_threshold
                                    and external_leakage <= leakage_threshold
                                ),
                            })
                        selected = choose(evaluated)
                        config_id = (
                            f"{dataset}|seed={seed}|fraction={fraction:g}|"
                            f"tau={target_threshold:g}|lambda={leakage_threshold:g}"
                        )
                        deployed = selected is not None
                        safe = deployed and selected["external_contract_satisfied"]
                        rows.append({
                            "config_id": config_id,
                            "dataset": dataset,
                            "seed": seed,
                            "validation_fraction": fraction,
                            "certification_n": len(subset),
                            "target_threshold": target_threshold,
                            "leakage_threshold": leakage_threshold,
                            "deployment_gamma": gamma,
                            "rule": "vera_iut",
                            "deployed": deployed,
                            "selected_candidate": selected["candidate"] if deployed else "",
                            "selected_method": selected["method"] if deployed else "",
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
                            "external_contract_satisfied": safe,
                            "measured_external_contract_violation": deployed and not safe,
                            "support_mismatch_forced_abstention": support_mismatch,
                            "candidate_count": candidate_count,
                            "candidate_failure_probability": delta / candidate_count,
                            "post_primary_exploratory": True,
                        })

    expected_rows = (
        len(study["datasets"])
        * len(study["seeds"])
        * len(fractions)
        * len(target_thresholds)
        * len(leakage_thresholds)
    )
    if len(rows) != expected_rows:
        raise RuntimeError(f"IUT row count {len(rows)} != {expected_rows}")
    primary_rows = read_csv(args.primary_rows)
    primary = {(row["config_id"], row["rule"]): row for row in primary_rows}
    iut = {row["config_id"]: row for row in rows}
    oracle_opportunities = sum(
        as_bool(primary[(config_id, "oracle")]["deployed"])
        for config_id in iut
    )
    safe_deployments = sum(
        row["deployed"]
        and row["external_contract_satisfied"]
        and as_bool(primary[(config_id, "oracle")]["deployed"])
        for config_id, row in iut.items()
    )
    summaries = {}
    for dataset in ["all", *study["datasets"]]:
        subset = rows if dataset == "all" else [row for row in rows if row["dataset"] == dataset]
        deployments = sum(row["deployed"] for row in subset)
        violations = sum(row["measured_external_contract_violation"] for row in subset)
        summaries[dataset] = {
            "configuration_count": len(subset),
            "deployment_count": deployments,
            "deployment_rate": deployments / len(subset),
            "measured_external_violation_count": violations,
            "measured_external_violation_rate": violations / len(subset),
            "violation_rate_conditional_on_deployment": (
                None if deployments == 0 else violations / deployments
            ),
            "configuration_cp95": list(cp_interval(violations, len(subset))),
        }

    seed_differences: dict[str, list[float]] = {}
    raw_p: dict[str, float] = {}
    for dataset in study["datasets"]:
        differences = []
        for seed in map(int, study["seeds"]):
            ids = [
                config_id
                for config_id, row in iut.items()
                if row["dataset"] == dataset and int(row["seed"]) == seed
            ]
            point_rate = float(np.mean([
                as_bool(primary[(config_id, "point_selection")][
                    "measured_external_contract_violation"
                ])
                for config_id in ids
            ]))
            iut_rate = float(np.mean([
                iut[config_id]["measured_external_contract_violation"]
                for config_id in ids
            ]))
            differences.append(point_rate - iut_rate)
        seed_differences[dataset] = differences
        raw_p[dataset] = exact_cluster_signflip(differences)
    adjusted_p = holm_adjust(raw_p)
    supported_deployment_datasets = sum(
        summaries[dataset]["deployment_count"] > 0
        for dataset, config in study["datasets"].items()
        if not config.get("force_abstain_for_unsupported_environment")
    )
    global_external_ok = all(
        summaries[dataset]["measured_external_violation_rate"] <= delta
        for dataset in study["datasets"]
    )
    report = {
        "name": "VERA-IUT existing-seed exploratory power diagnostic",
        "passed": True,
        "confirmatory": False,
        "post_primary_exploratory": True,
        "scientific_power_gate_pass": (
            supported_deployment_datasets >= 3
            and global_external_ok
            and safe_deployments / oracle_opportunities >= 0.30
        ),
        "parent_prereg_sha256": parent_hash,
        "iut_prereg_sha256": iut_hash,
        "receipt_audit_sha256": sha256(args.receipt_audit),
        "primary_rows_sha256": sha256(args.primary_rows),
        "row_count": len(rows),
        "delta": delta,
        "deployment_gamma": gamma,
        "candidate_count": 12,
        "candidate_failure_probability": delta / 12,
        "summaries": summaries,
        "safe_deployment_retention": safe_deployments / oracle_opportunities,
        "safe_deployment_count": safe_deployments,
        "measured_external_oracle_opportunity_count": oracle_opportunities,
        "supported_datasets_with_deployment": supported_deployment_datasets,
        "measured_external_violation_below_delta_every_dataset": global_external_ok,
        "selected_method_counts": dict(sorted(Counter(
            row["selected_method"] for row in rows if row["deployed"]
        ).items())),
        "seed_blocked_point_minus_iut_differences": seed_differences,
        "seed_blocked_signflip_raw_p": raw_p,
        "seed_blocked_signflip_holm_p": adjusted_p,
        "timing_disclosure": iut_prereg["timing_disclosure"],
        "claim_boundary": (
            "This candidate-wise intersection-union rule certifies only the fixed "
            "full-support Gamma=1.25 profile. It does not replace the simultaneous "
            "post-hoc support-aware envelope and is not confirmatory on seeds 0-4."
        ),
    }
    return rows, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--iut-prereg", type=Path, default=DEFAULT_IUT_PREREG)
    parser.add_argument("--iut-hash-file", type=Path, default=DEFAULT_IUT_HASH)
    parser.add_argument("--receipt-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--primary-rows", type=Path, default=DEFAULT_PRIMARY_ROWS)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, report = analyze(args)
    args.rows.parent.mkdir(parents=True, exist_ok=True)
    with args.rows.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "confirmatory": report["confirmatory"],
        "power_gate": report["scientific_power_gate_pass"],
        "deployments": report["summaries"]["all"]["deployment_count"],
        "violations": report["summaries"]["all"]["measured_external_violation_count"],
        "retention": report["safe_deployment_retention"],
    }, indent=2))


if __name__ == "__main__":
    main()
