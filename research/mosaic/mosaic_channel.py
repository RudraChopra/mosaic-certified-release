"""Adaptive finite-token channels and coupled-shift certificates for MOSAIC.

This module implements the deterministic core of the replacement theorem.  A
single fine-token multinomial confidence event is reused for every stochastic
release channel and every downstream attacker.  Deployment shift is modeled as
an arbitrary common channel plus bounded source-specific contamination.

The functions here do not infer that shift model from data.  A caller must
declare the contamination and task-flip budgets or audit them separately.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Iterable, Sequence

import numpy as np


MAX_EXACT_ASSIGNMENTS = 5_000_000


@dataclass(frozen=True)
class ChannelAttackerEnvelope:
    """Exact confidence-set envelope for every attacker on a release channel."""

    balanced_accuracy: float
    normalized_advantage: float
    maximizing_assignment: tuple[int, ...]
    source_count: int
    fine_token_count: int
    released_token_count: int
    l1_radii: tuple[float, ...]
    method: str


@dataclass(frozen=True)
class CoupledShiftEnvelope:
    """External universal-attacker envelope under coupled contamination shift."""

    balanced_accuracy: float
    normalized_advantage: float
    contamination: float
    reference_balanced_accuracy_bound: float
    reference_normalized_advantage_bound: float
    method: str


@dataclass(frozen=True)
class CommonChannelFit:
    """Maximum common-channel mass in an empirical reference/external pair."""

    retained_common_mass: float
    minimum_contamination: float
    common_channel: np.ndarray
    source_residuals: np.ndarray
    objective_status: str
    max_constraint_violation: float


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
        raise ValueError("all source distributions must share an alphabet")
    return np.stack(rows)


def _release_channel(values: Sequence[Sequence[float]], fine_count: int) -> np.ndarray:
    channel = np.asarray(values, dtype=np.float64)
    if channel.ndim != 2 or channel.shape[0] != fine_count or channel.shape[1] < 2:
        raise ValueError(
            "release channel must have one row per fine token and at least two outputs"
        )
    if not np.isfinite(channel).all() or np.any(channel < -1e-12):
        raise ValueError("release-channel probabilities must be finite and non-negative")
    if not np.allclose(channel.sum(axis=1), 1.0, atol=1e-10):
        raise ValueError("every release-channel row must sum to one")
    return np.clip(channel, 0.0, 1.0)


def _validate_radius(radius: float) -> float:
    if not np.isfinite(radius) or radius < 0.0:
        raise ValueError("L1 radius must be finite and non-negative")
    return min(float(radius), 2.0)


def l1_ball_expectation_upper(
    empirical_distribution: Iterable[float],
    scores: Iterable[float],
    *,
    l1_radius: float,
) -> float:
    """Exactly maximize an expectation over a multinomial L1 ball.

    Starting at the empirical law, the optimizer transports at most
    ``l1_radius / 2`` mass from the smallest scores to the largest scores.  This
    is a finite transportation problem, and the greedy extreme-to-extreme
    transfer is exact.
    """

    empirical = _probability_vector(empirical_distribution)
    values = np.asarray(tuple(scores), dtype=np.float64)
    if values.shape != empirical.shape or not np.isfinite(values).all():
        raise ValueError("scores must be finite with one value per fine token")
    radius = _validate_radius(l1_radius)
    if radius == 0.0 or np.allclose(values, values[0], atol=0.0, rtol=0.0):
        return float(empirical @ values)

    order = np.argsort(values, kind="stable")
    candidate = empirical.copy()
    budget = radius / 2.0
    low = 0
    high = order.size - 1
    tolerance = 1e-15

    while budget > tolerance and low < high:
        donor = int(order[low])
        receiver = int(order[high])
        if values[receiver] <= values[donor]:
            break
        if candidate[donor] <= tolerance:
            low += 1
            continue
        if candidate[receiver] >= 1.0 - tolerance:
            high -= 1
            continue
        moved = min(budget, float(candidate[donor]), float(1.0 - candidate[receiver]))
        candidate[donor] -= moved
        candidate[receiver] += moved
        budget -= moved
        if candidate[donor] <= tolerance:
            low += 1
        if candidate[receiver] >= 1.0 - tolerance:
            high -= 1

    return float(candidate @ values)


def l1_ball_expectation_lower(
    empirical_distribution: Iterable[float],
    scores: Iterable[float],
    *,
    l1_radius: float,
) -> float:
    """Exactly minimize an expectation over a multinomial L1 ball."""

    values = tuple(float(value) for value in scores)
    return -l1_ball_expectation_upper(
        empirical_distribution,
        (-value for value in values),
        l1_radius=l1_radius,
    )


def apply_channel(
    distributions: Sequence[Sequence[float]], channel: Sequence[Sequence[float]]
) -> np.ndarray:
    """Push one or more source laws through a row-stochastic channel."""

    probabilities = _probability_matrix(distributions)
    matrix = _release_channel(channel, probabilities.shape[1])
    return probabilities @ matrix


def population_balanced_attacker_accuracy(
    source_distributions: Sequence[Sequence[float]],
    channel: Sequence[Sequence[float]] | None = None,
) -> float:
    """Bayes balanced accuracy of the best arbitrary finite-token attacker."""

    probabilities = _probability_matrix(source_distributions)
    if channel is not None:
        probabilities = probabilities @ _release_channel(
            channel, probabilities.shape[1]
        )
    return float(np.max(probabilities, axis=0).sum() / probabilities.shape[0])


def normalized_attacker_advantage(
    balanced_accuracy: float, source_count: int
) -> float:
    if source_count < 2:
        raise ValueError("source_count must be at least two")
    chance = 1.0 / source_count
    if balanced_accuracy < chance - 1e-10 or balanced_accuracy > 1.0 + 1e-10:
        raise ValueError("balanced accuracy must lie between chance and one")
    return float(np.clip((balanced_accuracy - chance) / (1.0 - chance), 0.0, 1.0))


def adaptive_channel_attacker_confidence_bound(
    source_empirical_distributions: Sequence[Sequence[float]],
    release_channel: Sequence[Sequence[float]],
    *,
    l1_radii: Sequence[float],
) -> ChannelAttackerEnvelope:
    """Exact L1-confidence envelope for every attacker after any channel.

    The release channel may be stochastic and may have been selected using the
    same empirical distributions.  Validity comes from one fine-token
    confidence event that is uniform over all score vectors induced by channels
    and attacker assignments.
    """

    empirical = _probability_matrix(source_empirical_distributions)
    source_count, fine_count = empirical.shape
    channel = _release_channel(release_channel, fine_count)
    released_count = channel.shape[1]
    radii = tuple(_validate_radius(radius) for radius in l1_radii)
    if len(radii) != source_count:
        raise ValueError("provide one L1 radius per source")
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
            soft_correct = channel @ correct_outputs
            score += l1_ball_expectation_upper(
                empirical[source], soft_correct, l1_radius=radii[source]
            )
        score /= source_count
        if score > best:
            best = score
            best_assignment = tuple(int(value) for value in assignment)

    best = float(np.clip(best, 1.0 / source_count, 1.0))
    return ChannelAttackerEnvelope(
        balanced_accuracy=best,
        normalized_advantage=normalized_attacker_advantage(best, source_count),
        maximizing_assignment=best_assignment,
        source_count=source_count,
        fine_token_count=fine_count,
        released_token_count=released_count,
        l1_radii=radii,
        method="exact_fine_l1_adaptive_stochastic_channel_envelope",
    )


def coupled_shift_attacker_bound(
    reference: ChannelAttackerEnvelope, *, contamination: float
) -> CoupledShiftEnvelope:
    """Transfer a reference certificate through common drift plus contamination."""

    if not np.isfinite(contamination) or not 0.0 <= contamination <= 1.0:
        raise ValueError("contamination must lie in [0, 1]")
    eta = float(contamination)
    balanced = (1.0 - eta) * reference.balanced_accuracy + eta
    advantage = (1.0 - eta) * reference.normalized_advantage + eta
    return CoupledShiftEnvelope(
        balanced_accuracy=float(np.clip(balanced, 0.0, 1.0)),
        normalized_advantage=float(np.clip(advantage, 0.0, 1.0)),
        contamination=eta,
        reference_balanced_accuracy_bound=reference.balanced_accuracy,
        reference_normalized_advantage_bound=reference.normalized_advantage,
        method="minimax_sharp_common_channel_contamination_transfer",
    )


def selected_decoder_error_confidence_bound(
    empirical_distribution: Sequence[float],
    release_channel: Sequence[Sequence[float]],
    decoder: Sequence[int],
    *,
    true_label: int,
    l1_radius: float,
) -> float:
    """Exact fine-ball error bound for a jointly selected channel and decoder."""

    empirical = _probability_vector(empirical_distribution)
    channel = _release_channel(release_channel, empirical.size)
    predictions = np.asarray(tuple(decoder), dtype=np.int64)
    if predictions.shape != (channel.shape[1],):
        raise ValueError("decoder must provide one prediction per released token")
    error_outputs = (predictions != int(true_label)).astype(np.float64)
    soft_error = channel @ error_outputs
    bound = l1_ball_expectation_upper(
        empirical, soft_error, l1_radius=l1_radius
    )
    return float(np.clip(bound, 0.0, 1.0))


def coupled_shift_decoder_error_bound(
    reference_error_bound: float,
    *,
    contamination: float,
    common_channel_flip_probability: float,
) -> float:
    """Transfer a selected decoder's error through the coupled shift model."""

    for value, name in (
        (reference_error_bound, "reference_error_bound"),
        (contamination, "contamination"),
        (common_channel_flip_probability, "common_channel_flip_probability"),
    ):
        if not np.isfinite(value) or value < -1e-10 or value > 1.0 + 1e-10:
            raise ValueError(f"{name} must lie in [0, 1]")
    reference_error_bound = float(np.clip(reference_error_bound, 0.0, 1.0))
    contamination = float(np.clip(contamination, 0.0, 1.0))
    common_channel_flip_probability = float(
        np.clip(common_channel_flip_probability, 0.0, 1.0)
    )
    common_error = min(1.0, reference_error_bound + common_channel_flip_probability)
    return float((1.0 - contamination) * common_error + contamination)


