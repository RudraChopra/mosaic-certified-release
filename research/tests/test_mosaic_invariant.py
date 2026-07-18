from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "mosaic"
sys.path.insert(0, str(SCRIPTS))

from mosaic_channel import (  # noqa: E402
    adaptive_channel_attacker_confidence_bound,
    population_balanced_attacker_accuracy,
)
from mosaic_invariant import (  # noqa: E402
    adaptive_pre_release_attacker_certificate,
    apply_pre_release_shift,
    differential_shift_capacity,
    dobrushin_coefficient,
    pre_release_utility_certificate,
)


def test_binary_differential_capacity_is_exactly_dobrushin() -> None:
    release = np.asarray(
        [[0.90, 0.10], [0.55, 0.45], [0.15, 0.85]], dtype=np.float64
    )
    capacity = differential_shift_capacity(release, source_count=2)
    assert capacity.normalized_advantage == pytest.approx(
        dobrushin_coefficient(release)
    )


def test_full_simplex_reference_envelope_equals_channel_capacity() -> None:
    empirical = np.asarray(
        [[0.70, 0.20, 0.10], [0.15, 0.35, 0.50]], dtype=np.float64
    )
    release = np.asarray(
        [[0.82, 0.18], [0.48, 0.52], [0.12, 0.88]], dtype=np.float64
    )
    envelope = adaptive_channel_attacker_confidence_bound(
        empirical, release, l1_radii=(2.0, 2.0)
    )
    capacity = differential_shift_capacity(release, source_count=2)
    assert envelope.balanced_accuracy == pytest.approx(capacity.balanced_accuracy)


def test_selected_channel_certificate_covers_pre_release_shift() -> None:
    truth = np.asarray(
        [[0.62, 0.28, 0.10], [0.48, 0.37, 0.15]], dtype=np.float64
    )
    empirical = np.asarray(
        [[0.58, 0.31, 0.11], [0.51, 0.33, 0.16]], dtype=np.float64
    )
    radii = tuple(float(np.abs(row_true - row_empirical).sum())
                  for row_true, row_empirical in zip(truth, empirical, strict=True))
    identity = np.eye(3)
    common = np.asarray(
        [[0.88, 0.12, 0.00], [0.08, 0.84, 0.08], [0.00, 0.14, 0.86]],
        dtype=np.float64,
    )
    candidates = (
        np.asarray([[0.95, 0.05], [0.55, 0.45], [0.10, 0.90]]),
        np.asarray([[0.75, 0.25], [0.50, 0.50], [0.30, 0.70]]),
        np.asarray([[0.60, 0.40], [0.52, 0.48], [0.42, 0.58]]),
    )
    certificates = tuple(
        adaptive_pre_release_attacker_certificate(
            empirical,
            candidate,
            l1_radii=radii,
            common_fine_token_channels=(identity, common),
            contamination=0.20,
        )
        for candidate in candidates
    )
    selected_index = min(
        range(len(candidates)),
        key=lambda index: certificates[index].balanced_accuracy,
    )
    selected = candidates[selected_index]
    certificate = certificates[selected_index]
    residuals = np.asarray(
        [[0.05, 0.20, 0.75], [0.75, 0.20, 0.05]], dtype=np.float64
    )
    _, external_released = apply_pre_release_shift(
        truth,
        common,
        residuals,
        selected,
        retained_common_mass=0.80,
    )
    actual = population_balanced_attacker_accuracy(external_released)
    assert actual <= certificate.balanced_accuracy + 1e-12


def test_shifted_utility_certificate_covers_selected_decoder() -> None:
    truth = np.asarray([0.60, 0.30, 0.10], dtype=np.float64)
    empirical = np.asarray([0.56, 0.32, 0.12], dtype=np.float64)
    radius = float(np.abs(truth - empirical).sum())
    release = np.asarray(
        [[0.92, 0.08], [0.58, 0.42], [0.18, 0.82]], dtype=np.float64
    )
    common = np.asarray(
        [[0.90, 0.10, 0.00], [0.05, 0.90, 0.05], [0.00, 0.10, 0.90]],
        dtype=np.float64,
    )
    decoder = (0, 1)
    certificate = pre_release_utility_certificate(
        empirical,
        release,
        decoder,
        true_label=0,
        l1_radius=radius,
        common_fine_token_channels=(np.eye(3), common),
        contamination=0.15,
    )
    residual = np.asarray([0.05, 0.10, 0.85], dtype=np.float64)
    external = (0.85 * (truth @ common) + 0.15 * residual) @ release
    actual_error = float(external[1])
    assert actual_error <= certificate.error_probability + 1e-12


def test_task_utility_lower_bounds_arbitrary_shift_leakage() -> None:
    release = np.asarray([[0.91, 0.09], [0.18, 0.82]], dtype=np.float64)
    first_label_error = float(release[0, 1])
    second_label_error = float(release[1, 0])
    required_advantage = 1.0 - first_label_error - second_label_error
    assert dobrushin_coefficient(release) >= required_advantage - 1e-12
