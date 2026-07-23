#!/usr/bin/env python3
"""Audit the residual-floor decomposition against frozen release receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "research/artifacts/mosaic_residual_sharpness_v1.json"
OUTPUT = ROOT / "research/artifacts/mosaic_residual_sharpness_audit_v1.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def frozen_release(row: dict[str, Any]) -> dict[str, Any]:
    source = load(ROOT / row["inputs"][0])
    candidate = row["candidate"]
    if row["domain"] == "BiasBios-Clinical":
        selected = next(
            value for value in source["results"]
            if value["candidate"] == candidate
        )
        return selected["release_l2"]
    selected = next(
        value for value in source["alphabets"]["4"]["rows"]
        if value["candidate"] == candidate
    )
    return selected["mosaic_release"]


def recompute_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    source_sampling = [
        row["decomposition"]["source_advantage_upper"][
            "finite_sample_increment"
        ]
        for row in rows
    ]
    source_residual = [
        row["decomposition"]["source_advantage_upper"][
            "residual_shift_increment_at_population"
        ]
        for row in rows
    ]
    utility_sampling = [
        row["decomposition"]["worst_conditional_error_upper"][
            "finite_sample_increment"
        ]
        for row in rows
    ]
    utility_residual = [
        row["decomposition"]["worst_conditional_error_upper"][
            "residual_shift_increment_at_population"
        ]
        for row in rows
    ]
    return {
        "jobs": len(rows),
        "untouched_census_jobs": sum(
            not (
                row["domain"] == "BiasBios-Clinical"
                and int(row["seed"]) == 1200
            )
            for row in rows
        ),
        "median_source_finite_sample_increment": median(source_sampling),
        "maximum_source_finite_sample_increment": max(source_sampling),
        "median_source_residual_shift_increment": median(source_residual),
        "minimum_source_residual_shift_increment": min(source_residual),
        "median_utility_finite_sample_increment": median(utility_sampling),
        "maximum_utility_finite_sample_increment": max(utility_sampling),
        "median_utility_residual_shift_increment": median(utility_residual),
        "minimum_utility_residual_shift_increment": min(utility_residual),
        "jobs_residual_exceeds_sampling_for_source": sum(
            residual > sampling
            for residual, sampling in zip(source_residual, source_sampling)
        ),
        "jobs_residual_exceeds_sampling_for_utility": sum(
            residual > sampling
            for residual, sampling in zip(utility_residual, utility_sampling)
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    report = load(args.report)
    lock = ROOT / "research/mosaic/prereg_mosaic_residual_sharpness_v1.json"
    failures = []
    if report["lock_sha256"] != sha256(lock):
        failures.append("report lock hash differs")
    rows = report["rows"]
    for index, row in enumerate(rows):
        release = frozen_release(row)
        full = row["modes"]["full"]
        expected_source = max(release["certified_source_advantage_upper"])
        expected_utility = release["certified_worst_conditional_error_upper"]
        if not math.isclose(
            full["source_advantage_upper"],
            expected_source,
            abs_tol=2e-8,
        ):
            failures.append(f"row {index}: source bound differs from receipt")
        if not math.isclose(
            full["worst_conditional_error_upper"],
            expected_utility,
            abs_tol=2e-8,
        ):
            failures.append(f"row {index}: utility bound differs from receipt")
        for metric in (
            "source_advantage_upper",
            "worst_conditional_error_upper",
        ):
            sampling = row["decomposition"][metric]["finite_sample_increment"]
            if sampling < -1e-10:
                failures.append(f"row {index}: negative sampling increment")
    recomputed = recompute_summary(rows)
    if recomputed != report["summary"]:
        failures.append("summary differs from independent recomputation")
    payload = {
        "name": "MOSAIC residual-sharpness census audit v1",
        "passed": not failures,
        "report_sha256": sha256(args.report),
        "checks": {
            "rows": len(rows),
            "frozen_release_cross_checks": len(rows),
            "summary_recomputed": True,
        },
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
