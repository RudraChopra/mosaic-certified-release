#!/usr/bin/env python3
"""Deterministically audit every strictly replayed MOSAIC bridge decision."""

from __future__ import annotations

import argparse
import json
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from mosaic_real import sha256
from replay_mosaic_bridge_strict import replay_one
from run_mosaic_official_frontier_exact_confirmation import atomic_json_dump


def audit_pair(
    original_path: Path,
    strict_path: Path,
    *,
    prereg_hash: str,
    amendment_hash: str,
) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    stored = json.loads(strict_path.read_text(encoding="utf-8"))
    if stored.get("original_receipt_sha256") != sha256(original_path):
        failures.append("original receipt hash mismatch")
    if stored.get("preregistration_sha256") != prereg_hash:
        failures.append("preregistration hash mismatch")
    if stored.get("strict_amendment_sha256") != amendment_hash:
        failures.append("strict amendment hash mismatch")
    policy = stored.get("numerical_policy", {})
    if policy.get("decision_tolerance") != 0.0:
        failures.append("decision tolerance is not zero")

    with tempfile.TemporaryDirectory(prefix="mosaic-strict-audit-") as directory:
        replay_path = Path(directory) / strict_path.name
        replay_one(
            original_path,
            replay_path,
            prereg_hash=prereg_hash,
            amendment_hash=amendment_hash,
        )
        replayed = json.loads(replay_path.read_text(encoding="utf-8"))
    if replayed != stored:
        failures.append("strict receipt does not exactly match deterministic replay")

    protocol = stored["protocol"]
    source_threshold = float(protocol["privacy_advantage_threshold"])
    row_count = 0
    optimization_count = 0
    minimum_slack = None
    for row in stored.get("results", []):
        row_count += 1
        membership = row.get("bridge_membership")
        if not isinstance(membership, dict):
            failures.append(f"{row.get('candidate')}: missing bridge certificate")
            continue
        for label in membership.get("labels", []):
            slack = float(label["minimum_membership_slack"])
            minimum_slack = slack if minimum_slack is None else min(minimum_slack, slack)
            if slack < 0.0:
                failures.append(f"{row.get('candidate')}: negative bridge slack")
        for release_key in ("release_l2", "release_l4"):
            release = row.get(release_key)
            if not isinstance(release, dict):
                continue
            optimization_count += 1
            if max(float(value) for value in release["certified_source_advantage_upper"]) > source_threshold:
                failures.append(f"{row.get('candidate')}: source bound exceeds contract")
            for threshold in protocol["utility_thresholds"]:
                key = f"{float(threshold):.2f}"
                expected = bool(
                    max(
                        float(value)
                        for value in release["certified_source_advantage_upper"]
                    )
                    <= source_threshold
                    and float(release["certified_worst_conditional_error_upper"])
                    <= float(threshold)
                )
                if release["threshold_decisions"][key]["deployed"] is not expected:
                    failures.append(
                        f"{row.get('candidate')}: non-exact decision at {key}"
                    )
    return failures, {
        "dataset": stored.get("dataset"),
        "seed": stored.get("seed"),
        "original": str(original_path),
        "strict": str(strict_path),
        "original_sha256": sha256(original_path),
        "strict_sha256": sha256(strict_path),
        "candidate_rows": row_count,
        "global_optimizations": optimization_count,
        "minimum_membership_slack": minimum_slack,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--original-dir", required=True, type=Path)
    parser.add_argument("--strict-dir", required=True, type=Path)
    parser.add_argument("--prereg", required=True, type=Path)
    parser.add_argument("--amendment", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive")
    prereg_hash = sha256(args.prereg)
    prereg_sidecar = args.prereg.with_suffix(args.prereg.suffix + ".sha256")
    if prereg_sidecar.read_text(encoding="utf-8").strip() != prereg_hash:
        raise ValueError("preregistration sidecar mismatch")
    amendment_hash = sha256(args.amendment)
    amendment_sidecar = args.amendment.with_suffix(args.amendment.suffix + ".sha256")
    if amendment_sidecar.read_text(encoding="utf-8").strip() != amendment_hash:
        raise ValueError("strict amendment sidecar mismatch")
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
            future = executor.submit(
                audit_pair,
                original_path,
                strict_path,
                prereg_hash=prereg_hash,
                amendment_hash=amendment_hash,
            )
            futures[future] = index
        for future in as_completed(futures):
            index = futures[future]
            pair_failures, summary = future.result()
            failures.extend(
                f"{originals[index].name}: {failure}" for failure in pair_failures
            )
            summaries[index] = summary
            print(originals[index].name, flush=True)
    files = [summary for summary in summaries if summary is not None]
    report: dict[str, object] = {
        "name": "MOSAIC strict numerical bridge independent replay",
        "passed": not failures,
        "preregistration_sha256": prereg_hash,
        "strict_amendment_sha256": amendment_hash,
        "files_replayed": len(files),
        "candidate_rows_replayed": sum(
            int(file["candidate_rows"]) for file in files
        ),
        "global_optimization_replays": sum(
            int(file["global_optimizations"]) for file in files
        ),
        "minimum_membership_slack": min(
            (
                float(file["minimum_membership_slack"])
                for file in files
                if file["minimum_membership_slack"] is not None
            ),
            default=None,
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
