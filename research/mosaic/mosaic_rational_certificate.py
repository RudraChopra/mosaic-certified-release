"""Exact rational replay of serialized MOSAIC bridge and release certificates."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from typing import Sequence

import numpy as np


RADIUS_OUTWARD_GUARD = Fraction(1, 10**12)


def as_fraction(value: int | float | str | Fraction) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, (int, np.integer)):
        return Fraction(int(value), 1)
    return Fraction(str(float(value)))


def normalized_fraction_rows(values: Sequence[Sequence[float]]) -> tuple[tuple[Fraction, ...], ...]:
    rows = []
    for raw_row in values:
        row = tuple(as_fraction(value) for value in raw_row)
        if any(value < 0 for value in row):
            raise ValueError("serialized stochastic rows must be nonnegative")
        total = sum(row, Fraction(0))
        if total <= 0:
            raise ValueError("serialized stochastic rows must have positive mass")
        rows.append(tuple(value / total for value in row))
    if not rows or len({len(row) for row in rows}) != 1:
        raise ValueError("stochastic matrix must be nonempty and rectangular")
    return tuple(rows)


def outward_radius(value: float) -> Fraction:
    radius = as_fraction(value) + RADIUS_OUTWARD_GUARD
    return min(Fraction(2), max(Fraction(0), radius))


def empirical_from_counts(values: Sequence[int]) -> tuple[Fraction, ...]:
    counts = tuple(int(value) for value in values)
    if not counts or any(value < 0 for value in counts):
        raise ValueError("counts must be a nonnegative nonempty vector")
    total = sum(counts)
    if total == 0:
        return tuple(Fraction(1, len(counts)) for _ in counts)
    return tuple(Fraction(value, total) for value in counts)


def l1_expectation_upper_exact(
    empirical: Sequence[Fraction],
    scores: Sequence[Fraction],
    *,
    radius: Fraction,
) -> Fraction:
    probabilities = list(empirical)
    values = tuple(scores)
    if len(probabilities) != len(values) or not probabilities:
        raise ValueError("empirical law and scores must have one common alphabet")
    if sum(probabilities, Fraction(0)) != 1 or any(value < 0 for value in probabilities):
        raise ValueError("empirical law must lie on the simplex")
    if not Fraction(0) <= radius <= Fraction(2):
        raise ValueError("L1 radius must lie in [0, 2]")
    order = sorted(range(len(values)), key=lambda index: (values[index], index))
    budget = radius / 2
    low = 0
    high = len(order) - 1
    while budget > 0 and low < high:
        donor = order[low]
        receiver = order[high]
        if values[receiver] <= values[donor]:
            break
        if probabilities[donor] == 0:
            low += 1
            continue
        if probabilities[receiver] == 1:
            high -= 1
            continue
        moved = min(budget, probabilities[donor], 1 - probabilities[receiver])
        probabilities[donor] -= moved
        probabilities[receiver] += moved
        budget -= moved
        if probabilities[donor] == 0:
            low += 1
        if probabilities[receiver] == 1:
            high -= 1
    return sum(
        (probability * score for probability, score in zip(probabilities, values, strict=True)),
        Fraction(0),
    )


def l1_expectation_lower_exact(
    empirical: Sequence[Fraction],
    scores: Sequence[Fraction],
    *,
    radius: Fraction,
) -> Fraction:
    return -l1_expectation_upper_exact(
        empirical, tuple(-score for score in scores), radius=radius
    )


def matrix_vector(
    matrix: Sequence[Sequence[Fraction]], vector: Sequence[Fraction]
) -> tuple[Fraction, ...]:
    return tuple(
        sum((weight * value for weight, value in zip(row, vector, strict=True)), Fraction(0))
        for row in matrix
    )


@dataclass(frozen=True)
class RationalBridgeLabelAudit:
    retained_mass: Fraction
    contamination: Fraction
    minimum_membership_slack: Fraction
    transform: tuple[tuple[Fraction, ...], ...]


@dataclass(frozen=True)
class RationalBridgeAudit:
    labels: tuple[RationalBridgeLabelAudit, ...]
    minimum_membership_slack: Fraction


@dataclass(frozen=True)
class RationalReleaseAudit:
    source_advantages: tuple[Fraction, ...]
    worst_conditional_error: Fraction


def audit_bridge_exact(
    reference_counts: Sequence[Sequence[Sequence[int]]],
    bridge_counts: Sequence[Sequence[Sequence[int]]],
    *,
    reference_l1_radii: Sequence[Sequence[float]],
    bridge_l1_radii: Sequence[Sequence[float]],
    serialized_labels: Sequence[dict[str, object]],
) -> RationalBridgeAudit:
    reference = np.asarray(reference_counts, dtype=np.int64)
    bridge = np.asarray(bridge_counts, dtype=np.int64)
    if reference.shape != bridge.shape or reference.ndim != 3:
        raise ValueError("reference and bridge count tensors must share a 3D shape")
    label_count, source_count, token_count = reference.shape
    if len(serialized_labels) != label_count:
        raise ValueError("provide one serialized bridge label per task label")
    reference_radii = np.asarray(reference_l1_radii, dtype=np.float64)
    bridge_radii = np.asarray(bridge_l1_radii, dtype=np.float64)
    if reference_radii.shape != (label_count, source_count) or bridge_radii.shape != (
        label_count,
        source_count,
    ):
        raise ValueError("radius matrices have the wrong shape")

    audits = []
    for label_index, serialized in enumerate(serialized_labels):
        transform = normalized_fraction_rows(serialized["transform"])
        if len(transform) != token_count or len(transform[0]) != token_count:
            raise ValueError("bridge transform has the wrong shape")
        retained = as_fraction(serialized["retained_mass"])
        if not Fraction(0) <= retained <= Fraction(1):
            raise ValueError("retained mass must lie in [0, 1]")
        slacks = []
        for source in range(source_count):
            p = empirical_from_counts(reference[label_index, source])
            q = empirical_from_counts(bridge[label_index, source])
            p_radius = outward_radius(float(reference_radii[label_index, source]))
            q_radius = outward_radius(float(bridge_radii[label_index, source]))
            for output in range(token_count):
                indicator = tuple(
                    Fraction(int(token == output), 1) for token in range(token_count)
                )
                lower = l1_expectation_lower_exact(q, indicator, radius=q_radius)
                score = tuple(row[output] for row in transform)
                upper = l1_expectation_upper_exact(p, score, radius=p_radius)
                slacks.append(lower - retained * upper)
        audits.append(
            RationalBridgeLabelAudit(
                retained_mass=retained,
                contamination=1 - retained,
                minimum_membership_slack=min(slacks),
                transform=transform,
            )
        )
    return RationalBridgeAudit(
        labels=tuple(audits),
        minimum_membership_slack=min(
            audit.minimum_membership_slack for audit in audits
        ),
    )


def audit_release_exact(
    reference_counts: Sequence[Sequence[Sequence[int]]],
    *,
    reference_l1_radii: Sequence[Sequence[float]],
    bridge: RationalBridgeAudit,
    release_channel: Sequence[Sequence[float]],
    decoder: Sequence[int],
) -> RationalReleaseAudit:
    counts = np.asarray(reference_counts, dtype=np.int64)
    if counts.ndim != 3:
        raise ValueError("reference counts must be a 3D tensor")
    label_count, source_count, token_count = counts.shape
    radii = np.asarray(reference_l1_radii, dtype=np.float64)
    if radii.shape != (label_count, source_count):
        raise ValueError("reference radii have the wrong shape")
    channel = normalized_fraction_rows(release_channel)
    if len(channel) != token_count:
        raise ValueError("release channel has the wrong fine alphabet")
    released_count = len(channel[0])
    decoder_values = tuple(int(value) for value in decoder)
    if len(decoder_values) != released_count:
        raise ValueError("decoder has the wrong released alphabet")

    source_advantages = []
    utility_values = []
    for label in range(label_count):
        transform = bridge.labels[label].transform
        retained = bridge.labels[label].retained_mass
        contamination = 1 - retained
        best_accuracy = Fraction(0)
        for assignment in product(range(source_count), repeat=released_count):
            score = Fraction(0)
            for source in range(source_count):
                correct = tuple(
                    Fraction(int(assigned == source), 1) for assigned in assignment
                )
                fine_score = matrix_vector(channel, correct)
                transformed_score = matrix_vector(transform, fine_score)
                empirical = empirical_from_counts(counts[label, source])
                support = l1_expectation_upper_exact(
                    empirical,
                    transformed_score,
                    radius=outward_radius(float(radii[label, source])),
                )
                score += retained * support + contamination * max(fine_score)
            best_accuracy = max(best_accuracy, score / source_count)
        chance = Fraction(1, source_count)
        source_advantages.append((best_accuracy - chance) / (1 - chance))

        loss = tuple(
            Fraction(int(prediction != label), 1) for prediction in decoder_values
        )
        fine_loss = matrix_vector(channel, loss)
        transformed_loss = matrix_vector(transform, fine_loss)
        for source in range(source_count):
            empirical = empirical_from_counts(counts[label, source])
            support = l1_expectation_upper_exact(
                empirical,
                transformed_loss,
                radius=outward_radius(float(radii[label, source])),
            )
            utility_values.append(
                retained * support + contamination * max(fine_loss)
            )
    return RationalReleaseAudit(
        source_advantages=tuple(source_advantages),
        worst_conditional_error=max(utility_values),
    )


def fraction_decimal(value: Fraction, digits: int = 18) -> str:
    """Return an upward decimal approximation for compact audit receipts."""

    if digits < 1:
        raise ValueError("digits must be positive")
    scale = 10**digits
    numerator = value.numerator * scale
    quotient, remainder = divmod(numerator, value.denominator)
    if remainder:
        quotient += 1
    whole, fraction = divmod(quotient, scale)
    return f"{whole}.{fraction:0{digits}d}"
