"""Numerically conservative wrappers for MOSAIC bridge and release certificates.

The mathematical certificates are real-valued inequalities.  Optimizers return
floating-point candidates, so claim-grade decisions use a second, independent
post-solve layer: bridge retained mass is contracted until every recomputed
membership inequality has nonnegative slack, release optimization uses a
tighter source-distinguishability constraint, and reported risk values are
rounded outward before comparison with the registered contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from mosaic_bridge import (
    BridgeLabelCertificate,
    BridgeMembershipCertificate,
    certify_bridge_membership,
)
from mosaic_channel import (
    l1_ball_expectation_lower,
    l1_ball_expectation_upper,
)
from mosaic_transform_exact import (
    transform_exact_attacker_confidence_bound,
    transform_exact_utility_confidence_bound,
)
from mosaic_transform_exact_optimizer import optimize_transform_exact_channel


DEFAULT_FEASIBILITY_GUARD = 1e-9
DEFAULT_OPTIMIZATION_GUARD = 1e-6
DEFAULT_VALUE_GUARD = 1e-9


@dataclass(frozen=True)
class StrictReleaseCertificate:
    """A globally optimized release for a numerically tightened program."""

    release_channel: np.ndarray
    decoder: tuple[int, ...]
    certified_source_advantage_upper: tuple[float, ...]
    certified_worst_conditional_error_upper: float
    unguarded_source_advantages: tuple[float, ...]
    unguarded_worst_conditional_error: float
    optimization_source_thresholds: tuple[float, ...]
    solver_objective: float
    solver_status: str
    solver_mip_gap: float
    solver_dual_bound: float
    max_constraint_violation: float
    solved_decoder_assignments: int
    feasibility_guard: float
    value_guard: float
    method: str


def _validate_guard(value: float, *, name: str, maximum: float) -> float:
    guard = float(value)
    if not np.isfinite(guard) or not 0.0 < guard < maximum:
        raise ValueError(f"{name} must lie in (0, {maximum})")
    return guard


def _strict_label(
    label: BridgeLabelCertificate,
    reference: np.ndarray,
    reference_radii: np.ndarray,
    bridge: np.ndarray,
    bridge_radii: np.ndarray,
    *,
    feasibility_guard: float,
) -> BridgeLabelCertificate:
    token_count = reference.shape[1]
    indicators = np.eye(token_count, dtype=np.float64)
    lowers = np.asarray(
        [
            [
                l1_ball_expectation_lower(
                    bridge[source],
                    indicators[output],
                    l1_radius=float(bridge_radii[source]),
                )
                for output in range(token_count)
            ]
            for source in range(reference.shape[0])
        ],
        dtype=np.float64,
    )
    uppers = np.asarray(
        [
            [
                l1_ball_expectation_upper(
                    reference[source],
                    label.transform[:, output],
                    l1_radius=float(reference_radii[source]),
                )
                for output in range(token_count)
            ]
            for source in range(reference.shape[0])
        ],
        dtype=np.float64,
    )

    # Contract both sides before taking ratios.  This turns a floating-point
    # optimizer candidate into a conservative feasible point for the original
    # inequalities rather than accepting a small negative residual.
    lower_safe = np.maximum(0.0, lowers - feasibility_guard)
    upper_safe = np.minimum(1.0, uppers + feasibility_guard)
    ratios = [float(label.retained_mass)]
    for lower, upper in zip(lower_safe.flat, upper_safe.flat, strict=True):
        if upper > 0.0:
            ratios.append(float(lower / upper))
    retained = max(0.0, min(ratios) - feasibility_guard)
    if retained > 0.0:
        retained = float(np.nextafter(retained, 0.0))

    slacks = lowers - retained * uppers
    minimum_slack = float(np.min(slacks))
    if minimum_slack < 0.0:
        raise RuntimeError(
            "strict bridge repair failed to produce nonnegative membership slack"
        )
    return BridgeLabelCertificate(
        transform=np.asarray(label.transform, dtype=np.float64),
        retained_mass=retained,
        contamination=1.0 - retained,
        optimal_retained_mass_upper=label.optimal_retained_mass_upper,
        reference_l1_radii=label.reference_l1_radii,
        bridge_l1_radii=label.bridge_l1_radii,
        bridge_coordinate_lowers=tuple(
            tuple(float(value) for value in row) for row in lowers
        ),
        minimum_membership_slack=minimum_slack,
        transform_trace=label.transform_trace,
        solver_status=label.solver_status,
        solver_iterations=label.solver_iterations,
        method="strict_outward_repaired_l1_bridge",
    )


def certify_bridge_membership_strict(
    reference_empirical_distributions: Sequence[Sequence[Sequence[float]]],
    *,
    reference_l1_radii: Sequence[Sequence[float]],
    bridge_empirical_distributions: Sequence[Sequence[Sequence[float]]],
    bridge_l1_radii: Sequence[Sequence[float]],
    feasibility_guard: float = DEFAULT_FEASIBILITY_GUARD,
) -> BridgeMembershipCertificate:
    """Return a bridge certificate with verified nonnegative robust slacks."""

    guard = _validate_guard(
        feasibility_guard, name="feasibility_guard", maximum=1e-4
    )
    reference = np.asarray(reference_empirical_distributions, dtype=np.float64)
    bridge = np.asarray(bridge_empirical_distributions, dtype=np.float64)
    reference_radii = np.asarray(reference_l1_radii, dtype=np.float64)
    target_radii = np.asarray(bridge_l1_radii, dtype=np.float64)
    base = certify_bridge_membership(
        reference,
        reference_l1_radii=reference_radii,
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=target_radii,
    )
    labels = tuple(
        _strict_label(
            label,
            reference[label_index],
            reference_radii[label_index],
            bridge[label_index],
            target_radii[label_index],
            feasibility_guard=guard,
        )
        for label_index, label in enumerate(base.labels)
    )
    return BridgeMembershipCertificate(
        labels=labels,
        label_count=base.label_count,
        source_count=base.source_count,
        token_count=base.token_count,
        method="strict_simultaneous_l1_bridge_membership",
    )


def optimize_transform_exact_channel_strict(
    empirical_distributions: Sequence[Sequence[Sequence[float]]],
    *,
    l1_radii: Sequence[Sequence[float]],
    common_channels_by_label: Sequence[Sequence[Sequence[Sequence[float]]]],
    contaminations: Sequence[float],
    source_advantage_thresholds: Sequence[float],
    released_token_count: int,
    optimization_guard: float = DEFAULT_OPTIMIZATION_GUARD,
    value_guard: float = DEFAULT_VALUE_GUARD,
    solver_time_limit_seconds: float | None = None,
) -> StrictReleaseCertificate:
    """Optimize a tightened program and round every reported risk outward."""

    opt_guard = _validate_guard(
        optimization_guard, name="optimization_guard", maximum=1e-3
    )
    risk_guard = _validate_guard(value_guard, name="value_guard", maximum=1e-4)
    thresholds = np.asarray(source_advantage_thresholds, dtype=np.float64)
    if thresholds.ndim != 1 or np.any(thresholds <= opt_guard):
        raise ValueError("source thresholds must be one-dimensional and exceed the guard")
    tightened = thresholds - opt_guard
    solution = optimize_transform_exact_channel(
        empirical_distributions,
        l1_radii=l1_radii,
        common_channels_by_label=common_channels_by_label,
        contaminations=contaminations,
        privacy_advantage_thresholds=tightened,
        released_token_count=released_token_count,
        solver_time_limit_seconds=solver_time_limit_seconds,
    )

    empirical = np.asarray(empirical_distributions, dtype=np.float64)
    radii = np.asarray(l1_radii, dtype=np.float64)
    eta = np.asarray(contaminations, dtype=np.float64)
    libraries = tuple(
        tuple(np.asarray(transform, dtype=np.float64) for transform in library)
        for library in common_channels_by_label
    )
    unguarded_source = tuple(
        transform_exact_attacker_confidence_bound(
            empirical[label],
            solution.release_channel,
            l1_radii=radii[label],
            common_fine_token_channels=libraries[label],
            contamination=float(eta[label]),
        ).normalized_advantage
        for label in range(empirical.shape[0])
    )
    unguarded_utility = max(
        transform_exact_utility_confidence_bound(
            empirical[label, source],
            solution.release_channel,
            solution.decoder,
            true_label=label,
            l1_radius=float(radii[label, source]),
            common_fine_token_channels=libraries[label],
            contamination=float(eta[label]),
        ).error_probability
        for label in range(empirical.shape[0])
        for source in range(empirical.shape[1])
    )
    source_upper = tuple(
        min(1.0, float(np.nextafter(value + risk_guard, np.inf)))
        for value in unguarded_source
    )
    utility_upper = min(
        1.0, float(np.nextafter(unguarded_utility + risk_guard, np.inf))
    )
    if any(value > threshold for value, threshold in zip(source_upper, thresholds)):
        raise RuntimeError("strict source contract failed after outward rounding")
    if solution.max_constraint_violation > opt_guard / 2.0:
        raise RuntimeError("strict optimizer residual exceeds its numerical budget")

    return StrictReleaseCertificate(
        release_channel=np.asarray(solution.release_channel, dtype=np.float64),
        decoder=tuple(solution.decoder),
        certified_source_advantage_upper=source_upper,
        certified_worst_conditional_error_upper=utility_upper,
        unguarded_source_advantages=tuple(float(value) for value in unguarded_source),
        unguarded_worst_conditional_error=float(unguarded_utility),
        optimization_source_thresholds=tuple(float(value) for value in tightened),
        solver_objective=float(solution.solver_objective),
        solver_status=solution.solver_status,
        solver_mip_gap=float(solution.solver_mip_gap),
        solver_dual_bound=float(solution.solver_dual_bound),
        max_constraint_violation=float(solution.max_constraint_violation),
        solved_decoder_assignments=solution.solved_decoder_assignments,
        feasibility_guard=opt_guard,
        value_guard=risk_guard,
        method="strict_outward_transform_exact_lp",
    )
