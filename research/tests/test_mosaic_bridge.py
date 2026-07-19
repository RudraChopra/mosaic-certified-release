from __future__ import annotations

import numpy as np
import pytest

from mosaic_bridge import certify_bridge_membership


def base_distributions() -> np.ndarray:
    return np.asarray(
        [
            [[0.70, 0.20, 0.10], [0.10, 0.30, 0.60]],
            [[0.20, 0.50, 0.30], [0.40, 0.40, 0.20]],
        ],
        dtype=np.float64,
    )


def test_identity_shift_recovers_unit_retained_mass() -> None:
    probabilities = base_distributions()
    certificate = certify_bridge_membership(
        probabilities,
        reference_l1_radii=np.zeros((2, 2)),
        bridge_empirical_distributions=probabilities,
        bridge_l1_radii=np.zeros((2, 2)),
    )
    assert min(certificate.retained_masses) >= 1.0 - 2e-7
    for label in certificate.labels:
        assert np.allclose(label.transform, np.eye(3), atol=1e-8)
        assert label.minimum_membership_slack >= -1e-10


def test_known_common_transform_is_certified() -> None:
    reference = base_distributions()
    transform = np.asarray(
        [[0.8, 0.2, 0.0], [0.1, 0.7, 0.2], [0.0, 0.3, 0.7]],
        dtype=np.float64,
    )
    bridge = reference @ transform
    certificate = certify_bridge_membership(
        reference,
        reference_l1_radii=np.zeros((2, 2)),
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=np.zeros((2, 2)),
    )
    assert min(certificate.retained_masses) >= 1.0 - 2e-7
    for label_index, label in enumerate(certificate.labels):
        pushed = reference[label_index] @ label.transform
        assert np.all(bridge[label_index] >= label.retained_mass * pushed - 1e-9)


def test_confidence_certificate_implies_structured_membership() -> None:
    reference = base_distributions()
    transform = np.asarray(
        [[0.85, 0.15, 0.0], [0.05, 0.85, 0.10], [0.0, 0.20, 0.80]],
        dtype=np.float64,
    )
    residual = np.asarray(
        [
            [[0.1, 0.2, 0.7], [0.6, 0.2, 0.2]],
            [[0.3, 0.4, 0.3], [0.2, 0.7, 0.1]],
        ]
    )
    bridge = 0.8 * (reference @ transform) + 0.2 * residual
    certificate = certify_bridge_membership(
        reference,
        reference_l1_radii=np.full((2, 2), 0.04),
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=np.full((2, 2), 0.04),
    )
    for label_index, label in enumerate(certificate.labels):
        pushed = reference[label_index] @ label.transform
        difference = bridge[label_index] - label.retained_mass * pushed
        assert np.min(difference) >= -1e-9
        if label.contamination > 1e-12:
            reconstructed_residual = difference / label.contamination
            assert np.all(reconstructed_residual >= -1e-9)
            assert np.allclose(reconstructed_residual.sum(axis=1), 1.0, atol=1e-8)


def test_vacuous_bridge_regions_force_zero_retention() -> None:
    reference = base_distributions()
    bridge = np.full_like(reference, 1.0 / reference.shape[-1])
    certificate = certify_bridge_membership(
        reference,
        reference_l1_radii=np.zeros((2, 2)),
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=np.full((2, 2), 2.0),
    )
    assert max(certificate.retained_masses) == 0.0
    assert min(certificate.contaminations) == 1.0


def test_global_retained_mass_dominates_binary_grid() -> None:
    reference_label = np.asarray([[0.8, 0.2], [0.3, 0.7]])
    bridge_label = np.asarray([[0.62, 0.38], [0.34, 0.66]])
    reference = np.stack((reference_label, reference_label))
    bridge = np.stack((bridge_label, bridge_label))
    certificate = certify_bridge_membership(
        reference,
        reference_l1_radii=np.zeros((2, 2)),
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=np.zeros((2, 2)),
    )
    grid_best = 0.0
    for first in np.linspace(0.0, 1.0, 101):
        for second in np.linspace(0.0, 1.0, 101):
            transform = np.asarray([[first, 1.0 - first], [second, 1.0 - second]])
            pushed = reference_label @ transform
            ratios = np.divide(
                bridge_label,
                pushed,
                out=np.full_like(bridge_label, np.inf),
                where=pushed > 1e-12,
            )
            grid_best = max(grid_best, min(1.0, float(np.min(ratios))))
    assert certificate.labels[0].optimal_retained_mass_upper >= grid_best - 1e-8
    assert certificate.labels[0].retained_mass >= grid_best - 2e-4


def test_output_is_stochastic_and_numerically_verified() -> None:
    rng = np.random.default_rng(2027)
    reference = rng.dirichlet(np.ones(4), size=(2, 2))
    bridge = rng.dirichlet(np.ones(4), size=(2, 2))
    certificate = certify_bridge_membership(
        reference,
        reference_l1_radii=np.full((2, 2), 0.08),
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=np.full((2, 2), 0.08),
    )
    for label in certificate.labels:
        assert np.all(label.transform >= 0.0)
        assert np.allclose(label.transform.sum(axis=1), 1.0, atol=1e-9)
        assert label.minimum_membership_slack >= -1e-7
        assert label.optimal_retained_mass_upper + 1e-12 >= label.retained_mass


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value[:, :, :2],
        lambda value: value * 0.5,
        lambda value: np.where(np.indices(value.shape)[-1] == 0, -0.1, value),
    ],
)
def test_invalid_bridge_inputs_are_rejected(mutation) -> None:
    reference = base_distributions()
    bridge = mutation(reference.copy())
    with pytest.raises(ValueError):
        certify_bridge_membership(
            reference,
            reference_l1_radii=np.zeros((2, 2)),
            bridge_empirical_distributions=bridge,
            bridge_l1_radii=np.zeros((2, 2)),
        )


def test_invalid_numerical_margin_is_rejected() -> None:
    probabilities = base_distributions()
    with pytest.raises(ValueError):
        certify_bridge_membership(
            probabilities,
            reference_l1_radii=np.zeros((2, 2)),
            bridge_empirical_distributions=probabilities,
            bridge_l1_radii=np.zeros((2, 2)),
            numerical_margin=0.0,
        )
