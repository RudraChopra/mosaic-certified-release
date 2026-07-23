#!/usr/bin/env python3
"""Audit the locked ACS 2022 temporal replication from saved receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "research/mosaic/prereg_mosaic_acs_temporal_replication_v1.json"
AMENDMENT = ROOT / (
    "research/mosaic/"
    "prereg_mosaic_acs_temporal_replication_reference_stream_v1.json"
)
REPORT = ROOT / "research/artifacts/mosaic_acs_temporal_replication_v1.json"
OUTPUT = ROOT / "research/artifacts/mosaic_acs_temporal_replication_audit_v1.json"
RECEIPTS = ROOT / "research/artifacts/mosaic_acs_natural_shift_v1_receipts"
SOURCE_THRESHOLD = 0.35
UTILITY_THRESHOLD = 0.40


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
    lock = load(LOCK)
    amendment = load(AMENDMENT)
    failures: list[str] = []
    if report.get("lock_sha256") != sha256(LOCK):
        failures.append("report lock hash differs")
    if report.get("claim_boundary") != lock.get("claim_boundary"):
        failures.append("report claim boundary differs from lock")
    if amendment.get("original_lock_sha256") != sha256(LOCK):
        failures.append("transport amendment points to another lock")
    if amendment.get("original_protocol") != lock.get("protocol"):
        failures.append("transport amendment changed the protocol")

    rows = report.get("rows", [])
    keys = {
        (
            row.get("target_state"),
            row.get("task"),
            row.get("seed"),
            row.get("candidate"),
        )
        for row in rows
    }
    expected_keys = {
        (
            row["target_state"],
            row["task"],
            row["seed"],
            row["candidate"],
        )
        for row in lock["protocol"]["witnesses"]
    }
    if len(rows) != 3 or keys != expected_keys:
        failures.append("report does not contain exactly the three locked interfaces")

    receipt_checks = 0
    interval_checks = 0
    for index, row in enumerate(rows):
        path = RECEIPTS / (
            f"ACS-{row['task']}-CA-{row['target_state']}"
            f"__seed{row['seed']}.json"
        )
        receipt = load(path)
        direct = receipt["alphabets"]["4"]["primary_selection"]["direct"]
        mosaic = receipt["alphabets"]["4"]["primary_selection"]["mosaic"]
        if direct["decision"] != "deploy" or direct["candidate"] != row["candidate"]:
            failures.append(f"row {index}: direct receipt differs")
        if mosaic["decision"] != "abstain":
            failures.append(f"row {index}: paired MOSAIC receipt is not abstain")
        if row.get("reference_reconstruction_match") is not True:
            failures.append(f"row {index}: reference reconstruction did not match")
        receipt_checks += 1

        values = row["future_diagnostic"]
        expected = {
            "source_contract_violation_empirical": (
                values["source_advantage_empirical"] > SOURCE_THRESHOLD
            ),
            "source_contract_violation_confirmed": (
                values["source_advantage_lower"] > SOURCE_THRESHOLD
            ),
            "utility_contract_violation_empirical": (
                values["worst_conditional_error_empirical"] > UTILITY_THRESHOLD
            ),
            "utility_contract_violation_confirmed": (
                values["worst_conditional_error_lower"] > UTILITY_THRESHOLD
            ),
        }
        for name, value in expected.items():
            if values.get(name) is not value:
                failures.append(f"row {index}: {name} differs from metric")
        for prefix in ("source_advantage", "worst_conditional_error"):
            lower = values[f"{prefix}_lower"]
            empirical = values[f"{prefix}_empirical"]
            upper = values[f"{prefix}_upper"]
            if not (
                math.isfinite(lower)
                and math.isfinite(empirical)
                and math.isfinite(upper)
                and lower <= empirical <= upper
            ):
                failures.append(f"row {index}: malformed {prefix} interval")
            interval_checks += 1
        counts = row["confirmation_stratum_counts"]
        if len(counts) != 2 or any(len(value) != 2 for value in counts):
            failures.append(f"row {index}: malformed stratum counts")
        if sum(sum(value) for value in counts) != row["confirmation_rows"]:
            failures.append(f"row {index}: stratum counts do not sum to sample size")

    summary = {
        "registered_interfaces": len(rows),
        "empirical_2022_utility_violations": sum(
            row["future_diagnostic"]["utility_contract_violation_empirical"]
            for row in rows
        ),
        "familywise_confirmed_2022_utility_violations": sum(
            row["future_diagnostic"]["utility_contract_violation_confirmed"]
            for row in rows
        ),
        "paired_mosaic_2018_abstentions": sum(
            row["mosaic_decision_2018"] == "abstain" for row in rows
        ),
    }
    if summary != report.get("summary"):
        failures.append("summary differs from independent reconstruction")
    reference = report.get("reference_raw_asset", {})
    expected_reference = lock["reference_raw_asset"]
    if {
        key: reference.get(key)
        for key in ("year", "state", "bytes", "sha256")
    } != expected_reference:
        failures.append("reference raw asset differs from lock")
    assets = report.get("future_raw_assets", [])
    if sorted(asset.get("state") for asset in assets) != ["FL", "IL"]:
        failures.append("future asset census is incomplete")

    payload = {
        "name": "MOSAIC ACS 2022 temporal replication audit v1",
        "passed": not failures,
        "report_sha256": sha256(args.report),
        "lock_sha256": sha256(LOCK),
        "amendment_sha256": sha256(AMENDMENT),
        "checks": {
            "reported_interfaces": len(rows),
            "receipt_cross_checks": receipt_checks,
            "interval_order_checks": interval_checks,
            "future_assets": len(assets),
        },
        "summary": summary,
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
