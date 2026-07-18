#!/usr/bin/env python3
"""Falsification checks for the MOSAIC global channel optimizer."""

from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from mosaic_invariant import (
    adaptive_pre_release_attacker_certificate,
    pre_release_utility_certificate,
)
from mosaic_optimizer import optimize_invariant_channel


TOLERANCE = 3e-7


def random_probability(rng: np.random.Generator, count: int) -> np.ndarray:
    return rng.dirichlet(np.ones(count, dtype=np.float64))


def random_channel(
    rng: np.random.Generator, row_count: int, column_count: int
) -> np.ndarray:
    return rng.dirichlet(np.ones(column_count, dtype=np.float64), size=row_count)


def evaluate_channel(
    empirical: np.ndarray,
    radii: np.ndarray,
    libraries: tuple[tuple[np.ndarray, ...], ...],
    eta: tuple[float, ...],
    thresholds: tuple[float, ...],
    channel: np.ndarray,
    decoder: tuple[int, ...],
) -> float | None:
    label_count, source_count, _ = empirical.shape
    privacy = [
        adaptive_pre_release_attacker_certificate(
            empirical[label],
            channel,
            l1_radii=radii[label],
            common_fine_token_channels=libraries[label],
            contamination=eta[label],
        )
        for label in range(label_count)
    ]
    if any(
        privacy[label].normalized_advantage > thresholds[label] + 1e-9
        for label in range(label_count)
    ):
        return None
    errors = [
        pre_release_utility_certificate(
            empirical[label, source],
            channel,
            decoder,
            true_label=label,
            l1_radius=float(radii[label, source]),
            common_fine_token_channels=libraries[label],
            contamination=eta[label],
        ).error_probability
        for label in range(label_count)
        for source in range(source_count)
    ]
    return max(errors)


def brute_grid_optimum(
    empirical: np.ndarray,
    radii: np.ndarray,
    libraries: tuple[tuple[np.ndarray, ...], ...],
    eta: tuple[float, ...],
    thresholds: tuple[float, ...],
    *,
    grid_size: int,
) -> float:
    """Search all binary decoders and a grid of every 2x2 channel."""

    grid = np.linspace(0.0, 1.0, grid_size)
    best = np.inf
    for first_probability in grid:
        for second_probability in grid:
            channel = np.asarray(
                [
                    [first_probability, 1.0 - first_probability],
                    [second_probability, 1.0 - second_probability],
                ]
            )
            for decoder in product(range(2), repeat=2):
                objective = evaluate_channel(
                    empirical,
                    radii,
                    libraries,
                    eta,
                    thresholds,
                    channel,
                    decoder,
                )
                if objective is not None:
                    best = min(best, objective)
    if not np.isfinite(best):
        raise AssertionError("the brute grid omitted the always-feasible constant channel")
    return float(best)


def random_global_checks(
    *, rng: np.random.Generator, repetitions: int, grid_size: int
) -> dict[str, int | float]:
    milp_vs_grid_checks = 0
    posthoc_objective_checks = 0
    threshold_checks = 0
    worst_objective_mismatch = 0.0
    largest_milp_minus_grid = 0.0

    for _ in range(repetitions):
        empirical = np.stack(
            [
                np.stack([random_probability(rng, 2) for _ in range(2)])
                for _ in range(2)
            ]
        )
        radii = rng.uniform(0.0, 0.25, size=(2, 2))
        identity = np.eye(2)
        common = random_channel(rng, 2, 2)
        libraries = ((identity, common), (identity, common))
        eta = tuple(float(value) for value in rng.uniform(0.0, 0.35, size=2))
        thresholds = tuple(
            float(value) for value in rng.uniform(0.05, 0.9, size=2)
        )
        solution = optimize_invariant_channel(
            empirical,
            l1_radii=radii,
            common_channels_by_label=libraries,
            contaminations=eta,
            privacy_advantage_thresholds=thresholds,
            released_token_count=2,
        )
        grid_optimum = brute_grid_optimum(
            empirical,
            radii,
            libraries,
            eta,
            thresholds,
            grid_size=grid_size,
        )
        difference = solution.solver_objective - grid_optimum
        largest_milp_minus_grid = max(largest_milp_minus_grid, difference)
        if difference > TOLERANCE:
            raise AssertionError(
                "MILP objective is worse than a feasible brute-grid channel"
            )
        milp_vs_grid_checks += 1

        mismatch = abs(
            solution.solver_objective
            - solution.certified_worst_conditional_error
        )
        worst_objective_mismatch = max(worst_objective_mismatch, mismatch)
        if mismatch > TOLERANCE:
            raise AssertionError("MILP objective disagrees with post-hoc certificate")
        posthoc_objective_checks += 1

        if any(
            certificate.normalized_advantage
            > thresholds[label] + TOLERANCE
            for label, certificate in enumerate(solution.privacy_certificates)
        ):
            raise AssertionError("optimizer returned a privacy-violating channel")
        if solution.max_constraint_violation > TOLERANCE:
            raise AssertionError("MILP solution has excessive constraint violation")
        if solution.solver_mip_gap > 1e-10:
            raise AssertionError("optimizer reported a non-global MIP gap")
        if abs(solution.solver_objective - solution.solver_dual_bound) > TOLERANCE:
            raise AssertionError("MILP primal objective disagrees with dual bound")
        threshold_checks += 1

    return {
        "milp_vs_brute_grid_checks": milp_vs_grid_checks,
        "posthoc_objective_checks": posthoc_objective_checks,
        "privacy_threshold_checks": threshold_checks,
        "worst_objective_mismatch": worst_objective_mismatch,
        "largest_milp_minus_grid": largest_milp_minus_grid,
        "grid_size_per_channel_row": grid_size,
    }


