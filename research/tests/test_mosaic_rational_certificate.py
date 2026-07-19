from __future__ import annotations

from fractions import Fraction

import numpy as np

from mosaic_rational_certificate import (
    RADIUS_OUTWARD_GUARD,
    audit_bridge_exact,
    audit_release_exact,
    empirical_from_counts,
    fraction_decimal,
    l1_expectation_lower_exact,
    l1_expectation_upper_exact,
)
from mosaic_strict_certification import certify_bridge_membership_strict


def _counts() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    reference = np.asarray(
        [
            [[62, 25, 8, 5], [12, 23, 30, 35]],
            [[8, 17, 28, 47], [45, 28, 17, 10]],
        ]
    )
    bridge = np.asarray(
        [
            [[58, 27, 10, 5], [14, 22, 29, 35]],
            [[9, 18, 29, 44], [43, 29, 18, 10]],
        ]
    )
    radii = np.full((2, 2), 0.05)
    return reference, bridge, radii


def test_exact_support_matches_simple_binary_solution() -> None:
    empirical = empirical_from_counts([3, 1])
    scores = (Fraction(0), Fraction(1))
    assert l1_expectation_upper_exact(
        empirical, scores, radius=Fraction(1, 2)
    ) == Fraction(1, 2)
    assert l1_expectation_lower_exact(
        empirical, scores, radius=Fraction(1, 2)
    ) == 0


def test_rational_bridge_and_release_verify_strict_float_certificate() -> None:
    reference_counts, bridge_counts, radii = _counts()
    reference = reference_counts / reference_counts.sum(axis=2, keepdims=True)
    target = bridge_counts / bridge_counts.sum(axis=2, keepdims=True)
    strict = certify_bridge_membership_strict(
        reference,
        reference_l1_radii=radii + float(RADIUS_OUTWARD_GUARD),
        bridge_empirical_distributions=target,
        bridge_l1_radii=radii + float(RADIUS_OUTWARD_GUARD),
    )
    labels = [
        {
            "transform": label.transform.tolist(),
            "retained_mass": label.retained_mass,
        }
        for label in strict.labels
    ]
    bridge = audit_bridge_exact(
        reference_counts,
        bridge_counts,
        reference_l1_radii=radii,
        bridge_l1_radii=radii,
        serialized_labels=labels,
    )
    assert bridge.minimum_membership_slack >= 0

    release = audit_release_exact(
        reference_counts,
        reference_l1_radii=radii,
        bridge=bridge,
        release_channel=[[0.9, 0.1], [0.7, 0.3], [0.3, 0.7], [0.1, 0.9]],
        decoder=[0, 1],
    )
    assert len(release.source_advantages) == 2
    assert all(Fraction(0) <= value <= Fraction(1) for value in release.source_advantages)
    assert Fraction(0) <= release.worst_conditional_error <= Fraction(1)


def test_upward_decimal_never_rounds_down() -> None:
    value = Fraction(1, 3)
    rendered = fraction_decimal(value, digits=8)
    assert Fraction(rendered) >= value
    assert rendered == "0.33333334"
