"""Exploratory full-certification Gamma pilot for balanced VERA-IUT."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
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
from analyze_vera_secondary_ablations import load_json, read_csv, sha256
from vera_robust_certificate import certify_balanced_iut_fixed_profile


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_real.json"
DEFAULT_BALANCED_PREREG = ROOT / "prereg_balanced_leakage_extension.json"
DEFAULT_BALANCED_HASH = ROOT / "prereg_balanced_leakage_extension.sha256"
DEFAULT_AUDIT = ROOT / "artifacts" / "official_eraser_receipt_audit.json"
DEFAULT_RECEIPTS = ROOT / "artifacts" / "real_study_receipts"
DEFAULT_BALANCED_ROWS = ROOT / "artifacts" / "vera_balanced_existing_rule_rows.csv"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_balanced_iut_gamma_pilot.json"
GAMMAS = (1.0, 1.01, 1.02, 1.05, 1.10, 1.25)


def expected_hash(path: Path) -> str:
    return path.read_text(encoding="utf-8").split()[0]


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    balanced_hash = sha256(args.balanced_prereg)
    if balanced_hash != expected_hash(args.balanced_hash_file):
        raise RuntimeError("balanced-leakage extension hash mismatch")
    if load_json(args.receipt_audit).get("passed") is not True:
        raise RuntimeError("official receipt audit must pass")
    prereg = load_json(args.prereg)
    study = prereg["real_study"]
    delta = float(study["delta"])
    target_thresholds = [float(value) for value in study["target_harm_thresholds"]]
    leakage_thresholds = [float(value) for value in study["leakage_thresholds"]]
    balanced_rows = read_csv(args.balanced_rows)
    full_oracle_opportunities = int(sum(
        row["rule"] == "external_balanced_oracle"
        and np.isclose(float(row["validation_fraction"]), 1.0)
        and row["deployed"] == "True"
        for row in balanced_rows
    ))
    records: list[dict[str, Any]] = []
    for dataset, dataset_config in study["datasets"].items():
        support_mismatch = bool(
            dataset_config.get("force_abstain_for_unsupported_environment")
        )
        for seed in map(int, study["seeds"]):
            loaded, labels = load_candidates(args.receipt_dir, study, dataset, seed)
            indices = np.arange(len(labels[0]), dtype=np.int64)
            candidates = []
            for candidate in loaded:
                target, leakage, source = balanced_samples(candidate["arrays"], indices)
                target_point, leakage_point = balanced_point_metrics(
                    target, leakage, source
                )
                external_target, external_leakage = balanced_external_metrics(
                    candidate["arrays"]
                )
                candidates.append({
                    "candidate": candidate["candidate"],
                    "method": candidate["method"],
                    "target": target,
                    "leakage": leakage,
                    "source": source,
                    "validation_max_target_harm": target_point,
                    "validation_max_balanced_leakage": leakage_point,
                    "external_target": external_target,
                    "external_leakage": external_leakage,
                })
            for gamma in GAMMAS:
                for target_threshold in target_thresholds:
                    for leakage_threshold in leakage_thresholds:
                        evaluated = []
                        for candidate in candidates:
                            certificate = certify_balanced_iut_fixed_profile(
                                candidate["target"],
                                candidate["leakage"],
                                candidate["source"],
                                gamma=gamma,
                                delta=delta,
                                candidate_count=len(candidates),
                                target_threshold=target_threshold,
                                leakage_threshold=leakage_threshold,
                            )
                            external_leakage = candidate["external_leakage"]
                            external_satisfied = (
                                None
                                if external_leakage is None
                                else candidate["external_target"] <= target_threshold
                                and float(external_leakage) <= leakage_threshold
                            )
                            evaluated.append({
                                **candidate,
                                "eligible": (
                                    not support_mismatch
                                    and certificate.decision == "EDIT"
                                ),
                                "external_contract_satisfied": external_satisfied,
                            })
                        selected = choose(evaluated, "eligible")
                        deployed = selected is not None
                        records.append({
                            "dataset": dataset,
                            "seed": seed,
                            "gamma": gamma,
                            "target_threshold": target_threshold,
                            "leakage_threshold": leakage_threshold,
                            "deployed": deployed,
                            "safe": (
                                deployed
                                and selected["external_contract_satisfied"] is True
                            ),
                            "violation": (
                                deployed
                                and selected["external_contract_satisfied"] is False
                            ),
                            "estimable": dataset != "Camelyon17-WILDS",
                            "selected_candidate": (
                                selected["candidate"] if deployed else ""
                            ),
                        })
    summaries = {}
    for gamma in GAMMAS:
        gamma_rows = [row for row in records if row["gamma"] == gamma]
        estimable = [row for row in gamma_rows if row["estimable"]]
        deployments = sum(row["deployed"] for row in gamma_rows)
        safe = sum(row["safe"] for row in gamma_rows)
        violations = sum(row["violation"] for row in gamma_rows)
        summaries[f"{gamma:g}"] = {
            "configuration_count": len(gamma_rows),
            "estimable_configuration_count": len(estimable),
            "deployment_count": deployments,
            "safe_deployment_count": safe,
            "measured_external_violation_count": violations,
            "measured_external_violation_rate": violations / len(estimable),
            "violation_rate_conditional_on_deployment": (
                None if deployments == 0 else violations / deployments
            ),
            "safe_retention_against_locked_full_fraction_oracle": (
                safe / full_oracle_opportunities
            ),
            "datasets_with_deployment": sorted({
                row["dataset"] for row in gamma_rows if row["deployed"]
            }),
        }
    return {
        "name": "balanced VERA-IUT full-certification Gamma pilot",
        "passed": len(records) == len(GAMMAS) * 5 * 5 * 3 * 3,
        "confirmatory": False,
        "post_primary_exploratory": True,
        "balanced_prereg_sha256": balanced_hash,
        "receipt_audit_sha256": sha256(args.receipt_audit),
        "gammas": list(GAMMAS),
        "full_fraction_oracle_opportunities": full_oracle_opportunities,
        "summaries": summaries,
        "selection_warning": (
            "This pilot may choose a Gamma for a separately locked new-seed study; "
            "it is not confirmatory evidence at any Gamma."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--balanced-prereg", type=Path, default=DEFAULT_BALANCED_PREREG)
    parser.add_argument("--balanced-hash-file", type=Path, default=DEFAULT_BALANCED_HASH)
    parser.add_argument("--receipt-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--balanced-rows", type=Path, default=DEFAULT_BALANCED_ROWS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = analyze(args)
    args.report.write_text(
        json.dumps(
            report,
            indent=2,
            sort_keys=True,
            default=lambda value: value.item()
            if isinstance(value, np.generic)
            else str(value),
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            report["summaries"],
            indent=2,
            sort_keys=True,
            default=lambda value: value.item()
            if isinstance(value, np.generic)
            else str(value),
        )
    )


if __name__ == "__main__":
    main()
