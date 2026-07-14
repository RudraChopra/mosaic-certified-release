"""Recompute VERA under the locked secondary attacker portfolios."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from analyze_vera_real_study import (
    contract_samples,
    external_metrics,
    nested_stratified_indices,
    point_metrics,
)
from analyze_vera_secondary_ablations import (
    as_bool,
    cluster_summary,
    expected_hash,
    load_json,
    read_csv,
    sha256,
)
from vera_robust_certificate import certify_discrete_shift_radius


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_real.json"
DEFAULT_PREREG_HASH = ROOT / "prereg_real.sha256"
DEFAULT_ABLATION_PREREG = ROOT / "prereg_secondary_ablations.json"
DEFAULT_ABLATION_HASH = ROOT / "prereg_secondary_ablations.sha256"
DEFAULT_AUDIT = ROOT / "artifacts" / "official_eraser_receipt_audit.json"
DEFAULT_RECEIPTS = ROOT / "artifacts" / "real_study_receipts"
DEFAULT_RULE_ROWS = ROOT / "artifacts" / "vera_deployment_rule_rows.csv"
DEFAULT_OUTPUT_ROWS = ROOT / "artifacts" / "vera_attacker_ablation_rows.csv"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_attacker_ablation_report.json"


def filter_portfolio(
    samples: dict[str, np.ndarray],
    supports: dict[str, tuple[int, ...]],
    attackers: set[str],
) -> tuple[dict[str, np.ndarray], dict[str, tuple[int, ...]]]:
    keys = [
        key
        for key in samples
        if key.startswith("target::")
        or (key.startswith("leakage::") and key.split("::", 2)[1] in attackers)
    ]
    return (
        {key: samples[key] for key in keys},
        {key: supports[key] for key in keys},
    )


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


def load_candidates(
    receipt_dir: Path,
    study: dict[str, Any],
    dataset: str,
    seed: int,
) -> tuple[list[dict[str, Any]], tuple[np.ndarray, np.ndarray, np.ndarray]]:
    loaded: list[dict[str, Any]] = []
    reference: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
    for method_key, method in study["methods"].items():
        receipt = load_json(receipt_dir / f"{dataset}__{method_key}__seed-{seed}.json")
        for candidate in receipt["candidates"]:
            with np.load(candidate["audit_npz"]) as archive:
                arrays = {key: np.asarray(archive[key]) for key in archive.files}
            labels = (
                arrays["target_certification"],
                arrays["source_certification"],
                arrays["environment_certification"],
            )
            if reference is None:
                reference = labels
            elif not all(
                np.array_equal(left, right) for left, right in zip(reference, labels)
            ):
                raise RuntimeError(f"candidate labels disagree for {dataset}/seed-{seed}")
            loaded.append({
                "candidate": f"{method['display_name']}::{candidate['strength']}",
                "method": method["display_name"],
                "arrays": arrays,
                "external_metrics": external_metrics(arrays),
            })
    if reference is None:
        raise RuntimeError(f"no candidates loaded for {dataset}/seed-{seed}")
    return loaded, reference


def analyze(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parent_hash = sha256(args.prereg)
    ablation_hash = sha256(args.ablation_prereg)
    if parent_hash != expected_hash(args.prereg_hash):
        raise RuntimeError("parent preregistration hash mismatch")
    if ablation_hash != expected_hash(args.ablation_hash):
        raise RuntimeError("secondary-ablation preregistration hash mismatch")
    receipt_audit = load_json(args.receipt_audit)
    if receipt_audit.get("passed") is not True:
        raise RuntimeError("official receipt matrix has not passed its audit")
    prereg = load_json(args.prereg)
    ablation_prereg = load_json(args.ablation_prereg)
    study = prereg["real_study"]
    portfolios = {
        name: set(attackers)
        for name, attackers in ablation_prereg["ablations"]["attacker_portfolio"][
            "portfolios"
        ].items()
    }
    required_attackers = {"linear", "rbf", "forest", "mlp"}
    if portfolios.get("full") != required_attackers:
        raise RuntimeError("locked full portfolio does not contain all four attackers")
    gamma = float(study["deployment_gamma"])
    delta = float(study["delta"])
    gamma_cap = float(study["gamma_cap"])
    fractions = [float(value) for value in study["validation_fractions"]]
    target_thresholds = [float(value) for value in study["target_harm_thresholds"]]
    leakage_thresholds = [float(value) for value in study["leakage_thresholds"]]
    rule_rows = read_csv(args.rule_rows)
    primary = {
        (row["config_id"], row["rule"]): row
        for row in rule_rows
        if row["rule"] in {"vera", "oracle"}
    }

    rows: list[dict[str, Any]] = []
    for dataset, dataset_config in study["datasets"].items():
        support_mismatch = bool(
            dataset_config.get("force_abstain_for_unsupported_environment")
        )
        for seed in map(int, study["seeds"]):
            loaded, labels = load_candidates(args.receipt_dir, study, dataset, seed)
            subsets = nested_stratified_indices(
                *labels,
                fractions,
                seed=2_027_071_300 + 1009 * seed + sum(map(ord, dataset)),
            )
            for fraction in fractions:
                subset = subsets[fraction]
                complete_samples = []
                for candidate in loaded:
                    samples, supports = contract_samples(candidate["arrays"], subset)
                    complete_samples.append((candidate, samples, supports))
                for portfolio_name, attackers in portfolios.items():
                    candidate_samples = []
                    family_size = 0
                    for candidate, samples, supports in complete_samples:
                        filtered_samples, filtered_supports = filter_portfolio(
                            samples, supports, attackers
                        )
                        candidate_samples.append(
                            (candidate, filtered_samples, filtered_supports)
                        )
                        family_size += len(filtered_samples)
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
                                radius = certify_discrete_shift_radius(
                                    samples,
                                    delta=delta,
                                    supports=supports,
                                    thresholds=thresholds,
                                    family_size=family_size,
                                    gamma_cap=gamma_cap,
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
                                    "certified_radius": radius.certified_radius,
                                    "eligible": (
                                        not support_mismatch
                                        and radius.certified_radius >= gamma
                                    ),
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
                                "target_threshold": target_threshold,
                                "leakage_threshold": leakage_threshold,
                                "portfolio": portfolio_name,
                                "family_size": family_size,
                                "deployed": deployed,
                                "violation": deployed and not safe,
                                "safe": safe,
                                "oracle_deployed": as_bool(
                                    primary[(config_id, "oracle")]["deployed"]
                                ),
                                "selected_candidate": (
                                    selected["candidate"] if deployed else ""
                                ),
                                "selected_method": selected["method"] if deployed else "",
                                "certified_radius": (
                                    selected["certified_radius"] if deployed else 0.0
                                ),
                            })

    by_portfolio: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_portfolio[row["portfolio"]].append(row)
    expected_per_portfolio = (
        len(study["datasets"])
        * len(study["seeds"])
        * len(fractions)
        * len(target_thresholds)
        * len(leakage_thresholds)
    )
    if any(len(values) != expected_per_portfolio for values in by_portfolio.values()):
        raise RuntimeError("attacker-ablation portfolio is missing registered cells")

    parity_errors = []
    full_by_config = {row["config_id"]: row for row in by_portfolio["full"]}
    for config_id, observed in full_by_config.items():
        expected = primary[(config_id, "vera")]
        if observed["deployed"] != as_bool(expected["deployed"]):
            parity_errors.append(config_id)
        elif observed["deployed"] and observed["selected_candidate"] != expected["selected_candidate"]:
            parity_errors.append(config_id)

    report_portfolios = {}
    for index, (name, portfolio_rows) in enumerate(sorted(by_portfolio.items())):
        full_changes = sum(
            row["selected_candidate"]
            != full_by_config[row["config_id"]]["selected_candidate"]
            for row in portfolio_rows
        )
        report_portfolios[name] = {
            "attackers": sorted(portfolios[name]),
            "all_datasets": cluster_summary(
                portfolio_rows, bootstrap_seed=14100 + index
            ),
            "by_dataset": {
                dataset: cluster_summary(
                    [row for row in portfolio_rows if row["dataset"] == dataset],
                    bootstrap_seed=15100 + 101 * index + dataset_index,
                )
                for dataset_index, dataset in enumerate(study["datasets"])
            },
            "selection_changes_from_full": full_changes,
            "selected_method_counts": dict(
                sorted(
                    Counter(
                        row["selected_method"]
                        for row in portfolio_rows
                        if row["deployed"]
                    ).items()
                )
            ),
        }
    report = {
        "name": "VERA locked attacker-portfolio ablation",
        "passed": not parity_errors and len(by_portfolio) == len(portfolios),
        "claim_status": "secondary outcome-blindly locked sensitivity analysis",
        "parent_prereg_sha256": parent_hash,
        "ablation_prereg_sha256": ablation_hash,
        "receipt_audit_sha256": sha256(args.receipt_audit),
        "source_rule_rows_sha256": sha256(args.rule_rows),
        "row_count": len(rows),
        "expected_row_count": expected_per_portfolio * len(portfolios),
        "full_portfolio_parity": {
            "passed": not parity_errors,
            "error_count": len(parity_errors),
            "first_errors": parity_errors[:20],
        },
        "portfolios": report_portfolios,
        "endpoint_semantics": (
            "External safety is always evaluated against the full four-attacker "
            "contract, even when certification uses a reduced portfolio."
        ),
        "statistical_caution": (
            "Intervals resample seed clusters and are descriptive. Configurations "
            "within a seed share fits, examples, thresholds, and nested fractions."
        ),
    }
    return rows, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--prereg-hash", type=Path, default=DEFAULT_PREREG_HASH)
    parser.add_argument("--ablation-prereg", type=Path, default=DEFAULT_ABLATION_PREREG)
    parser.add_argument("--ablation-hash", type=Path, default=DEFAULT_ABLATION_HASH)
    parser.add_argument("--receipt-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--rule-rows", type=Path, default=DEFAULT_RULE_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, report = analyze(args)
    args.output_rows.parent.mkdir(parents=True, exist_ok=True)
    with args.output_rows.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "passed": report["passed"],
        "rows": len(rows),
        "parity_errors": report["full_portfolio_parity"]["error_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