def stochastic_strict_improvement_check() -> dict[str, object]:
    """Construct a case where every useful deterministic release is uncertified."""

    empirical = np.asarray(
        [
            [[0.80, 0.15, 0.05], [0.65, 0.30, 0.05]],
            [[0.05, 0.20, 0.75], [0.05, 0.35, 0.60]],
        ]
    )
    radii = np.full((2, 2), 0.08)
    identity = np.eye(3)
    common = np.asarray(
        [[0.90, 0.10, 0.00], [0.05, 0.90, 0.05], [0.00, 0.10, 0.90]]
    )
    libraries = ((identity, common), (identity, common))
    eta = (0.10, 0.10)
    thresholds = (0.35, 0.35)
    solution = optimize_invariant_channel(
        empirical,
        l1_radii=radii,
        common_channels_by_label=libraries,
        contaminations=eta,
        privacy_advantage_thresholds=thresholds,
        released_token_count=2,
    )

    deterministic_best = np.inf
    for row_outputs in product(range(2), repeat=3):
        channel = np.zeros((3, 2))
        channel[np.arange(3), row_outputs] = 1.0
        for decoder in product(range(2), repeat=2):
            objective = evaluate_channel(
                empirical,
                radii,
                libraries,
                eta,
                thresholds,
                channel,
                decoder,
            )
            if objective is not None:
                deterministic_best = min(deterministic_best, objective)
    if not np.isfinite(deterministic_best):
        raise AssertionError("constant deterministic channels should remain feasible")
    improvement = deterministic_best - solution.certified_worst_conditional_error
    if improvement <= 0.10:
        raise AssertionError("stochastic channel failed the strict-improvement witness")
    if not np.any(
        (solution.release_channel > 1e-7)
        & (solution.release_channel < 1.0 - 1e-7)
    ):
        raise AssertionError("strict-improvement witness did not randomize")
    return {
        "stochastic_certified_worst_error": (
            solution.certified_worst_conditional_error
        ),
        "best_deterministic_certified_worst_error": deterministic_best,
        "absolute_improvement": improvement,
        "release_channel": solution.release_channel.tolist(),
        "decoder": list(solution.decoder),
        "privacy_advantages": [
            certificate.normalized_advantage
            for certificate in solution.privacy_certificates
        ],
        "pass": True,
    }


def abstention_check() -> dict[str, object]:
    """Verify that a registered impossible utility contract returns abstention."""

    empirical = np.full((2, 2, 2), 0.5)
    radii = np.full((2, 2), 2.0)
    identity = np.eye(2)
    try:
        optimize_invariant_channel(
            empirical,
            l1_radii=radii,
            common_channels_by_label=((identity,), (identity,)),
            contaminations=(0.0, 0.0),
            privacy_advantage_thresholds=(0.0, 0.0),
            released_token_count=2,
            maximum_worst_conditional_error=0.49,
        )
    except RuntimeError as error:
        message = str(error)
        if "ABSTAIN_NO_FEASIBLE_CHANNEL" not in message:
            raise AssertionError("optimizer raised the wrong abstention status") from error
        return {"pass": True, "status": "ABSTAIN_NO_FEASIBLE_CHANNEL"}
    raise AssertionError("impossible unsupported-stratum utility contract was accepted")


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
    parser.add_argument("--seed", type=int, default=20260718)
    parser.add_argument("--repetitions", type=int, default=30)
    parser.add_argument("--grid-size", type=int, default=21)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/artifacts/mosaic_optimizer_verification_v0.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repetitions <= 0 or args.grid_size < 2:
        raise ValueError("repetitions must be positive and grid size at least two")
    rng = np.random.default_rng(args.seed)
    global_checks = random_global_checks(
        rng=rng, repetitions=args.repetitions, grid_size=args.grid_size
    )
    strict_improvement = stochastic_strict_improvement_check()
    abstention = abstention_check()
    passed = bool(
        global_checks["largest_milp_minus_grid"] <= TOLERANCE
        and global_checks["worst_objective_mismatch"] <= TOLERANCE
        and strict_improvement["pass"]
        and abstention["pass"]
    )
    payload: dict[str, object] = {
        "name": "MOSAIC global invariant-channel optimizer audit v0",
        "status": "development_only_not_independent_review",
        "seed": args.seed,
        "global_checks": global_checks,
        "stochastic_strict_improvement": strict_improvement,
        "abstention": abstention,
        "pass": passed,
        "scope": (
            "Compares the exact branch MILP against brute channel grids, "
            "recomputes every certificate, exhibits a strict stochastic-over-"
            "deterministic witness, and checks utility-contract abstention."
        ),
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
