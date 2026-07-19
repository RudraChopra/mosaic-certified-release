#!/usr/bin/env python3
"""Summarize the locked strict ACS California-to-Texas confirmation."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from mosaic_real import sha256
from run_mosaic_official_frontier_exact_confirmation import atomic_json_dump


EXPECTED_SEEDS = (1305, 1306, 1307, 1308, 1309)


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def summarize(strict_dir: Path, audit_path: Path) -> dict[str, Any]:
    receipts = [load(path) for path in sorted(strict_dir.glob("*.json"))]
    seeds = tuple(int(receipt["seed"]) for receipt in receipts)
    if seeds != EXPECTED_SEEDS:
        raise ValueError(f"expected seeds {EXPECTED_SEEDS}, found {seeds}")
    if {receipt.get("dataset") for receipt in receipts} != {"ACSIncome-CA-TX"}:
        raise ValueError("ACS receipts have the wrong dataset label")
    audit = load(audit_path)
    if not audit.get("passed"):
        raise ValueError("the ACS strict replay audit must pass")
    thresholds = tuple(sorted(receipts[0]["selection_by_utility_threshold"], key=float))
    rows: dict[str, dict[str, Any]] = {}
    for threshold in thresholds:
        choices = [receipt["selection_by_utility_threshold"][threshold] for receipt in receipts]
        deployments = [choice for choice in choices if choice.get("decision") == "deploy"]
        methods = Counter(str(choice["method"]) for choice in deployments)
        rows[threshold] = {
            "trials": len(choices),
            "deployments": len(deployments),
            "abstentions": len(choices) - len(deployments),
            "diagnostic_estimable_deployments": sum(
                bool(choice.get("diagnostic_estimable")) for choice in deployments
            ),
            "diagnostic_safe_deployments": sum(
                bool(choice.get("diagnostic_safe")) for choice in deployments
            ),
            "diagnostic_contract_violations": sum(
                bool(choice.get("false_acceptance")) for choice in deployments
            ),
            "selected_method_counts": dict(sorted(methods.items())),
        }
    return {
        "name": "MOSAIC locked strict ACS California-to-Texas summary",
        "dataset": "ACSIncome-CA-TX",
        "reference_population": "California ACS 2018 1-Year PUMS",
        "target_population": "Texas ACS 2018 1-Year PUMS",
        "seeds": list(seeds),
        "candidate_rows": sum(len(receipt["results"]) for receipt in receipts),
        "primary_utility_threshold": "0.40",
        "selection_by_utility_threshold": rows,
        "strict_audit": {
            "path": str(audit_path),
            "sha256": sha256(audit_path),
            "passed": True,
            "candidate_rows_replayed": audit["candidate_rows_replayed"],
            "global_optimization_replays": audit["global_optimization_replays"],
        },
        "claim_boundary": (
            "This is a five-seed, pre-outcome-locked geographic-shift confirmation. "
            "Texas diagnostics are held out from selection and are reported as checks, "
            "not as a population-wide guarantee."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-dir", required=True, type=Path)
    parser.add_argument("--audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    atomic_json_dump(summarize(args.strict_dir, args.audit), args.output)
    print(args.output)


if __name__ == "__main__":
    main()
