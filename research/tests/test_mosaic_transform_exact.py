from __future__ import annotations

import numpy as np

from mosaic_exact import exact_external_attacker_risk, exact_external_utility_risk
from mosaic_invariant import (
    adaptive_pre_release_attacker_certificate,
    pre_release_utility_certificate,
)
from mosaic_transform_exact import (
    transform_exact_attacker_confidence_bound,
    transform_exact_utility_confidence_bound,
)


def _problem() -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, ...]]:
    empirical = np.asarray([[0.72, 0.18, 0.10], [0.42, 0.43, 0.15]])
    release = np.asarray([[0.95, 0.05], [0.35, 0.65], [0.10, 0.90]])
    smoothing = np.asarray(
        [[0.9, 0.1, 0.0], [0.05, 0.9, 0.05], [0.0, 0.1, 0.9]]
    )
    return empirical, release, (np.eye(3), smoothing)


def test_zero_radius_matches_exact_population_attacker_risk() -> None:
    empirical, release, transforms = _problem()
    certificate = transform_exact_attacker_confidence_bound(
        empirical,
        release,
        l1_radii=(0.0, 0.0),
        common_fine_token_channels=transforms,
        contamination=0.17,
    )
    exact = exact_external_attacker_risk(
        empirical,
        release,
        transforms,
        contamination=0.17,
    )
    assert abs(certificate.balanced_accuracy - exact.balanced_accuracy) < 1e-12
    assert certificate.worst_transform_index == exact.worst_transform_index
    assert certificate.maximizing_assignment == exact.maximizing_assignment


def test_zero_radius_matches_exact_population_utility_risk() -> None:
    empirical, release, transforms = _problem()
    certificate = transform_exact_utility_confidence_bound(
        empirical[0],
        release,
        (0, 1),
        true_label=0,
        l1_radius=0.0,
        common_fine_token_channels=transforms,
        contamination=0.17,
    )
    exact = exact_external_utility_risk(
        empirical[0],
        release,
        (0, 1),
        true_label=0,
        common_fine_token_channels=transforms,
        contamination=0.17,
    )
    assert abs(certificate.error_probability - exact.error_probability) < 1e-12
    assert certificate.worst_transform_index == exact.worst_transform_index


def test_transform_exact_attacker_bound_dominates_capacity_transfer() -> None:
    empirical, release, transforms = _problem()
    exact = transform_exact_attacker_confidence_bound(
        empirical,
        release,
        l1_radii=(0.22, 0.19),
        common_fine_token_channels=transforms,
        contamination=0.17,
    )
    transfer = adaptive_pre_release_attacker_certificate(
        empirical,
        release,
        l1_radii=(0.22, 0.19),
        common_fine_token_channels=transforms,
        contamination=0.17,
    )
    assert exact.balanced_accuracy <= transfer.balanced_accuracy + 1e-12


def test_transform_exact_utility_bound_dominates_capacity_transfer() -> None:
    empirical, release, transforms = _problem()
    exact = transform_exact_utility_confidence_bound(
        empirical[0],
        release,
        (0, 1),
        true_label=0,
        l1_radius=0.22,
        common_fine_token_channels=transforms,
        contamination=0.17,
    )
    transfer = pre_release_utility_certificate(
        empirical[0],
        release,
        (0, 1),
        true_label=0,
        l1_radius=0.22,
        common_fine_token_channels=transforms,
        contamination=0.17,
    )
    assert exact.error_probability <= transfer.error_probability + 1e-12


def test_binary_confidence_supremum_matches_endpoint_enumeration() -> None:
    empirical = np.asarray([[0.63, 0.37], [0.44, 0.56]])
    release = np.asarray([[0.88, 0.12], [0.21, 0.79]])
    transforms = (
        np.eye(2),
        np.asarray([[0.8, 0.2], [0.1, 0.9]]),
    )
    radii = (0.24, 0.18)
    eta = 0.13
    certificate = transform_exact_attacker_confidence_bound(
        empirical,
        release,
        l1_radii=radii,
        common_fine_token_channels=transforms,
        contamination=eta,
    )

    endpoints = []
    for source in range(2):
        half = radii[source] / 2.0
        low = max(0.0, empirical[source, 0] - half)
        high = min(1.0, empirical[source, 0] + half)
        endpoints.append((np.asarray([low, 1.0 - low]), np.asarray([high, 1.0 - high])))

    brute = -1.0
    for first in endpoints[0]:
        for second in endpoints[1]:
            risk = exact_external_attacker_risk(
                (first, second),
                release,
                transforms,
                contamination=eta,
            )
            brute = max(brute, risk.balanced_accuracy)
    assert abs(certificate.balanced_accuracy - brute) < 1e-12


def test_randomized_dominance_and_zero_radius_exactness() -> None:
    rng = np.random.default_rng(91827)
    for _ in range(100):
        empirical = rng.dirichlet(np.ones(3), size=2)
        release = rng.dirichlet(np.ones(2), size=3)
        transforms = (np.eye(3), rng.dirichlet(np.ones(3), size=3))
        radii = tuple(rng.uniform(0.0, 0.5, size=2))
        eta = float(rng.uniform(0.0, 0.4))

        exact = transform_exact_attacker_confidence_bound(
            empirical,
            release,
            l1_radii=radii,
            common_fine_token_channels=transforms,
            contamination=eta,
        )
        transfer = adaptive_pre_release_attacker_certificate(
            empirical,
            release,
            l1_radii=radii,
            common_fine_token_channels=transforms,
            contamination=eta,
        )
        assert exact.balanced_accuracy <= transfer.balanced_accuracy + 1e-11

        zero = transform_exact_attacker_confidence_bound(
            empirical,
            release,
            l1_radii=(0.0, 0.0),
            common_fine_token_channels=transforms,
            contamination=eta,
        )
        population = exact_external_attacker_risk(
            empirical,
            release,
            transforms,
            contamination=eta,
        )
        assert abs(zero.balanced_accuracy - population.balanced_accuracy) < 1e-11
