#!/usr/bin/env python3
"""Build the preregistered MOSAIC bridge confirmation manifest and gates."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from scipy.stats import beta

from mosaic_real import sha256


TOLERANCE = 3e-7


def atomic_json_dump(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def exact_interval(successes: int, trials: int, confidence: float = 0.95) -> list[float] | None:
    if trials == 0:
        return None
    alpha = 1.0 - confidence
    lower = (
        0.0
        if successes == 0
        else float(beta.ppf(alpha / 2.0, successes, trials - successes + 1))
    )
    upper = (
        1.0
        if successes == trials
        else float(
            beta.ppf(1.0 - alpha / 2.0, successes + 1, trials - successes)
        )
    )
    return [lower, upper]


def one_sided_upper(successes: int, trials: int, confidence: float = 0.95) -> float | None:
    if trials == 0:
        return None
    if successes == trials:
        return 1.0
    return float(beta.ppf(confidence, successes + 1, trials - successes))


def load(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain an object")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("receipts", nargs="+", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prereg_hash = sha256(args.prereg)
    sidecar = args.prereg.with_suffix(args.prereg.suffix + ".sha256")
    if not sidecar.exists() or sidecar.read_text(encoding="utf-8").strip() != prereg_hash:
        raise AssertionError("preregistration sidecar mismatch")
    prereg = load(args.prereg)
    audit = load(args.audit)
    receipts = [load(path) for path in args.receipts]
    gates = prereg["decision_gates"]
    expected_pairs = {
        (dataset, seed)
        for dataset in prereg["datasets"]
        for seed in prereg["confirmation_seeds"]
    }
    observed_pairs = {
        (str(receipt["dataset"]), int(receipt["seed"])) for receipt in receipts
    }

    failures: list[str] = []
    for relative, expected_hash in prereg.get("code_sha256", {}).items():
        if sha256(Path(__file__).resolve().parents[2] / relative) != expected_hash:
            failures.append(f"locked code hash mismatch: {relative}")
    for dataset, receipt in prereg["datasets"].items():
        if sha256(Path(receipt["path"]) / "manifest.json") != receipt[
            "manifest_sha256"
        ]:
            failures.append(f"frozen dataset manifest mismatch: {dataset}")
    if len(receipts) != int(gates["required_files"]):
        failures.append("receipt count mismatch")
    if observed_pairs != expected_pairs or len(observed_pairs) != len(receipts):
        failures.append("dataset-seed matrix mismatch or duplicate")
    if any(receipt.get("prereg_sha256") != prereg_hash for receipt in receipts):
        failures.append("receipt preregistration hash mismatch")
    if audit.get("passed") is not True:
        failures.append("independent replay failed")
    if int(audit.get("files_replayed", -1)) != int(gates["required_files"]):
        failures.append("audit file count mismatch")
    if int(audit.get("candidate_rows_replayed", -1)) != int(
        gates["required_candidate_rows"]
    ):
        failures.append("audit candidate replay count mismatch")
    if int(audit.get("global_optimization_replays", -1)) != int(
        gates["required_global_optimization_replays"]
    ):
        failures.append("audit global optimization count mismatch")
    minimum_slack = audit.get("minimum_membership_slack")
    if minimum_slack is None or float(minimum_slack) < -float(
        gates["maximum_bridge_membership_violation"]
    ):
        failures.append("bridge membership violation")

    candidate_rows = sum(len(receipt.get("results", [])) for receipt in receipts)
    optimization_errors = sum(
        "optimization_error" in result
        for receipt in receipts
        for result in receipt.get("results", [])
    )
    if candidate_rows != int(gates["required_candidate_rows"]):
        failures.append("candidate row count mismatch")
    if optimization_errors > int(gates["maximum_optimization_errors"]):
        failures.append("optimization errors exceed gate")

    thresholds = prereg["protocol"]["utility_thresholds"]
    per_dataset_threshold: dict[str, Counter[str]] = defaultdict(Counter)
    primary_deployments = []
    selected_contaminations = []
    for receipt in receipts:
        dataset = str(receipt["dataset"])
        for threshold in thresholds:
            key = f"{float(threshold):.2f}"
            selection = receipt["selection_by_utility_threshold"][key]
            per_dataset_threshold[dataset][key] += int(
                selection["decision"] == "deploy"
            )
        primary = receipt["primary_selection"]
        if primary["decision"] == "deploy":
            primary_deployments.append(primary)
            selected_contaminations.extend(
                float(value) for value in primary["bridge_contaminations"]
            )

    estimable_primary = [
        value for value in primary_deployments if value["diagnostic_estimable"]
    ]
    false_primary = sum(bool(value["false_acceptance"]) for value in estimable_primary)
    if len(estimable_primary) < int(gates["minimum_estimable_primary_deployments"]):
        failures.append("too few estimable primary deployments")
    if false_primary > int(gates["maximum_primary_false_acceptances"]):
        failures.append("primary false acceptances exceed gate")
    bias_primary = per_dataset_threshold["BiasBios-Clinical"]["0.40"]
    bias_tau035 = per_dataset_threshold["BiasBios-Clinical"]["0.35"]
    if bias_primary < int(gates["minimum_biasbios_primary_deployments"]):
        failures.append("BiasBios primary deployment gate failed")
    if bias_tau035 < int(gates["minimum_biasbios_tau035_deployments"]):
        failures.append("BiasBios tau=0.35 deployment gate failed")

    l4_differences = []
    for receipt in receipts:
        comparison = receipt.get("l4_interface_comparison")
        if not isinstance(comparison, dict):
            failures.append("missing L4 interface comparison")
            continue
        difference = float(comparison["l4_certified_error"]) - float(
            comparison["l2_certified_error"]
        )
        l4_differences.append(difference)
        if difference > TOLERANCE:
            failures.append("L4 objective is worse than L2 embedding")

    camelyon = [
        receipt for receipt in receipts if receipt["dataset"] == "Camelyon17-WILDS"
    ]
    camelyon_missing_support_abstentions = 0
    for receipt in camelyon:
        missing_bridge = any(
            0 in np.asarray(result.get("bridge_stratum_counts", []), dtype=np.int64)
            for result in receipt.get("results", [])
            if "optimization_error" not in result
        )
        zero_retention = any(
            min(result["bridge_membership"]["retained_masses"]) <= 1e-12
            for result in receipt.get("results", [])
            if "optimization_error" not in result
        )
        abstained = receipt["primary_selection"]["decision"] == "abstain"
        camelyon_missing_support_abstentions += int(
            missing_bridge and zero_retention and abstained
        )
    if bool(gates["require_camelyon_missing_support_abstention"]) and (
        camelyon_missing_support_abstentions != len(camelyon)
    ):
        failures.append("Camelyon missing-support abstention gate failed")

    summaries = {
        dataset: {
            key: {
                "deployments": int(count),
                "trials": len(prereg["confirmation_seeds"]),
                "rate": count / len(prereg["confirmation_seeds"]),
                "exact_95_interval": exact_interval(
                    int(count), len(prereg["confirmation_seeds"])
                ),
            }
            for key, count in sorted(counts.items())
        }
        for dataset, counts in sorted(per_dataset_threshold.items())
    }
    report: dict[str, object] = {
        "name": "MOSAIC data-certified bridge confirmation manifest",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not failures else "complete_with_failed_gates",
        "preregistration_sha256": prereg_hash,
        "audit_sha256": sha256(args.audit),
        "receipt_hashes": {
            str(path): sha256(path) for path in sorted(args.receipts)
        },
        "all_pass": not failures,
        "failures": failures,
        "files": len(receipts),
        "candidate_rows": candidate_rows,
        "optimization_errors": optimization_errors,
        "global_optimization_replays": audit.get("global_optimization_replays"),
        "minimum_membership_slack": minimum_slack,
        "primary_deployments": len(primary_deployments),
        "estimable_primary_deployments": len(estimable_primary),
        "primary_false_acceptances": false_primary,
        "primary_false_acceptance_rate": (
            false_primary / len(estimable_primary) if estimable_primary else None
        ),
        "primary_false_acceptance_one_sided_95_upper": one_sided_upper(
            false_primary, len(estimable_primary)
        ),
        "selected_contamination_median": (
            float(np.median(selected_contaminations))
            if selected_contaminations
            else None
        ),
        "selected_contamination_range": (
            [min(selected_contaminations), max(selected_contaminations)]
            if selected_contaminations
            else None
        ),
        "l4_no_worse_rows": sum(value <= TOLERANCE for value in l4_differences),
        "l4_strict_improvement_rows": sum(value < -1e-10 for value in l4_differences),
        "l4_difference_range": (
            [min(l4_differences), max(l4_differences)] if l4_differences else None
        ),
        "camelyon_missing_support_abstentions": (
            camelyon_missing_support_abstentions
        ),
        "deployment_by_dataset_and_threshold": summaries,
        "claim_boundary": prereg["claim_boundary"],
    }
    atomic_json_dump(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
