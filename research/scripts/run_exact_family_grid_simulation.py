"""Run the locked VERA coverage grid over n, candidate count, groups, and delta."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import beta


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PREREG = ROOT / "prereg_exact_family_grid.json"
DEFAULT_HASH = ROOT / "prereg_exact_family_grid.sha256"
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_exact_family_grid_report.json"


@dataclass(frozen=True)
class Cell:
    validation_size: int
    candidate_count: int
    environment_count: int
    delta: float
    gamma: float
    replicates: int
    n_per_environment: int
    n_per_source_class: int
    unsafe_candidate_count: int
    false_acceptances: int
    false_acceptance_rate: float
    false_acceptance_cp95_upper_simultaneous: float
    abstentions: int
    abstention_rate: float
    coverage_pass: bool


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def upper_cp(successes: np.ndarray | int, trials: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    output = np.ones(values.shape, dtype=np.float64)
    mask = values < trials
    output[mask] = beta.ppf(1.0 - alpha, values[mask] + 1, trials - values[mask])
    return output


def lower_cp(successes: np.ndarray | int, trials: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    output = np.zeros(values.shape, dtype=np.float64)
    mask = values > 0
    output[mask] = beta.ppf(alpha, values[mask], trials - values[mask] + 1)
    return output


def robust_paired(
    positive_probability: np.ndarray,
    negative_probability: np.ndarray,
    gamma: float,
) -> np.ndarray:
    positive = np.minimum(positive_probability, 1.0 - negative_probability)
    zero = np.maximum(0.0, 1.0 - positive - negative_probability)
    shifted_positive = np.minimum(1.0, gamma * positive)
    remainder = 1.0 - shifted_positive
    shifted_zero = np.minimum(remainder, gamma * zero)
    return shifted_positive - np.maximum(0.0, remainder - shifted_zero)


def environment_offsets(environment_count: int) -> np.ndarray:
    if environment_count == 1:
        return np.asarray([0.0])
    return np.linspace(-0.005, 0.005, environment_count)


def probability_arrays(
    config: dict[str, Any], candidate_count: int, environment_count: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    target_base = np.asarray(
        config["candidate_target_positive_probabilities"][:candidate_count],
        dtype=np.float64,
    )
    target = target_base[:, None] + environment_offsets(environment_count)[None, :]
    identity_index = int(config["identity_candidate_index"])
    if identity_index < candidate_count:
        target[identity_index] = 0.0
    target_negative = np.asarray(
        config["candidate_target_negative_probabilities"][:candidate_count],
        dtype=np.float64,
    )
    leakage = np.asarray(
        config["candidate_balanced_leakage_probabilities"][:candidate_count],
        dtype=np.float64,
    )[:, None, None]
    leakage = leakage + np.asarray(
        config["attacker_probability_offsets"], dtype=np.float64
    )[None, :, None]
    leakage = leakage + np.asarray(
        config["class_recall_offsets"], dtype=np.float64
    )[None, None, :]
    if target.shape != (candidate_count, environment_count):
        raise ValueError("target probability grid has the wrong shape")
    if leakage.shape != (candidate_count, int(config["attacker_count"]), 2):
        raise ValueError("leakage probability grid has the wrong shape")
    if np.any(target < 0.0) or np.any(target >= 1.0):
        raise ValueError("target probabilities must be inside [0, 1)")
    if np.any(target_negative < 0.0) or np.any(
        target + target_negative[:, None] >= 1.0
    ):
        raise ValueError("paired target probabilities leave the simplex")
    if np.any(leakage <= 0.0) or np.any(leakage >= 1.0):
        raise ValueError("leakage probabilities must be inside (0, 1)")
    return target, target_negative, leakage


def run_cell(
    payload: tuple[dict[str, Any], int, int, int, float, int]
) -> Cell:
    config, n, candidate_count, environment_count, delta, seed = payload
    rng = np.random.default_rng(seed)
    replicates = int(config["replicates"])
    gamma = float(config["gamma"])
    target, target_negative, leakage = probability_arrays(
        config, candidate_count, environment_count
    )
    n_environment = n // environment_count
    n_source_class = n // 2
    candidate_alpha = delta / candidate_count

    target_counts = np.empty(
        (replicates, candidate_count, environment_count, 3), dtype=np.int64
    )
    for candidate in range(candidate_count):
        for environment in range(environment_count):
            positive_probability = float(target[candidate, environment])
            negative_probability = float(target_negative[candidate])
            target_counts[:, candidate, environment] = rng.multinomial(
                n_environment,
                [
                    negative_probability,
                    1.0 - positive_probability - negative_probability,
                    positive_probability,
                ],
                size=replicates,
            )
    target_upper = robust_paired(
        upper_cp(target_counts[:, :, :, 2], n_environment, candidate_alpha / 2.0),
        lower_cp(target_counts[:, :, :, 0], n_environment, candidate_alpha / 2.0),
        gamma,
    )

    leakage_counts = rng.binomial(
        n_source_class,
        leakage,
        size=(replicates, candidate_count, int(config["attacker_count"]), 2),
    )
    class_upper = np.minimum(
        1.0,
        gamma
        * upper_cp(leakage_counts, n_source_class, candidate_alpha / 2.0),
    )
    balanced_upper = np.mean(class_upper, axis=3)
    accepted = np.all(
        target_upper <= float(config["target_threshold"]), axis=2
    ) & np.all(
        balanced_upper <= float(config["leakage_threshold"]), axis=2
    )
    deployed = np.any(accepted, axis=1)
    selected = np.argmax(accepted, axis=1)

    true_target = np.max(
        robust_paired(
            target,
            np.broadcast_to(target_negative[:, None], target.shape),
            gamma,
        ),
        axis=1,
    )
    true_leakage = np.max(
        np.mean(np.minimum(1.0, gamma * leakage), axis=2), axis=1
    )
    unsafe = (true_target > float(config["target_threshold"])) | (
        true_leakage > float(config["leakage_threshold"])
    )
    false_acceptances = int(np.count_nonzero(deployed & unsafe[selected]))
    abstentions = int(np.count_nonzero(~deployed))
    simultaneous_alpha = 0.05 / int(config["cell_count"])
    false_upper = float(upper_cp(false_acceptances, replicates, simultaneous_alpha))
    return Cell(
        validation_size=n,
        candidate_count=candidate_count,
        environment_count=environment_count,
        delta=delta,
        gamma=gamma,
        replicates=replicates,
        n_per_environment=n_environment,
        n_per_source_class=n_source_class,
        unsafe_candidate_count=int(np.count_nonzero(unsafe)),
        false_acceptances=false_acceptances,
        false_acceptance_rate=false_acceptances / replicates,
        false_acceptance_cp95_upper_simultaneous=false_upper,
        abstentions=abstentions,
        abstention_rate=abstentions / replicates,
        coverage_pass=false_upper <= delta,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
    config = prereg["study"]
    prereg_hash = file_sha256(args.prereg)
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    if prereg_hash != expected_hash:
        raise RuntimeError("family-grid preregistration hash mismatch")
    relative = args.prereg.resolve().relative_to(REPOSITORY.resolve()).as_posix()
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    ).stdout
    if hashlib.sha256(committed).hexdigest() != prereg_hash:
        raise RuntimeError("family-grid preregistration is not committed at HEAD")

    cells = [
        (int(n), int(candidate_count), int(environment_count), float(delta))
        for n in config["validation_sizes"]
        for candidate_count in config["candidate_counts"]
        for environment_count in config["environment_counts"]
        for delta in config["delta_levels"]
    ]
    if len(cells) != int(config["cell_count"]):
        raise RuntimeError("registered family-grid cell count is inconsistent")
    payloads = [
        (
            config,
            n,
            candidate_count,
            environment_count,
            delta,
            int(config["seed"]) + 1009 * index,
        )
        for index, (n, candidate_count, environment_count, delta) in enumerate(cells)
    ]
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        results = list(executor.map(run_cell, payloads))
    all_cells_pass = all(
        cell.coverage_pass and cell.unsafe_candidate_count > 0 for cell in results
    )
    report = {
        "name": "VERA exact candidate-family and group-count coverage grid",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "claim_grade": True,
        "prereg_sha256": prereg_hash,
        "git_commit": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "config": config,
        "candidate_counts_tested": sorted({cell.candidate_count for cell in results}),
        "group_counts_tested": sorted({cell.environment_count for cell in results}),
        "cells": [asdict(cell) for cell in results],
        "cell_count": len(results),
        "total_replicates": sum(cell.replicates for cell in results),
        "false_acceptance_count": sum(cell.false_acceptances for cell in results),
        "coverage_pass": all(cell.coverage_pass for cell in results),
        "all_cells_have_unsafe_candidate": all(
            cell.unsafe_candidate_count > 0 for cell in results
        ),
        "all_cells_pass": all_cells_pass,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "all_cells_pass": all_cells_pass,
                "cell_count": len(results),
                "false_acceptance_count": report["false_acceptance_count"],
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0 if all_cells_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
