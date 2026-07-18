#!/usr/bin/env python3
"""Independent falsification checks for the MOSAIC coupled-shift theorems.

The verifier compares the custom water-filling routine with generic linear
programming, re-enumerates attacker assignments, performs data-dependent
channel selection in repeated samples, generates coupled external shifts, and
checks the common-channel compatibility LP.  It remains a development audit,
not an independent mathematical review.
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
    coupled_shift_attacker_bound,
    coupled_shift_decoder_error_bound,
    fit_common_channel_contamination,
    l1_ball_expectation_upper,
    normalized_attacker_advantage,
    population_balanced_attacker_accuracy,
    selected_decoder_error_confidence_bound,
)
from mosaic_envelope import robust_total_variation, weissman_l1_radius


def random_probability(rng: np.random.Generator, count: int) -> np.ndarray:
    return rng.dirichlet(np.ones(count, dtype=np.float64))


def random_channel(
    rng: np.random.Generator, input_count: int, output_count: int
) -> np.ndarray:
    return rng.dirichlet(
        np.ones(output_count, dtype=np.float64), size=input_count
    )


def lp_l1_expectation_upper(
    empirical: np.ndarray, scores: np.ndarray, radius: float
) -> float:
    """Generic LP re-derivation of the L1-ball support function."""

    count = empirical.size
    objective = np.concatenate((-scores, np.zeros(count)))
    upper_rows = []
    upper_rhs = []
    for token in range(count):
        positive = np.zeros(2 * count)
        positive[token] = 1.0
        positive[count + token] = -1.0
        upper_rows.append(positive)
        upper_rhs.append(empirical[token])

        negative = np.zeros(2 * count)
        negative[token] = -1.0
        negative[count + token] = -1.0
        upper_rows.append(negative)
        upper_rhs.append(-empirical[token])
    radius_row = np.zeros(2 * count)
    radius_row[count:] = 1.0
    upper_rows.append(radius_row)
    upper_rhs.append(radius)

    equality = np.zeros((1, 2 * count))
    equality[0, :count] = 1.0
    result = linprog(
        objective,
        A_ub=np.asarray(upper_rows),
        b_ub=np.asarray(upper_rhs),
        A_eq=equality,
        b_eq=np.asarray([1.0]),
        bounds=[(0.0, 1.0)] * count + [(0.0, None)] * count,
        method="highs",
    )
    if not result.success:
        raise AssertionError(f"support-function LP failed: {result.message}")
    return float(-result.fun)


def independent_channel_envelope(
    empirical: np.ndarray, channel: np.ndarray, radii: tuple[float, ...]
) -> tuple[float, tuple[int, ...]]:
    """Slow reimplementation using generic LPs for every source/assignment."""

    source_count = empirical.shape[0]
    released_count = channel.shape[1]
    best = -1.0
    best_assignment: tuple[int, ...] = ()
    for assignment in product(range(source_count), repeat=released_count):
        assignment_array = np.asarray(assignment)
        score = 0.0
        for source in range(source_count):
            soft_correct = channel @ (assignment_array == source).astype(float)
            score += lp_l1_expectation_upper(
                empirical[source], soft_correct, radii[source]
            )
        score /= source_count
        if score > best:
            best = score
            best_assignment = assignment
    return best, best_assignment


def deterministic_checks(
    *, rng: np.random.Generator, repetitions: int
) -> dict[str, int | float]:
    support_lp_checks = 0
    exact_envelope_checks = 0
    selected_channel_checks = 0
    data_processing_checks = 0
    utility_checks = 0
    shift_transfer_checks = 0
    compatibility_lp_checks = 0
    sharpness_checks = 0
    worst_numeric_gap = 0.0

    for _ in range(repetitions):
        fine_count = int(rng.integers(2, 8))
        empirical = random_probability(rng, fine_count)
        scores = rng.uniform(-1.0, 2.0, size=fine_count)
        radius = float(rng.uniform(0.0, 2.0))
        custom = l1_ball_expectation_upper(
            empirical, scores, l1_radius=radius
        )
        generic = lp_l1_expectation_upper(empirical, scores, radius)
        gap = abs(custom - generic)
        worst_numeric_gap = max(worst_numeric_gap, gap)
        if gap > 2e-9:
            raise AssertionError(
                f"water-filling mismatch: custom={custom}, LP={generic}, gap={gap}"
            )
        support_lp_checks += 1

        source_count = int(rng.integers(2, 5))
        released_count = int(rng.integers(2, 4))
        source_empirical = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        radii = tuple(float(rng.uniform(0.0, 1.0)) for _ in range(source_count))
        channel = random_channel(rng, fine_count, released_count)
        custom_envelope = adaptive_channel_attacker_confidence_bound(
            source_empirical, channel, l1_radii=radii
        )
        generic_envelope, _ = independent_channel_envelope(
            source_empirical, channel, radii
        )
        gap = abs(custom_envelope.balanced_accuracy - generic_envelope)
        worst_numeric_gap = max(worst_numeric_gap, gap)
        if gap > 3e-9:
            raise AssertionError("adaptive-channel envelope disagrees with independent LP")
        exact_envelope_checks += 1

        truth = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        selected_empirical = np.stack(
            [random_probability(rng, fine_count) for _ in range(source_count)]
        )
        exact_radii = tuple(
            float(np.abs(truth[s] - selected_empirical[s]).sum())
            for s in range(source_count)
        )
        candidates = [
            random_channel(rng, fine_count, released_count) for _ in range(12)
        ]
        selected = min(
            candidates,
            key=lambda candidate: adaptive_channel_attacker_confidence_bound(
                selected_empirical, candidate, l1_radii=exact_radii
            ).balanced_accuracy,
        )
        selected_bound = adaptive_channel_attacker_confidence_bound(
            selected_empirical, selected, l1_radii=exact_radii
        )
        selected_truth = population_balanced_attacker_accuracy(truth, selected)
        if selected_truth > selected_bound.balanced_accuracy + 3e-10:
            raise AssertionError("data-selected stochastic channel escaped confidence set")
        selected_channel_checks += 1

        downstream = random_channel(rng, released_count, released_count)
        before = population_balanced_attacker_accuracy(truth, selected)
        after = population_balanced_attacker_accuracy(truth, selected @ downstream)
        if after > before + 3e-10:
            raise AssertionError("a common Markov channel increased Bayes source accuracy")
        data_processing_checks += 1

        decoder = tuple(
            int(value) for value in rng.integers(0, 3, size=released_count)
        )
        true_label = int(rng.integers(0, 3))
        one_source = truth[0]
        one_empirical = selected_empirical[0]
        one_radius = exact_radii[0]
        utility_bound = selected_decoder_error_confidence_bound(
            one_empirical,
            selected,
            decoder,
            true_label=true_label,
            l1_radius=one_radius,
        )
        predictions = np.asarray(decoder)
        error_outputs = (predictions != true_label).astype(float)
        true_error = float(one_source @ selected @ error_outputs)
        if true_error > utility_bound + 3e-10:
            raise AssertionError("selected decoder escaped utility confidence bound")
        utility_checks += 1

        eta = float(rng.uniform(0.0, 0.5))
        common = random_channel(rng, released_count, released_count)
        residuals = np.stack(
            [random_probability(rng, released_count) for _ in range(source_count)]
        )
        external = (1.0 - eta) * (truth @ selected @ common) + eta * residuals
        external_truth = population_balanced_attacker_accuracy(external)
        external_bound = coupled_shift_attacker_bound(
            selected_bound, contamination=eta
        )
        if external_truth > external_bound.balanced_accuracy + 3e-10:
            raise AssertionError("coupled external shift escaped attacker transfer bound")
        shift_transfer_checks += 1

        flip = max(
            float(
                common[token]
                @ (predictions != predictions[token]).astype(float)
            )
            for token in range(released_count)
        )
        residual = random_probability(rng, released_count)
        external_one = (1.0 - eta) * (one_source @ selected @ common) + eta * residual
        external_error = float(external_one @ error_outputs)
        transferred_utility = coupled_shift_decoder_error_bound(
            utility_bound,
            contamination=eta,
            common_channel_flip_probability=flip,
        )
        if external_error > transferred_utility + 3e-10:
            raise AssertionError("coupled shift escaped decoder error transfer bound")
        utility_checks += 1

        fit = fit_common_channel_contamination(truth @ selected, external)
        if fit.minimum_contamination > eta + 2e-8:
            raise AssertionError("compatibility LP missed a known feasible decomposition")
        reconstructed = (
            fit.retained_common_mass
            * (truth @ selected @ fit.common_channel)
            + fit.minimum_contamination * fit.source_residuals
        )
        if not np.allclose(reconstructed, external, atol=2e-8):
            raise AssertionError("compatibility LP decomposition did not reconstruct Q")
        if fit.max_constraint_violation > 2e-8:
            raise AssertionError("compatibility LP reported excessive constraint error")
        compatibility_lp_checks += 1

    gamma = 1.25
    p = np.asarray([1.0 / (gamma + 1.0), gamma / (gamma + 1.0)])
    floor = robust_total_variation(p, p, gamma=gamma).value
    if not np.isclose(floor, 1.0 - 1.0 / gamma, atol=1e-12):
        raise AssertionError("independent likelihood-ratio floor construction failed")
    sharpness_checks += 1

    source_count = 3
    eta = 0.23
    common_reference = np.tile(np.asarray([0.3, 0.7]), (source_count, 1))
    external = np.zeros((source_count, 2 + source_count))
    external[:, :2] = (1.0 - eta) * common_reference
    for source in range(source_count):
        external[source, 2 + source] = eta
    fit = fit_common_channel_contamination(common_reference, external)
    if not np.isclose(fit.minimum_contamination, eta, atol=2e-8):
        raise AssertionError("common-channel contamination sharpness construction failed")
    external_accuracy = population_balanced_attacker_accuracy(external)
    reference_accuracy = population_balanced_attacker_accuracy(common_reference)
    expected = (1.0 - eta) * reference_accuracy + eta
    if not np.isclose(external_accuracy, expected, atol=1e-12):
        raise AssertionError("attacker transfer bound was not attained in sharpness case")
    sharpness_checks += 1

    return {
        "support_function_vs_lp_checks": support_lp_checks,
        "exact_envelope_vs_lp_checks": exact_envelope_checks,
        "post_selected_channel_checks": selected_channel_checks,
        "data_processing_checks": data_processing_checks,
        "utility_transfer_checks": utility_checks,
        "coupled_shift_transfer_checks": shift_transfer_checks,
        "compatibility_lp_checks": compatibility_lp_checks,
        "sharpness_and_impossibility_checks": sharpness_checks,
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
    """Repeatedly select a channel on the certification table and audit coverage."""

    per_source_failure = delta / source_count
    radius = weissman_l1_radius(sample_size, fine_count, per_source_failure)
    confidence_event_failures = 0
    reference_envelope_failures = 0
    external_envelope_failures = 0
    total_candidate_checks = 0
    all_candidate_failures = 0
    all_candidate_failures_on_confidence_event = 0
    reference_failures_on_confidence_event = 0
    external_failures_on_confidence_event = 0
    worst_reference_undercoverage = 0.0
    worst_external_undercoverage = 0.0
    worst_reference_undercoverage_on_confidence_event = 0.0
    worst_external_undercoverage_on_confidence_event = 0.0

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

        candidates = [
            random_channel(rng, fine_count, released_count)
            for _ in range(candidate_count)
        ]
        candidate_bounds = [
            adaptive_channel_attacker_confidence_bound(
                empirical,
                channel,
                l1_radii=(radius,) * source_count,
            )
            for channel in candidates
        ]
        for channel, bound in zip(candidates, candidate_bounds, strict=True):
            candidate_truth = population_balanced_attacker_accuracy(truth, channel)
            if candidate_truth > bound.balanced_accuracy + 1e-10:
                all_candidate_failures += 1
                if confidence_event:
                    all_candidate_failures_on_confidence_event += 1
            total_candidate_checks += 1

        selected_index = min(
            range(candidate_count),
            key=lambda index: candidate_bounds[index].balanced_accuracy,
        )
        selected = candidates[selected_index]
        bound = candidate_bounds[selected_index]
        reference_truth = population_balanced_attacker_accuracy(truth, selected)
        reference_gap = reference_truth - bound.balanced_accuracy
        worst_reference_undercoverage = max(
            worst_reference_undercoverage, reference_gap
        )
        if reference_gap > 1e-10:
            reference_envelope_failures += 1
            if confidence_event:
                reference_failures_on_confidence_event += 1
        if confidence_event:
            worst_reference_undercoverage_on_confidence_event = max(
                worst_reference_undercoverage_on_confidence_event, reference_gap
            )

        eta = float(rng.uniform(0.0, 0.35))
        common = random_channel(rng, released_count, released_count)
        residuals = np.stack(
            [random_probability(rng, released_count) for _ in range(source_count)]
        )
        external = (1.0 - eta) * (truth @ selected @ common) + eta * residuals
        external_truth = population_balanced_attacker_accuracy(external)
        external_bound = coupled_shift_attacker_bound(bound, contamination=eta)
        external_gap = external_truth - external_bound.balanced_accuracy
        worst_external_undercoverage = max(
            worst_external_undercoverage, external_gap
        )
        if external_gap > 1e-10:
            external_envelope_failures += 1
            if confidence_event:
                external_failures_on_confidence_event += 1
        if confidence_event:
            worst_external_undercoverage_on_confidence_event = max(
                worst_external_undercoverage_on_confidence_event, external_gap
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
        "selected_reference_envelope_failures": reference_envelope_failures,
        "selected_reference_envelope_failure_rate": reference_envelope_failures
        / repetitions,
        "selected_external_envelope_failures": external_envelope_failures,
        "selected_external_envelope_failure_rate": external_envelope_failures
        / repetitions,
        "all_candidate_checks": total_candidate_checks,
        "all_candidate_failures": all_candidate_failures,
        "all_candidate_failures_on_confidence_event": (
            all_candidate_failures_on_confidence_event
        ),
        "selected_reference_failures_on_confidence_event": (
            reference_failures_on_confidence_event
        ),
        "selected_external_failures_on_confidence_event": (
            external_failures_on_confidence_event
        ),
        "worst_reference_undercoverage": worst_reference_undercoverage,
        "worst_external_undercoverage": worst_external_undercoverage,
        "worst_reference_undercoverage_on_confidence_event": (
            worst_reference_undercoverage_on_confidence_event
        ),
        "worst_external_undercoverage_on_confidence_event": (
            worst_external_undercoverage_on_confidence_event
        ),
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
            "research/artifacts/mosaic_coupled_theorem_verification_v0.json"
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
    payload: dict[str, object] = {
        "name": "MOSAIC coupled-shift theorem falsification receipt v0",
        "status": "development_only_not_independent_review",
        "seed": args.seed,
        "deterministic": deterministic,
        "coverage": coverage,
        "pass": bool(
            deterministic["worst_numeric_gap"] <= 3e-9
            and coverage["confidence_event_failure_rate"] <= args.delta
            and coverage["selected_reference_envelope_failure_rate"] <= args.delta
            and coverage["selected_external_envelope_failure_rate"] <= args.delta
            and coverage["all_candidate_failures_on_confidence_event"] == 0
            and coverage["selected_reference_failures_on_confidence_event"] == 0
            and coverage["selected_external_failures_on_confidence_event"] == 0
            and coverage[
                "worst_reference_undercoverage_on_confidence_event"
            ]
            <= 1e-10
            and coverage[
                "worst_external_undercoverage_on_confidence_event"
            ]
            <= 1e-10
        ),
        "scope": (
            "Checks formulas, generic-LP agreement, post-selection coverage, coupled "
            "shift transfer, utility transfer, and compatibility decompositions. It "
            "does not establish novelty or replace independent proof review."
        ),
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
