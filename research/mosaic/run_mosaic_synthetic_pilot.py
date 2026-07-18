#!/usr/bin/env python3
"""Run the disclosed MOSAIC v2 synthetic design pilot.

Pilot seeds are for scenario and threshold selection only. They are permanently
excluded from any confirmatory estimate. Every selected channel is evaluated by
the exact population-risk module, never by its own deployment certificate.
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from itertools import product
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Sequence

import numpy as np

from mosaic_channel import normalized_attacker_advantage
from mosaic_envelope import weissman_l1_radius
from mosaic_exact import (
    exact_external_attacker_risk,
    exact_external_utility_risk,
)
from mosaic_invariant import (
    adaptive_pre_release_attacker_certificate,
    pre_release_utility_certificate,
)
from mosaic_optimizer import (
    InvariantChannelSolution,
    PopulationExternalChannelSolution,
    optimize_invariant_channel,
    optimize_population_external_channel,
)


METHODS = (
    "always_deploy_plugin",
    "plugin_continuum",
    "heldout_fixed_channel",
    "finite_ltt",
    "deterministic_mosaic",
    "shift_unaware_mosaic",
    "mosaic",
    "population_oracle",
)


@dataclass(frozen=True)
class Scenario:
    name: str
    population: np.ndarray
    libraries: tuple[tuple[np.ndarray, ...], ...]
    contaminations: tuple[float, ...]
    privacy_thresholds: tuple[float, ...]
    utility_threshold: float
    released_token_count: int


@dataclass(frozen=True)
class Selection:
    channel: np.ndarray
    decoder: tuple[int, ...]
    criterion: float


@dataclass(frozen=True)
class ReplicateResult:
    seed: int
    sample_size_per_stratum: int
    method: str
    deployed: bool
    exact_safe: bool
    false_acceptance: bool
    exact_worst_privacy_advantage: float
    exact_worst_conditional_error: float
    selection_criterion: float
    release_channel: tuple[tuple[float, ...], ...]
    decoder: tuple[int, ...]
    confidence_event: bool | None
    failure_on_confidence_event: bool | None


def witness_scenario(
    *, privacy_threshold: float, utility_threshold: float, contamination: float
) -> Scenario:
    population = np.asarray(
        [
            [[0.80, 0.15, 0.05], [0.65, 0.30, 0.05]],
            [[0.05, 0.20, 0.75], [0.05, 0.35, 0.60]],
        ],
        dtype=np.float64,
    )
    identity = np.eye(3)
    common = np.asarray(
        [[0.90, 0.10, 0.00], [0.05, 0.90, 0.05], [0.00, 0.10, 0.90]],
        dtype=np.float64,
    )
    return Scenario(
        name="stochastic_middle_token",
        population=population,
        libraries=((identity, common), (identity, common)),
        contaminations=(contamination, contamination),
        privacy_thresholds=(privacy_threshold, privacy_threshold),
        utility_threshold=utility_threshold,
        released_token_count=2,
    )


def empirical_table(
    rng: np.random.Generator, population: np.ndarray, n: int
) -> np.ndarray:
    return np.stack(
        [
            np.stack(
                [
                    rng.multinomial(n, population[label, source]) / n
                    for source in range(population.shape[1])
                ]
            )
            for label in range(population.shape[0])
        ]
    )


def simultaneous_radii(
    n: int, *, label_count: int, source_count: int, fine_count: int, delta: float
) -> np.ndarray:
    allocation = delta / (label_count * source_count)
    radius = weissman_l1_radius(n, fine_count, allocation)
    return np.full((label_count, source_count), radius, dtype=np.float64)


def confidence_event(
    empirical: np.ndarray, population: np.ndarray, radii: np.ndarray
) -> bool:
    distances = np.abs(empirical - population).sum(axis=2)
    return bool(np.all(distances <= radii + 1e-12))


def selection_from_population_solution(
    solution: PopulationExternalChannelSolution,
) -> Selection:
    return Selection(
        channel=solution.release_channel,
        decoder=solution.decoder,
        criterion=solution.exact_worst_conditional_error,
    )


def selection_from_mosaic_solution(
    solution: InvariantChannelSolution,
) -> Selection:
    return Selection(
        channel=solution.release_channel,
        decoder=solution.decoder,
        criterion=solution.certified_worst_conditional_error,
    )


def exact_risks(
    scenario: Scenario, selection: Selection
) -> tuple[tuple[float, ...], float]:
    privacy = tuple(
        exact_external_attacker_risk(
            scenario.population[label],
            selection.channel,
            scenario.libraries[label],
            contamination=scenario.contaminations[label],
        ).normalized_advantage
        for label in range(scenario.population.shape[0])
    )
    utility = max(
        exact_external_utility_risk(
            scenario.population[label, source],
            selection.channel,
            selection.decoder,
            true_label=label,
            common_fine_token_channels=scenario.libraries[label],
            contamination=scenario.contaminations[label],
        ).error_probability
        for label in range(scenario.population.shape[0])
        for source in range(scenario.population.shape[1])
    )
    return privacy, float(utility)


def direct_one_sided_confidence_event(
    empirical: np.ndarray,
    scenario: Scenario,
    selection: Selection,
    *,
    privacy_radius: float,
    utility_radius: float,
) -> bool:
    """Check the selected direct-Hoeffding inequalities against population laws."""

    label_count, source_count, _ = empirical.shape
    assignments = tuple(
        product(range(source_count), repeat=selection.channel.shape[1])
    )
    for label in range(label_count):
        for transform in scenario.libraries[label]:
            empirical_shifted = empirical[label] @ transform
            population_shifted = scenario.population[label] @ transform
            for assignment in assignments:
                assignment_array = np.asarray(assignment, dtype=np.int64)
                empirical_score = 0.0
                population_score = 0.0
                for source in range(source_count):
                    correct_outputs = (
                        assignment_array == source
                    ).astype(np.float64)
                    soft_correct = selection.channel @ correct_outputs
                    empirical_score += float(
                        empirical_shifted[source] @ soft_correct
                    )
                    population_score += float(
                        population_shifted[source] @ soft_correct
                    )
                if (
                    population_score / source_count
                    > empirical_score / source_count + privacy_radius + 1e-12
                ):
                    return False

    predictions = np.asarray(selection.decoder, dtype=np.int64)
    for label in range(label_count):
        loss = (predictions != label).astype(np.float64)
        row_errors = selection.channel @ loss
        for source in range(source_count):
            for transform in scenario.libraries[label]:
                empirical_error = float(
                    empirical[label, source] @ transform @ row_errors
                )
                population_error = float(
                    scenario.population[label, source]
                    @ transform
                    @ row_errors
                )
                if population_error > empirical_error + utility_radius + 1e-12:
                    return False
    return True


def fixed_channel_certified_selection(
    empirical: np.ndarray,
    scenario: Scenario,
    selection: Selection,
    *,
    n: int,
    delta: float,
) -> tuple[bool, float, bool]:
    label_count, source_count, _ = empirical.shape
    assignments = tuple(
        product(range(source_count), repeat=selection.channel.shape[1])
    )
    privacy_test_count = len(assignments) * sum(
        len(library) for library in scenario.libraries
    )
    utility_test_count = source_count * sum(
        len(library) for library in scenario.libraries
    )
    privacy_radius = float(
        np.sqrt(
            np.log(privacy_test_count / (delta / 2.0))
            / (2.0 * source_count * n)
        )
    )
    utility_radius = float(
        np.sqrt(
            np.log(utility_test_count / (delta / 2.0)) / (2.0 * n)
        )
    )

    privacy_advantages = []
    for label in range(label_count):
        worst_ba = 1.0 / source_count
        eta = scenario.contaminations[label]
        for transform in scenario.libraries[label]:
            shifted = empirical[label] @ transform
            for assignment in assignments:
                assignment_array = np.asarray(assignment, dtype=np.int64)
                common_score = 0.0
                residual_score = 0.0
                for source in range(source_count):
                    correct_outputs = (
                        assignment_array == source
                    ).astype(np.float64)
                    soft_correct = selection.channel @ correct_outputs
                    common_score += float(shifted[source] @ soft_correct)
                    residual_score += float(np.max(soft_correct))
                common_upper = min(
                    1.0, common_score / source_count + privacy_radius
                )
                worst_ba = max(
                    worst_ba,
                    (1.0 - eta) * common_upper
                    + eta * residual_score / source_count,
                )
        privacy_advantages.append(
            normalized_attacker_advantage(worst_ba, source_count)
        )
    privacy_pass = all(
        advantage <= scenario.privacy_thresholds[label] + 1e-10
        for label, advantage in enumerate(privacy_advantages)
    )

    predictions = np.asarray(selection.decoder, dtype=np.int64)
    worst_error = 0.0
    for label in range(label_count):
        loss = (predictions != label).astype(np.float64)
        row_errors = selection.channel @ loss
        capacity = float(np.max(row_errors))
        eta = scenario.contaminations[label]
        for source in range(source_count):
            for transform in scenario.libraries[label]:
                common_error = float(
                    empirical[label, source] @ transform @ row_errors
                )
                common_upper = min(1.0, common_error + utility_radius)
                worst_error = max(
                    worst_error,
                    (1.0 - eta) * common_upper + eta * capacity,
                )
    event = direct_one_sided_confidence_event(
        empirical,
        scenario,
        selection,
        privacy_radius=privacy_radius,
        utility_radius=utility_radius,
    )
    return (
        privacy_pass and worst_error <= scenario.utility_threshold + 1e-10,
        float(worst_error),
        event,
    )


def deterministic_selection(
    empirical: np.ndarray,
    radii: np.ndarray,
    scenario: Scenario,
) -> Selection:
    label_count, source_count, fine_count = empirical.shape
    released_count = scenario.released_token_count
    best: Selection | None = None
    for row_outputs in product(range(released_count), repeat=fine_count):
        channel = np.zeros((fine_count, released_count), dtype=np.float64)
        channel[np.arange(fine_count), row_outputs] = 1.0
        privacy = tuple(
            adaptive_pre_release_attacker_certificate(
                empirical[label],
                channel,
                l1_radii=radii[label],
                common_fine_token_channels=scenario.libraries[label],
                contamination=scenario.contaminations[label],
            )
            for label in range(label_count)
        )
        if any(
            certificate.normalized_advantage
            > scenario.privacy_thresholds[label] + 1e-10
            for label, certificate in enumerate(privacy)
        ):
            continue
        for decoder in product(range(label_count), repeat=released_count):
            worst_error = max(
                pre_release_utility_certificate(
                    empirical[label, source],
                    channel,
                    decoder,
                    true_label=label,
                    l1_radius=float(radii[label, source]),
                    common_fine_token_channels=scenario.libraries[label],
                    contamination=scenario.contaminations[label],
                ).error_probability
                for label in range(label_count)
                for source in range(source_count)
            )
            candidate = Selection(channel, tuple(decoder), float(worst_error))
            if best is None or (candidate.criterion, row_outputs, decoder) < (
                best.criterion,
                tuple(np.argmax(best.channel, axis=1)),
                best.decoder,
            ):
                best = candidate
    if best is None:
        raise AssertionError("constant deterministic channel must be privacy-feasible")
    return best


def finite_ltt_selection(
    empirical: np.ndarray,
    scenario: Scenario,
    *,
    n: int,
    delta: float,
) -> tuple[Selection, bool]:
    label_count, source_count, fine_count = empirical.shape
    released_count = scenario.released_token_count
    grid = np.linspace(0.0, 1.0, 5)
    channels = tuple(
        np.asarray(
            [[probability, 1.0 - probability] for probability in probabilities],
            dtype=np.float64,
        )
        for probabilities in product(grid, repeat=fine_count)
    )
    decoders = tuple(product(range(label_count), repeat=released_count))
    assignments = tuple(product(range(source_count), repeat=released_count))
    privacy_test_count = (
        len(channels)
        * len(assignments)
        * sum(len(library) for library in scenario.libraries)
    )
    utility_test_count = (
        len(channels)
        * len(decoders)
        * source_count
        * sum(len(library) for library in scenario.libraries)
    )
    privacy_radius = float(
        np.sqrt(
            np.log(privacy_test_count / (delta / 2.0))
            / (2.0 * source_count * n)
        )
    )
    utility_radius = float(
        np.sqrt(
            np.log(utility_test_count / (delta / 2.0)) / (2.0 * n)
        )
    )
    best: Selection | None = None
    best_key: tuple[float, int, int] | None = None
    for channel_index, channel in enumerate(channels):
        privacy = []
        for label in range(label_count):
            worst_ba = 1.0 / source_count
            eta = scenario.contaminations[label]
            for transform in scenario.libraries[label]:
                shifted = empirical[label] @ transform
                for assignment in assignments:
                    assignment_array = np.asarray(assignment, dtype=np.int64)
                    common_score = 0.0
                    residual_score = 0.0
                    for source in range(source_count):
                        correct_outputs = (
                            assignment_array == source
                        ).astype(np.float64)
                        soft_correct = channel @ correct_outputs
                        common_score += float(shifted[source] @ soft_correct)
                        residual_score += float(np.max(soft_correct))
                    common_upper = min(
                        1.0,
                        common_score / source_count + privacy_radius,
                    )
                    external_upper = (
                        (1.0 - eta) * common_upper
                        + eta * residual_score / source_count
                    )
                    worst_ba = max(worst_ba, external_upper)
            privacy.append(
                normalized_attacker_advantage(worst_ba, source_count)
            )
        if any(
            advantage
            > scenario.privacy_thresholds[label] + 1e-10
            for label, advantage in enumerate(privacy)
        ):
            continue
        for decoder_index, decoder in enumerate(decoders):
            predictions = np.asarray(decoder, dtype=np.int64)
            worst_error = 0.0
            for label in range(label_count):
                loss = (predictions != label).astype(np.float64)
                row_errors = channel @ loss
                capacity = float(np.max(row_errors))
                eta = scenario.contaminations[label]
                for source in range(source_count):
                    for transform in scenario.libraries[label]:
                        common_error = float(
                            empirical[label, source] @ transform @ row_errors
                        )
                        common_upper = min(1.0, common_error + utility_radius)
                        external_upper = (
                            (1.0 - eta) * common_upper + eta * capacity
                        )
                        worst_error = max(worst_error, external_upper)
            candidate = Selection(channel, tuple(decoder), float(worst_error))
            candidate_key = (candidate.criterion, channel_index, decoder_index)
            if best_key is None or candidate_key < best_key:
                best = candidate
                best_key = candidate_key
    if best is None:
        raise AssertionError("finite family omitted a constant feasible channel")
    event = direct_one_sided_confidence_event(
        empirical,
        scenario,
        best,
        privacy_radius=privacy_radius,
        utility_radius=utility_radius,
    )
    return best, event


def result_for_selection(
    *,
    seed: int,
    n: int,
    method: str,
    scenario: Scenario,
    selection: Selection,
    deployed: bool,
    event: bool | None,
) -> ReplicateResult:
    privacy_by_label, utility = exact_risks(scenario, selection)
    privacy = max(privacy_by_label)
    safe = bool(
        all(
            value <= scenario.privacy_thresholds[label] + 1e-9
            for label, value in enumerate(privacy_by_label)
        )
        and utility <= scenario.utility_threshold + 1e-9
    )
    false_acceptance = bool(deployed and not safe)
    failure_on_event = None if event is None else bool(false_acceptance and event)
    return ReplicateResult(
        seed=seed,
        sample_size_per_stratum=n,
        method=method,
        deployed=deployed,
        exact_safe=safe,
        false_acceptance=false_acceptance,
        exact_worst_privacy_advantage=privacy,
        exact_worst_conditional_error=utility,
        selection_criterion=selection.criterion,
        release_channel=tuple(
            tuple(float(value) for value in row) for row in selection.channel
        ),
        decoder=tuple(int(value) for value in selection.decoder),
        confidence_event=event,
        failure_on_confidence_event=failure_on_event,
    )


def run_replicate(
    payload: tuple[int, int, Scenario, float, Selection]
) -> list[ReplicateResult]:
    seed, n, scenario, delta, oracle = payload
    rng = np.random.default_rng(seed)
    selection_n = n // 2
    certification_n = n - selection_n
    selection_empirical = empirical_table(rng, scenario.population, selection_n)
    certification_empirical = empirical_table(
        rng, scenario.population, certification_n
    )
    empirical = (
        selection_n * selection_empirical
        + certification_n * certification_empirical
    ) / n
    radii = simultaneous_radii(
        n,
        label_count=empirical.shape[0],
        source_count=empirical.shape[1],
        fine_count=empirical.shape[2],
        delta=delta,
    )
    event = confidence_event(empirical, scenario.population, radii)

    plugin_solution = optimize_population_external_channel(
        empirical,
        common_channels_by_label=scenario.libraries,
        contaminations=scenario.contaminations,
        privacy_advantage_thresholds=scenario.privacy_thresholds,
        released_token_count=scenario.released_token_count,
    )
    plugin = selection_from_population_solution(plugin_solution)
    output = [
        result_for_selection(
            seed=seed,
            n=n,
            method="always_deploy_plugin",
            scenario=scenario,
            selection=plugin,
            deployed=True,
            event=None,
        ),
        result_for_selection(
            seed=seed,
            n=n,
            method="plugin_continuum",
            scenario=scenario,
            selection=plugin,
            deployed=plugin.criterion <= scenario.utility_threshold + 1e-10,
            event=None,
        ),
    ]

    selected_solution = optimize_population_external_channel(
        selection_empirical,
        common_channels_by_label=scenario.libraries,
        contaminations=scenario.contaminations,
        privacy_advantage_thresholds=scenario.privacy_thresholds,
        released_token_count=scenario.released_token_count,
    )
    heldout = selection_from_population_solution(selected_solution)
    heldout_deployed, heldout_criterion, heldout_event = (
        fixed_channel_certified_selection(
            certification_empirical,
            scenario,
            heldout,
            n=certification_n,
            delta=delta,
        )
    )
    heldout = Selection(heldout.channel, heldout.decoder, heldout_criterion)
    output.append(
        result_for_selection(
            seed=seed,
            n=n,
            method="heldout_fixed_channel",
            scenario=scenario,
            selection=heldout,
            deployed=heldout_deployed,
            event=heldout_event,
        )
    )

    ltt, ltt_event = finite_ltt_selection(empirical, scenario, n=n, delta=delta)
    output.append(
        result_for_selection(
            seed=seed,
            n=n,
            method="finite_ltt",
            scenario=scenario,
            selection=ltt,
            deployed=ltt.criterion <= scenario.utility_threshold + 1e-10,
            event=ltt_event,
        )
    )

    deterministic = deterministic_selection(empirical, radii, scenario)
    output.append(
        result_for_selection(
            seed=seed,
            n=n,
            method="deterministic_mosaic",
            scenario=scenario,
            selection=deterministic,
            deployed=deterministic.criterion <= scenario.utility_threshold + 1e-10,
            event=event,
        )
    )

    identity_libraries = tuple(
        (np.eye(empirical.shape[2]),) for _ in range(empirical.shape[0])
    )
    shift_unaware_solution = optimize_invariant_channel(
        empirical,
        l1_radii=radii,
        common_channels_by_label=identity_libraries,
        contaminations=tuple(0.0 for _ in range(empirical.shape[0])),
        privacy_advantage_thresholds=scenario.privacy_thresholds,
        released_token_count=scenario.released_token_count,
    )
    shift_unaware = selection_from_mosaic_solution(shift_unaware_solution)
    output.append(
        result_for_selection(
            seed=seed,
            n=n,
            method="shift_unaware_mosaic",
            scenario=scenario,
            selection=shift_unaware,
            deployed=shift_unaware.criterion <= scenario.utility_threshold + 1e-10,
            event=None,
        )
    )

    mosaic_solution = optimize_invariant_channel(
        empirical,
        l1_radii=radii,
        common_channels_by_label=scenario.libraries,
        contaminations=scenario.contaminations,
        privacy_advantage_thresholds=scenario.privacy_thresholds,
        released_token_count=scenario.released_token_count,
    )
    mosaic = selection_from_mosaic_solution(mosaic_solution)
    output.append(
        result_for_selection(
            seed=seed,
            n=n,
            method="mosaic",
            scenario=scenario,
            selection=mosaic,
            deployed=mosaic.criterion <= scenario.utility_threshold + 1e-10,
            event=event,
        )
    )

    output.append(
        result_for_selection(
            seed=seed,
            n=n,
            method="population_oracle",
            scenario=scenario,
            selection=oracle,
            deployed=oracle.criterion <= scenario.utility_threshold + 1e-10,
            event=None,
        )
    )
    return output


def aggregate(results: Sequence[ReplicateResult]) -> list[dict[str, object]]:
    cells = []
    keys = sorted({(result.sample_size_per_stratum, result.method) for result in results})
    for n, method in keys:
        subset = [
            result
            for result in results
            if result.sample_size_per_stratum == n and result.method == method
        ]
        count = len(subset)
        deployments = sum(result.deployed for result in subset)
        false_acceptances = sum(result.false_acceptance for result in subset)
        safe_deployments = sum(result.deployed and result.exact_safe for result in subset)
        event_count = sum(result.confidence_event is True for result in subset)
        event_failures = sum(result.failure_on_confidence_event is True for result in subset)
        cells.append(
            {
                "sample_size_per_stratum": n,
                "method": method,
                "replicates": count,
                "deployments": deployments,
                "deployment_rate": deployments / count,
                "false_acceptances": false_acceptances,
                "false_acceptance_rate": false_acceptances / count,
                "safe_deployments": safe_deployments,
                "safe_deployment_rate": safe_deployments / count,
                "confidence_event_count": event_count,
                "failures_on_confidence_event": event_failures,
                "mean_exact_privacy_advantage": float(
                    np.mean([result.exact_worst_privacy_advantage for result in subset])
                ),
                "mean_exact_worst_error": float(
                    np.mean([result.exact_worst_conditional_error for result in subset])
                ),
                "mean_selection_criterion": float(
                    np.mean([result.selection_criterion for result in subset])
                ),
            }
        )
    return cells


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
    parser.add_argument("--replicates", type=int, default=20)
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument(
        "--sample-sizes", type=int, nargs="+", default=(250, 500, 1000)
    )
    parser.add_argument("--privacy-threshold", type=float, default=0.35)
    parser.add_argument("--utility-threshold", type=float, default=0.45)
    parser.add_argument("--contamination", type=float, default=0.10)
    parser.add_argument("--delta", type=float, default=0.05)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/artifacts/mosaic_synthetic_design_pilot_v0.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.replicates <= 0 or args.workers <= 0:
        raise ValueError("replicates and workers must be positive")
    if any(n < 2 for n in args.sample_sizes):
        raise ValueError("sample sizes must be at least two")
    if not 0.0 < args.delta < 1.0:
        raise ValueError("delta must lie in (0, 1)")
    scenario = witness_scenario(
        privacy_threshold=args.privacy_threshold,
        utility_threshold=args.utility_threshold,
        contamination=args.contamination,
    )
    oracle_solution = optimize_population_external_channel(
        scenario.population,
        common_channels_by_label=scenario.libraries,
        contaminations=scenario.contaminations,
        privacy_advantage_thresholds=scenario.privacy_thresholds,
        released_token_count=scenario.released_token_count,
    )
    oracle = selection_from_population_solution(oracle_solution)
    payloads = [
        (seed, n, scenario, args.delta, oracle)
        for n in args.sample_sizes
        for seed in range(args.seed_start, args.seed_start + args.replicates)
    ]
    if args.workers == 1:
        nested_results = [run_replicate(payload) for payload in payloads]
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            nested_results = list(executor.map(run_replicate, payloads))
    results = [result for group in nested_results for result in group]
    output: dict[str, object] = {
        "name": "MOSAIC v2 disclosed synthetic design pilot v0",
        "status": "pilot_only_excluded_from_confirmatory_results",
        "scenario": {
            "name": scenario.name,
            "population": scenario.population.tolist(),
            "common_transform_libraries": [
                [transform.tolist() for transform in library]
                for library in scenario.libraries
            ],
            "contaminations": list(scenario.contaminations),
            "privacy_advantage_thresholds": list(scenario.privacy_thresholds),
            "utility_threshold": scenario.utility_threshold,
            "released_token_count": scenario.released_token_count,
        },
        "delta": args.delta,
        "seed_start": args.seed_start,
        "replicates_per_sample_size": args.replicates,
        "sample_sizes_per_stratum": list(args.sample_sizes),
        "methods": list(METHODS),
        "cells": aggregate(results),
        "replicate_results": [asdict(result) for result in results],
        "scope": (
            "Disclosed pilot for bounded scenario/threshold selection. Every "
            "selected release is graded by exact population external risk. "
            "Seeds in this artifact are barred from confirmation."
        ),
    }
    atomic_json_dump(output, args.output)
    print(json.dumps({key: value for key, value in output.items() if key != "replicate_results"}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
