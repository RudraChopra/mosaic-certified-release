"""Exact population risks for the MOSAIC pre-release shift model.

This module is deliberately separate from the confidence-certificate code. It
evaluates a selected release against known population laws by enumerating every
finite attacker assignment, every registered extreme common transformation,
and the vertices of the arbitrary residual simplex. Synthetic experiments use
these quantities to decide whether a deployment is truly contract-safe.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Sequence

import numpy as np

from mosaic_channel import MAX_EXACT_ASSIGNMENTS, normalized_attacker_advantage


@dataclass(frozen=True)
class ExactExternalAttackerRisk:
    """Exact worst balanced source accuracy in the registered shift class."""

    balanced_accuracy: float
    normalized_advantage: float
    contamination: float
    worst_transform_index: int
    maximizing_assignment: tuple[int, ...]
    source_count: int
    fine_token_count: int
    released_token_count: int
    method: str


@dataclass(frozen=True)
class ExactExternalUtilityRisk:
    """Exact worst decoder error for one source-label stratum."""

    error_probability: float
    contamination: float
    worst_transform_index: int
    differential_error_capacity: float
    fine_token_count: int
    released_token_count: int
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


def _contamination(value: float) -> float:
    if not np.isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError("contamination must lie in [0, 1]")
    return float(value)


def exact_external_attacker_risk(
    reference_distributions: Sequence[Sequence[float]],
    release_channel: Sequence[Sequence[float]],
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
    *,
    contamination: float,
) -> ExactExternalAttackerRisk:
    """Return the exact worst source attacker under the registered shift model.

    The common transformation is selected from the provided extreme library.
    For each deterministic released-token attacker, every source-specific
    residual law concentrates on its best fine-token row. Maximizing these
    finite expressions is exactly equivalent to maximizing over all residual
    distributions and the convex hull of the listed transforms.
    """

    reference = _source_laws(reference_distributions)
    source_count, fine_count = reference.shape
    release = _stochastic_matrix(
        release_channel,
        name="release channel",
        row_count=fine_count,
    )
    transforms = _common_transforms(
        common_fine_token_channels, fine_count
    )
    eta = _contamination(contamination)
    released_count = release.shape[1]
    assignment_count = source_count**released_count
    if assignment_count > MAX_EXACT_ASSIGNMENTS:
        raise ValueError(
            f"exact enumeration requires {assignment_count:,} assignments; "
            f"cap is {MAX_EXACT_ASSIGNMENTS:,}"
        )

    assignments = tuple(product(range(source_count), repeat=released_count))
    best = -1.0
    best_transform = -1
    best_assignment: tuple[int, ...] = ()
    for transform_index, transform in enumerate(transforms):
        common_released = reference @ transform @ release
        for assignment in assignments:
            assignment_array = np.asarray(assignment, dtype=np.int64)
            common_score = 0.0
            residual_score = 0.0
            for source in range(source_count):
                correct_outputs = (assignment_array == source).astype(np.float64)
                common_score += float(common_released[source] @ correct_outputs)
                residual_score += float(np.max(release @ correct_outputs))
            score = (
                (1.0 - eta) * common_score + eta * residual_score
            ) / source_count
            if score > best:
                best = score
                best_transform = transform_index
                best_assignment = tuple(int(value) for value in assignment)

    best = float(np.clip(best, 1.0 / source_count, 1.0))
    return ExactExternalAttackerRisk(
        balanced_accuracy=best,
        normalized_advantage=normalized_attacker_advantage(best, source_count),
        contamination=eta,
        worst_transform_index=best_transform,
        maximizing_assignment=best_assignment,
        source_count=source_count,
        fine_token_count=fine_count,
        released_token_count=released_count,
        method="exact_common_extremes_attacker_assignments_residual_vertices",
    )


def exact_external_utility_risk(
    reference_distribution: Sequence[float],
    release_channel: Sequence[Sequence[float]],
    decoder: Sequence[int],
    *,
    true_label: int,
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
    contamination: float,
) -> ExactExternalUtilityRisk:
    """Return exact worst error for one source-label conditional law."""

    reference = _probability_vector(
        reference_distribution, name="reference distribution"
    )
    fine_count = reference.size
    release = _stochastic_matrix(
        release_channel,
        name="release channel",
        row_count=fine_count,
    )
    transforms = _common_transforms(
        common_fine_token_channels, fine_count
    )
    eta = _contamination(contamination)
    predictions = np.asarray(tuple(decoder), dtype=np.int64)
    if predictions.shape != (release.shape[1],):
        raise ValueError("decoder must provide one label per released token")
    loss = (predictions != int(true_label)).astype(np.float64)
    row_errors = release @ loss
    residual_capacity = float(np.max(row_errors))

    best = -1.0
    best_transform = -1
    for transform_index, transform in enumerate(transforms):
        common_error = float(reference @ transform @ row_errors)
        external_error = (
            (1.0 - eta) * common_error + eta * residual_capacity
        )
        if external_error > best:
            best = external_error
            best_transform = transform_index

    return ExactExternalUtilityRisk(
        error_probability=float(np.clip(best, 0.0, 1.0)),
        contamination=eta,
        worst_transform_index=best_transform,
        differential_error_capacity=residual_capacity,
        fine_token_count=fine_count,
        released_token_count=release.shape[1],
        method="exact_common_extremes_utility_residual_vertices",
    )
