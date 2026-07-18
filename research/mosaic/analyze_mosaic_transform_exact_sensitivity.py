#!/usr/bin/env python3
"""Derive an explicitly post-hoc threshold sensitivity from audited receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_REPORT = REPOSITORY / "research/artifacts/mosaic_transform_exact_confirmation_v2.json"
DEFAULT_AUDIT = (
    REPOSITORY / "research/artifacts/mosaic_transform_exact_confirmation_audit_v2.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY / "research/artifacts/mosaic_transform_exact_sensitivity_v1.json"
)
UTILITY_THRESHOLDS = (0.43, 0.44, 0.45, 0.46, 0.47)
SAMPLE_SIZES = (125, 250)
PRIVACY_THRESHOLD = 0.35


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def atomic_json(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite sensitivity output")
    report = load(args.report)
    audit = load(args.audit)
    if audit.get("pass") is not True or audit.get("report_sha256") != sha256(args.report):
        raise RuntimeError("sensitivity requires the matching passing receipt replay")

    rows = report["replicate_results"]
    cells = []
    for n in SAMPLE_SIZES:
        for threshold in UTILITY_THRESHOLDS:
            for method in report["methods"]:
                subset = [
                    row
                    for row in rows
                    if row["scenario"] == "retention_and_exactness_value"
                    and int(row["sample_size_per_stratum"]) == n
                    and row["method"] == method
                ]
                if len(subset) != 1000:
                    raise RuntimeError("incomplete audited sensitivity cell")
                deployments = 0
                false_acceptances = 0
                for row in subset:
                    privacy_pass = all(
                        float(value) <= PRIVACY_THRESHOLD + 1e-10
                        for value in row["certified_privacy_advantages"]
                    )
                    deployed = bool(
                        privacy_pass
                        and float(row["certified_worst_conditional_error"])
                        <= threshold + 1e-10
                    )
                    exact_safe = bool(
                        float(row["exact_worst_privacy_advantage"])
                        <= PRIVACY_THRESHOLD + 1e-9
                        and float(row["exact_worst_conditional_error"])
                        <= threshold + 1e-9
                    )
                    deployments += int(deployed)
                    false_acceptances += int(deployed and not exact_safe)
                cells.append(
                    {
                        "sample_size_per_stratum": n,
                        "utility_threshold": threshold,
                        "privacy_threshold": PRIVACY_THRESHOLD,
                        "method": method,
                        "replicates": len(subset),
                        "deployments": deployments,
                        "safe_deployment_rate": (deployments - false_acceptances) / len(subset),
                        "false_acceptances": false_acceptances,
                    }
                )

    index = {
        (cell["sample_size_per_stratum"], cell["utility_threshold"], cell["method"]): cell
        for cell in cells
    }
    pointwise_retention = all(
        index[(n, threshold, "transform_exact")]["safe_deployment_rate"]
        >= index[(n, threshold, "capacity_transfer")]["safe_deployment_rate"]
        for n in SAMPLE_SIZES
        for threshold in UTILITY_THRESHOLDS
    )
    payload = {
        "name": "MOSAIC transform-exact post-hoc utility-threshold sensitivity v1",
        "status": "post_outcome_exploratory_not_preregistered",
        "claim_boundary": "Thresholds other than 0.45 were selected after confirmation and are descriptive. Channels, tables, privacy threshold, and exact population risks are unchanged from the audited confirmation.",
        "report_sha256": sha256(args.report),
        "audit_sha256": sha256(args.audit),
        "utility_thresholds": list(UTILITY_THRESHOLDS),
        "sample_sizes_per_stratum": list(SAMPLE_SIZES),
        "cells": cells,
        "all_false_acceptances_zero": all(
            int(cell["false_acceptances"]) == 0 for cell in cells
        ),
        "transform_exact_retention_no_lower_in_every_cell": pointwise_retention,
    }
    atomic_json(payload, args.output)
    print(json.dumps({key: value for key, value in payload.items() if key != "cells"}, indent=2))


if __name__ == "__main__":
    main()
