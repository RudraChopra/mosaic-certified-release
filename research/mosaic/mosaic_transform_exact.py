"""Exact confidence certificates for MOSAIC's structured shift class.

The earlier capacity-transfer certificate bounds a common pre-release
transformation through an invariance defect.  When the common-transform
uncertainty set is the convex hull of finitely many registered extremes, the
entire shifted confidence problem can instead be solved exactly.  This module
implements that tighter finite-alphabet certificate without changing the
statistical event used to select the release channel.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Sequence

import numpy as np

from mosaic_channel import (
    MAX_EXACT_ASSIGNMENTS,
    l1_ball_expectation_upper,
    normalized_attacker_advantage,
)


@dataclass(frozen=True)
class TransformExactAttackerCertificate:
    """Exact confidence-set attacker envelope under structured shift."""

    balanced_accuracy: float
    normalized_advantage: float
    contamination: float
    worst_transform_index: int
    maximizing_assignment: tuple[int, ...]
    source_count: int
    fine_token_count: int
    released_token_count: int
    l1_radii: tuple[float, ...]
    method: str


@dataclass(frozen=True)
class TransformExactUtilityCertificate:
    """Exact confidence-set error envelope for one source-label stratum."""

    error_probability: float
    contamination: float
    worst_transform_index: int
    differential_error_capacity: float
    fine_token_count: int
    released_token_count: int
    l1_radius: float
    method: str


def _probability_vector(values: Iterable[float], *, name: str) -> np.ndarray:
    array = np.asarray(tuple(values), dtype=np.float64)
    if array.ndim != 1 or array.size < 2:
        raise ValueError(f"{name} must contain at least two probabilities")
    if not np.isfinite(array).all() or np.any(array < -1e-12):
        raise ValueError(f"{name} must be finite and non-negative")
    if not np.isclose(float(array.sum()), 1.0, atol=1e-10):
        raise ValueError(f"{name} must sum to one")
    return np.clip(array, 0.0, 1.0)


def _source_laws(values: Sequence[Sequence[float]]) -> np.ndarray:
    rows = tuple(
        _probability_vector(row, name="source distribution") for row in values
    )
    if len(rows) < 2:
        raise ValueError("at least two source distributions are required")
    if any(row.size != rows[0].size for row in rows):
        raise ValueError("source distributions must share a fine alphabet")
    return np.stack(rows)


def _stochastic_matrix(
    values: Sequence[Sequence[float]],
    *,
    name: str,
    row_count: int | None = None,
    column_count: int | None = None,
) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 2:
        raise ValueError(f"{name} must be a two-dimensional stochastic matrix")
    if row_count is not None and matrix.shape[0] != row_count:
        raise ValueError(f"{name} has the wrong row count")
    if column_count is not None and matrix.shape[1] != column_count:
        raise ValueError(f"{name} has the wrong column count")
    if not np.isfinite(matrix).all() or np.any(matrix < -1e-12):
        raise ValueError(f"{name} must be finite and non-negative")
    if not np.allclose(matrix.sum(axis=1), 1.0, atol=1e-10):
        raise ValueError(f"every row of {name} must sum to one")
    return np.clip(matrix, 0.0, 1.0)


def _common_transforms(
    values: Sequence[Sequence[Sequence[float]]], fine_count: int
) -> tuple[np.ndarray, ...]:
    transforms = tuple(
        _stochastic_matrix(
            transform,
            name="common fine-token transform",
            row_count=fine_count,
            column_count=fine_count,
        )
        for transform in values
    )
    if not transforms:
        raise ValueError("at least one common transform is required")
    return transforms


def _radius(value: float) -> float:
    if not np.isfinite(value) or value < 0.0:
        raise ValueError("L1 radii must be finite and non-negative")
    return min(float(value), 2.0)


def _contamination(value: float) -> float:
    if not np.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("contamination must lie in [0, 1]")
    return float(value)


def transform_exact_attacker_confidence_bound(
    source_empirical_distributions: Sequence[Sequence[float]],
    release_channel: Sequence[Sequence[float]],
    *,
    l1_radii: Sequence[float],
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
    contamination: float,
) -> TransformExactAttackerCertificate:
    """Exactly maximize shifted Bayes accuracy over the stated confidence sets.

    The common transform ranges over the convex hull of the listed extremes.
    The maximum is attained at an extreme because the confidence support
    function is convex in the transform.  Source-specific residual laws attain
    their maxima at simplex vertices.
    """

    empirical = _source_laws(source_empirical_distributions)
    source_count, fine_count = empirical.shape
    release = _stochastic_matrix(
        release_channel, name="release channel", row_count=fine_count
    )
    transforms = _common_transforms(common_fine_token_channels, fine_count)
    radii = tuple(_radius(value) for value in l1_radii)
    if len(radii) != source_count:
        raise ValueError("provide one L1 radius per source")
    eta = _contamination(contamination)
    released_count = release.shape[1]
    assignment_count = source_count**released_count
    if assignment_count > MAX_EXACT_ASSIGNMENTS:
        raise ValueError(
            f"exact enumeration requires {assignment_count:,} assignments; "
            f"cap is {MAX_EXACT_ASSIGNMENTS:,}"
        )

    best = -1.0
    best_transform = -1
    best_assignment: tuple[int, ...] = ()
    for transform_index, transform in enumerate(transforms):
        for assignment in product(range(source_count), repeat=released_count):
            assignment_array = np.asarray(assignment, dtype=np.int64)
            score = 0.0
            for source in range(source_count):
                correct_outputs = (assignment_array == source).astype(np.float64)
                fine_scores = release @ correct_outputs
                common_scores = transform @ fine_scores
                common_bound = l1_ball_expectation_upper(
                    empirical[source],
                    common_scores,
                    l1_radius=radii[source],
                )
                residual_bound = float(np.max(fine_scores))
                score += (1.0 - eta) * common_bound + eta * residual_bound
            score /= source_count
            if score > best:
                best = score
                best_transform = transform_index
                best_assignment = tuple(int(value) for value in assignment)

    best = float(np.clip(best, 1.0 / source_count, 1.0))
    return TransformExactAttackerCertificate(
        balanced_accuracy=best,
        normalized_advantage=normalized_attacker_advantage(best, source_count),
        contamination=eta,
        worst_transform_index=best_transform,
        maximizing_assignment=best_assignment,
        source_count=source_count,
        fine_token_count=fine_count,
        released_token_count=released_count,
        l1_radii=radii,
        method="exact_l1_common_extremes_attacker_assignments_residual_vertices",
    )


def transform_exact_utility_confidence_bound(
    empirical_distribution: Sequence[float],
    release_channel: Sequence[Sequence[float]],
    decoder: Sequence[int],
    *,
    true_label: int,
    l1_radius: float,
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
    contamination: float,
) -> TransformExactUtilityCertificate:
    """Exactly maximize shifted decoder error over one multinomial L1 ball."""

    empirical = _probability_vector(
        empirical_distribution, name="empirical distribution"
    )
    fine_count = empirical.size
    release = _stochastic_matrix(
        release_channel, name="release channel", row_count=fine_count
    )
    transforms = _common_transforms(common_fine_token_channels, fine_count)
    predictions = np.asarray(tuple(decoder), dtype=np.int64)
    if predictions.shape != (release.shape[1],):
        raise ValueError("decoder must provide one label per released token")
    radius = _radius(l1_radius)
    eta = _contamination(contamination)
    loss = (predictions != int(true_label)).astype(np.float64)
    row_errors = release @ loss
    residual_capacity = float(np.max(row_errors))

    best = -1.0
    best_transform = -1
    for transform_index, transform in enumerate(transforms):
        common_bound = l1_ball_expectation_upper(
            empirical,
            transform @ row_errors,
            l1_radius=radius,
        )
        shifted_bound = (1.0 - eta) * common_bound + eta * residual_capacity
        if shifted_bound > best:
            best = shifted_bound
            best_transform = transform_index

    return TransformExactUtilityCertificate(
        error_probability=float(np.clip(best, 0.0, 1.0)),
        contamination=eta,
        worst_transform_index=best_transform,
        differential_error_capacity=residual_capacity,
        fine_token_count=fine_count,
        released_token_count=release.shape[1],
        l1_radius=radius,
        method="exact_l1_common_extremes_utility_residual_vertices",
    )
