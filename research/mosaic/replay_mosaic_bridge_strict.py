#!/usr/bin/env python3
"""Recompute every bridge-confirmation decision with strict numerical guards."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from audit_mosaic_bridge_frontier import diagnostic_from_counts, table_from_counts
from mosaic_real import sha256
from mosaic_strict_certification import (
    DEFAULT_FEASIBILITY_GUARD,
    DEFAULT_OPTIMIZATION_GUARD,
    DEFAULT_VALUE_GUARD,
    StrictReleaseCertificate,
    certify_bridge_membership_strict,
    optimize_transform_exact_channel_strict,
)
from run_mosaic_official_frontier_exact_confirmation import atomic_json_dump


def threshold_key(value: float) -> str:
    return f"{float(value):.2f}"


def serialize_bridge(certificate: object) -> dict[str, object]:
    return {
        "method": certificate.method,
        "retained_masses": list(certificate.retained_masses),
        "contaminations": list(certificate.contaminations),
        "labels": [
            {
                "transform": label.transform.tolist(),
                "retained_mass": label.retained_mass,
                "contamination": label.contamination,
                "optimal_retained_mass_upper": label.optimal_retained_mass_upper,
                "minimum_membership_slack": label.minimum_membership_slack,
                "transform_trace": label.transform_trace,
                "method": label.method,
            }
            for label in certificate.labels
        ],
    }


def serialize_release(
    certificate: StrictReleaseCertificate,
    *,
    diagnostic_counts: object,
    source_threshold: float,
    utility_thresholds: list[float],
) -> dict[str, object]:
    diagnostic = diagnostic_from_counts(
        diagnostic_counts, certificate.release_channel, certificate.decoder
    )
    decisions: dict[str, object] = {}
    for threshold in utility_thresholds:
        key = threshold_key(threshold)
        deployed = bool(
            max(certificate.certified_source_advantage_upper) <= source_threshold
            and certificate.certified_worst_conditional_error_upper <= threshold
        )
        diagnostic_safe = bool(
            diagnostic["estimable"]
            and float(diagnostic["worst_privacy_advantage"]) <= source_threshold
            and float(diagnostic["worst_conditional_error"]) <= threshold
        )
        decisions[key] = {
            "deployed": deployed,
            "diagnostic_safe": diagnostic_safe,
            "false_acceptance": bool(
                deployed and diagnostic["estimable"] and not diagnostic_safe
            ),
        }
    return {
        "method": certificate.method,
        "released_token_count": certificate.release_channel.shape[1],
        "release_channel": certificate.release_channel.tolist(),
        "decoder": list(certificate.decoder),
        "certified_source_advantage_upper": list(
            certificate.certified_source_advantage_upper
        ),
        "certified_worst_conditional_error_upper": (
            certificate.certified_worst_conditional_error_upper
        ),
        "unguarded_source_advantages": list(
            certificate.unguarded_source_advantages
        ),
        "unguarded_worst_conditional_error": (
            certificate.unguarded_worst_conditional_error
        ),
        "optimization_source_thresholds": list(
            certificate.optimization_source_thresholds
        ),
        "solver_objective": certificate.solver_objective,
        "solver_status": certificate.solver_status,
        "solver_mip_gap": certificate.solver_mip_gap,
        "solver_dual_bound": certificate.solver_dual_bound,
        "max_constraint_violation": certificate.max_constraint_violation,
        "solved_decoder_assignments": certificate.solved_decoder_assignments,
        "feasibility_guard": certificate.feasibility_guard,
        "value_guard": certificate.value_guard,
        "diagnostic": diagnostic,
        "threshold_decisions": decisions,
    }


def select_candidate(
    rows: list[dict[str, object]], *, release_key: str, utility_threshold: float
) -> dict[str, object]:
    key = threshold_key(utility_threshold)
    eligible = [
        row
        for row in rows
        if isinstance(row.get(release_key), dict)
        and row[release_key]["threshold_decisions"][key]["deployed"] is True
    ]
    if not eligible:
        return {
            "decision": "abstain",
            "candidate": None,
            "utility_threshold": utility_threshold,
            "reason": "no candidate satisfied the strictly replayed contract",
        }
    selected = min(
        eligible,
        key=lambda row: (
            float(row[release_key]["certified_worst_conditional_error_upper"]),
            str(row["candidate"]),
        ),
    )
    release = selected[release_key]
    decision = release["threshold_decisions"][key]
    return {
        "decision": "deploy",
        "candidate": selected["candidate"],
        "method": selected["method"],
        "strength": selected["strength"],
        "released_token_count": release["released_token_count"],
        "utility_threshold": utility_threshold,
        "certified_worst_conditional_error_upper": release[
            "certified_worst_conditional_error_upper"
        ],
        "certified_source_advantage_upper": release[
            "certified_source_advantage_upper"
        ],
        "bridge_contaminations": selected["bridge_membership"]["contaminations"],
        "diagnostic_estimable": release["diagnostic"]["estimable"],
        "diagnostic_worst_source_advantage": release["diagnostic"][
            "worst_privacy_advantage"
        ],
        "diagnostic_worst_conditional_error": release["diagnostic"][
            "worst_conditional_error"
        ],
        "diagnostic_safe": decision["diagnostic_safe"],
        "false_acceptance": decision["false_acceptance"],
    }


def replay_one(
    original_path: Path,
    output_path: Path,
    *,
    prereg_hash: str,
    amendment_hash: str,
) -> dict[str, object]:
    original = json.loads(original_path.read_text(encoding="utf-8"))
    if original.get("prereg_sha256") != prereg_hash:
        raise ValueError(f"{original_path} has the wrong preregistration hash")
    protocol = original["protocol"]
    token_count = int(protocol["fine_token_count"])
    table_delta = float(protocol["per_candidate_table_delta"])
    source_threshold = float(protocol["privacy_advantage_threshold"])
    utility_thresholds = [float(value) for value in protocol["utility_thresholds"]]
    rows: list[dict[str, object]] = []
    bridge_slacks: list[float] = []
    for original_row in original["results"]:
        row = {
            key: original_row[key]
            for key in ("candidate", "method", "strength", "provenance")
        }
        if "optimization_error" in original_row:
            row["upstream_error"] = original_row["optimization_error"]
            rows.append(row)
            continue
        reference, reference_radii, _ = table_from_counts(
            original_row["reference_token_counts"],
            token_count=token_count,
            familywise_delta=table_delta,
        )
        bridge, bridge_radii, _ = table_from_counts(
            original_row["bridge_token_counts"],
            token_count=token_count,
            familywise_delta=table_delta,
        )
        membership = certify_bridge_membership_strict(
            reference,
            reference_l1_radii=reference_radii,
            bridge_empirical_distributions=bridge,
            bridge_l1_radii=bridge_radii,
            feasibility_guard=DEFAULT_FEASIBILITY_GUARD,
        )
        row["bridge_membership"] = serialize_bridge(membership)
        bridge_slacks.extend(
            float(label.minimum_membership_slack) for label in membership.labels
        )
        release = optimize_transform_exact_channel_strict(
            reference,
            l1_radii=reference_radii,
            common_channels_by_label=membership.transforms_by_label,
            contaminations=membership.contaminations,
            source_advantage_thresholds=(source_threshold, source_threshold),
            released_token_count=int(protocol["primary_released_token_count"]),
            solver_time_limit_seconds=300.0,
        )
        row["release_l2"] = serialize_release(
            release,
            diagnostic_counts=original_row["diagnostic_token_counts"],
            source_threshold=source_threshold,
            utility_thresholds=utility_thresholds,
        )
        row["_reference"] = reference
        row["_reference_radii"] = reference_radii
        row["_membership"] = membership
        row["_diagnostic_counts"] = original_row["diagnostic_token_counts"]
        rows.append(row)

    successful = [row for row in rows if isinstance(row.get("release_l2"), dict)]
    l4_candidate = None
    if successful:
        l4_candidate = min(
            successful,
            key=lambda row: (
                float(row["release_l2"]["certified_worst_conditional_error_upper"]),
                str(row["candidate"]),
            ),
        )
        release = optimize_transform_exact_channel_strict(
            l4_candidate["_reference"],
            l1_radii=l4_candidate["_reference_radii"],
            common_channels_by_label=l4_candidate["_membership"].transforms_by_label,
            contaminations=l4_candidate["_membership"].contaminations,
            source_advantage_thresholds=(source_threshold, source_threshold),
            released_token_count=int(protocol["secondary_released_token_count"]),
            solver_time_limit_seconds=300.0,
        )
        l4_candidate["release_l4"] = serialize_release(
            release,
            diagnostic_counts=l4_candidate["_diagnostic_counts"],
            source_threshold=source_threshold,
            utility_thresholds=utility_thresholds,
        )

    for row in rows:
        for key in tuple(row):
            if key.startswith("_"):
                del row[key]
    selections = {
        threshold_key(threshold): select_candidate(
            rows, release_key="release_l2", utility_threshold=threshold
        )
        for threshold in utility_thresholds
    }
    primary_key = threshold_key(float(protocol["primary_utility_threshold"]))
    payload: dict[str, object] = {
        "project": "MOSAIC strict numerical bridge replay",
        "dataset": original["dataset"],
        "seed": original["seed"],
        "protocol": protocol,
        "original_receipt": str(original_path),
        "original_receipt_sha256": sha256(original_path),
        "preregistration_sha256": prereg_hash,
        "strict_amendment_sha256": amendment_hash,
        "numerical_policy": {
            "bridge_feasibility_guard": DEFAULT_FEASIBILITY_GUARD,
            "release_optimization_guard": DEFAULT_OPTIMIZATION_GUARD,
            "reported_value_guard": DEFAULT_VALUE_GUARD,
            "decision_tolerance": 0.0,
        },
        "minimum_membership_slack": min(bridge_slacks, default=None),
        "results": rows,
        "selection_by_utility_threshold": selections,
        "primary_selection": selections[primary_key],
        "l4_candidate": l4_candidate["candidate"] if l4_candidate else None,
    }
    atomic_json_dump(payload, output_path)
    return {
        "dataset": payload["dataset"],
        "seed": payload["seed"],
        "output": str(output_path),
        "sha256": sha256(output_path),
        "candidate_rows": len(rows),
        "global_optimizations": len(successful) + int(l4_candidate is not None),
        "minimum_membership_slack": payload["minimum_membership_slack"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--prereg", required=True, type=Path)
    parser.add_argument("--amendment", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive")
    prereg_hash = sha256(args.prereg)
    sidecar = args.prereg.with_suffix(args.prereg.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").strip() != prereg_hash:
        raise ValueError("preregistration sidecar mismatch")
    amendment_hash = sha256(args.amendment)
    amendment_sidecar = args.amendment.with_suffix(args.amendment.suffix + ".sha256")
    if amendment_sidecar.read_text(encoding="utf-8").strip() != amendment_hash:
        raise ValueError("strict amendment sidecar mismatch")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object] | None] = [None] * len(args.inputs)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for index, path in enumerate(args.inputs):
            output = args.output_dir / path.name
            if output.exists():
                raise FileExistsError(f"refusing to overwrite {output}")
            future = executor.submit(
                replay_one,
                path,
                output,
                prereg_hash=prereg_hash,
                amendment_hash=amendment_hash,
            )
            futures[future] = index
        for future in as_completed(futures):
            index = futures[future]
            summaries[index] = future.result()
            print(summaries[index]["output"], flush=True)
    files = [summary for summary in summaries if summary is not None]
    manifest = {
        "name": "MOSAIC strict numerical bridge replay manifest",
        "preregistration_sha256": prereg_hash,
        "strict_amendment_sha256": amendment_hash,
        "files": files,
        "file_count": len(files),
        "candidate_rows": sum(int(file["candidate_rows"]) for file in files),
        "global_optimizations": sum(
            int(file["global_optimizations"]) for file in files
        ),
        "minimum_membership_slack": min(
            float(file["minimum_membership_slack"])
            for file in files
            if file["minimum_membership_slack"] is not None
        ),
    }
    atomic_json_dump(manifest, args.manifest)
    print(args.manifest)


if __name__ == "__main__":
    main()
