#!/usr/bin/env python3
"""Independently audit the locked ACS 2018-to-2021 temporal panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "research/mosaic/prereg_mosaic_acs_pandemic_panel_v1.json"
REPORT = ROOT / "research/artifacts/mosaic_acs_pandemic_panel_v1.json"
OUTPUT = ROOT / "research/artifacts/mosaic_acs_pandemic_panel_audit_v1.json"
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


def receipt_path(row: dict[str, Any]) -> Path:
    return RECEIPTS / (
        f"ACS-{row['task']}-CA-{row['target_state']}__seed{row['seed']}.json"
    )


def paired_witnesses(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, int], dict[str, dict[str, Any]]] = {}
    for row in rows:
        key = (str(row["target_state"]), str(row["task"]), int(row["seed"]))
        grouped.setdefault(key, {})[str(row["rule"])] = row
    witnesses = []
    for (state, task, seed), pair in sorted(grouped.items()):
        direct = pair["direct"]
        mosaic = pair["mosaic"]
        diagnostic = direct.get("future_diagnostic", {})
        empirical_failure = bool(
            diagnostic.get("source_contract_violation_empirical", False)
            or diagnostic.get("utility_contract_violation_empirical", False)
        )
        confirmed_failure = bool(
            diagnostic.get("source_contract_violation_confirmed", False)
            or diagnostic.get("utility_contract_violation_confirmed", False)
        )
        mosaic_abstains = str(
            mosaic.get("runtime_action_2021", "")
        ).startswith("abstain")
        mosaic_safe = bool(
            mosaic.get("future_diagnostic", {}).get(
                "both_contracts_safe_confirmed", False
            )
        )
        direct_deployed = direct.get("decision_2018") == "deploy"
        witnesses.append(
            {
                "target_state": state,
                "task": task,
                "seed": seed,
                "direct_deployed_2018": direct_deployed,
                "direct_empirical_failure_2021": empirical_failure,
                "direct_confirmed_failure_2021": confirmed_failure,
                "mosaic_runtime_abstains_2021": mosaic_abstains,
                "mosaic_confirmed_safe_2021": mosaic_safe,
                "empirical_natural_failure_witness": (
                    direct_deployed
                    and empirical_failure
                    and (mosaic_abstains or mosaic_safe)
                ),
                "confirmed_natural_failure_witness": (
                    direct_deployed
                    and confirmed_failure
                    and (mosaic_abstains or mosaic_safe)
                ),
            }
        )
    return witnesses


def recompute_summary(
    rows: list[dict[str, Any]],
    witnesses: list[dict[str, Any]],
) -> dict[str, int]:
    direct = [
        row
        for row in rows
        if row["rule"] == "direct" and row["decision_2018"] == "deploy"
    ]
    mosaic = [row for row in rows if row["rule"] == "mosaic"]
    releases = [row for row in mosaic if row["runtime_action_2021"] == "release"]
    return {
        "population_jobs": len(witnesses),
        "reported_rule_rows": len(rows),
        "direct_frozen_deployments": len(direct),
        "direct_empirical_contract_violations_2021": sum(
            row["future_diagnostic"]["source_contract_violation_empirical"]
            or row["future_diagnostic"]["utility_contract_violation_empirical"]
            for row in direct
        ),
        "direct_confirmed_contract_violations_2021": sum(
            row["future_diagnostic"]["source_contract_violation_confirmed"]
            or row["future_diagnostic"]["utility_contract_violation_confirmed"]
            for row in direct
        ),
        "mosaic_runtime_releases_2021": len(releases),
        "mosaic_runtime_abstentions_2021": sum(
            str(row["runtime_action_2021"]).startswith("abstain")
            for row in mosaic
        ),
        "mosaic_confirmed_safe_releases_2021": sum(
            row["future_diagnostic"]["both_contracts_safe_confirmed"]
            for row in releases
        ),
        "empirical_natural_failure_witnesses": sum(
            row["empirical_natural_failure_witness"] for row in witnesses
        ),
        "confirmed_natural_failure_witnesses": sum(
            row["confirmed_natural_failure_witness"] for row in witnesses
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
    lock = load(LOCK)
    failures: list[str] = []
    if report.get("lock_sha256") != sha256(LOCK):
        failures.append("report lock hash differs")
    if report.get("claim_boundary") != lock.get("claim_boundary"):
        failures.append("claim boundary differs from preregistration")

    rows = report.get("rows", [])
    keys = [
        (row.get("target_state"), row.get("task"), row.get("seed"), row.get("rule"))
        for row in rows
    ]
    if len(rows) != 120 or len(set(keys)) != 120:
        failures.append("expected 120 unique state-task-seed-rule rows")

    receipt_checks = 0
    interval_checks = 0
    puma_checks = 0
    for index, row in enumerate(rows):
        receipt = load(receipt_path(row))
        frozen = receipt["alphabets"]["4"]["primary_selection"][row["rule"]]
        if row["decision_2018"] != frozen["decision"]:
            failures.append(f"row {index}: 2018 decision differs from receipt")
        if frozen["decision"] != "deploy":
            if "future_diagnostic" in row:
                failures.append(f"row {index}: abstention unexpectedly has diagnostics")
            continue
        receipt_checks += 1
        if row["candidate"] != frozen["candidate"]:
            failures.append(f"row {index}: candidate differs from receipt")
        if row.get("reference_reconstruction_match") is not True:
            failures.append(f"row {index}: reference reconstruction did not match")
        member = set(row["future_membership_pumas"])
        diagnostic = set(row["future_diagnostic_pumas"])
        if not member or not diagnostic or member & diagnostic:
            failures.append(f"row {index}: PUMA folds are empty or overlap")
        puma_checks += 1
        values = row["future_diagnostic"]
        expected_flags = {
            "source_contract_violation_empirical": (
                values["source_advantage_empirical"] > SOURCE_THRESHOLD
            ),
            "utility_contract_violation_empirical": (
                values["worst_conditional_error_empirical"] > UTILITY_THRESHOLD
            ),
            "source_contract_violation_confirmed": (
                values["source_advantage_lower"] > SOURCE_THRESHOLD
            ),
            "utility_contract_violation_confirmed": (
                values["worst_conditional_error_lower"] > UTILITY_THRESHOLD
            ),
            "both_contracts_safe_confirmed": (
                values["source_advantage_upper"] <= SOURCE_THRESHOLD
                and values["worst_conditional_error_upper"] <= UTILITY_THRESHOLD
            ),
        }
        for name, expected in expected_flags.items():
            if values[name] is not expected:
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
        interval_checks += 2

    witnesses = paired_witnesses(rows)
    if witnesses != report.get("paired_witnesses"):
        failures.append("paired witnesses differ from independent reconstruction")
    summary = recompute_summary(rows, witnesses)
    if summary != report.get("summary"):
        failures.append("summary differs from independent reconstruction")

    assets = report.get("future_raw_assets", [])
    if sorted(asset.get("state") for asset in assets) != ["FL", "IL", "NY", "WA"]:
        failures.append("future asset census is incomplete")
    if any(
        asset.get("url") != lock["protocol"]["future_asset_urls"][asset["state"]]
        for asset in assets
    ):
        failures.append("future asset URL differs from preregistration")

    payload = {
        "name": "MOSAIC ACS pandemic-discontinuity panel audit v1",
        "passed": not failures,
        "report_sha256": sha256(args.report),
        "lock_sha256": sha256(LOCK),
        "checks": {
            "reported_rows": len(rows),
            "receipt_cross_checks": receipt_checks,
            "interval_order_checks": interval_checks,
            "disjoint_puma_checks": puma_checks,
            "paired_witnesses_recomputed": len(witnesses),
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
