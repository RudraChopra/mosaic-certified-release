#!/usr/bin/env python3
"""Decompose every real MOSAIC release into sampling and residual-shift terms."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from statistics import median
from typing import Any

import numpy as np

from mosaic_transform_exact import (
    transform_exact_attacker_confidence_bound,
    transform_exact_utility_confidence_bound,
)
from run_mosaic_local_dp_baseline import (
    LOCK as LOCAL_DP_LOCK,
    ROOT,
    acs_jobs,
    biasbios_jobs,
    load,
    sha256,
)


LOCK = ROOT / "research/mosaic/prereg_mosaic_residual_sharpness_v1.json"
OUTPUT = ROOT / "research/artifacts/mosaic_residual_sharpness_v1.json"


def expected_protocol() -> dict[str, Any]:
    return {
        "jobs": (
            "all 35 frozen primary MOSAIC deployments from BiasBios-Clinical "
            "and ACS-geographic"
        ),
        "modes": {
            "full": "registered radii and registered residual budgets",
            "zero_radius": "zero radii and registered residual budgets",
            "zero_residual": "registered radii and zero residual budgets",
            "population_common": "zero radii and zero residual budgets",
        },
        "estimands": [
            "exact bridge-class source-advantage upper bound",
            "exact bridge-class worst conditional task-error upper bound",
        ],
        "primary_comparison": (
            "full minus zero_radius is the removable finite-sample increment; "
            "zero_radius minus population_common is the infinite-sample "
            "residual-shift increment"
        ),
        "design_case": (
            "BiasBios seed 1200 was inspected while designing this analysis; "
            "the remaining 34 jobs form the untouched deterministic census"
        ),
    }


def validate_lock(path: Path) -> dict[str, Any]:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").split()[0] != sha256(path):
        raise ValueError("residual-sharpness lock sidecar mismatch")
    lock = load(path)
    if lock.get("status") != "locked_before_residual_census":
        raise ValueError("residual-sharpness lock has the wrong status")
    if lock.get("protocol") != expected_protocol():
        raise ValueError("residual-sharpness protocol differs from its lock")
    for relative, expected in lock["code_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f"locked code mismatch: {relative}")
    for relative, expected in lock["input_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f"locked input mismatch: {relative}")
    for local in (path, sidecar):
        relative = local.resolve().relative_to(ROOT.resolve())
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative.as_posix()}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed != local.read_bytes():
            raise ValueError(f"{relative} is not the committed lock")
    return lock


def release_for_job(job: dict[str, Any]) -> tuple[np.ndarray, tuple[int, ...], float, float]:
    payload = load(ROOT / job["inputs"][0])
    candidate = job["candidate"]
    if job["domain"] == "BiasBios-Clinical":
        row = next(
            value for value in payload["results"]
            if value["candidate"] == candidate
        )
        release = row["release_l2"]
    else:
        row = next(
            value for value in payload["alphabets"]["4"]["rows"]
            if value["candidate"] == candidate
        )
        release = row["mosaic_release"]
    diagnostic = release["diagnostic"]
    return (
        np.asarray(release["release_channel"], dtype=np.float64),
        tuple(int(value) for value in release["decoder"]),
        float(diagnostic["worst_privacy_advantage"]),
        float(diagnostic["worst_conditional_error"]),
    )


def exact_bounds(
    *,
    probabilities: np.ndarray,
    radii: np.ndarray,
    bridge: dict[str, Any],
    channel: np.ndarray,
    decoder: tuple[int, ...],
    zero_residual: bool,
) -> dict[str, float]:
    privacy = []
    utility = []
    for label, certificate in enumerate(bridge["labels"]):
        contamination = (
            0.0 if zero_residual else float(certificate["contamination"])
        )
        transforms = (certificate["transform"],)
        privacy.append(
            transform_exact_attacker_confidence_bound(
                probabilities[label],
                channel,
                l1_radii=radii[label],
                common_fine_token_channels=transforms,
                contamination=contamination,
            ).normalized_advantage
        )
        for source in range(probabilities.shape[1]):
            utility.append(
                transform_exact_utility_confidence_bound(
                    probabilities[label, source],
                    channel,
                    decoder,
                    true_label=label,
                    l1_radius=float(radii[label, source]),
                    common_fine_token_channels=transforms,
                    contamination=contamination,
                ).error_probability
            )
    return {
        "source_advantage_upper": float(max(privacy)),
        "worst_conditional_error_upper": float(max(utility)),
    }


def decompose_job(job: dict[str, Any]) -> dict[str, Any]:
    counts = np.asarray(job.pop("reference_counts"), dtype=np.int64)
    radii = np.asarray(job.pop("reference_radii"), dtype=np.float64)
    bridge = job.pop("bridge")
    job.pop("mosaic_error")
    probabilities = counts / counts.sum(axis=2, keepdims=True)
    channel, decoder, diagnostic_source, diagnostic_utility = release_for_job(job)
    modes = {
        "full": exact_bounds(
            probabilities=probabilities,
            radii=radii,
            bridge=bridge,
            channel=channel,
            decoder=decoder,
            zero_residual=False,
        ),
        "zero_radius": exact_bounds(
            probabilities=probabilities,
            radii=np.zeros_like(radii),
            bridge=bridge,
            channel=channel,
            decoder=decoder,
            zero_residual=False,
        ),
        "zero_residual": exact_bounds(
            probabilities=probabilities,
            radii=radii,
            bridge=bridge,
            channel=channel,
            decoder=decoder,
            zero_residual=True,
        ),
        "population_common": exact_bounds(
            probabilities=probabilities,
            radii=np.zeros_like(radii),
            bridge=bridge,
            channel=channel,
            decoder=decoder,
            zero_residual=True,
        ),
    }
    decomposition = {}
    for metric in (
        "source_advantage_upper",
        "worst_conditional_error_upper",
    ):
        decomposition[metric] = {
            "finite_sample_increment": (
                modes["full"][metric] - modes["zero_radius"][metric]
            ),
            "residual_shift_increment_at_population": (
                modes["zero_radius"][metric]
                - modes["population_common"][metric]
            ),
            "total_minus_zero_residual": (
                modes["full"][metric] - modes["zero_residual"][metric]
            ),
        }
    return {
        **job,
        "modes": modes,
        "decomposition": decomposition,
        "held_out_diagnostic": {
            "source_advantage": diagnostic_source,
            "worst_conditional_error": diagnostic_utility,
        },
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
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
    confirmatory = [
        row for row in rows
        if not (
            row["domain"] == "BiasBios-Clinical"
            and int(row["seed"]) == 1200
        )
    ]
    return {
        "jobs": len(rows),
        "untouched_census_jobs": len(confirmatory),
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
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    lock = validate_lock(args.lock)
    jobs = biasbios_jobs() + acs_jobs()
    if len(jobs) != 35:
        raise RuntimeError(f"expected 35 frozen deployments, found {len(jobs)}")
    rows = [decompose_job(job) for job in jobs]
    payload = {
        "name": "MOSAIC residual-sharpness census v1",
        "status": "complete_locked_residual_census",
        "lock_sha256": sha256(args.lock),
        "protocol": expected_protocol(),
        "rows": rows,
        "summary": summarize(rows),
        "claim_boundary": lock["claim_boundary"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
