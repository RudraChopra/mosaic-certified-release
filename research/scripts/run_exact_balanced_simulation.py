"""Run the preregistered exact balanced-leakage VERA simulation."""

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
from scipy.stats import beta, binom


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PREREG = ROOT / "prereg_confirmatory_balanced.json"
DEFAULT_HASH = ROOT / "prereg_confirmatory_balanced.sha256"
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_exact_balanced_report.json"


@dataclass(frozen=True)
class Cell:
    n: int
    n_per_environment: int
    n_per_source_class: int
    delta: float
    gamma: float
    replicates: int
    unsafe_candidate_count: int
    false_acceptances: int
    abstentions: int
    false_acceptance_rate: float
    false_acceptance_cp95_upper_simultaneous: float
    observed_abstention: float
    predicted_abstention: float
    prediction_band_lower: float
    prediction_band_upper: float
    coverage_pass: bool
    overlay_pass: bool


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cp_upper(successes: np.ndarray | int, n: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    output = np.ones(values.shape, dtype=np.float64)
    mask = values < n
    output[mask] = beta.ppf(1.0 - alpha, values[mask] + 1, n - values[mask])
    return output


def cp_lower(successes: np.ndarray | int, n: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    output = np.zeros(values.shape, dtype=np.float64)
    mask = values > 0
    output[mask] = beta.ppf(alpha, values[mask], n - values[mask] + 1)
    return output


def robust_paired(
    positive: np.ndarray, negative: np.ndarray, gamma: float
) -> np.ndarray:
    bounded_positive = np.minimum(positive, 1.0 - negative)
    zero = np.maximum(0.0, 1.0 - bounded_positive - negative)
    shifted_positive = np.minimum(1.0, gamma * bounded_positive)
    remainder = 1.0 - shifted_positive
    shifted_zero = np.minimum(remainder, gamma * zero)
    return shifted_positive - np.maximum(0.0, remainder - shifted_zero)


def exact_target_pass_probability(
    n: int,
    positive_probability: float,
    negative_probability: float,
    *,
    gamma: float,
    threshold: float,
    candidate_alpha: float,
) -> float:
    positive_counts = np.arange(n + 1)
    positive_upper = cp_upper(positive_counts, n, candidate_alpha / 2.0)
    negative_lower = cp_lower(np.arange(n + 1), n, candidate_alpha / 2.0)
    conditional_negative = negative_probability / max(
        1e-15, 1.0 - positive_probability
    )
    probability = 0.0
    for positive_count, positive_mass in enumerate(
        binom.pmf(positive_counts, n, positive_probability)
    ):
        remaining = n - positive_count
        low, high = 0, remaining + 1
        while low < high:
            midpoint = (low + high) // 2
            bound = robust_paired(
                np.asarray([positive_upper[positive_count]]),
                np.asarray([negative_lower[midpoint]]),
                gamma,
            )[0]
            if bound <= threshold:
                high = midpoint
            else:
                low = midpoint + 1
        if low <= remaining:
            probability += float(positive_mass) * float(
                binom.sf(low - 1, remaining, conditional_negative)
            )
    return float(np.clip(probability, 0.0, 1.0))


def exact_balanced_pass_probability(
    n_per_class: int,
    class_probabilities: tuple[float, float],
    *,
    gamma: float,
    threshold: float,
    candidate_alpha: float,
) -> float:
    counts = np.arange(n_per_class + 1)
    class_upper = np.minimum(
        1.0,
        gamma * cp_upper(counts, n_per_class, candidate_alpha / 2.0),
    )
    probability = 0.0
    second_probability = float(class_probabilities[1])
    for first_count, first_mass in enumerate(
        binom.pmf(counts, n_per_class, float(class_probabilities[0]))
    ):
        remaining_bound = 2.0 * threshold - class_upper[first_count]
        passing = np.flatnonzero(class_upper <= remaining_bound + 1e-15)
        if passing.size:
            probability += float(first_mass) * float(
                binom.cdf(int(passing[-1]), n_per_class, second_probability)
            )
    return float(np.clip(probability, 0.0, 1.0))


def probability_arrays(config: dict[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    target = np.asarray(
        config["candidate_target_positive_probabilities"], dtype=np.float64
    )[:, None] + np.asarray(
        config["environment_target_positive_offsets"], dtype=np.float64
    )[None, :]
    leakage = np.asarray(
        config["candidate_balanced_leakage_probabilities"], dtype=np.float64
    )[:, None, None]
    leakage = leakage + np.asarray(
        config["attacker_probability_offsets"], dtype=np.float64
    )[None, :, None]
    leakage = leakage + np.asarray(
        config["class_recall_offsets"], dtype=np.float64
    )[None, None, :]
    if np.any(target <= 0.0) or np.any(target >= 1.0):
        raise ValueError("target probabilities leave (0, 1)")
    if np.any(leakage <= 0.0) or np.any(leakage >= 1.0):
        raise ValueError("leakage probabilities leave (0, 1)")
    return target, leakage


def predicted_abstention(
    config: dict[str, Any], n: int, delta: float, gamma: float
) -> float:
    target, leakage = probability_arrays(config)
    candidate_count, environment_count = target.shape
    attacker_count = leakage.shape[1]
    n_environment = n // environment_count
    n_source = n // 2
    candidate_alpha = delta / candidate_count
    candidate_passes = []
    for candidate in range(candidate_count):
        target_pass = np.prod(
            [
                exact_target_pass_probability(
                    n_environment,
                    float(target[candidate, environment]),
                    float(config["target_negative_probability"]),
                    gamma=gamma,
                    threshold=float(config["target_threshold"]),
                    candidate_alpha=candidate_alpha,
                )
                for environment in range(environment_count)
            ]
        )
        leakage_pass = np.prod(
            [
                exact_balanced_pass_probability(
                    n_source,
                    (
                        float(leakage[candidate, attacker, 0]),
                        float(leakage[candidate, attacker, 1]),
                    ),
                    gamma=gamma,
                    threshold=float(config["leakage_threshold"]),
                    candidate_alpha=candidate_alpha,
                )
                for attacker in range(attacker_count)
            ]
        )
        candidate_passes.append(float(target_pass * leakage_pass))
    return float(np.prod([1.0 - probability for probability in candidate_passes]))


def run_cell(payload: tuple[dict[str, Any], int, float, float, int]) -> Cell:
    config, n, delta, gamma, seed = payload
    rng = np.random.default_rng(seed)
    replicates = int(config["replicates"])
    target, leakage = probability_arrays(config)
    candidate_count, environment_count = target.shape
    attacker_count = leakage.shape[1]
    n_environment = n // environment_count
    n_source = n // 2
    candidate_alpha = delta / candidate_count
    target_negative = float(config["target_negative_probability"])

    target_counts = np.empty(
        (replicates, candidate_count, environment_count, 3), dtype=np.int64
    )
    for candidate in range(candidate_count):
        for environment in range(environment_count):
            positive = target[candidate, environment]
            target_counts[:, candidate, environment] = rng.multinomial(
                n_environment,
                [target_negative, 1.0 - positive - target_negative, positive],
                size=replicates,
            )
    target_ucb = robust_paired(
        cp_upper(
            target_counts[:, :, :, 2], n_environment, candidate_alpha / 2.0
        ),
        cp_lower(
            target_counts[:, :, :, 0], n_environment, candidate_alpha / 2.0
        ),
        gamma,
    )
    target_pass = np.all(target_ucb <= float(config["target_threshold"]), axis=2)

    leakage_counts = rng.binomial(
        n_source,
        leakage,
        size=(replicates, candidate_count, attacker_count, 2),
    )
    leakage_ucb = np.minimum(
        1.0,
        gamma
        * cp_upper(leakage_counts, n_source, candidate_alpha / 2.0),
    )
    balanced_ucb = np.mean(leakage_ucb, axis=3)
    leakage_pass = np.all(
        balanced_ucb <= float(config["leakage_threshold"]), axis=2
    )
    accepted = target_pass & leakage_pass
    deployed = np.any(accepted, axis=1)
    selected = np.argmax(accepted, axis=1)

    true_target = np.max(
        robust_paired(
            target,
            np.full_like(target, target_negative),
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

    cell_count = (
        len(config["validation_sizes"])
        * len(config["delta_levels"])
        * len(config["gamma_levels"])
    )
    simultaneous_alpha = 0.05 / cell_count
    false_upper = float(
        cp_upper(false_acceptances, replicates, simultaneous_alpha / 2.0)
    )
    predicted = predicted_abstention(config, n, delta, gamma)
    lower = float(
        binom.ppf(simultaneous_alpha / 2.0, replicates, predicted) / replicates
    )
    upper = float(
        binom.ppf(1.0 - simultaneous_alpha / 2.0, replicates, predicted)
        / replicates
    )
    observed = abstentions / replicates
    return Cell(
        n=n,
        n_per_environment=n_environment,
        n_per_source_class=n_source,
        delta=delta,
        gamma=gamma,
        replicates=replicates,
        unsafe_candidate_count=int(np.count_nonzero(unsafe)),
        false_acceptances=false_acceptances,
        abstentions=abstentions,
        false_acceptance_rate=false_acceptances / replicates,
        false_acceptance_cp95_upper_simultaneous=false_upper,
        observed_abstention=observed,
        predicted_abstention=predicted,
        prediction_band_lower=lower,
        prediction_band_upper=upper,
        coverage_pass=false_upper <= delta,
        overlay_pass=lower <= observed <= upper,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
    prereg_hash = sha256(args.prereg)
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    if prereg_hash != expected_hash:
        raise RuntimeError("balanced simulation preregistration hash mismatch")
    relative = args.prereg.resolve().relative_to(REPOSITORY.resolve()).as_posix()
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    ).stdout
    if hashlib.sha256(committed).hexdigest() != prereg_hash:
        raise RuntimeError("balanced simulation preregistration is not committed at HEAD")
    config = prereg["exact_synthetic_study"]
    cells = [
        (int(n), float(delta), float(gamma))
        for n in config["validation_sizes"]
        for delta in config["delta_levels"]
        for gamma in config["gamma_levels"]
    ]
    payloads = [
        (config, n, delta, gamma, int(config["seed"]) + 1009 * index)
        for index, (n, delta, gamma) in enumerate(cells)
    ]
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        results = list(executor.map(run_cell, payloads))
    report = {
        "name": "VERA exact balanced-leakage synthetic validation",
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
        "cells": [asdict(cell) for cell in results],
        "cell_count": len(results),
        "coverage_pass": all(cell.coverage_pass for cell in results),
        "overlay_pass": all(cell.overlay_pass for cell in results),
        "all_cells_pass": all(
            cell.coverage_pass and cell.overlay_pass for cell in results
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "cell_count": len(results),
                "coverage_pass": report["coverage_pass"],
                "overlay_pass": report["overlay_pass"],
                "output": str(args.output),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
