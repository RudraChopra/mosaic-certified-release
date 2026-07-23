#!/usr/bin/env python3
"""Run the locked MOSAIC released-alphabet constraint-generation study."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np

from mosaic_envelope import weissman_l1_radius
from mosaic_transform_exact_optimizer import optimize_transform_exact_channel
from run_mosaic_scaling_study import population_table, sampled_table


ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research/mosaic/prereg_mosaic_large_release_scaling_v1.json"
DEFAULT_OUTPUT = ROOT / "research/artifacts/mosaic_large_release_scaling_v1.json"
DEFAULT_AUDIT = (
    ROOT / "research/artifacts/mosaic_large_release_scaling_v1_audit.json"
)
POINTS = {4: (2, 4, 8), 2: (2, 4, 8, 16)}
SEEDS = (4300, 4301, 4302)
TOKEN_COUNT = 16
LABEL_COUNT = 2
SAMPLE_SIZE = 2_000
FAILURE_PROBABILITY = 0.05
PRIVACY_THRESHOLD = 0.35
UTILITY_THRESHOLD = 0.40
CONTAMINATION = 0.05
TIME_LIMIT_SECONDS = 120.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def solve(source_count: int, released_count: int, seed: int) -> dict[str, Any]:
    delta = FAILURE_PROBABILITY / (LABEL_COUNT * source_count)
    radius = weissman_l1_radius(SAMPLE_SIZE, TOKEN_COUNT, delta)
    population = population_table(TOKEN_COUNT, source_count)
    empirical = sampled_table(population, SAMPLE_SIZE, seed)
    decoder = tuple(
        [0] * (released_count // 2) + [1] * (released_count // 2)
    )
    started = perf_counter()
    try:
        solution = optimize_transform_exact_channel(
            empirical,
            l1_radii=np.full((LABEL_COUNT, source_count), radius),
            common_channels_by_label=(
                (np.eye(TOKEN_COUNT),),
                (np.eye(TOKEN_COUNT),),
            ),
            contaminations=(CONTAMINATION, CONTAMINATION),
            privacy_advantage_thresholds=(
                PRIVACY_THRESHOLD,
                PRIVACY_THRESHOLD,
            ),
            released_token_count=released_count,
            decoder_candidates=(decoder,),
            solver_time_limit_seconds=TIME_LIMIT_SECONDS,
            attacker_constraint_generation=True,
        )
    except Exception as error:
        return {
            "source_count": source_count,
            "released_token_count": released_count,
            "seed": seed,
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
            "wall_clock_seconds": perf_counter() - started,
            "full_attacker_assignments": source_count**released_count,
        }
    privacy = max(
        certificate.normalized_advantage
        for certificate in solution.privacy_certificates
    )
    error = solution.certified_worst_conditional_error
    return {
        "source_count": source_count,
        "released_token_count": released_count,
        "seed": seed,
        "status": "solved",
        "sample_size_per_stratum": SAMPLE_SIZE,
        "l1_radius": radius,
        "wall_clock_seconds": perf_counter() - started,
        "full_attacker_assignments": source_count**released_count,
        "active_attacker_assignments": solution.active_attacker_assignments,
        "constraint_generation_iterations": (
            solution.constraint_generation_iterations
        ),
        "certified_source_advantage": privacy,
        "certified_worst_stratum_error": error,
        "retained": error <= UTILITY_THRESHOLD + 1e-10,
        "solver_status": solution.solver_status,
        "max_constraint_violation": solution.max_constraint_violation,
    }


def summarize(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for source_count, released_counts in POINTS.items():
        for released_count in released_counts:
            cell = [
                row
                for row in rows
                if row["source_count"] == source_count
                and row["released_token_count"] == released_count
            ]
            solved = [row for row in cell if row["status"] == "solved"]
            output.append(
                {
                    "source_count": source_count,
                    "released_token_count": released_count,
                    "jobs": len(cell),
                    "solved": len(solved),
                    "retention_rate": (
                        float(np.mean([row["retained"] for row in solved]))
                        if solved
                        else None
                    ),
                    "wall_clock_seconds_median": (
                        float(np.median(
                            [row["wall_clock_seconds"] for row in solved]
                        ))
                        if solved
                        else None
                    ),
                    "wall_clock_seconds_max": (
                        float(np.max(
                            [row["wall_clock_seconds"] for row in solved]
                        ))
                        if solved
                        else None
                    ),
                    "active_attacker_assignments_max": (
                        max(
                            row["active_attacker_assignments"]
                            for row in solved
                        )
                        if solved
                        else None
                    ),
                    "full_attacker_assignments": source_count**released_count,
                    "certified_worst_error_median": (
                        float(np.median(
                            [
                                row["certified_worst_stratum_error"]
                                for row in solved
                            ]
                        ))
                        if solved
                        else None
                    ),
                }
            )
    return output


def audit(payload: dict[str, Any]) -> dict[str, Any]:
    rows = payload["rows"]
    solved_l8 = [
        row
        for row in rows
        if row["released_token_count"] == 8 and row["status"] == "solved"
    ]
    solved_l16 = [
        row
        for row in rows
        if row["released_token_count"] == 16 and row["status"] == "solved"
    ]
    checks = {
        "all_21_jobs_reported": len(rows) == 21,
        "at_least_one_L8_job_solved": bool(solved_l8),
        "at_least_one_L16_job_solved": bool(solved_l16),
        "all_rows_have_status": all("status" in row for row in rows),
        "solved_rows_have_finite_bounds": all(
            np.isfinite(row["certified_source_advantage"])
            and np.isfinite(row["certified_worst_stratum_error"])
            for row in rows
            if row["status"] == "solved"
        ),
        "constraint_generation_is_exactly_rechecked": all(
            row["certified_source_advantage"] <= PRIVACY_THRESHOLD + 1e-8
            for row in rows
            if row["status"] == "solved"
        ),
    }
    return {
        "name": "MOSAIC large released-alphabet scaling v1 audit",
        "checks": checks,
        "passed": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--audit-output", type=Path, default=DEFAULT_AUDIT)
    arguments = parser.parse_args()
    rows = [
        solve(source_count, released_count, seed)
        for source_count, released_counts in POINTS.items()
        for released_count in released_counts
        for seed in SEEDS
    ]
    payload = {
        "name": "MOSAIC large released-alphabet scaling v1",
        "status": "executed after preregistration lock",
        "claim_boundary": (
            "Synthetic finite-token tables isolate optimization and "
            "certification scaling. They do not establish natural-shift "
            "frequency, real feature quality, or production latency."
        ),
        "preregistration": str(PREREG.relative_to(ROOT)),
        "preregistration_sha256": sha256(PREREG),
        "settings": {
            "fine_token_count": TOKEN_COUNT,
            "label_count": LABEL_COUNT,
            "points": POINTS,
            "seeds": SEEDS,
            "sample_size_per_stratum": SAMPLE_SIZE,
            "failure_probability": FAILURE_PROBABILITY,
            "privacy_threshold": PRIVACY_THRESHOLD,
            "utility_threshold": UTILITY_THRESHOLD,
            "contamination": CONTAMINATION,
            "time_limit_seconds": TIME_LIMIT_SECONDS,
        },
        "summary": summarize(rows),
        "rows": rows,
    }
    report = audit(payload)
    payload["audit"] = report
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    arguments.audit_output.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(
        {
            "output": str(arguments.output),
            "audit_output": str(arguments.audit_output),
            "audit": report,
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
