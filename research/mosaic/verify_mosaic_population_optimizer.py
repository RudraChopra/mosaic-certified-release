#!/usr/bin/env python3
"""Falsification checks for the exact population external-risk optimizer."""

from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from mosaic_exact import (
    exact_external_attacker_risk,
    exact_external_utility_risk,
)
from mosaic_optimizer import optimize_population_external_channel


TOLERANCE = 3e-7


def random_probability(rng: np.random.Generator, count: int) -> np.ndarray:
    return rng.dirichlet(np.ones(count, dtype=np.float64))


def random_channel(
    rng: np.random.Generator, rows: int, columns: int
) -> np.ndarray:
    return rng.dirichlet(np.ones(columns, dtype=np.float64), size=rows)


def evaluate(
    population: np.ndarray,
    libraries: tuple[tuple[np.ndarray, ...], ...],
    eta: tuple[float, ...],
    thresholds: tuple[float, ...],
    channel: np.ndarray,
    decoder: tuple[int, ...],
) -> float | None:
    label_count, source_count, _ = population.shape
    privacy = tuple(
        exact_external_attacker_risk(
            population[label],
            channel,
            libraries[label],
            contamination=eta[label],
        )
        for label in range(label_count)
    )
    if any(
        risk.normalized_advantage > thresholds[label] + 1e-9
        for label, risk in enumerate(privacy)
    ):
        return None
    utility = tuple(
        exact_external_utility_risk(
            population[label, source],
            channel,
            decoder,
            true_label=label,
            common_fine_token_channels=libraries[label],
            contamination=eta[label],
        ).error_probability
        for label in range(label_count)
        for source in range(source_count)
    )
    return max(utility)


def brute_grid(
    population: np.ndarray,
    libraries: tuple[tuple[np.ndarray, ...], ...],
    eta: tuple[float, ...],
    thresholds: tuple[float, ...],
    *,
    grid_size: int,
) -> float:
    grid = np.linspace(0.0, 1.0, grid_size)
    best = np.inf
    for first in grid:
        for second in grid:
            channel = np.asarray(
                [[first, 1.0 - first], [second, 1.0 - second]],
                dtype=np.float64,
            )
            for decoder in product(range(2), repeat=2):
                value = evaluate(
                    population,
                    libraries,
                    eta,
                    thresholds,
                    channel,
                    decoder,
                )
                if value is not None:
                    best = min(best, value)
    if not np.isfinite(best):
        raise AssertionError("brute grid omitted the constant feasible channel")
    return float(best)


def run_checks(
    *, rng: np.random.Generator, repetitions: int, grid_size: int
) -> dict[str, int | float]:
    grid_checks = 0
    objective_checks = 0
    privacy_checks = 0
    worst_objective_gap = 0.0
    largest_lp_minus_grid = 0.0

    for _ in range(repetitions):
        population = np.stack(
            [
                np.stack([random_probability(rng, 2) for _ in range(2)])
                for _ in range(2)
            ]
        )
        identity = np.eye(2)
        common = random_channel(rng, 2, 2)
        libraries = ((identity, common), (identity, common))
        eta = tuple(float(value) for value in rng.uniform(0.0, 0.35, size=2))
        thresholds = tuple(
            float(value) for value in rng.uniform(0.05, 0.9, size=2)
        )
        solution = optimize_population_external_channel(
            population,
            common_channels_by_label=libraries,
            contaminations=eta,
            privacy_advantage_thresholds=thresholds,
            released_token_count=2,
        )
        grid_optimum = brute_grid(
            population,
            libraries,
            eta,
            thresholds,
            grid_size=grid_size,
        )
        difference = solution.solver_objective - grid_optimum
        largest_lp_minus_grid = max(largest_lp_minus_grid, difference)
        if difference > TOLERANCE:
            raise AssertionError("population LP is worse than a brute-grid point")
        grid_checks += 1

        mismatch = abs(
            solution.solver_objective
            - solution.exact_worst_conditional_error
        )
        worst_objective_gap = max(worst_objective_gap, mismatch)
        if mismatch > TOLERANCE:
            raise AssertionError("population LP disagrees with exact evaluator")
        objective_checks += 1

        if any(
            risk.normalized_advantage > thresholds[label] + TOLERANCE
            for label, risk in enumerate(solution.privacy_risks)
        ):
            raise AssertionError("population LP returned a privacy violation")
        if solution.max_constraint_violation > TOLERANCE:
            raise AssertionError("population LP has excessive constraint violation")
        privacy_checks += 1

    return {
        "lp_vs_brute_grid_checks": grid_checks,
        "posthoc_exact_objective_checks": objective_checks,
        "privacy_threshold_checks": privacy_checks,
        "worst_objective_mismatch": worst_objective_gap,
        "largest_lp_minus_grid": largest_lp_minus_grid,
        "grid_size_per_channel_row": grid_size,
    }


def abstention_check() -> dict[str, object]:
    population = np.full((2, 2, 2), 0.5)
    identity = np.eye(2)
    try:
        optimize_population_external_channel(
            population,
            common_channels_by_label=((identity,), (identity,)),
            contaminations=(0.0, 0.0),
            privacy_advantage_thresholds=(0.0, 0.0),
            released_token_count=2,
            maximum_worst_conditional_error=0.49,
        )
    except RuntimeError as error:
        if "ABSTAIN_POPULATION_UTILITY" not in str(error):
            raise AssertionError("population optimizer raised wrong abstention") from error
        return {"pass": True, "status": "ABSTAIN_POPULATION_UTILITY"}
    raise AssertionError("population optimizer accepted impossible utility")


def atomic_json_dump(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20260720)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--grid-size", type=int, default=21)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "research/artifacts/mosaic_population_optimizer_verification_v0.json"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repetitions <= 0 or args.grid_size < 2:
        raise ValueError("repetitions must be positive and grid size at least two")
    checks = run_checks(
        rng=np.random.default_rng(args.seed),
        repetitions=args.repetitions,
        grid_size=args.grid_size,
    )
    abstention = abstention_check()
    passed = bool(
        checks["largest_lp_minus_grid"] <= TOLERANCE
        and checks["worst_objective_mismatch"] <= TOLERANCE
        and abstention["pass"]
    )
    payload: dict[str, object] = {
        "name": "MOSAIC exact population optimizer audit v0",
        "status": "development_only_not_independent_review",
        "seed": args.seed,
        "checks": checks,
        "abstention": abstention,
        "pass": passed,
        "scope": (
            "Compares the exact population LP with exhaustive channel grids, "
            "recomputes true external risks independently, and checks utility "
            "abstention."
        ),
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
