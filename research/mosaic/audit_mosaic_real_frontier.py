#!/usr/bin/env python3
"""Replay MOSAIC real-frontier certificates and diagnostics from receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from mosaic_channel import normalized_attacker_advantage
from mosaic_envelope import weissman_l1_radius
from mosaic_invariant import (
    adaptive_pre_release_attacker_certificate,
    pre_release_utility_certificate,
)
from mosaic_real import ordered_smoothing_library
from run_mosaic_official_frontier_pilot import select_certified_result


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


def probabilities_from_counts(counts: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if counts.shape != (2, 2, 4) or np.any(counts < 0):
        raise ValueError("token counts must have shape (2, 2, 4) and be nonnegative")
    totals = counts.sum(axis=2)
    probabilities = np.full(counts.shape, 0.25, dtype=np.float64)
    for label in range(2):
        for source in range(2):
            if totals[label, source] > 0:
                probabilities[label, source] = (
                    counts[label, source] / totals[label, source]
                )
    return probabilities, totals


def replay_external(
    counts: np.ndarray,
    channel: np.ndarray,
    decoder: tuple[int, ...],
) -> dict[str, object]:
    probabilities, totals = probabilities_from_counts(counts)
    missing = [
        (label, source)
        for label in range(2)
        for source in range(2)
        if totals[label, source] == 0
    ]
    if missing:
        return {
            "estimable": False,
            "worst_privacy_advantage": None,
            "worst_conditional_error": None,
            "missing_strata": missing,
        }
    privacy = []
    errors = []
    decoder_array = np.asarray(decoder, dtype=np.int64)
    for label in range(2):
        released = probabilities[label] @ channel
        balanced_accuracy = float(np.max(released, axis=0).sum() / 2.0)
        privacy.append(normalized_attacker_advantage(balanced_accuracy, 2))
        loss = (decoder_array != label).astype(np.float64)
        errors.extend(
            float(probabilities[label, source] @ channel @ loss)
            for source in range(2)
        )
    return {
        "estimable": True,
        "worst_privacy_advantage": max(privacy),
        "worst_conditional_error": max(errors),
        "missing_strata": [],
    }


def close(first: object, second: object) -> bool:
    if first is None or second is None:
        return first is second
    return abs(float(first) - float(second)) <= TOLERANCE


def replay_candidate(
    result: dict[str, object], protocol: dict[str, object]
) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    certification_counts = np.asarray(result["certification_token_counts"], dtype=np.int64)
    probabilities, totals = probabilities_from_counts(certification_counts)
    delta = float(protocol["per_candidate_delta"])
    radii = np.asarray(
        [
            [
                2.0
                if totals[label, source] == 0
                else weissman_l1_radius(
                    int(totals[label, source]), 4, delta / 4.0
                )
                for source in range(2)
            ]
            for label in range(2)
        ],
        dtype=np.float64,
    )
    stored_radii = np.asarray(result["l1_radii"], dtype=np.float64)
    if not np.allclose(radii, stored_radii, atol=TOLERANCE, rtol=0.0):
        failures.append("L1 radius mismatch")

    channel = np.asarray(result["release_channel"], dtype=np.float64)
    decoder = tuple(int(value) for value in result["decoder"])
    smoothing = float(protocol["ordered_smoothing"])
    common = ordered_smoothing_library(4, smoothing=smoothing)
    eta = float(protocol["contamination"])
    privacy = [
        adaptive_pre_release_attacker_certificate(
            probabilities[label],
            channel,
            l1_radii=radii[label],
            common_fine_token_channels=common,
            contamination=eta,
        ).normalized_advantage
        for label in range(2)
    ]
    if not np.allclose(
        privacy,
        np.asarray(result["certified_privacy_advantages"], dtype=np.float64),
        atol=TOLERANCE,
        rtol=0.0,
    ):
        failures.append("privacy certificate mismatch")
    utility = max(
        pre_release_utility_certificate(
            probabilities[label, source],
            channel,
            decoder,
            true_label=label,
            l1_radius=float(radii[label, source]),
            common_fine_token_channels=common,
            contamination=eta,
        ).error_probability
        for label in range(2)
        for source in range(2)
    )
    if not close(utility, result["certified_worst_conditional_error"]):
        failures.append("utility certificate mismatch")

    privacy_threshold = float(protocol["privacy_advantage_threshold"])
    utility_threshold = float(protocol["maximum_worst_conditional_error"])
    deployed = utility <= utility_threshold + 1e-10 and max(privacy) <= privacy_threshold + 1e-10
    if deployed is not bool(result["deployed"]):
        failures.append("deployment decision mismatch")

    external = replay_external(
        np.asarray(result["external_token_counts"], dtype=np.int64),
        channel,
        decoder,
    )
    if external["estimable"] is not bool(result["external_estimable"]):
        failures.append("external estimability mismatch")
    if not close(
        external["worst_privacy_advantage"],
        result["external_worst_privacy_advantage"],
    ):
        failures.append("external privacy mismatch")
    if not close(
        external["worst_conditional_error"],
        result["external_worst_conditional_error"],
    ):
        failures.append("external utility mismatch")
    external_safe = bool(
        external["estimable"]
        and float(external["worst_privacy_advantage"]) <= privacy_threshold + 1e-10
        and float(external["worst_conditional_error"]) <= utility_threshold + 1e-10
    )
    if external_safe is not bool(result["external_safe"]):
        failures.append("external safety mismatch")
    if bool(deployed and external["estimable"] and not external_safe) is not bool(
        result["false_acceptance"]
    ):
        failures.append("false-acceptance mismatch")
    return failures, {
        "candidate": result["candidate"],
        "certified_error": utility,
        "certified_privacy_advantages": privacy,
        "deployed": deployed,
        "external": external,
    }


def audit_file(path: Path) -> tuple[list[str], dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    failures: list[str] = []
    results = payload.get("results", [])
    registered_count = int(payload["protocol"]["frontier_candidate_count"])
    if payload.get("smoke") is True:
        if not 0 < len(results) <= registered_count:
            failures.append("invalid reduced smoke frontier size")
    elif len(results) != registered_count:
        failures.append("frontier candidate count mismatch")
    replayed = []
    for result in results:
        if "optimization_error" in result:
            failures.append(f"{result['candidate']}: optimization failed")
            continue
        candidate_failures, replay = replay_candidate(result, payload["protocol"])
        failures.extend(f"{result['candidate']}: {value}" for value in candidate_failures)
        replayed.append(replay)
    expected_selection = select_certified_result(results)
    if payload.get("selection") != expected_selection:
        failures.append("frontier selection mismatch")
    return failures, {
        "path": str(path),
        "sha256": sha256(path),
        "dataset": payload.get("dataset"),
        "seed": payload.get("seed"),
        "candidate_rows_replayed": len(replayed),
        "selection": expected_selection,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    failures: list[str] = []
    files = []
    for path in args.inputs:
        file_failures, summary = audit_file(path)
        failures.extend(f"{path.name}: {value}" for value in file_failures)
        files.append(summary)
    report: dict[str, object] = {
        "name": "MOSAIC real-frontier independent receipt replay",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not failures,
        "tolerance": TOLERANCE,
        "files_replayed": len(files),
        "candidate_rows_replayed": sum(
            int(value["candidate_rows_replayed"]) for value in files
        ),
        "failures": failures,
        "files": files,
    }
    if args.output:
        atomic_json_dump(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
