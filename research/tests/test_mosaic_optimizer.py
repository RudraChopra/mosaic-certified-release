from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "mosaic"
sys.path.insert(0, str(SCRIPTS))

from mosaic_invariant import (  # noqa: E402
    adaptive_pre_release_attacker_certificate,
    pre_release_utility_certificate,
)
from mosaic_optimizer import (  # noqa: E402
    optimize_invariant_channel,
    optimize_population_external_channel,
)


def _witness_problem() -> tuple[
    np.ndarray,
    np.ndarray,
    tuple[tuple[np.ndarray, ...], ...],
    tuple[float, ...],
    tuple[float, ...],
]:
    empirical = np.asarray(
        [
            [[0.80, 0.15, 0.05], [0.65, 0.30, 0.05]],
            [[0.05, 0.20, 0.75], [0.05, 0.35, 0.60]],
        ],
        dtype=np.float64,
    )
    radii = np.full((2, 2), 0.08)
    identity = np.eye(3)
    common = np.asarray(
        [[0.90, 0.10, 0.00], [0.05, 0.90, 0.05], [0.00, 0.10, 0.90]],
        dtype=np.float64,
    )
    return (
        empirical,
        radii,
        ((identity, common), (identity, common)),
        (0.10, 0.10),
        (0.35, 0.35),
    )


def _evaluate(
    empirical: np.ndarray,
    radii: np.ndarray,
    libraries: tuple[tuple[np.ndarray, ...], ...],
    contaminations: tuple[float, ...],
    thresholds: tuple[float, ...],
    channel: np.ndarray,
    decoder: tuple[int, ...],
) -> float | None:
    privacy = tuple(
        adaptive_pre_release_attacker_certificate(
            empirical[label],
            channel,
            l1_radii=radii[label],
            common_fine_token_channels=libraries[label],
            contamination=contaminations[label],
        )
        for label in range(2)
    )
    if any(
        certificate.normalized_advantage > thresholds[label] + 1e-9
        for label, certificate in enumerate(privacy)
    ):
        return None
    return max(
        pre_release_utility_certificate(
            empirical[label, source],
            channel,
            decoder,
            true_label=label,
            l1_radius=float(radii[label, source]),
            common_fine_token_channels=libraries[label],
            contamination=contaminations[label],
        ).error_probability
        for label in range(2)
        for source in range(2)
    )


def test_optimizer_matches_posthoc_certificates_and_privacy_contract() -> None:
    empirical, radii, libraries, contaminations, thresholds = _witness_problem()
    solution = optimize_invariant_channel(
        empirical,
        l1_radii=radii,
        common_channels_by_label=libraries,
        contaminations=contaminations,
        privacy_advantage_thresholds=thresholds,
        released_token_count=2,
    )
    assert solution.solver_status.startswith("Optimization terminated successfully")
    assert solution.solver_objective == pytest.approx(
        solution.certified_worst_conditional_error, abs=3e-7
    )
    assert solution.max_constraint_violation <= 3e-7
    assert solution.solver_mip_gap <= 1e-10
    assert solution.solver_mip_feasibility_tolerance == pytest.approx(1e-9)
    assert solution.solver_dual_bound == pytest.approx(
        solution.solver_objective, abs=3e-7
    )
    assert all(
        certificate.normalized_advantage <= thresholds[label] + 3e-7
        for label, certificate in enumerate(solution.privacy_certificates)
    )


def test_stochastic_solution_strictly_beats_every_deterministic_channel() -> None:
    empirical, radii, libraries, contaminations, thresholds = _witness_problem()
    solution = optimize_invariant_channel(
        empirical,
        l1_radii=radii,
        common_channels_by_label=libraries,
        contaminations=contaminations,
        privacy_advantage_thresholds=thresholds,
        released_token_count=2,
    )
    deterministic_best = 1.0
    for outputs in product(range(2), repeat=3):
        channel = np.zeros((3, 2), dtype=np.float64)
        channel[np.arange(3), outputs] = 1.0
        for decoder in product(range(2), repeat=2):
            value = _evaluate(
                empirical,
                radii,
                libraries,
                contaminations,
                thresholds,
                channel,
                decoder,
            )
            if value is not None:
                deterministic_best = min(deterministic_best, value)
    assert np.any(
        (solution.release_channel > 1e-7)
        & (solution.release_channel < 1.0 - 1e-7)
    )
    assert solution.certified_worst_conditional_error < deterministic_best - 0.10


def test_optimizer_abstains_when_registered_utility_is_impossible() -> None:
    empirical = np.full((2, 2, 2), 0.5)
    radii = np.full((2, 2), 2.0)
    identity = np.eye(2)
    with pytest.raises(RuntimeError, match="ABSTAIN_NO_FEASIBLE_CHANNEL"):
        optimize_invariant_channel(
            empirical,
            l1_radii=radii,
            common_channels_by_label=((identity,), (identity,)),
            contaminations=(0.0, 0.0),
            privacy_advantage_thresholds=(0.0, 0.0),
            released_token_count=2,
            maximum_worst_conditional_error=0.49,
        )


def test_population_optimizer_matches_exact_external_evaluator() -> None:
    empirical, _, libraries, contaminations, thresholds = _witness_problem()
    solution = optimize_population_external_channel(
        empirical,
        common_channels_by_label=libraries,
        contaminations=contaminations,
        privacy_advantage_thresholds=thresholds,
        released_token_count=2,
    )
    assert solution.solver_objective == pytest.approx(
        solution.exact_worst_conditional_error, abs=3e-7
    )
    assert solution.max_constraint_violation <= 3e-7
    assert all(
        risk.normalized_advantage <= thresholds[label] + 3e-7
        for label, risk in enumerate(solution.privacy_risks)
    )
