#!/usr/bin/env python3
"""Compute a concentration-based upper envelope on MOSAIC abstention."""

from __future__ import annotations

import argparse
import json
from math import exp
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from scipy.stats import norm

from mosaic_envelope import weissman_l1_radius
from mosaic_optimizer import optimize_invariant_channel
from run_mosaic_synthetic_confirmation import (
    DEFAULT_PREREG,
    DEFAULT_SIDECAR,
    scenario_from_config,
    verify_lock,
)


DEFAULT_OUTPUT = Path(
    "research/artifacts/mosaic_synthetic_theory_curve_v1.json"
)


def best_criterion(
    population: np.ndarray,
    *,
    radius: float,
    scenario,
) -> float:
    radii = np.full(population.shape[:2], radius, dtype=np.float64)
    solution = optimize_invariant_channel(
        population,
        l1_radii=radii,
        common_channels_by_label=scenario.libraries,
        contaminations=scenario.contaminations,
        privacy_advantage_thresholds=scenario.privacy_thresholds,
        released_token_count=scenario.released_token_count,
    )
    return float(solution.certified_worst_conditional_error)


def local_active_set_power(
    population: np.ndarray,
    *,
    radius: float,
    scenario,
    n: int,
    base_criterion: float,
    finite_difference_step: float = 1e-4,
) -> dict[str, object]:
    """Delta-method deployment power under a locally stable optimizer basis."""

    label_count, source_count, fine_count = population.shape

    def gradient(step_scale: float) -> np.ndarray:
        result = np.zeros_like(population)
        for label in range(label_count):
            for source in range(source_count):
                reference = fine_count - 1
                for token in range(fine_count - 1):
                    maximum_step = 0.25 * min(
                        population[label, source, token],
                        population[label, source, reference],
                    )
                    step = min(finite_difference_step * step_scale, maximum_step)
                    if step <= 0.0:
                        raise ValueError(
                            "central simplex sensitivity requires positive "
                            "registered cell probabilities"
                        )
                    direction = np.zeros_like(population)
                    direction[label, source, token] = 1.0
                    direction[label, source, reference] = -1.0
                    upper = best_criterion(
                        population + step * direction,
                        radius=radius,
                        scenario=scenario,
                    )
                    lower = best_criterion(
                        population - step * direction,
                        radius=radius,
                        scenario=scenario,
                    )
                    result[label, source, token] = (upper - lower) / (2.0 * step)
        return result

    gradient_full = gradient(1.0)
    half_step_gradient = gradient(0.5)
    stability = float(np.max(np.abs(gradient_full - half_step_gradient)))
    variance_coefficient = 0.0
    for label in range(label_count):
        for source in range(source_count):
            probabilities = population[label, source]
            covariance = np.diag(probabilities) - np.outer(
                probabilities, probabilities
            )
            local_gradient = gradient_full[label, source]
            variance_coefficient += float(
                local_gradient @ covariance @ local_gradient
            )
    standard_error = float(np.sqrt(max(0.0, variance_coefficient) / n))
    margin = float(scenario.utility_threshold - base_criterion)
    if standard_error <= 1e-15:
        predicted_deployment = float(margin >= 0.0)
        z_score = None
    else:
        z_score = margin / standard_error
        predicted_deployment = float(norm.cdf(z_score))
    return {
        "population_centered_utility_margin": margin,
        "local_gradient_variance_coefficient": variance_coefficient,
        "local_asymptotic_standard_error": standard_error,
        "local_asymptotic_z_score": z_score,
        "local_asymptotic_deployment_probability": predicted_deployment,
        "finite_difference_step": finite_difference_step,
        "finite_difference_gradient_stability": stability,
        "active_set_stability_pass": stability <= 5e-3,
        "approximation": (
            "If the selected MILP branch is locally unique and the resulting "
            "parametric LP is strongly regular, its value is differentiable "
            "at the population table. The stratified multinomial CLT and delta "
            "method then give the reported Gaussian deployment probability. "
            "This is a preregistered approximation, not a finite-sample "
            "coverage guarantee."
        ),
    }


def curve_cell(
    scenario_config: dict[str, object],
    population_config: dict[str, object],
    *,
    n: int,
    delta: float,
) -> dict[str, object]:
    scenario = scenario_from_config(scenario_config, population_config)
    label_count, source_count, fine_count = scenario.population.shape
    stratum_count = label_count * source_count
    registered_radius = weissman_l1_radius(
        n, fine_count, delta / stratum_count
    )
    registered_criterion = best_criterion(
        scenario.population,
        radius=registered_radius,
        scenario=scenario,
    )
    base_feasible = registered_criterion <= scenario.utility_threshold + 1e-10
    additional_radius = 0.0
    boundary_criterion = registered_criterion

    if base_feasible:
        low = 0.0
        high = max(0.0, 2.0 - registered_radius)
        high_criterion = best_criterion(
            scenario.population,
            radius=registered_radius + high,
            scenario=scenario,
        )
        if high_criterion <= scenario.utility_threshold + 1e-10:
            low = high
            boundary_criterion = high_criterion
        else:
            for _ in range(45):
                midpoint = 0.5 * (low + high)
                criterion = best_criterion(
                    scenario.population,
                    radius=registered_radius + midpoint,
                    scenario=scenario,
                )
                if criterion <= scenario.utility_threshold + 1e-10:
                    low = midpoint
                    boundary_criterion = criterion
                else:
                    high = midpoint
            additional_radius = max(0.0, low - 1e-10)
        if low == high:
            additional_radius = low

    prefactor = stratum_count * ((1 << fine_count) - 2)
    abstention_upper = min(
        1.0,
        prefactor * exp(-n * additional_radius * additional_radius / 2.0),
    )
    power = local_active_set_power(
        scenario.population,
        radius=registered_radius,
        scenario=scenario,
        n=n,
        base_criterion=registered_criterion,
    )
    return {
        "scenario": scenario_config["name"],
        "sample_size_per_stratum": n,
        "registered_l1_radius": registered_radius,
        "population_centered_registered_criterion": registered_criterion,
        "population_centered_registered_deploys": base_feasible,
        "maximum_certified_center_deviation": additional_radius,
        "boundary_criterion": boundary_criterion,
        "concentration_abstention_upper": abstention_upper,
        "derivation": (
            "If ||p_hat-p||_1<=r in every stratum, each radius-epsilon ball "
            "around p_hat lies inside the radius-(epsilon+r) ball around p. "
            "Feasibility of the population-centered enlarged problem therefore "
            "forces the adaptive optimizer to deploy. Weissman plus a stratum "
            "union bound controls the complement."
        ),
        **power,
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
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    config, prereg_hash = verify_lock(args.prereg, args.sidecar)
    delta = float(config["delta"])
    cells = [
        curve_cell(scenario, config["population"], n=int(n), delta=delta)
        for scenario in config["scenarios"]
        for n in scenario["sample_sizes_per_stratum"]
    ]
    payload: dict[str, object] = {
        "name": "MOSAIC preregistered abstention theory curve v1",
        "status": "locked_preconfirmation_theory_prediction",
        "preregistration_sha256": prereg_hash,
        "delta": delta,
        "cells": cells,
        "scope": (
            "Outcome-free finite-sample abstention envelope and local active-set "
            "delta-method power curve computed from locked population laws."
        ),
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
