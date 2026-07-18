#!/usr/bin/env python3
"""Adversarial numerical audit for the MOSAIC pre-release theorem.

The audit independently re-derives support functions with generic linear
programming, brute-forces source residual vertices, selects stochastic channels
on the certification table, and simulates common-plus-differential fine-token
shift.  A passing receipt checks implementation and theorem consequences; it is
not an independent proof or a novelty determination.
"""

from __future__ import annotations

import argparse
import json
from itertools import product
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from scipy.optimize import linprog

from mosaic_channel import (
    adaptive_channel_attacker_confidence_bound,
    l1_ball_expectation_upper,
    population_balanced_attacker_accuracy,
    selected_decoder_error_confidence_bound,
)
from mosaic_envelope import weissman_l1_radius
from mosaic_invariant import (
    adaptive_pre_release_attacker_certificate,
    apply_pre_release_shift,
    differential_decoder_error_capacity,
    differential_shift_capacity,
    directional_decoder_invariance_defect,
    dobrushin_coefficient,
    invariance_defect,
    pre_release_utility_certificate,
)


TOLERANCE = 5e-9


def random_probability(rng: np.random.Generator, count: int) -> np.ndarray:
    return rng.dirichlet(np.ones(count, dtype=np.float64))


def random_channel(
    rng: np.random.Generator, row_count: int, column_count: int
) -> np.ndarray:
    return rng.dirichlet(np.ones(column_count, dtype=np.float64), size=row_count)


def l1_support_dual_lp(
    empirical: np.ndarray, scores: np.ndarray, radius: float
) -> float:
    """Solve the dual stated in the theorem without using custom code."""

    count = empirical.size
    # Variables are nu_positive, nu_negative, lambda, and unrestricted theta.
    variable_count = 3 + count
    objective = np.zeros(variable_count)
    objective[0] = 1.0
    objective[1] = -1.0
    objective[2] = radius
    objective[3:] = empirical
    upper_rows = []
    upper_rhs = []
    for token in range(count):
        # scores[token] <= nu_positive - nu_negative + theta[token]
        row = np.zeros(variable_count)
        row[0] = -1.0
        row[1] = 1.0
        row[3 + token] = -1.0
        upper_rows.append(row)
        upper_rhs.append(-scores[token])

        # theta[token] <= lambda
        row = np.zeros(variable_count)
        row[2] = -1.0
        row[3 + token] = 1.0
        upper_rows.append(row)
        upper_rhs.append(0.0)

        # -theta[token] <= lambda
        row = np.zeros(variable_count)
        row[2] = -1.0
        row[3 + token] = -1.0
        upper_rows.append(row)
        upper_rhs.append(0.0)

    result = linprog(
        objective,
        A_ub=np.asarray(upper_rows),
        b_ub=np.asarray(upper_rhs),
        bounds=[(0.0, None), (0.0, None), (0.0, None)]
        + [(None, None)] * count,
        method="highs",
    )
    if not result.success:
        raise AssertionError(f"L1 support dual failed: {result.message}")
    return float(result.fun)


def brute_capacity_by_source_vertices(
    release_channel: np.ndarray, source_count: int
) -> float:
    """Enumerate all deterministic fine-token laws for every source."""

    fine_count = release_channel.shape[0]
    best = 0.0
    for source_tokens in product(range(fine_count), repeat=source_count):
        released_laws = np.stack(
            [release_channel[token] for token in source_tokens]
        )
        best = max(best, population_balanced_attacker_accuracy(released_laws))
    return best


def random_transform_library(
    rng: np.random.Generator, fine_count: int, count: int
) -> tuple[np.ndarray, ...]:
    identity = np.eye(fine_count, dtype=np.float64)
    return (identity,) + tuple(
        random_channel(rng, fine_count, fine_count) for _ in range(count - 1)
    )


def random_convex_combination(
    rng: np.random.Generator, matrices: tuple[np.ndarray, ...]
) -> np.ndarray:
    weights = rng.dirichlet(np.ones(len(matrices), dtype=np.float64))
    return sum(weight * matrix for weight, matrix in zip(weights, matrices, strict=True))


def decoder_error(
    released_distribution: np.ndarray, decoder: tuple[int, ...], true_label: int
) -> float:
    loss = (np.asarray(decoder) != true_label).astype(float)
    return float(released_distribution @ loss)


