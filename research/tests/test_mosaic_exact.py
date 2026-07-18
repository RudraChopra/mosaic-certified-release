from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "mosaic"
sys.path.insert(0, str(SCRIPTS))

from mosaic_channel import population_balanced_attacker_accuracy  # noqa: E402
from mosaic_exact import (  # noqa: E402
    exact_external_attacker_risk,
    exact_external_utility_risk,
)
from mosaic_invariant import (  # noqa: E402
    adaptive_pre_release_attacker_certificate,
    differential_shift_capacity,
)


def test_exact_attacker_risk_matches_all_residual_vertices() -> None:
    reference = np.asarray(
        [[0.72, 0.20, 0.08], [0.54, 0.34, 0.12]], dtype=np.float64
    )
    release = np.asarray(
        [[0.90, 0.10], [0.52, 0.48], [0.16, 0.84]], dtype=np.float64
    )
    transform = np.asarray(
        [[0.90, 0.10, 0.00], [0.05, 0.90, 0.05], [0.00, 0.10, 0.90]],
        dtype=np.float64,
    )
    eta = 0.20
    exact = exact_external_attacker_risk(
        reference, release, (transform,), contamination=eta
    )
    brute = 0.0
    for residual_tokens in product(range(3), repeat=2):
        external = []
        for source, token in enumerate(residual_tokens):
            residual = np.zeros(3)
            residual[token] = 1.0
            external.append(
                ((1.0 - eta) * (reference[source] @ transform) + eta * residual)
                @ release
            )
        brute = max(brute, population_balanced_attacker_accuracy(external))
    assert exact.balanced_accuracy == pytest.approx(brute)


def test_exact_risk_is_below_same_model_certificate() -> None:
    truth = np.asarray(
        [[0.72, 0.20, 0.08], [0.54, 0.34, 0.12]], dtype=np.float64
    )
    empirical = np.asarray(
        [[0.68, 0.23, 0.09], [0.57, 0.30, 0.13]], dtype=np.float64
    )
    radii = tuple(
        float(np.abs(true_row - empirical_row).sum())
        for true_row, empirical_row in zip(truth, empirical, strict=True)
    )
    release = np.asarray(
        [[0.90, 0.10], [0.52, 0.48], [0.16, 0.84]], dtype=np.float64
    )
    transform = np.asarray(
        [[0.90, 0.10, 0.00], [0.05, 0.90, 0.05], [0.00, 0.10, 0.90]],
        dtype=np.float64,
    )
    exact = exact_external_attacker_risk(
        truth, release, (np.eye(3), transform), contamination=0.20
    )
    certificate = adaptive_pre_release_attacker_certificate(
        empirical,
        release,
        l1_radii=radii,
        common_fine_token_channels=(np.eye(3), transform),
        contamination=0.20,
    )
    assert exact.balanced_accuracy <= certificate.balanced_accuracy + 1e-12


def test_full_differential_shift_equals_channel_capacity() -> None:
    reference = np.asarray([[0.8, 0.2], [0.3, 0.7]], dtype=np.float64)
    release = np.asarray([[0.88, 0.12], [0.21, 0.79]], dtype=np.float64)
    exact = exact_external_attacker_risk(
        reference, release, (np.eye(2),), contamination=1.0
    )
    capacity = differential_shift_capacity(release, source_count=2)
    assert exact.balanced_accuracy == pytest.approx(capacity.balanced_accuracy)


def test_exact_utility_risk_selects_worst_transform_and_residual() -> None:
    reference = np.asarray([0.75, 0.20, 0.05], dtype=np.float64)
    release = np.asarray(
        [[0.94, 0.06], [0.56, 0.44], [0.18, 0.82]], dtype=np.float64
    )
    transform = np.asarray(
        [[0.85, 0.15, 0.00], [0.05, 0.90, 0.05], [0.00, 0.10, 0.90]],
        dtype=np.float64,
    )
    exact = exact_external_utility_risk(
        reference,
        release,
        (0, 1),
        true_label=0,
        common_fine_token_channels=(np.eye(3), transform),
        contamination=0.10,
    )
    row_errors = release[:, 1]
    expected = max(
        0.9 * float(reference @ candidate @ row_errors)
        + 0.1 * float(np.max(row_errors))
        for candidate in (np.eye(3), transform)
    )
    assert exact.error_probability == pytest.approx(expected)
