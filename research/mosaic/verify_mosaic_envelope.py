#!/usr/bin/env python3
"""Dependency-free adversarial checks for the MOSAIC envelope.

This verifier intentionally re-derives key quantities instead of importing the
implementation's private helpers.  It is a development-time falsification tool,
not independent human proof review.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from itertools import product
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from mosaic_envelope import (
    coarsen_distribution,
    coarsened_confidence_certificate,
    coarsened_multiclass_confidence_certificate,
    robust_multiclass_attacker_accuracy,
    robust_multiclass_attacker_confidence_bound,
    robust_selected_rule_error_bound,
    robust_total_variation,
    robust_total_variation_confidence_bound,
    upper_event_mass,
    weissman_l1_radius,
)


def direct_total_variation(p0: np.ndarray, p1: np.ndarray) -> float:
    return float(0.5 * np.abs(p1 - p0).sum())


def direct_shifted_event_envelope(
    p0: np.ndarray, p1: np.ndarray, gamma: float
) -> tuple[float, int]:
    """Independent subset implementation of the likelihood-ratio identity."""

    best_value = 0.0
    best_mask = 0
    for mask in range(1 << p0.size):
        selected = np.fromiter(
            ((mask >> token) & 1 for token in range(p0.size)),
            dtype=np.float64,
            count=p0.size,
        )
        mass_0 = float(selected @ p0)
        mass_1 = float(selected @ p1)
        lower_0 = max(mass_0 / gamma, 1.0 - gamma * (1.0 - mass_0))
        upper_1 = min(gamma * mass_1, 1.0 - (1.0 - mass_1) / gamma)
        value = upper_1 - lower_0
        if value > best_value:
            best_value = value
            best_mask = mask
    return best_value, best_mask


def random_probability(rng: np.random.Generator, token_count: int) -> np.ndarray:
    return rng.dirichlet(np.ones(token_count, dtype=np.float64))


def all_surjective_mappings(token_count: int, coarse_count: int):
    for mapping in product(range(coarse_count), repeat=token_count):
        if set(mapping) == set(range(coarse_count)):
            yield mapping


def run_deterministic_checks(
    *, rng: np.random.Generator, repetitions: int
) -> dict[str, int | float]:
    formula_checks = 0
    monotonicity_checks = 0
    confidence_set_checks = 0
    selected_coarsening_checks = 0
    multiclass_checks = 0
    selected_rule_checks = 0

    for _ in range(repetitions):
        token_count = int(rng.integers(2, 8))
        gamma = float(rng.uniform(1.0, 3.0))
        p0 = random_probability(rng, token_count)
        p1 = random_probability(rng, token_count)

        exact = robust_total_variation(p0, p1, gamma=gamma)
        direct, direct_mask = direct_shifted_event_envelope(p0, p1, gamma)
        if not np.isclose(exact.value, direct, atol=1e-12):
            raise AssertionError(
                f"formula mismatch: implementation={exact.value}, direct={direct}, "
                f"implementation_mask={exact.maximizing_mask}, direct_mask={direct_mask}"
            )
        formula_checks += 1

        identity = robust_total_variation(p0, p1, gamma=1.0)
        if not np.isclose(identity.value, direct_total_variation(p0, p1), atol=1e-12):
            raise AssertionError("gamma=1 did not recover ordinary total variation")
        formula_checks += 1

        if token_count >= 3:
            coarse_count = int(rng.integers(2, token_count))
            mapping = tuple(
                list(range(coarse_count))
                + rng.integers(0, coarse_count, size=token_count - coarse_count).tolist()
            )
            mapping = tuple(np.asarray(mapping)[rng.permutation(token_count)].tolist())
            coarse = robust_total_variation(
                coarsen_distribution(p0, mapping),
                coarsen_distribution(p1, mapping),
                gamma=gamma,
            )
            if coarse.value > exact.value + 1e-12:
                raise AssertionError("coarsening increased population robust TV")
            monotonicity_checks += 1

        empirical_0 = random_probability(rng, token_count)
        empirical_1 = random_probability(rng, token_count)
        radius_0 = float(np.abs(empirical_0 - p0).sum())
        radius_1 = float(np.abs(empirical_1 - p1).sum())
        confidence = robust_total_variation_confidence_bound(
            empirical_0,
            empirical_1,
            gamma=gamma,
            l1_radius_group_0=radius_0,
            l1_radius_group_1=radius_1,
        )
        if confidence.value + 1e-12 < exact.value:
            raise AssertionError("L1 confidence envelope failed to contain truth")
        confidence_set_checks += 1

        worst_gap = -np.inf
        for mask in range(1 << token_count):
            error_tokens = tuple(
                bool((mask >> token) & 1) for token in range(token_count)
            )
            bound = robust_selected_rule_error_bound(
                empirical_0,
                error_tokens,
                gamma=gamma,
                l1_radius=radius_0,
            )
            event = np.asarray(error_tokens, dtype=bool)
            truth = float(upper_event_mass(float(p0[event].sum()), gamma))
            worst_gap = max(worst_gap, truth - bound)
        if worst_gap > 1e-12:
            raise AssertionError("a data-selected token rule escaped the L1 event")
        selected_rule_checks += 1

        if token_count <= 7 and token_count >= 3:
            candidates = []
            for mapping in all_surjective_mappings(token_count, 2):
                candidate = coarsened_confidence_certificate(
                    empirical_0,
                    empirical_1,
                    mapping,
                    gamma=gamma,
                    fine_l1_radius_group_0=radius_0,
                    fine_l1_radius_group_1=radius_1,
                )
                candidates.append((candidate.value, mapping, candidate))
            _, selected_mapping, selected_bound = min(candidates, key=lambda item: item[0])
            selected_truth = robust_total_variation(
                coarsen_distribution(p0, selected_mapping),
                coarsen_distribution(p1, selected_mapping),
                gamma=gamma,
            )
            if selected_bound.value + 1e-12 < selected_truth.value:
                raise AssertionError("post-selected coarsening invalidated its bound")
            selected_coarsening_checks += 1

        multiclass_source_count = int(rng.integers(3, 5))
        multiclass_token_count = int(rng.integers(2, 6))
        multiclass_truth = np.stack(
            [
                random_probability(rng, multiclass_token_count)
                for _ in range(multiclass_source_count)
            ]
        )
        multiclass_empirical = np.stack(
            [
                random_probability(rng, multiclass_token_count)
                for _ in range(multiclass_source_count)
            ]
        )
        multiclass_radii = tuple(
            float(np.abs(multiclass_truth[source] - multiclass_empirical[source]).sum())
            for source in range(multiclass_source_count)
        )
        multiclass_exact = robust_multiclass_attacker_accuracy(
            multiclass_truth, gamma=gamma
        )
        multiclass_bound = robust_multiclass_attacker_confidence_bound(
            multiclass_empirical,
            gamma=gamma,
            l1_radii=multiclass_radii,
        )
        if multiclass_bound.balanced_accuracy + 1e-12 < multiclass_exact.balanced_accuracy:
            raise AssertionError("multiclass confidence envelope missed the truth")
        gamma_one = robust_multiclass_attacker_accuracy(
            multiclass_truth, gamma=1.0
        )
        bayes_accuracy = float(
            np.max(multiclass_truth, axis=0).sum() / multiclass_source_count
        )
        if not np.isclose(gamma_one.balanced_accuracy, bayes_accuracy, atol=1e-12):
            raise AssertionError("multiclass gamma=1 identity failed")
        multiclass_checks += 2

        if multiclass_token_count >= 3:
            mappings = tuple(
                all_surjective_mappings(multiclass_token_count, 2)
            )
            selected_mapping = min(
                mappings,
                key=lambda mapping: coarsened_multiclass_confidence_certificate(
                    multiclass_empirical,
                    mapping,
                    gamma=gamma,
                    fine_l1_radii=multiclass_radii,
                ).balanced_accuracy,
            )
            selected_bound = coarsened_multiclass_confidence_certificate(
                multiclass_empirical,
                selected_mapping,
                gamma=gamma,
                fine_l1_radii=multiclass_radii,
            )
            selected_truth = robust_multiclass_attacker_accuracy(
                tuple(
                    coarsen_distribution(row, selected_mapping)
                    for row in multiclass_truth
                ),
                gamma=gamma,
            )
            if (
                selected_bound.balanced_accuracy + 1e-12
                < selected_truth.balanced_accuracy
            ):
                raise AssertionError("selected multiclass coarsening escaped its bound")
            selected_coarsening_checks += 1

    return {
        "formula_checks": formula_checks,
        "monotonicity_checks": monotonicity_checks,
        "confidence_set_checks": confidence_set_checks,
        "selected_coarsening_checks": selected_coarsening_checks,
        "multiclass_checks": multiclass_checks,
        "selected_rule_checks": selected_rule_checks,
    }


def run_coverage_simulation(
    *,
    rng: np.random.Generator,
    repetitions: int,
    token_count: int,
    sample_size: int,
    gamma_grid: tuple[float, ...],
    delta: float,
) -> dict[str, object]:
    """Check the simultaneous confidence event and all-Gamma TV coverage."""

    radius = weissman_l1_radius(sample_size, token_count, delta / 2.0)
    confidence_event_failures = 0
    envelope_failures = 0
    total_gamma_comparisons = 0
    worst_undercoverage = 0.0

    for _ in range(repetitions):
        p0 = random_probability(rng, token_count)
        p1 = random_probability(rng, token_count)
        counts_0 = rng.multinomial(sample_size, p0)
        counts_1 = rng.multinomial(sample_size, p1)
        empirical_0 = counts_0 / sample_size
        empirical_1 = counts_1 / sample_size
        confidence_event = (
            np.abs(empirical_0 - p0).sum() <= radius + 1e-12
            and np.abs(empirical_1 - p1).sum() <= radius + 1e-12
        )
        if not confidence_event:
            confidence_event_failures += 1

        replicate_failed = False
        for gamma in gamma_grid:
            bound = robust_total_variation_confidence_bound(
                empirical_0,
                empirical_1,
                gamma=gamma,
                l1_radius_group_0=radius,
                l1_radius_group_1=radius,
            )
            truth = robust_total_variation(p0, p1, gamma=gamma)
            gap = truth.value - bound.value
            worst_undercoverage = max(worst_undercoverage, gap)
            if gap > 1e-12:
                replicate_failed = True
            total_gamma_comparisons += 1
        if replicate_failed:
            envelope_failures += 1

    return {
        "repetitions": repetitions,
        "token_count": token_count,
        "sample_size_per_group": sample_size,
        "gamma_grid": list(gamma_grid),
        "familywise_delta": delta,
        "weissman_l1_radius_per_group": radius,
        "confidence_event_failures": confidence_event_failures,
        "confidence_event_failure_rate": confidence_event_failures / repetitions,
        "envelope_failures": envelope_failures,
        "envelope_failure_rate": envelope_failures / repetitions,
        "gamma_comparisons": total_gamma_comparisons,
        "worst_undercoverage": worst_undercoverage,
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
    parser.add_argument("--seed", type=int, default=20260718)
    parser.add_argument("--deterministic-repetitions", type=int, default=500)
    parser.add_argument("--coverage-repetitions", type=int, default=2000)
    parser.add_argument("--token-count", type=int, default=6)
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--delta", type=float, default=0.05)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/artifacts/mosaic_theorem_verification_v0.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.deterministic_repetitions <= 0 or args.coverage_repetitions <= 0:
        raise ValueError("repetition counts must be positive")
    if not 0.0 < args.delta < 1.0:
        raise ValueError("delta must lie in (0, 1)")
    rng = np.random.default_rng(args.seed)
    deterministic = run_deterministic_checks(
        rng=rng, repetitions=args.deterministic_repetitions
    )
    coverage = run_coverage_simulation(
        rng=rng,
        repetitions=args.coverage_repetitions,
        token_count=args.token_count,
        sample_size=args.sample_size,
        gamma_grid=(1.0, 1.1, 1.25, 1.5, 2.0),
        delta=args.delta,
    )
    payload: dict[str, object] = {
        "name": "MOSAIC theorem implementation falsification receipt v0",
        "status": "development_only_not_independent_review",
        "seed": args.seed,
        "deterministic": deterministic,
        "coverage": coverage,
        "pass": bool(
            coverage["envelope_failure_rate"] <= args.delta
            and coverage["worst_undercoverage"] <= 1e-12
        ),
        "scope": (
            "Checks implementation identities and simulated coverage only; it does "
            "not establish novelty, prove the theorem, or replace external review."
        ),
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
