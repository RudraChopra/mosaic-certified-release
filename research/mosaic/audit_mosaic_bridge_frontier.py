#!/usr/bin/env python3
"""Independent replay audit for MOSAIC's data-certified bridge frontier."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from mosaic_bridge import certify_bridge_membership
from mosaic_channel import (
    l1_ball_expectation_lower,
    l1_ball_expectation_upper,
    normalized_attacker_advantage,
)
from mosaic_envelope import weissman_l1_radius
from mosaic_real import sha256
from mosaic_transform_exact import (
    transform_exact_attacker_confidence_bound,
    transform_exact_utility_confidence_bound,
)
from mosaic_transform_exact_optimizer import optimize_transform_exact_channel


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


def close(first: object, second: object, tolerance: float = TOLERANCE) -> bool:
    if first is None or second is None:
        return first is second
    return abs(float(first) - float(second)) <= tolerance


def table_from_counts(
    values: object, *, token_count: int, familywise_delta: float
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    counts = np.asarray(values, dtype=np.int64)
    if counts.shape != (2, 2, token_count) or np.any(counts < 0):
        raise ValueError("invalid stored token table")
    totals = counts.sum(axis=2)
    probabilities = np.divide(
        counts,
        totals[:, :, None],
        out=np.full_like(counts, 1.0 / token_count, dtype=np.float64),
        where=totals[:, :, None] > 0,
    )
    stratum_delta = familywise_delta / 4.0
    radii = np.asarray(
        [
            [
                2.0
                if totals[label, source] == 0
                else weissman_l1_radius(
                    int(totals[label, source]), token_count, stratum_delta
                )
                for source in range(2)
            ]
            for label in range(2)
        ]
    )
    return probabilities, radii, totals


def diagnostic_from_counts(
    values: object, channel: np.ndarray, decoder: tuple[int, ...]
) -> dict[str, object]:
    counts = np.asarray(values, dtype=np.int64)
    totals = counts.sum(axis=2)
    missing = [
        [label, source]
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
    probabilities = counts / totals[:, :, None]
    privacy = []
    utility = []
    decoder_array = np.asarray(decoder, dtype=np.int64)
    for label in range(2):
        released = probabilities[label] @ channel
        balanced_accuracy = float(np.max(released, axis=0).sum() / 2.0)
        privacy.append(normalized_attacker_advantage(balanced_accuracy, 2))
        loss = (decoder_array != label).astype(np.float64)
        utility.extend(
            float(probabilities[label, source] @ channel @ loss)
            for source in range(2)
        )
    return {
        "estimable": True,
        "worst_privacy_advantage": max(privacy),
        "worst_conditional_error": max(utility),
        "missing_strata": [],
    }


def replay_bridge(
    result: dict[str, object], protocol: dict[str, object]
) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    token_count = int(protocol["fine_token_count"])
    table_delta = float(protocol["per_candidate_table_delta"])
    reference, reference_radii, _ = table_from_counts(
        result["reference_token_counts"],
        token_count=token_count,
        familywise_delta=table_delta,
    )
    bridge, bridge_radii, _ = table_from_counts(
        result["bridge_token_counts"],
        token_count=token_count,
        familywise_delta=table_delta,
    )
    if not np.allclose(
        reference_radii,
        np.asarray(result["reference_l1_radii"]),
        atol=TOLERANCE,
        rtol=0.0,
    ):
        failures.append("reference radius mismatch")
    if not np.allclose(
        bridge_radii,
        np.asarray(result["bridge_l1_radii"]),
        atol=TOLERANCE,
        rtol=0.0,
    ):
        failures.append("bridge radius mismatch")
    certificate = certify_bridge_membership(
        reference,
        reference_l1_radii=reference_radii,
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=bridge_radii,
    )
    stored = result["bridge_membership"]
    if not np.allclose(
        certificate.retained_masses,
        np.asarray(stored["retained_masses"]),
        atol=TOLERANCE,
        rtol=0.0,
    ):
        failures.append("retained-mass mismatch")
    if not np.allclose(
        certificate.contaminations,
        np.asarray(stored["contaminations"]),
        atol=TOLERANCE,
        rtol=0.0,
    ):
        failures.append("contamination mismatch")

    smallest_slack = np.inf
    for label_index, label in enumerate(certificate.labels):
        stored_label = stored["labels"][label_index]
        if not np.allclose(
            label.transform,
            np.asarray(stored_label["transform"]),
            atol=TOLERANCE,
            rtol=0.0,
        ):
            failures.append(f"label {label_index} transform mismatch")
        for source in range(2):
            for output in range(token_count):
                lower = l1_ball_expectation_lower(
                    bridge[label_index, source],
                    np.eye(token_count)[output],
                    l1_radius=float(bridge_radii[label_index, source]),
                )
                upper = l1_ball_expectation_upper(
                    reference[label_index, source],
                    label.transform[:, output],
                    l1_radius=float(reference_radii[label_index, source]),
                )
                slack = lower - label.retained_mass * upper
                smallest_slack = min(smallest_slack, slack)
                if slack < -TOLERANCE:
                    failures.append(
                        f"label {label_index} robust membership violation"
                    )
    return failures, {
        "reference": reference,
        "reference_radii": reference_radii,
        "certificate": certificate,
        "smallest_independent_membership_slack": smallest_slack,
    }


def replay_release(
    stored: dict[str, object],
    *,
    bridge_replay: dict[str, object],
    diagnostic_counts: object,
    protocol: dict[str, object],
) -> tuple[list[str], dict[str, object]]:
    failures: list[str] = []
    reference = bridge_replay["reference"]
    radii = bridge_replay["reference_radii"]
    certificate = bridge_replay["certificate"]
    token_count = int(protocol["fine_token_count"])
    released_count = int(stored["released_token_count"])
    channel = np.asarray(stored["release_channel"], dtype=np.float64)
    decoder = tuple(int(value) for value in stored["decoder"])
    if (
        channel.shape != (token_count, released_count)
        or not np.allclose(channel.sum(axis=1), 1.0, atol=TOLERANCE, rtol=0.0)
        or np.any(channel < -TOLERANCE)
        or np.any(channel > 1.0 + TOLERANCE)
    ):
        failures.append("invalid release channel")
        return failures, {}
    privacy = [
        transform_exact_attacker_confidence_bound(
            reference[label],
            channel,
            l1_radii=radii[label],
            common_fine_token_channels=certificate.transforms_by_label[label],
            contamination=certificate.contaminations[label],
        ).normalized_advantage
        for label in range(2)
    ]
    utility = max(
        transform_exact_utility_confidence_bound(
            reference[label, source],
            channel,
            decoder,
            true_label=label,
            l1_radius=float(radii[label, source]),
            common_fine_token_channels=certificate.transforms_by_label[label],
            contamination=certificate.contaminations[label],
        ).error_probability
        for label in range(2)
        for source in range(2)
    )
    if not np.allclose(
        privacy,
        np.asarray(stored["certified_privacy_advantages"]),
        atol=TOLERANCE,
        rtol=0.0,
    ):
        failures.append("privacy certificate mismatch")
    if not close(utility, stored["certified_worst_conditional_error"]):
        failures.append("utility certificate mismatch")
    optimum = optimize_transform_exact_channel(
        reference,
        l1_radii=radii,
        common_channels_by_label=certificate.transforms_by_label,
        contaminations=certificate.contaminations,
        privacy_advantage_thresholds=(
            float(protocol["privacy_advantage_threshold"]),
            float(protocol["privacy_advantage_threshold"]),
        ),
        released_token_count=released_count,
        solver_time_limit_seconds=300.0,
    )
    if not close(optimum.certified_worst_conditional_error, utility):
        failures.append("global optimum mismatch")
    if not close(stored["solver_objective"], utility):
        failures.append("stored objective mismatch")
    if float(stored["solver_mip_gap"]) > 1e-10:
        failures.append("non-global solver gap")
    if float(stored["max_constraint_violation"]) > TOLERANCE:
        failures.append("solver constraint violation")

    diagnostic = diagnostic_from_counts(diagnostic_counts, channel, decoder)
    if diagnostic["estimable"] is not bool(stored["diagnostic_estimable"]):
        failures.append("diagnostic estimability mismatch")
    if not close(
        diagnostic["worst_privacy_advantage"],
        stored["diagnostic_worst_privacy_advantage"],
    ):
        failures.append("diagnostic privacy mismatch")
    if not close(
        diagnostic["worst_conditional_error"],
        stored["diagnostic_worst_conditional_error"],
    ):
        failures.append("diagnostic utility mismatch")
    if diagnostic["missing_strata"] != stored["missing_diagnostic_strata"]:
        failures.append("diagnostic missing-strata mismatch")

    threshold_decisions: dict[str, object] = {}
    privacy_threshold = float(protocol["privacy_advantage_threshold"])
    for threshold in protocol["utility_thresholds"]:
        key = f"{float(threshold):.2f}"
        deployed = bool(
            max(privacy) <= privacy_threshold + 1e-10
            and utility <= float(threshold) + 1e-10
        )
        safe = bool(
            diagnostic["estimable"]
            and float(diagnostic["worst_privacy_advantage"])
            <= privacy_threshold + 1e-10
            and float(diagnostic["worst_conditional_error"])
            <= float(threshold) + 1e-10
        )
        threshold_decisions[key] = {
            "deployed": deployed,
            "diagnostic_safe": safe,
            "false_acceptance": bool(
                deployed and diagnostic["estimable"] and not safe
            ),
        }
    if threshold_decisions != stored["threshold_decisions"]:
        failures.append("threshold decision mismatch")
    return failures, {
        "certified_error": utility,
        "privacy": privacy,
        "diagnostic": diagnostic,
        "threshold_decisions": threshold_decisions,
        "released_token_count": released_count,
    }


def audit_file(path: Path) -> tuple[list[str], dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    protocol = payload["protocol"]
    failures: list[str] = []
    results = payload.get("results", [])
    expected_count = int(protocol["frontier_candidate_count"])
    if payload.get("smoke") is True:
        if not 0 < len(results) <= expected_count:
            failures.append("invalid smoke candidate count")
    elif len(results) != expected_count:
        failures.append("frontier candidate count mismatch")
    replayed_rows = []
    for result in results:
        if "optimization_error" in result:
            failures.append(f"{result['candidate']}: optimization error")
            continue
        bridge_failures, bridge_replay = replay_bridge(result, protocol)
        failures.extend(
            f"{result['candidate']}: bridge: {value}" for value in bridge_failures
        )
        row: dict[str, object] = {
            "candidate": result["candidate"],
            "bridge_contaminations": list(
                bridge_replay["certificate"].contaminations
            ),
            "smallest_membership_slack": bridge_replay[
                "smallest_independent_membership_slack"
            ],
        }
        for release_key in ("release_l2", "release_l4"):
            if not isinstance(result.get(release_key), dict):
                continue
            release_failures, replay = replay_release(
                result[release_key],
                bridge_replay=bridge_replay,
                diagnostic_counts=result["diagnostic_token_counts"],
                protocol=protocol,
            )
            failures.extend(
                f"{result['candidate']}: {release_key}: {value}"
                for value in release_failures
            )
            row[release_key] = replay
        replayed_rows.append(row)

    successful_l2 = [row for row in replayed_rows if "release_l2" in row]
    expected_l4_candidate = None
    if successful_l2:
        expected_l4_candidate = min(
            successful_l2,
            key=lambda row: (
                float(row["release_l2"]["certified_error"]),
                str(row["candidate"]),
            ),
        )["candidate"]
    observed_l4 = [row["candidate"] for row in replayed_rows if "release_l4" in row]
    if observed_l4 != ([expected_l4_candidate] if expected_l4_candidate else []):
        failures.append("L4 follow-up candidate mismatch")

    selection_summary: dict[str, object] = {}
    for threshold in protocol["utility_thresholds"]:
        key = f"{float(threshold):.2f}"
        eligible = [
            row
            for row in successful_l2
            if row["release_l2"]["threshold_decisions"][key]["deployed"]
        ]
        expected_candidate = None
        if eligible:
            expected_candidate = min(
                eligible,
                key=lambda row: (
                    float(row["release_l2"]["certified_error"]),
                    str(row["candidate"]),
                ),
            )["candidate"]
        stored_selection = payload["selection_by_utility_threshold"][key]
        if stored_selection["candidate"] != expected_candidate:
            failures.append(f"selection mismatch at utility threshold {key}")
        selection_summary[key] = {
            "candidate": expected_candidate,
            "decision": "deploy" if expected_candidate is not None else "abstain",
        }

    return failures, {
        "path": str(path),
        "sha256": sha256(path),
        "dataset": payload.get("dataset"),
        "seed": payload.get("seed"),
        "prereg_sha256": payload.get("prereg_sha256"),
        "candidate_rows_replayed": len(replayed_rows),
        "global_optimization_replays": sum(
            int("release_l2" in row) + int("release_l4" in row)
            for row in replayed_rows
        ),
        "minimum_membership_slack": min(
            (float(row["smallest_membership_slack"]) for row in replayed_rows),
            default=None,
        ),
        "l4_candidate": expected_l4_candidate,
        "selection": selection_summary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--workers", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive")
    failures: list[str] = []
    summaries: list[dict[str, object] | None] = [None] * len(args.inputs)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(audit_file, path): index
            for index, path in enumerate(args.inputs)
        }
        for future in as_completed(futures):
            index = futures[future]
            file_failures, summary = future.result()
            failures.extend(
                f"{args.inputs[index].name}: {value}" for value in file_failures
            )
            summaries[index] = summary
    files = [value for value in summaries if value is not None]
    prereg_hashes = {value["prereg_sha256"] for value in files}
    if len(files) > 1 and len(prereg_hashes) != 1:
        failures.append("receipts do not share one preregistration hash")
    report: dict[str, object] = {
        "name": "MOSAIC data-certified bridge independent replay",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not failures,
        "files_replayed": len(files),
        "candidate_rows_replayed": sum(
            int(value["candidate_rows_replayed"]) for value in files
        ),
        "global_optimization_replays": sum(
            int(value["global_optimization_replays"]) for value in files
        ),
        "minimum_membership_slack": min(
            (
                float(value["minimum_membership_slack"])
                for value in files
                if value["minimum_membership_slack"] is not None
            ),
            default=None,
        ),
        "failures": failures,
        "files": files,
    }
    if args.output is not None:
        atomic_json_dump(report, args.output)
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