def deterministic_checks(
    *, rng: np.random.Generator, repetitions: int
) -> dict[str, int | float]:
    support_dual_checks = 0
    capacity_vertex_checks = 0
    dobrushin_identity_checks = 0
    full_simplex_checks = 0
    common_invariance_checks = 0
    coupled_shift_checks = 0
    utility_shift_checks = 0
    convex_hull_checks = 0
    convexity_checks = 0
    no_free_lunch_checks = 0
    utility_lower_bound_checks = 0
    worst_numeric_gap = 0.0

    for _ in range(repetitions):
        fine_count = int(rng.integers(2, 7))
        released_count = int(rng.integers(2, 4))
        source_count = int(rng.integers(2, 4))
        empirical_one = random_probability(rng, fine_count)
        scores = rng.uniform(-2.0, 3.0, size=fine_count)
        radius = float(rng.uniform(0.0, 2.0))
        custom_support = l1_ball_expectation_upper(
            empirical_one, scores, l1_radius=radius
        )
        dual_support = l1_support_dual_lp(empirical_one, scores, radius)
        gap = abs(custom_support - dual_support)
        worst_numeric_gap = max(worst_numeric_gap, gap)
        if gap > TOLERANCE:
            raise AssertionError("water-filling support disagrees with its LP dual")
        support_dual_checks += 1

        release = random_channel(rng, fine_count, released_count)
        capacity = differential_shift_capacity(
            release, source_count=source_count
        )
        brute_capacity = brute_capacity_by_source_vertices(release, source_count)
        gap = abs(capacity.balanced_accuracy - brute_capacity)
        worst_numeric_gap = max(worst_numeric_gap, gap)
        if gap > TOLERANCE:
            raise AssertionError("closed capacity formula disagrees with source vertices")
        capacity_vertex_checks += 1

        binary_capacity = differential_shift_capacity(release, source_count=2)
        alpha = dobrushin_coefficient(release)
        gap = abs(binary_capacity.normalized_advantage - alpha)
        worst_numeric_gap = max(worst_numeric_gap, gap)
        if gap > TOLERANCE:
            raise AssertionError("binary capacity is not the Dobrushin coefficient")
        dobrushin_identity_checks += 1

        arbitrary_empirical = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        full_simplex = adaptive_channel_attacker_confidence_bound(
            arbitrary_empirical,
            release,
            l1_radii=(2.0,) * source_count,
        )
        gap = abs(full_simplex.balanced_accuracy - capacity.balanced_accuracy)
        worst_numeric_gap = max(worst_numeric_gap, gap)
        if gap > TOLERANCE:
            raise AssertionError("full-simplex confidence envelope missed capacity")
        full_simplex_checks += 1

        truth = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        empirical = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        exact_radii = tuple(
            float(np.abs(truth[source] - empirical[source]).sum())
            for source in range(source_count)
        )
        transforms = random_transform_library(rng, fine_count, 4)
        transform = random_convex_combination(rng, transforms)
        defect = invariance_defect(release, transforms).total_variation
        reference_truth = population_balanced_attacker_accuracy(truth, release)
        shifted_truth = population_balanced_attacker_accuracy(
            truth @ transform, release
        )
        common_bound = min(
            capacity.balanced_accuracy, reference_truth + defect
        )
        if shifted_truth > common_bound + TOLERANCE:
            raise AssertionError("common pre-release drift escaped invariance bound")
        common_invariance_checks += 1

        selected_candidates = [
            random_channel(rng, fine_count, released_count) for _ in range(10)
        ]
        selected_certificates = [
            adaptive_pre_release_attacker_certificate(
                empirical,
                candidate,
                l1_radii=exact_radii,
                common_fine_token_channels=transforms,
                contamination=0.3,
            )
            for candidate in selected_candidates
        ]
        selected_index = min(
            range(len(selected_candidates)),
            key=lambda index: selected_certificates[index].balanced_accuracy,
        )
        selected = selected_candidates[selected_index]
        eta = float(rng.uniform(0.0, 0.5))
        selected_certificate = adaptive_pre_release_attacker_certificate(
            empirical,
            selected,
            l1_radii=exact_radii,
            common_fine_token_channels=transforms,
            contamination=eta,
        )
        actual_contamination = float(rng.uniform(0.0, eta))
        residuals = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        _, external_released = apply_pre_release_shift(
            truth,
            transform,
            residuals,
            selected,
            retained_common_mass=1.0 - actual_contamination,
        )
        external_truth = population_balanced_attacker_accuracy(external_released)
        if external_truth > selected_certificate.balanced_accuracy + TOLERANCE:
            raise AssertionError("coupled fine-token shift escaped external certificate")
        coupled_shift_checks += 1

        decoder = tuple(
            int(value) for value in rng.integers(0, 3, size=released_count)
        )
        true_label = int(rng.integers(0, 3))
        source = int(rng.integers(0, source_count))
        utility_certificate = pre_release_utility_certificate(
            empirical[source],
            selected,
            decoder,
            true_label=true_label,
            l1_radius=exact_radii[source],
            common_fine_token_channels=transforms,
            contamination=eta,
        )
        external_error = decoder_error(
            external_released[source], decoder, true_label
        )
        if external_error > utility_certificate.error_probability + TOLERANCE:
            raise AssertionError("coupled fine-token shift escaped utility certificate")
        utility_shift_checks += 1

        mixture_defect = invariance_defect(
            release, (transform,)
        ).total_variation
        if mixture_defect > defect + TOLERANCE:
            raise AssertionError("convex-hull transform exceeded an extreme defect")
        convex_hull_checks += 1

        second_release = random_channel(rng, fine_count, released_count)
        weight = float(rng.uniform())
        mixed_release = weight * release + (1.0 - weight) * second_release
        radii = tuple(float(rng.uniform(0.0, 1.0)) for _ in range(source_count))
        first_reference = adaptive_channel_attacker_confidence_bound(
            empirical, release, l1_radii=radii
        ).balanced_accuracy
        second_reference = adaptive_channel_attacker_confidence_bound(
            empirical, second_release, l1_radii=radii
        ).balanced_accuracy
        mixed_reference = adaptive_channel_attacker_confidence_bound(
            empirical, mixed_release, l1_radii=radii
        ).balanced_accuracy
        if mixed_reference > (
            weight * first_reference + (1.0 - weight) * second_reference
            + TOLERANCE
        ):
            raise AssertionError("reference envelope violated convexity")

        first_capacity = differential_shift_capacity(
            release, source_count=source_count
        ).balanced_accuracy
        second_capacity = differential_shift_capacity(
            second_release, source_count=source_count
        ).balanced_accuracy
        mixed_capacity = differential_shift_capacity(
            mixed_release, source_count=source_count
        ).balanced_accuracy
        if mixed_capacity > (
            weight * first_capacity + (1.0 - weight) * second_capacity
            + TOLERANCE
        ):
            raise AssertionError("differential capacity violated convexity")

        first_defect = invariance_defect(release, transforms).total_variation
        second_defect = invariance_defect(
            second_release, transforms
        ).total_variation
        mixed_defect = invariance_defect(
            mixed_release, transforms
        ).total_variation
        if mixed_defect > (
            weight * first_defect + (1.0 - weight) * second_defect + TOLERANCE
        ):
            raise AssertionError("invariance defect violated convexity")
        convexity_checks += 3

        common_row = random_probability(rng, released_count)
        zero_capacity_release = np.tile(common_row, (fine_count, 1))
        zero_capacity = differential_shift_capacity(
            zero_capacity_release, source_count=source_count
        )
        if not np.isclose(
            zero_capacity.balanced_accuracy, 1.0 / source_count, atol=TOLERANCE
        ):
            raise AssertionError("identical release rows did not have zero capacity")
        perturbed = zero_capacity_release.copy()
        transfer = min(0.1, float(perturbed[0, 0]), float(1.0 - perturbed[0, 1]))
        if transfer > 1e-8:
            perturbed[0, 0] -= transfer
            perturbed[0, 1] += transfer
            perturbed_capacity = differential_shift_capacity(
                perturbed, source_count=source_count
            )
            if perturbed_capacity.balanced_accuracy <= (
                1.0 / source_count + 1e-10
            ):
                raise AssertionError("distinct release rows retained zero capacity")
        no_free_lunch_checks += 1

        binary_decoder = tuple(
            int(value) for value in rng.integers(0, 2, size=released_count)
        )
        first_token = int(rng.integers(0, fine_count))
        second_token = int(rng.integers(0, fine_count))
        first_error = decoder_error(release[first_token], binary_decoder, 0)
        second_error = decoder_error(release[second_token], binary_decoder, 1)
        lower_bound = max(0.0, 1.0 - first_error - second_error)
        if dobrushin_coefficient(release) + TOLERANCE < lower_bound:
            raise AssertionError("task utility did not imply required leakage capacity")
        utility_lower_bound_checks += 1

    return {
        "l1_support_dual_checks": support_dual_checks,
        "capacity_vs_source_vertex_checks": capacity_vertex_checks,
        "binary_dobrushin_identity_checks": dobrushin_identity_checks,
        "full_simplex_equals_capacity_checks": full_simplex_checks,
        "common_invariance_transfer_checks": common_invariance_checks,
        "coupled_pre_release_shift_checks": coupled_shift_checks,
        "utility_shift_checks": utility_shift_checks,
        "convex_hull_extreme_checks": convex_hull_checks,
        "convexity_checks": convexity_checks,
        "zero_capacity_no_free_lunch_checks": no_free_lunch_checks,
        "utility_leakage_lower_bound_checks": utility_lower_bound_checks,
        "worst_numeric_gap": worst_numeric_gap,
    }


