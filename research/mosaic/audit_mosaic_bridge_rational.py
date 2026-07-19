#!/usr/bin/env python3
"""Exact-rational audit for all serialized MOSAIC bridge releases."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from fractions import Fraction
from pathlib import Path

import numpy as np

from mosaic_rational_certificate import (
    audit_bridge_exact,
    audit_release_exact,
    fraction_decimal,
)
from mosaic_real import sha256
from run_mosaic_official_frontier_exact_confirmation import atomic_json_dump


def audit_pair(
    original_path: Path,
    strict_path: Path,
) -> tuple[list[str], dict[str, object]]:
    original = json.loads(original_path.read_text(encoding="utf-8"))
    strict = json.loads(strict_path.read_text(encoding="utf-8"))
    failures: list[str] = []
    if strict.get("original_receipt_sha256") != sha256(original_path):
        failures.append("original receipt hash mismatch")
    original_rows = {row["candidate"]: row for row in original.get("results", [])}
    strict_rows = {row["candidate"]: row for row in strict.get("results", [])}
    if set(original_rows) != set(strict_rows):
        failures.append("candidate sets differ")
    bridge_count = 0
    release_count = 0
    minimum_slack: Fraction | None = None
    maximum_source_gap = Fraction(0)
    maximum_utility_gap = Fraction(0)
    for candidate, row in strict_rows.items():
        source_row = original_rows.get(candidate)
        if source_row is None or "optimization_error" in source_row:
            failures.append(f"{candidate}: missing valid original token tables")
            continue
        membership = row.get("bridge_membership")
        if not isinstance(membership, dict):
            failures.append(f"{candidate}: missing strict bridge membership")
            continue
        bridge = audit_bridge_exact(
            source_row["reference_token_counts"],
            source_row["bridge_token_counts"],
            reference_l1_radii=source_row["reference_l1_radii"],
            bridge_l1_radii=source_row["bridge_l1_radii"],
            serialized_labels=membership["labels"],
        )
        bridge_count += 1
        minimum_slack = (
            bridge.minimum_membership_slack
            if minimum_slack is None
            else min(minimum_slack, bridge.minimum_membership_slack)
        )
        if bridge.minimum_membership_slack < 0:
            failures.append(f"{candidate}: exact bridge slack is negative")
        for release_key in ("release_l2", "release_l4"):
            release = row.get(release_key)
            if not isinstance(release, dict):
                continue
            exact = audit_release_exact(
                source_row["reference_token_counts"],
                reference_l1_radii=source_row["reference_l1_radii"],
                bridge=bridge,
                release_channel=release["release_channel"],
                decoder=release["decoder"],
            )
            release_count += 1
            stored_source = tuple(
                Fraction(str(float(value)))
                for value in release["certified_source_advantage_upper"]
            )
            stored_utility = Fraction(
                str(float(release["certified_worst_conditional_error_upper"]))
            )
            for label, (stored, verified) in enumerate(
                zip(stored_source, exact.source_advantages, strict=True)
            ):
                if stored < verified:
                    failures.append(
                        f"{candidate}: {release_key}: label {label} source bound rounds inward"
                    )
                maximum_source_gap = max(maximum_source_gap, stored - verified)
            if stored_utility < exact.worst_conditional_error:
                failures.append(f"{candidate}: {release_key}: utility bound rounds inward")
            maximum_utility_gap = max(
                maximum_utility_gap,
                stored_utility - exact.worst_conditional_error,
            )
    return failures, {
        "dataset": strict.get("dataset"),
        "seed": strict.get("seed"),
        "original_sha256": sha256(original_path),
        "strict_sha256": sha256(strict_path),
        "bridges_replayed": bridge_count,
        "releases_replayed": release_count,
        "minimum_exact_membership_slack": (
            fraction_decimal(minimum_slack) if minimum_slack is not None else None
        ),
        "maximum_source_outward_gap": fraction_decimal(maximum_source_gap),
        "maximum_utility_outward_gap": fraction_decimal(maximum_utility_gap),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-dir", required=True, type=Path)
    parser.add_argument("--strict-dir", required=True, type=Path)
    parser.add_argument("--strict-amendment", required=True, type=Path)
    parser.add_argument("--rational-lock", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive")
    strict_amendment_hash = sha256(args.strict_amendment)
    strict_sidecar = args.strict_amendment.with_suffix(
        args.strict_amendment.suffix + ".sha256"
    )
    if strict_sidecar.read_text(encoding="utf-8").strip() != strict_amendment_hash:
        raise ValueError("strict amendment sidecar mismatch")
    rational_lock_hash = sha256(args.rational_lock)
    rational_sidecar = args.rational_lock.with_suffix(args.rational_lock.suffix + ".sha256")
    if rational_sidecar.read_text(encoding="utf-8").strip() != rational_lock_hash:
        raise ValueError("rational audit lock sidecar mismatch")
    originals = sorted(args.original_dir.glob("*.json"))
    strict = {path.name: path for path in args.strict_dir.glob("*.json")}
    failures: list[str] = []
    if set(strict) != {path.name for path in originals}:
        failures.append("original and strict receipt filename sets differ")
    summaries: list[dict[str, object] | None] = [None] * len(originals)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for index, original_path in enumerate(originals):
            strict_path = strict.get(original_path.name)
            if strict_path is None:
                continue
            futures[
                executor.submit(audit_pair, original_path, strict_path)
            ] = index
        for future in as_completed(futures):
            index = futures[future]
            pair_failures, summary = future.result()
            failures.extend(
                f"{originals[index].name}: {failure}" for failure in pair_failures
            )
            summaries[index] = summary
            print(originals[index].name, flush=True)
    files = [summary for summary in summaries if summary is not None]
    exact_slacks = [
        Fraction(file["minimum_exact_membership_slack"])
        for file in files
        if file["minimum_exact_membership_slack"] is not None
    ]
    report: dict[str, object] = {
        "name": "MOSAIC exact-rational serialized-certificate audit",
        "passed": not failures,
        "strict_amendment_sha256": strict_amendment_hash,
        "rational_audit_lock_sha256": rational_lock_hash,
        "radius_outward_guard": "0.000000000001",
        "files_replayed": len(files),
        "bridges_replayed": sum(int(file["bridges_replayed"]) for file in files),
        "releases_replayed": sum(int(file["releases_replayed"]) for file in files),
        "minimum_exact_membership_slack": (
            fraction_decimal(min(exact_slacks)) if exact_slacks else None
        ),
        "failures": failures,
        "files": files,
    }
    atomic_json_dump(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
