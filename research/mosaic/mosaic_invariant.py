"""MOSAIC invariant-channel certificates for pre-release deployment shift.

The public representation is produced by a fixed row-stochastic channel ``M``.
Deployment drift acts on fine tokens before that channel.  A common Markov
transformation is controlled through an invariance defect, while arbitrary
source-specific residual shift is controlled by the channel's exact Bayes
leakage capacity.

All statistical guarantees are conditional on simultaneous confidence regions
for the fine-token source laws.  This module does not estimate or validate the
deployment-shift model itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Sequence

import numpy as np

from mosaic_channel import (
    MAX_EXACT_ASSIGNMENTS,
    ChannelAttackerEnvelope,
    adaptive_channel_attacker_confidence_bound,
    normalized_attacker_advantage,
    selected_decoder_error_confidence_bound,
)


@dataclass(frozen=True)
class DifferentialShiftCapacity:
    """Exact worst-case source accuracy allowed by a release channel."""

    balanced_accuracy: float
    normalized_advantage: float
    maximizing_assignment: tuple[int, ...]
    source_count: int
    fine_token_count: int
    released_token_count: int
    method: str


@dataclass(frozen=True)
class InvarianceDefect:
    """Worst row-wise TV change after an allowed common fine-token shift."""

    total_variation: float
    worst_transform_index: int
    worst_fine_token: int
    transform_count: int
    method: str


@dataclass(frozen=True)
class PreReleaseAttackerCertificate:
    """External arbitrary-attacker bound under pre-release coupled shift."""

    balanced_accuracy: float
    normalized_advantage: float
    contamination: float
    reference_balanced_accuracy_bound: float
    reference_normalized_advantage_bound: float
    invariance_defect: float
    common_component_balanced_accuracy_bound: float
    differential_capacity_balanced_accuracy: float
    differential_capacity_normalized_advantage: float
    method: str


@dataclass(frozen=True)
class PreReleaseUtilityCertificate:
    """External decoder-error bound under the same pre-release shift model."""

    error_probability: float
    contamination: float
    reference_error_bound: float
    directional_invariance_defect: float
    common_component_error_bound: float
    differential_error_capacity: float
    method: str


def _probability_vector(values: Iterable[float]) -> np.ndarray:
    array = np.asarray(tuple(values), dtype=np.float64)
    if array.ndim != 1 or array.size < 2:
        raise ValueError("a probability vector with at least two entries is required")
    if not np.isfinite(array).all() or np.any(array < -1e-12):
        raise ValueError("probabilities must be finite and non-negative")
    total = float(array.sum())
    if not np.isclose(total, 1.0, atol=1e-10):
        raise ValueError(f"probabilities must sum to one, received {total}")
    return np.clip(array, 0.0, 1.0)


def _probability_matrix(values: Sequence[Sequence[float]]) -> np.ndarray:
    rows = tuple(_probability_vector(row) for row in values)
    if len(rows) < 2:
        raise ValueError("at least two source distributions are required")
    width = rows[0].size
    if any(row.size != width for row in rows):
        raise ValueError("all distributions must share an alphabet")
    return np.stack(rows)


def _stochastic_matrix(
    values: Sequence[Sequence[float]],
    *,
    row_count: int | None = None,
    column_count: int | None = None,
    name: str,
) -> np.ndarray:
    matrix = np.asarray(values, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] < 2 or matrix.shape[1] < 2:
        raise ValueError(f"{name} must be a two-dimensional stochastic matrix")
    if row_count is not None and matrix.shape[0] != row_count:
        raise ValueError(f"{name} has {matrix.shape[0]} rows; expected {row_count}")
    if column_count is not None and matrix.shape[1] != column_count:
        raise ValueError(
            f"{name} has {matrix.shape[1]} columns; expected {column_count}"
        )
    if not np.isfinite(matrix).all() or np.any(matrix < -1e-12):
        raise ValueError(f"{name} entries must be finite and non-negative")
    if not np.allclose(matrix.sum(axis=1), 1.0, atol=1e-10):
        raise ValueError(f"every row of {name} must sum to one")
    return np.clip(matrix, 0.0, 1.0)


def _release_channel(values: Sequence[Sequence[float]]) -> np.ndarray:
    return _stochastic_matrix(values, name="release channel")


def _common_channels(
    values: Sequence[Sequence[Sequence[float]]], fine_count: int
) -> tuple[np.ndarray, ...]:
    channels = tuple(
        _stochastic_matrix(
            channel,
            row_count=fine_count,
            column_count=fine_count,
            name="common fine-token channel",
        )
        for channel in values
    )
    if not channels:
        raise ValueError("at least one common fine-token channel is required")
    return channels


def _decoder_loss(
    decoder: Sequence[int], released_count: int, true_label: int
) -> np.ndarray:
    predictions = np.asarray(tuple(decoder), dtype=np.int64)
    if predictions.shape != (released_count,):
        raise ValueError("decoder must provide one label per released token")
    return (predictions != int(true_label)).astype(np.float64)


def _contamination(value: float) -> float:
    if not np.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError("contamination must lie in [0, 1]")
    return float(value)


def differential_shift_capacity(
    release_channel: Sequence[Sequence[float]], *, source_count: int
) -> DifferentialShiftCapacity:
    """Compute exact worst-case balanced source accuracy through ``M``.

    Each source may choose an arbitrary fine-token law.  For a fixed attacker
    assignment, each source therefore concentrates on the row of ``M`` that
    maximizes its correct-decision probability.
    """

    channel = _release_channel(release_channel)
    if source_count < 2:
        raise ValueError("source_count must be at least two")
    released_count = channel.shape[1]
    assignment_count = source_count**released_count
    if assignment_count > MAX_EXACT_ASSIGNMENTS:
        raise ValueError(
            f"exact enumeration requires {assignment_count:,} assignments; "
            f"cap is {MAX_EXACT_ASSIGNMENTS:,}"
        )

    best = -1.0
    best_assignment: tuple[int, ...] = ()
    for assignment in product(range(source_count), repeat=released_count):
        assignment_array = np.asarray(assignment, dtype=np.int64)
        score = 0.0
        for source in range(source_count):
            correct_outputs = (assignment_array == source).astype(np.float64)
            score += float(np.max(channel @ correct_outputs))
        score /= source_count
        if score > best:
            best = score
            best_assignment = tuple(int(value) for value in assignment)

    best = float(np.clip(best, 1.0 / source_count, 1.0))
    return DifferentialShiftCapacity(
        balanced_accuracy=best,
        normalized_advantage=normalized_attacker_advantage(best, source_count),
        maximizing_assignment=best_assignment,
        source_count=source_count,
        fine_token_count=channel.shape[0],
        released_token_count=released_count,
        method="exact_arbitrary_fine_shift_bayes_capacity",
    )


def dobrushin_coefficient(
    release_channel: Sequence[Sequence[float]],
) -> float:
    """Return the total-variation Dobrushin coefficient of ``M``."""

    channel = _release_channel(release_channel)
    largest = 0.0
    for first in range(channel.shape[0]):
        for second in range(first + 1, channel.shape[0]):
            largest = max(
                largest,
                0.5 * float(np.abs(channel[first] - channel[second]).sum()),
            )
    return float(largest)


def invariance_defect(
    release_channel: Sequence[Sequence[float]],
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
) -> InvarianceDefect:
    """Worst ``max_c TV((T M)_c, M_c)`` over a channel library."""

    release = _release_channel(release_channel)
    common = _common_channels(common_fine_token_channels, release.shape[0])
    worst = -1.0
    worst_transform = -1
    worst_token = -1
    for transform_index, transform in enumerate(common):
        shifted = transform @ release
        row_distances = 0.5 * np.abs(shifted - release).sum(axis=1)
        token = int(np.argmax(row_distances))
        value = float(row_distances[token])
        if value > worst:
            worst = value
            worst_transform = transform_index
            worst_token = token
    return InvarianceDefect(
        total_variation=float(np.clip(worst, 0.0, 1.0)),
        worst_transform_index=worst_transform,
        worst_fine_token=worst_token,
        transform_count=len(common),
        method="finite_extreme_library_rowwise_tv_invariance_defect",
    )


def directional_decoder_invariance_defect(
    release_channel: Sequence[Sequence[float]],
    decoder: Sequence[int],
    *,
    true_label: int,
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
) -> float:
    """Largest possible row-wise increase in decoder error under common drift."""

    release = _release_channel(release_channel)
    loss = _decoder_loss(decoder, release.shape[1], true_label)
    common = _common_channels(common_fine_token_channels, release.shape[0])
    base_error = release @ loss
    largest_increase = 0.0
    for transform in common:
        shifted_error = transform @ release @ loss
        largest_increase = max(
            largest_increase, float(np.max(shifted_error - base_error))
        )
    return float(np.clip(largest_increase, 0.0, 1.0))


def differential_decoder_error_capacity(
    release_channel: Sequence[Sequence[float]],
    decoder: Sequence[int],
    *,
    true_label: int,
) -> float:
    """Worst decoder error over an arbitrary fine-token input law."""

    release = _release_channel(release_channel)
    loss = _decoder_loss(decoder, release.shape[1], true_label)
    return float(np.clip(np.max(release @ loss), 0.0, 1.0))


def pre_release_attacker_certificate(
    reference: ChannelAttackerEnvelope,
    release_channel: Sequence[Sequence[float]],
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
    *,
    contamination: float,
) -> PreReleaseAttackerCertificate:
    """Transfer a reference envelope through common drift plus residual shift."""

    eta = _contamination(contamination)
    release = _release_channel(release_channel)
    if release.shape != (
        reference.fine_token_count,
        reference.released_token_count,
    ):
        raise ValueError("release channel does not match the reference envelope")
    capacity = differential_shift_capacity(
        release, source_count=reference.source_count
    )
    defect = invariance_defect(release, common_fine_token_channels)
    common_bound = min(
        capacity.balanced_accuracy,
        reference.balanced_accuracy + defect.total_variation,
    )
    external = (1.0 - eta) * common_bound + eta * capacity.balanced_accuracy
    external = float(np.clip(external, 1.0 / reference.source_count, 1.0))
    return PreReleaseAttackerCertificate(
        balanced_accuracy=external,
        normalized_advantage=normalized_attacker_advantage(
            external, reference.source_count
        ),
        contamination=eta,
        reference_balanced_accuracy_bound=reference.balanced_accuracy,
        reference_normalized_advantage_bound=reference.normalized_advantage,
        invariance_defect=defect.total_variation,
        common_component_balanced_accuracy_bound=common_bound,
        differential_capacity_balanced_accuracy=capacity.balanced_accuracy,
        differential_capacity_normalized_advantage=capacity.normalized_advantage,
        method="adaptive_pre_release_common_invariance_plus_capacity_bound",
    )


def pre_release_utility_certificate(
    empirical_distribution: Sequence[float],
    release_channel: Sequence[Sequence[float]],
    decoder: Sequence[int],
    *,
    true_label: int,
    l1_radius: float,
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
    contamination: float,
) -> PreReleaseUtilityCertificate:
    """Certify one source-label decoder error under pre-release shift."""

    eta = _contamination(contamination)
    release = _release_channel(release_channel)
    reference = selected_decoder_error_confidence_bound(
        empirical_distribution,
        release,
        decoder,
        true_label=true_label,
        l1_radius=l1_radius,
    )
    defect = directional_decoder_invariance_defect(
        release,
        decoder,
        true_label=true_label,
        common_fine_token_channels=common_fine_token_channels,
    )
    capacity = differential_decoder_error_capacity(
        release, decoder, true_label=true_label
    )
    common_bound = min(capacity, reference + defect)
    external = (1.0 - eta) * common_bound + eta * capacity
    return PreReleaseUtilityCertificate(
        error_probability=float(np.clip(external, 0.0, 1.0)),
        contamination=eta,
        reference_error_bound=reference,
        directional_invariance_defect=defect,
        common_component_error_bound=common_bound,
        differential_error_capacity=capacity,
        method="adaptive_pre_release_decoder_invariance_plus_capacity_bound",
    )


def adaptive_pre_release_attacker_certificate(
    source_empirical_distributions: Sequence[Sequence[float]],
    release_channel: Sequence[Sequence[float]],
    *,
    l1_radii: Sequence[float],
    common_fine_token_channels: Sequence[Sequence[Sequence[float]]],
    contamination: float,
) -> PreReleaseAttackerCertificate:
    """Convenience wrapper constructing both reference and shifted bounds."""

    reference = adaptive_channel_attacker_confidence_bound(
        source_empirical_distributions,
        release_channel,
        l1_radii=l1_radii,
    )
    return pre_release_attacker_certificate(
        reference,
        release_channel,
        common_fine_token_channels,
        contamination=contamination,
    )


def apply_pre_release_shift(
    reference_distributions: Sequence[Sequence[float]],
    common_fine_token_channel: Sequence[Sequence[float]],
    residual_distributions: Sequence[Sequence[float]],
    release_channel: Sequence[Sequence[float]],
    *,
    retained_common_mass: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Construct external fine-token and released laws for auditing."""

    reference = _probability_matrix(reference_distributions)
    residual = _probability_matrix(residual_distributions)
    if residual.shape != reference.shape:
        raise ValueError("reference and residual laws must have matching shapes")
    common = _stochastic_matrix(
        common_fine_token_channel,
        row_count=reference.shape[1],
        column_count=reference.shape[1],
        name="common fine-token channel",
    )
    release = _stochastic_matrix(
        release_channel,
        row_count=reference.shape[1],
        name="release channel",
    )
    retained = float(retained_common_mass)
    if not np.isfinite(retained) or not 0.0 <= retained <= 1.0:
        raise ValueError("retained_common_mass must lie in [0, 1]")
    external_fine = retained * (reference @ common) + (1.0 - retained) * residual
    return external_fine, external_fine @ release
