from __future__ import annotations

import numpy as np

from mosaic_channel import l1_ball_expectation_lower, l1_ball_expectation_upper
from mosaic_strict_certification import (
    certify_bridge_membership_strict,
    optimize_transform_exact_channel_strict,
)


def _tables() -> tuple[np.ndarray, np.ndarray]:
    reference = np.asarray(
        [
            [[0.62, 0.25, 0.08, 0.05], [0.12, 0.23, 0.30, 0.35]],
            [[0.08, 0.17, 0.28, 0.47], [0.45, 0.28, 0.17, 0.10]],
        ]
    )
    transform = np.asarray(
        [
            [0.90, 0.10, 0.00, 0.00],
            [0.05, 0.90, 0.05, 0.00],
            [0.00, 0.05, 0.90, 0.05],
            [0.00, 0.00, 0.10, 0.90],
        ]
    )
    bridge = reference @ transform
    return reference, bridge


def test_strict_bridge_has_nonnegative_recomputed_slack() -> None:
    reference, bridge = _tables()
    radii = np.full((2, 2), 0.02)
    certificate = certify_bridge_membership_strict(
        reference,
        reference_l1_radii=radii,
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=radii,
    )
    for label_index, label in enumerate(certificate.labels):
        assert label.minimum_membership_slack >= 0.0
        assert 0.0 <= label.retained_mass <= label.optimal_retained_mass_upper
        np.testing.assert_allclose(label.transform.sum(axis=1), 1.0, atol=1e-12)
        for source in range(2):
            for output in range(4):
                indicator = np.eye(4)[output]
                lower = l1_ball_expectation_lower(
                    bridge[label_index, source],
                    indicator,
                    l1_radius=radii[label_index, source],
                )
                upper = l1_ball_expectation_upper(
                    reference[label_index, source],
                    label.transform[:, output],
                    l1_radius=radii[label_index, source],
                )
                assert lower - label.retained_mass * upper >= 0.0


def test_strict_release_uses_tightened_constraint_and_outward_values() -> None:
    reference, bridge = _tables()
    radii = np.full((2, 2), 0.01)
    membership = certify_bridge_membership_strict(
        reference,
        reference_l1_radii=radii,
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=radii,
    )
    result = optimize_transform_exact_channel_strict(
        reference,
        l1_radii=radii,
        common_channels_by_label=membership.transforms_by_label,
        contaminations=membership.contaminations,
        source_advantage_thresholds=(0.80, 0.80),
        released_token_count=2,
    )
    assert max(result.certified_source_advantage_upper) <= 0.80
    assert result.certified_worst_conditional_error_upper >= (
        result.unguarded_worst_conditional_error
    )
    assert all(
        upper >= raw
        for upper, raw in zip(
            result.certified_source_advantage_upper,
            result.unguarded_source_advantages,
            strict=True,
        )
    )
    assert all(value < 0.80 for value in result.optimization_source_thresholds)


def test_missing_bridge_support_still_forces_zero_retention() -> None:
    reference, bridge = _tables()
    radii = np.full((2, 2), 0.02)
    bridge[0, 1] = 0.25
    target_radii = radii.copy()
    target_radii[0, 1] = 2.0
    certificate = certify_bridge_membership_strict(
        reference,
        reference_l1_radii=radii,
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=target_radii,
    )
    assert certificate.labels[0].retained_mass == 0.0
