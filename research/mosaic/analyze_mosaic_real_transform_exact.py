#!/usr/bin/env python3
"""Exploratory transform-exact reanalysis of locked real-feature token tables."""

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

from mosaic_transform_exact_optimizer import optimize_transform_exact_channel
from mosaic_real import ordered_smoothing_library


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_INPUT_DIR = REPOSITORY / "research/artifacts/mosaic_real_confirmation_v1"
DEFAULT_OUTPUT = REPOSITORY / "research/artifacts/mosaic_real_transform_exact_exploratory_v1.json"
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
        raise ValueError("expected nonnegative 2-by-2-by-4 token counts")
    totals = values.sum(axis=2)
    probabilities = np.full(values.shape, 0.25, dtype=np.float64)
    supported = totals > 0
    probabilities[supported] = values[supported] / totals[supported, None]
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
        privacy.append(2.0 * balanced_accuracy - 1.0)
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


def exact_row(
    receipt: dict[str, Any],
    result: dict[str, Any],
    receipt_path: Path,
) -> dict[str, object]:
    protocol = receipt["protocol"]
    empirical, _ = distributions(result["certification_token_counts"])
    radii = np.asarray(result["l1_radii"], dtype=np.float64)
    smoothing = float(protocol["ordered_smoothing"])
    transforms = ordered_smoothing_library(4, smoothing=smoothing)
    eta = float(protocol["contamination"])
    privacy_threshold = float(protocol["privacy_advantage_threshold"])
    utility_threshold = float(protocol["maximum_worst_conditional_error"])
    solution = optimize_transform_exact_channel(
        empirical,
        l1_radii=radii,
        common_channels_by_label=(transforms, transforms),
        contaminations=(eta, eta),
        privacy_advantage_thresholds=(privacy_threshold, privacy_threshold),
        released_token_count=2,
        solver_time_limit_seconds=300.0,
    )
    privacy = [value.normalized_advantage for value in solution.privacy_certificates]
    deployed = bool(
        max(privacy) <= privacy_threshold + 1e-10
        and solution.certified_worst_conditional_error <= utility_threshold + 1e-10
    )
    external = external_diagnostic(
        result["external_token_counts"], solution.release_channel, solution.decoder
    )
    external_safe = bool(
        external["estimable"]
        and float(external["worst_privacy_advantage"]) <= privacy_threshold + 1e-10
        and float(external["worst_conditional_error"]) <= utility_threshold + 1e-10
    )
    fallback_error = float(result["certified_worst_conditional_error"])
    if solution.certified_worst_conditional_error > fallback_error + TOLERANCE:
        raise RuntimeError(f"exact objective exceeds fallback for {result['candidate']}")
    return {
        "receipt": receipt_path.relative_to(REPOSITORY).as_posix(),
        "receipt_sha256": sha256(receipt_path),
        "dataset": receipt["dataset"],
        "seed": int(receipt["seed"]),
        "candidate": result["candidate"],
        "method": result["method"],
        "strength": result["strength"],
        "fallback_certified_error": fallback_error,
        "fallback_deployed": bool(result["deployed"]),
        "exact_certified_error": solution.certified_worst_conditional_error,
        "exact_certified_privacy_advantages": privacy,
        "exact_release_channel": solution.release_channel.tolist(),
        "exact_decoder": list(solution.decoder),
        "exact_deployed": deployed,
        "objective_improvement": fallback_error - solution.certified_worst_conditional_error,
        "crossed_utility_contract": bool(deployed and not result["deployed"]),
        "external_estimable": bool(external["estimable"]),
        "external_worst_privacy_advantage": external["worst_privacy_advantage"],
        "external_worst_conditional_error": external["worst_conditional_error"],
        "external_safe": external_safe,
        "false_acceptance": bool(deployed and external["estimable"] and not external_safe),
        "missing_external_strata": external["missing_strata"],
        "solver_status": solution.solver_status,
        "solver_mip_gap": solution.solver_mip_gap,
        "max_constraint_violation": solution.max_constraint_violation,
    }