def fit_common_channel_contamination(
    reference_distributions: Sequence[Sequence[float]],
    external_distributions: Sequence[Sequence[float]],
) -> CommonChannelFit:
    """Solve the exact empirical common-channel compatibility linear program.

    This is a diagnostic, not a confidence statement.  It finds the largest
    common mass ``t`` such that ``Q_s = t P_s T + (1-t) R_s`` for all sources.
    """

    from scipy.optimize import linprog

    reference = _probability_matrix(reference_distributions)
    external = _probability_matrix(external_distributions)
    if reference.shape[0] != external.shape[0]:
        raise ValueError("reference and external laws need the same sources")
    source_count, input_count = reference.shape
    output_count = external.shape[1]
    matrix_variable_count = input_count * output_count
    t_index = matrix_variable_count
    variable_count = matrix_variable_count + 1

    objective = np.zeros(variable_count, dtype=np.float64)
    objective[t_index] = -1.0

    equality_rows = []
    equality_rhs = []
    for input_token in range(input_count):
        row = np.zeros(variable_count, dtype=np.float64)
        start = input_token * output_count
        row[start : start + output_count] = 1.0
        row[t_index] = -1.0
        equality_rows.append(row)
        equality_rhs.append(0.0)

    upper_rows = []
    upper_rhs = []
    for source in range(source_count):
        for output_token in range(output_count):
            row = np.zeros(variable_count, dtype=np.float64)
            for input_token in range(input_count):
                row[input_token * output_count + output_token] = reference[
                    source, input_token
                ]
            upper_rows.append(row)
            upper_rhs.append(external[source, output_token])

    result = linprog(
        objective,
        A_ub=np.asarray(upper_rows),
        b_ub=np.asarray(upper_rhs),
        A_eq=np.asarray(equality_rows),
        b_eq=np.asarray(equality_rhs),
        bounds=[(0.0, None)] * matrix_variable_count + [(0.0, 1.0)],
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"common-channel LP failed: {result.message}")

    retained = float(np.clip(result.x[t_index], 0.0, 1.0))
    subchannel = result.x[:matrix_variable_count].reshape(input_count, output_count)
    if retained > 1e-12:
        common_channel = subchannel / retained
    else:
        common_channel = np.full(
            (input_count, output_count), 1.0 / output_count, dtype=np.float64
        )
    unexplained = np.maximum(0.0, external - reference @ subchannel)
    contamination = 1.0 - retained
    if contamination > 1e-12:
        residuals = unexplained / contamination
        residuals /= residuals.sum(axis=1, keepdims=True)
    else:
        residuals = np.full_like(external, 1.0 / output_count)

    row_violation = float(np.max(np.abs(subchannel.sum(axis=1) - retained)))
    dominance_violation = float(np.max(reference @ subchannel - external))
    residual_mass_violation = float(
        np.max(np.abs(unexplained.sum(axis=1) - contamination))
    )
    max_violation = max(row_violation, dominance_violation, residual_mass_violation, 0.0)
    return CommonChannelFit(
        retained_common_mass=retained,
        minimum_contamination=contamination,
        common_channel=common_channel,
        source_residuals=residuals,
        objective_status=str(result.message),
        max_constraint_violation=max_violation,
    )
