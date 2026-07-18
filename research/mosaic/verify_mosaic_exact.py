#!/usr/bin/env python3
"""Independent finite-enumeration checks for MOSAIC population risk code."""

from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from mosaic_channel import population_balanced_attacker_accuracy
from mosaic_exact import (
    exact_external_attacker_risk,
    exact_external_utility_risk,
)
from mosaic_invariant import (
    adaptive_pre_release_attacker_certificate,
    differential_shift_capacity,
    pre_release_utility_certificate,
)


TOLERANCE = 5e-10


def random_probability(rng: np.random.Generator, count: int) -> np.ndarray:
    return rng.dirichlet(np.ones(count, dtype=np.float64))


def random_channel(
    rng: np.random.Generator, rows: int, columns: int
) -> np.ndarray:
    return rng.dirichlet(np.ones(columns, dtype=np.float64), size=rows)


def brute_residual_attacker_risk(
    reference: np.ndarray,
    release: np.ndarray,
    transform: np.ndarray,
    eta: float,
) -> float:
    source_count, fine_count = reference.shape
    best = -1.0
    for residual_tokens in product(range(fine_count), repeat=source_count):
        external = []
        for source, token in enumerate(residual_tokens):
            residual = np.zeros(fine_count)
            residual[token] = 1.0
            external.append(
                ((1.0 - eta) * (reference[source] @ transform) + eta * residual)
                @ release
            )
        best = max(best, population_balanced_attacker_accuracy(external))
    return float(best)


def brute_residual_utility_risk(
    reference: np.ndarray,
    release: np.ndarray,
    transform: np.ndarray,
    decoder: tuple[int, ...],
    true_label: int,
    eta: float,
) -> float:
    loss = (np.asarray(decoder) != true_label).astype(np.float64)
    best = -1.0
    for token in range(reference.size):
        residual = np.zeros(reference.size)
        residual[token] = 1.0
        external = (
            (1.0 - eta) * (reference @ transform) + eta * residual
        ) @ release
        best = max(best, float(external @ loss))
    return float(best)


def run_checks(
    *, rng: np.random.Generator, repetitions: int
) -> dict[str, int | float]:
    attacker_vertex_checks = 0
    utility_vertex_checks = 0
    certificate_domination_checks = 0
    endpoint_checks = 0
    convex_hull_checks = 0
    worst_gap = 0.0

    for _ in range(repetitions):
        source_count = int(rng.integers(2, 4))
        fine_count = int(rng.integers(2, 5))
        released_count = int(rng.integers(2, 4))
        reference = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        empirical = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        radii = tuple(
            float(np.abs(reference[source] - empirical[source]).sum())
            for source in range(source_count)
        )
        release = random_channel(rng, fine_count, released_count)
        transforms = tuple(
            random_channel(rng, fine_count, fine_count) for _ in range(3)
        )
        eta = float(rng.uniform(0.0, 0.5))

        exact_attacker = exact_external_attacker_risk(
            reference,
            release,
            transforms,
            contamination=eta,
        )
        brute_attacker = max(
            brute_residual_attacker_risk(
                reference, release, transform, eta
            )
            for transform in transforms
        )
        gap = abs(exact_attacker.balanced_accuracy - brute_attacker)
        worst_gap = max(worst_gap, gap)
        if gap > TOLERANCE:
            raise AssertionError("exact attacker risk missed a residual vertex")
        attacker_vertex_checks += 1

        decoder = tuple(
            int(value) for value in rng.integers(0, 3, size=released_count)
        )
        true_label = int(rng.integers(0, 3))
        source = int(rng.integers(0, source_count))
        exact_utility = exact_external_utility_risk(
            reference[source],
            release,
            decoder,
            true_label=true_label,
            common_fine_token_channels=transforms,
            contamination=eta,
        )
        brute_utility = max(
            brute_residual_utility_risk(
                reference[source],
                release,
                transform,
                decoder,
                true_label,
                eta,
            )
            for transform in transforms
        )
        gap = abs(exact_utility.error_probability - brute_utility)
        worst_gap = max(worst_gap, gap)
        if gap > TOLERANCE:
            raise AssertionError("exact utility risk missed a residual vertex")
        utility_vertex_checks += 1

        attacker_certificate = adaptive_pre_release_attacker_certificate(
            empirical,
            release,
            l1_radii=radii,
            common_fine_token_channels=transforms,
            contamination=eta,
        )
        utility_certificate = pre_release_utility_certificate(
            empirical[source],
            release,
            decoder,
            true_label=true_label,
            l1_radius=radii[source],
            common_fine_token_channels=transforms,
            contamination=eta,
        )
        if (
            exact_attacker.balanced_accuracy
            > attacker_certificate.balanced_accuracy + TOLERANCE
            or exact_utility.error_probability
            > utility_certificate.error_probability + TOLERANCE
        ):
            raise AssertionError("a certificate failed to dominate exact truth")
        certificate_domination_checks += 2

        full_shift = exact_external_attacker_risk(
            reference,
            release,
            transforms,
            contamination=1.0,
        )
        capacity = differential_shift_capacity(
            release, source_count=source_count
        )
        gap = abs(full_shift.balanced_accuracy - capacity.balanced_accuracy)
        worst_gap = max(worst_gap, gap)
        if gap > TOLERANCE:
            raise AssertionError("eta=1 did not equal channel capacity")
        endpoint_checks += 1

        weights = rng.dirichlet(np.ones(len(transforms)))
        mixture = sum(
            weight * transform
            for weight, transform in zip(weights, transforms, strict=True)
        )
        mixture_risk = exact_external_attacker_risk(
            reference,
            release,
            (mixture,),
            contamination=eta,
        )
        if mixture_risk.balanced_accuracy > exact_attacker.balanced_accuracy + TOLERANCE:
            raise AssertionError("a convex-hull transform exceeded its extremes")
        convex_hull_checks += 1

    return {
        "attacker_residual_vertex_checks": attacker_vertex_checks,
        "utility_residual_vertex_checks": utility_vertex_checks,
        "certificate_domination_checks": certificate_domination_checks,
        "eta_one_capacity_checks": endpoint_checks,
        "convex_hull_extreme_checks": convex_hull_checks,
        "worst_numeric_gap": worst_gap,
    }


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
    parser.add_argument("--seed", type=int, default=20260719)
    parser.add_argument("--repetitions", type=int, default=500)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/artifacts/mosaic_exact_risk_verification_v0.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.repetitions <= 0:
        raise ValueError("repetitions must be positive")
    checks = run_checks(
        rng=np.random.default_rng(args.seed), repetitions=args.repetitions
    )
    passed = bool(checks["worst_numeric_gap"] <= TOLERANCE)
    payload: dict[str, object] = {
        "name": "MOSAIC exact external-risk evaluator audit v0",
        "status": "development_only_not_independent_review",
        "seed": args.seed,
        "checks": checks,
        "pass": passed,
        "scope": (
            "Compares exact external risks with direct residual-simplex vertex "
            "enumeration, checks confidence-certificate domination, verifies "
            "the arbitrary-shift endpoint, and tests convex-hull extremes."
        ),
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