def select(rows: list[dict[str, object]], prefix: str) -> dict[str, object]:
    eligible = [row for row in rows if bool(row[f"{prefix}_deployed"])]
    if not eligible:
        return {"decision": "abstain", "candidate": None}
    error_key = f"{prefix}_certified_error"
    chosen = min(eligible, key=lambda row: (float(row[error_key]), str(row["candidate"])))
    selection = {
        "decision": "deploy",
        "candidate": chosen["candidate"],
        "method": chosen["method"],
        "strength": chosen["strength"],
        "certified_worst_conditional_error": chosen[error_key],
    }
    if prefix == "exact":
        selection.update(
            {
                "certified_privacy_advantages": chosen[
                    "exact_certified_privacy_advantages"
                ],
                "external_estimable": chosen["external_estimable"],
                "external_safe": chosen["external_safe"],
                "external_worst_privacy_advantage": chosen[
                    "external_worst_privacy_advantage"
                ],
                "external_worst_conditional_error": chosen[
                    "external_worst_conditional_error"
                ],
                "false_acceptance": chosen["false_acceptance"],
            }
        )
    return selection


def summarize(rows: list[dict[str, object]]) -> dict[str, object]:
    by_job: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_job[(str(row["dataset"]), int(row["seed"]))].append(row)
    jobs = []
    for (dataset, seed), values in sorted(by_job.items()):
        jobs.append(
            {
                "dataset": dataset,
                "seed": seed,
                "fallback_selection": select(values, "fallback"),
                "exact_selection": select(values, "exact"),
                "candidate_count": len(values),
            }
        )
    by_dataset = {}
    for dataset in sorted({str(row["dataset"]) for row in rows}):
        dataset_rows = [row for row in rows if row["dataset"] == dataset]
        dataset_jobs = [job for job in jobs if job["dataset"] == dataset]
        exact_selected = [
            job["exact_selection"]
            for job in dataset_jobs
            if job["exact_selection"]["decision"] == "deploy"
        ]
        by_dataset[dataset] = {
            "candidate_rows": len(dataset_rows),
            "fallback_candidate_deployments": sum(
                bool(row["fallback_deployed"]) for row in dataset_rows
            ),
            "exact_candidate_deployments": sum(
                bool(row["exact_deployed"]) for row in dataset_rows
            ),
            "candidate_contract_crossings": sum(
                bool(row["crossed_utility_contract"]) for row in dataset_rows
            ),
            "fallback_job_deployments": sum(
                job["fallback_selection"]["decision"] == "deploy" for job in dataset_jobs
            ),
            "exact_job_deployments": len(exact_selected),
            "estimable_exact_selections": sum(
                bool(selection["external_estimable"]) for selection in exact_selected
            ),
            "safe_estimable_exact_selections": sum(
                bool(selection["external_estimable"] and selection["external_safe"])
                for selection in exact_selected
            ),
            "false_accepting_exact_selections": sum(
                bool(selection["false_acceptance"]) for selection in exact_selected
            ),
        }
    exact_selected = [
        job["exact_selection"]
        for job in jobs
        if job["exact_selection"]["decision"] == "deploy"
    ]
    return {
        "candidate_rows": len(rows),
        "jobs": jobs,
        "datasets": by_dataset,
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
        "maximum_objective_improvement": max(
            float(row["objective_improvement"]) for row in rows
        ),
        "exact_job_deployments": len(exact_selected),
        "estimable_exact_selections": sum(
            bool(selection["external_estimable"]) for selection in exact_selected
        ),
        "safe_estimable_exact_selections": sum(
            bool(selection["external_estimable"] and selection["external_safe"])
            for selection in exact_selected
        ),
        "false_accepting_exact_selections": sum(
            bool(selection["false_acceptance"]) for selection in exact_selected
        ),
        "pointwise_dominance": all(
            float(row["objective_improvement"]) >= -TOLERANCE for row in rows
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError("refusing to overwrite exploratory analysis")
    paths = sorted(args.input_dir.glob("mosaic_real_confirmation_*_seed*.json"))
    if len(paths) != 25:
        raise RuntimeError(f"expected 25 locked receipts, found {len(paths)}")
    rows = []
    for path in paths:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        if len(receipt.get("results", [])) != 13:
            raise RuntimeError(f"incomplete receipt: {path}")
        for result in receipt["results"]:
            rows.append(exact_row(receipt, result, path))
    summary = summarize(rows)
    payload = {
        "name": "MOSAIC exploratory transform-exact real-feature reanalysis v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "post_outcome_exploratory_not_preregistered",
        "claim_boundary": (
            "This reuses locked real-feature token tables after confirmatory outcomes were "
            "known. It tests exact-certificate behavior but is not a new confirmatory study, "
            "does not establish shift-class membership, and supports no clinical claim."
        ),
        "optimizer": "global_decoder_enumeration_transform_exact_lp",
        "tolerance": TOLERANCE,
        "summary": summary,
        "rows": rows,
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
