#!/usr/bin/env python3
"""Independent receipt replay for the exploratory real transform-exact analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Sequence

import numpy as np

from mosaic_real import ordered_smoothing_library
from mosaic_transform_exact import (
    transform_exact_attacker_confidence_bound,
    transform_exact_utility_confidence_bound,
)
from mosaic_transform_exact_optimizer import optimize_transform_exact_channel


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_ANALYSIS = REPOSITORY / "research/artifacts/mosaic_real_transform_exact_exploratory_v1.json"
DEFAULT_OUTPUT = REPOSITORY / "research/artifacts/mosaic_real_transform_exact_exploratory_audit_v1.json"
TOLERANCE = 2e-7


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json_dump(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def distributions(counts: Sequence[Sequence[Sequence[int]]]) -> tuple[np.ndarray, np.ndarray]:
    values = np.asarray(counts, dtype=np.int64)
    if values.shape != (2, 2, 4) or np.any(values < 0):
        raise ValueError("invalid token counts")
    totals = values.sum(axis=2)
    probabilities = np.full(values.shape, 0.25, dtype=np.float64)
    for label in range(2):
        for source in range(2):
            if totals[label, source] > 0:
                probabilities[label, source] = (
                    values[label, source] / totals[label, source]
                )
    return probabilities, totals


def external_diagnostic(
    counts: Sequence[Sequence[Sequence[int]]],
    channel: np.ndarray,
    decoder: tuple[int, ...],
) -> dict[str, object]:
    probabilities, totals = distributions(counts)
    missing = [
        [label, source]
        for label in range(2)
        for source in range(2)
        if totals[label, source] == 0
    ]
    if missing:
        return {"estimable": False, "privacy": None, "utility": None, "missing": missing}
    decoder_array = np.asarray(decoder, dtype=np.int64)
    privacy = []
    utility = []
    for label in range(2):
        released = probabilities[label] @ channel
        privacy.append(float(2.0 * (np.max(released, axis=0).sum() / 2.0) - 1.0))
        loss = (decoder_array != label).astype(np.float64)
        utility.extend(
            float(probabilities[label, source] @ channel @ loss)
            for source in range(2)
        )
    return {
        "estimable": True,
        "privacy": max(privacy),
        "utility": max(utility),
        "missing": [],
    }


def close(first: object, second: object) -> bool:
    if first is None or second is None:
        return first is second
    return abs(float(first) - float(second)) <= TOLERANCE


def select(rows: list[dict[str, Any]], prefix: str) -> tuple[str | None, float | None]:
    eligible = [row for row in rows if bool(row[f"{prefix}_deployed"])]
    if not eligible:
        return None, None
    key = f"{prefix}_certified_error"
    chosen = min(eligible, key=lambda row: (float(row[key]), str(row["candidate"])))
    return str(chosen["candidate"]), float(chosen[key])


def audit_row(
    row: dict[str, Any], receipt: dict[str, Any], original: dict[str, Any]
) -> list[str]:
    failures = []
    protocol = receipt["protocol"]
    empirical, _ = distributions(original["certification_token_counts"])
    radii = np.asarray(original["l1_radii"], dtype=np.float64)
    transforms = ordered_smoothing_library(
        4, smoothing=float(protocol["ordered_smoothing"])
    )
    eta = float(protocol["contamination"])
    privacy_threshold = float(protocol["privacy_advantage_threshold"])
    utility_threshold = float(protocol["maximum_worst_conditional_error"])
    channel = np.asarray(row["exact_release_channel"], dtype=np.float64)
    decoder = tuple(int(value) for value in row["exact_decoder"])
    if (
        channel.shape != (4, 2)
        or np.any(channel < -TOLERANCE)
        or not np.allclose(channel.sum(axis=1), 1.0, atol=TOLERANCE, rtol=0.0)
    ):
        failures.append("invalid stored release channel")
        return failures
    privacy = [
        transform_exact_attacker_confidence_bound(
            empirical[label],
            channel,
            l1_radii=radii[label],
            common_fine_token_channels=transforms,
            contamination=eta,
        ).normalized_advantage
        for label in range(2)
    ]
    utility = max(
        transform_exact_utility_confidence_bound(
            empirical[label, source],
            channel,
            decoder,
            true_label=label,
            l1_radius=float(radii[label, source]),
            common_fine_token_channels=transforms,
            contamination=eta,
        ).error_probability
        for label in range(2)
        for source in range(2)
    )
    if not np.allclose(
        privacy,
        np.asarray(row["exact_certified_privacy_advantages"], dtype=np.float64),
        atol=TOLERANCE,
        rtol=0.0,
    ):
        failures.append("stored-channel privacy mismatch")
    if not close(utility, row["exact_certified_error"]):
        failures.append("stored-channel utility mismatch")
    deployed = bool(
        max(privacy) <= privacy_threshold + 1e-10
        and utility <= utility_threshold + 1e-10
    )
    if deployed is not bool(row["exact_deployed"]):
        failures.append("deployment decision mismatch")

    optimized = optimize_transform_exact_channel(
        empirical,
        l1_radii=radii,
        common_channels_by_label=(transforms, transforms),
        contaminations=(eta, eta),
        privacy_advantage_thresholds=(privacy_threshold, privacy_threshold),
        released_token_count=2,
        solver_time_limit_seconds=300.0,
    )
    if not close(optimized.certified_worst_conditional_error, utility):
        failures.append("global optimum mismatch")
    fallback_error = float(original["certified_worst_conditional_error"])
    if not close(fallback_error, row["fallback_certified_error"]):
        failures.append("fallback objective mismatch")
    if bool(original["deployed"]) is not bool(row["fallback_deployed"]):
        failures.append("fallback decision mismatch")
    if utility > fallback_error + TOLERANCE:
        failures.append("pointwise dominance violation")
    if not close(fallback_error - utility, row["objective_improvement"]):
        failures.append("objective improvement mismatch")
    crossing = bool(deployed and not original["deployed"])
    if crossing is not bool(row["crossed_utility_contract"]):
        failures.append("contract crossing mismatch")

    external = external_diagnostic(
        original["external_token_counts"], channel, decoder
    )
    if bool(external["estimable"]) is not bool(row["external_estimable"]):
        failures.append("external estimability mismatch")
    if not close(external["privacy"], row["external_worst_privacy_advantage"]):
        failures.append("external privacy mismatch")
    if not close(external["utility"], row["external_worst_conditional_error"]):
        failures.append("external utility mismatch")
    external_safe = bool(
        external["estimable"]
        and float(external["privacy"]) <= privacy_threshold + 1e-10
        and float(external["utility"]) <= utility_threshold + 1e-10
    )
    if external_safe is not bool(row["external_safe"]):
        failures.append("external safety mismatch")
    false_acceptance = bool(deployed and external["estimable"] and not external_safe)
    if false_acceptance is not bool(row["false_acceptance"]):
        failures.append("false acceptance mismatch")
    return failures


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", type=Path, default=DEFAULT_ANALYSIS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite audit output")
    analysis = json.loads(args.analysis.read_text(encoding="utf-8"))
    rows = analysis.get("rows", [])
    if len(rows) != 325:
        raise RuntimeError(f"expected 325 analysis rows, found {len(rows)}")
    receipt_cache: dict[str, dict[str, Any]] = {}
    original_cache: dict[tuple[str, str], dict[str, Any]] = {}
    failures = []
    by_job: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        relative = str(row["receipt"])
        if relative not in receipt_cache:
            path = REPOSITORY / relative
            if sha256(path) != row["receipt_sha256"]:
                failures.append(f"row {index}: receipt hash mismatch")
            receipt = json.loads(path.read_text(encoding="utf-8"))
            receipt_cache[relative] = receipt
            for original in receipt["results"]:
                original_cache[(relative, str(original["candidate"]))] = original
        receipt = receipt_cache[relative]
        original = original_cache.get((relative, str(row["candidate"])))
        if original is None:
            failures.append(f"row {index}: candidate missing from receipt")
            continue
        row_failures = audit_row(row, receipt, original)
        failures.extend(f"row {index} {row['candidate']}: {value}" for value in row_failures)
        by_job[(str(row["dataset"]), int(row["seed"]))].append(row)

    expected_jobs = analysis["summary"]["jobs"]
    indexed_jobs = {
        (str(job["dataset"]), int(job["seed"])): job for job in expected_jobs
    }
    if len(by_job) != 25 or len(indexed_jobs) != 25:
        failures.append("job count mismatch")
    for key, job_rows in by_job.items():
        expected = indexed_jobs.get(key)
        if expected is None or len(job_rows) != 13:
            failures.append(f"invalid job {key}")
            continue
        for prefix in ("fallback", "exact"):
            candidate, error = select(job_rows, prefix)
            stored = expected[f"{prefix}_selection"]
            if candidate != stored["candidate"]:
                failures.append(f"{key} {prefix} selection mismatch")
            if candidate is not None and not close(error, stored["certified_worst_conditional_error"]):
                failures.append(f"{key} {prefix} selected objective mismatch")

    summary = analysis["summary"]
    checks = {
        "candidate_rows": len(rows),
        "fallback_candidate_deployments": sum(
            bool(row["fallback_deployed"]) for row in rows
        ),
        "exact_candidate_deployments": sum(bool(row["exact_deployed"]) for row in rows),
        "candidate_contract_crossings": sum(
            bool(row["crossed_utility_contract"]) for row in rows
        ),
        "strict_objective_improvements": sum(
            float(row["objective_improvement"]) > 1e-10 for row in rows
        ),
        "pointwise_dominance": all(
            float(row["objective_improvement"]) >= -TOLERANCE for row in rows
        ),
    }
    for key, observed in checks.items():
        if observed != summary[key]:
            failures.append(f"aggregate mismatch: {key}")
    payload = {
        "name": "MOSAIC exploratory real transform-exact independent replay v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "analysis_sha256": sha256(args.analysis),
        "audited_rows": len(rows),
        "optimization_replays": len(rows),
        "receipt_files": len(receipt_cache),
        "aggregate_checks": checks,
        "mismatch_count": len(failures),
        "mismatches": failures[:100],
        "pass": not failures,
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