def coverage_simulation(
    *,
    rng: np.random.Generator,
    repetitions: int,
    source_count: int,
    fine_count: int,
    released_count: int,
    sample_size: int,
    delta: float,
    candidate_count: int,
) -> dict[str, object]:
    """Audit same-table channel selection under shifted external laws."""

    radius = weissman_l1_radius(
        sample_size, fine_count, delta / source_count
    )
    confidence_event_failures = 0
    all_candidate_reference_failures = 0
    all_candidate_external_failures = 0
    all_candidate_failures_on_event = 0
    selected_reference_failures = 0
    selected_external_failures = 0
    selected_utility_failures = 0
    selected_failures_on_event = 0
    total_candidate_checks = 0
    worst_reference_undercoverage = 0.0
    worst_external_undercoverage = 0.0
    worst_utility_undercoverage = 0.0
    worst_undercoverage_on_event = 0.0

    for _ in range(repetitions):
        truth = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        empirical = np.stack(
            [
                rng.multinomial(sample_size, truth[source]) / sample_size
                for source in range(source_count)
            ]
        )
        confidence_event = all(
            np.abs(empirical[source] - truth[source]).sum() <= radius + 1e-12
            for source in range(source_count)
        )
        if not confidence_event:
            confidence_event_failures += 1

        transforms = random_transform_library(rng, fine_count, 4)
        actual_transform = random_convex_combination(rng, transforms)
        eta = float(rng.uniform(0.0, 0.4))
        residuals = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        decoder = tuple(
            int(value) for value in rng.integers(0, 3, size=released_count)
        )
        true_label = int(rng.integers(0, 3))

        candidates = [
            random_channel(rng, fine_count, released_count)
            for _ in range(candidate_count)
        ]
        certificates = [
            adaptive_pre_release_attacker_certificate(
                empirical,
                candidate,
                l1_radii=(radius,) * source_count,
                common_fine_token_channels=transforms,
                contamination=eta,
            )
            for candidate in candidates
        ]
        utilities = [
            pre_release_utility_certificate(
                empirical[0],
                candidate,
                decoder,
                true_label=true_label,
                l1_radius=radius,
                common_fine_token_channels=transforms,
                contamination=eta,
            )
            for candidate in candidates
        ]

        for candidate, certificate in zip(candidates, certificates, strict=True):
            reference_truth = population_balanced_attacker_accuracy(truth, candidate)
            reference_gap = (
                reference_truth - certificate.reference_balanced_accuracy_bound
            )
            worst_reference_undercoverage = max(
                worst_reference_undercoverage, reference_gap
            )
            failed = False
            if reference_gap > TOLERANCE:
                all_candidate_reference_failures += 1
                failed = True

            _, external_released = apply_pre_release_shift(
                truth,
                actual_transform,
                residuals,
                candidate,
                retained_common_mass=1.0 - eta,
            )
            external_truth = population_balanced_attacker_accuracy(
                external_released
            )
            external_gap = external_truth - certificate.balanced_accuracy
            worst_external_undercoverage = max(
                worst_external_undercoverage, external_gap
            )
            if external_gap > TOLERANCE:
                all_candidate_external_failures += 1
                failed = True
            if failed and confidence_event:
                all_candidate_failures_on_event += 1
                worst_undercoverage_on_event = max(
                    worst_undercoverage_on_event, reference_gap, external_gap
                )
            total_candidate_checks += 1

        selected_index = min(
            range(candidate_count),
            key=lambda index: (
                certificates[index].balanced_accuracy
                + 0.35 * utilities[index].error_probability
            ),
        )
        selected = candidates[selected_index]
        selected_certificate = certificates[selected_index]
        selected_utility = utilities[selected_index]
        selected_reference_truth = population_balanced_attacker_accuracy(
            truth, selected
        )
        selected_reference_gap = (
            selected_reference_truth
            - selected_certificate.reference_balanced_accuracy_bound
        )
        selected_failed = False
        if selected_reference_gap > TOLERANCE:
            selected_reference_failures += 1
            selected_failed = True

        _, selected_external = apply_pre_release_shift(
            truth,
            actual_transform,
            residuals,
            selected,
            retained_common_mass=1.0 - eta,
        )
        selected_external_truth = population_balanced_attacker_accuracy(
            selected_external
        )
        selected_external_gap = (
            selected_external_truth - selected_certificate.balanced_accuracy
        )
        if selected_external_gap > TOLERANCE:
            selected_external_failures += 1
            selected_failed = True

        selected_external_error = decoder_error(
            selected_external[0], decoder, true_label
        )
        selected_utility_gap = (
            selected_external_error - selected_utility.error_probability
        )
        worst_utility_undercoverage = max(
            worst_utility_undercoverage, selected_utility_gap
        )
        if selected_utility_gap > TOLERANCE:
            selected_utility_failures += 1
            selected_failed = True

        if selected_failed and confidence_event:
            selected_failures_on_event += 1
            worst_undercoverage_on_event = max(
                worst_undercoverage_on_event,
                selected_reference_gap,
                selected_external_gap,
                selected_utility_gap,
            )

    return {
        "repetitions": repetitions,
        "source_count": source_count,
        "fine_token_count": fine_count,
        "released_token_count": released_count,
        "sample_size_per_source": sample_size,
        "candidate_channels_per_repetition": candidate_count,
        "familywise_delta": delta,
        "weissman_l1_radius_per_source": radius,
        "confidence_event_failures": confidence_event_failures,
        "confidence_event_failure_rate": confidence_event_failures / repetitions,
        "all_candidate_checks": total_candidate_checks,
        "all_candidate_reference_failures": all_candidate_reference_failures,
        "all_candidate_external_failures": all_candidate_external_failures,
        "all_candidate_failures_on_confidence_event": (
            all_candidate_failures_on_event
        ),
        "selected_reference_failures": selected_reference_failures,
        "selected_external_failures": selected_external_failures,
        "selected_utility_failures": selected_utility_failures,
        "selected_failures_on_confidence_event": selected_failures_on_event,
        "selected_reference_failure_rate": selected_reference_failures
        / repetitions,
        "selected_external_failure_rate": selected_external_failures / repetitions,
        "selected_utility_failure_rate": selected_utility_failures / repetitions,
        "worst_reference_undercoverage": worst_reference_undercoverage,
        "worst_external_undercoverage": worst_external_undercoverage,
        "worst_utility_undercoverage": worst_utility_undercoverage,
        "worst_undercoverage_on_confidence_event": worst_undercoverage_on_event,
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
    parser.add_argument("--deterministic-repetitions", type=int, default=250)
    parser.add_argument("--coverage-repetitions", type=int, default=2000)
    parser.add_argument("--source-count", type=int, default=3)
    parser.add_argument("--fine-token-count", type=int, default=6)
    parser.add_argument("--released-token-count", type=int, default=3)
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--candidate-count", type=int, default=12)
    parser.add_argument("--delta", type=float, default=0.05)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "research/artifacts/mosaic_pre_release_theorem_verification_v0.json"
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.deterministic_repetitions <= 0 or args.coverage_repetitions <= 0:
        raise ValueError("repetition counts must be positive")
    if not 0.0 < args.delta < 1.0:
        raise ValueError("delta must lie in (0, 1)")
    rng = np.random.default_rng(args.seed)
    deterministic = deterministic_checks(
        rng=rng, repetitions=args.deterministic_repetitions
    )
    coverage = coverage_simulation(
        rng=rng,
        repetitions=args.coverage_repetitions,
        source_count=args.source_count,
        fine_count=args.fine_token_count,
        released_count=args.released_token_count,
        sample_size=args.sample_size,
        delta=args.delta,
        candidate_count=args.candidate_count,
    )
    passed = bool(
        deterministic["worst_numeric_gap"] <= TOLERANCE
        and coverage["confidence_event_failure_rate"] <= args.delta
        and coverage["all_candidate_failures_on_confidence_event"] == 0
        and coverage["selected_failures_on_confidence_event"] == 0
        and coverage["selected_reference_failure_rate"] <= args.delta
        and coverage["selected_external_failure_rate"] <= args.delta
        and coverage["selected_utility_failure_rate"] <= args.delta
        and coverage["worst_undercoverage_on_confidence_event"] <= TOLERANCE
    )
    payload: dict[str, object] = {
        "name": "MOSAIC pre-release invariant-channel theorem audit v0",
        "status": "development_only_not_independent_review",
        "seed": args.seed,
        "deterministic": deterministic,
        "coverage": coverage,
        "pass": passed,
        "scope": (
            "Checks LP duality, exact differential capacity, the Dobrushin "
            "identity, same-table channel selection, common-shift invariance, "
            "differential contamination, utility transfer, convexity, and the "
            "no-free-lunch boundary. It does not establish novelty or empirical "
            "usefulness and does not replace independent proof review."
        ),
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
