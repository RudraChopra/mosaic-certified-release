"""Finite-sample certification of MOSAIC's structured deployment shift."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

import numpy as np
from scipy.optimize import linprog

from mosaic_channel import (
    l1_ball_expectation_lower,
    l1_ball_expectation_upper,
)


@dataclass(frozen=True)
class BridgeLabelCertificate:
    """One label's certified source-blind transform and retained mass."""

    transform: np.ndarray
    retained_mass: float
    contamination: float
    optimal_retained_mass_upper: float
    reference_l1_radii: tuple[float, ...]
    bridge_l1_radii: tuple[float, ...]
    bridge_coordinate_lowers: tuple[tuple[float, ...], ...]
    minimum_membership_slack: float
    transform_trace: float
    solver_status: str
    solver_iterations: int
    method: str


@dataclass(frozen=True)
class BridgeMembershipCertificate:
    """Simultaneous structured-shift certificate for every task label."""

    labels: tuple[BridgeLabelCertificate, ...]
    label_count: int
    source_count: int
    token_count: int
    method: str

    @property
    def retained_masses(self) -> tuple[float, ...]:
        return tuple(value.retained_mass for value in self.labels)

    @property
    def contaminations(self) -> tuple[float, ...]:
        return tuple(value.contamination for value in self.labels)

    @property
    def transforms_by_label(self) -> tuple[tuple[np.ndarray, ...], ...]:
        return tuple((value.transform,) for value in self.labels)


def _probability_tensor(
    values: Sequence[Sequence[Sequence[float]]], *, name: str
) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.ndim != 3 or min(array.shape) < 2:
        raise ValueError(f"{name} must have shape labels x sources x tokens")
    if not np.isfinite(array).all() or np.any(array < -1e-12):
        raise ValueError(f"{name} must be finite and nonnegative")
    if not np.allclose(array.sum(axis=2), 1.0, atol=1e-10, rtol=0.0):
        raise ValueError(f"every row of {name} must sum to one")
    return np.clip(array, 0.0, 1.0)


def _radius_matrix(
    values: Sequence[Sequence[float]], *, shape: tuple[int, int], name: str
) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    if array.shape != shape:
        raise ValueError(f"{name} must have shape {shape}")
    if not np.isfinite(array).all() or np.any(array < 0.0):
        raise ValueError(f"{name} must be finite and nonnegative")
    return np.clip(array, 0.0, 2.0)


class _BridgeLP:
    """Exact robust LP using the dual of each multinomial L1 support."""

    def __init__(
        self,
        reference: np.ndarray,
        reference_radii: np.ndarray,
        bridge_lowers: np.ndarray,
    ) -> None:
        self.reference = reference
        self.reference_radii = reference_radii
        self.bridge_lowers = bridge_lowers
        self.source_count, self.token_count = reference.shape
        self.cursor = 0
        self.transform_mass = np.arange(
            self.cursor, self.cursor + self.token_count * self.token_count
        ).reshape(self.token_count, self.token_count)
        self.cursor += self.token_count * self.token_count
        self.retained_mass = self.cursor
        self.cursor += 1
        self.duals: dict[tuple[int, int], tuple[np.ndarray, int, int]] = {}
        for source in range(self.source_count):
            for output in range(self.token_count):
                multipliers = np.arange(self.cursor, self.cursor + self.token_count)
                self.cursor += self.token_count
                simplex_multiplier = self.cursor
                self.cursor += 1
                radius_multiplier = self.cursor
                self.cursor += 1
                self.duals[source, output] = (
                    multipliers,
                    simplex_multiplier,
                    radius_multiplier,
                )

    def bounds(self) -> list[tuple[float | None, float | None]]:
        bounds: list[tuple[float | None, float | None]] = [
            (0.0, 1.0) for _ in range(self.token_count * self.token_count)
        ]
        bounds.append((0.0, 1.0))
        for _ in range(self.source_count * self.token_count):
            bounds.extend([(None, None)] * self.token_count)
            bounds.append((None, None))
            bounds.append((0.0, None))
        return bounds

    def constraints(
        self, *, fixed_retained_mass: float | None = None
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        equalities: list[np.ndarray] = []
        equality_values: list[float] = []
        for fine_token in range(self.token_count):
            row = np.zeros(self.cursor)
            row[self.transform_mass[fine_token]] = 1.0
            row[self.retained_mass] = -1.0
            equalities.append(row)
            equality_values.append(0.0)
        if fixed_retained_mass is not None:
            row = np.zeros(self.cursor)
            row[self.retained_mass] = 1.0
            equalities.append(row)
            equality_values.append(float(fixed_retained_mass))

        inequalities: list[np.ndarray] = []
        inequality_values: list[float] = []
        for source in range(self.source_count):
            empirical = self.reference[source]
            radius = float(self.reference_radii[source])
            for output in range(self.token_count):
                multipliers, simplex_multiplier, radius_multiplier = self.duals[
                    source, output
                ]
                for fine_token in range(self.token_count):
                    # W[c,z] <= lambda[c] + mu.
                    row = np.zeros(self.cursor)
                    row[self.transform_mass[fine_token, output]] = 1.0
                    row[multipliers[fine_token]] = -1.0
                    row[simplex_multiplier] = -1.0
                    inequalities.append(row)
                    inequality_values.append(0.0)

                    # |lambda[c]| <= gamma.
                    row = np.zeros(self.cursor)
                    row[multipliers[fine_token]] = 1.0
                    row[radius_multiplier] = -1.0
                    inequalities.append(row)
                    inequality_values.append(0.0)
                    row = np.zeros(self.cursor)
                    row[multipliers[fine_token]] = -1.0
                    row[radius_multiplier] = -1.0
                    inequalities.append(row)
                    inequality_values.append(0.0)

                # h_C(W[:,z]) <= lower bridge mass.
                row = np.zeros(self.cursor)
                row[multipliers] = empirical
                row[simplex_multiplier] = 1.0
                row[radius_multiplier] = radius
                inequalities.append(row)
                inequality_values.append(float(self.bridge_lowers[source, output]))
        return (
            np.asarray(inequalities),
            np.asarray(inequality_values),
            np.asarray(equalities),
            np.asarray(equality_values),
        )

    def solve(
        self, *, maximize_trace: bool, fixed_retained_mass: float | None = None
    ) -> object:
        objective = np.zeros(self.cursor)
        if maximize_trace:
            for token in range(self.token_count):
                objective[self.transform_mass[token, token]] = -1.0
        else:
            objective[self.retained_mass] = -1.0
        a_ub, b_ub, a_eq, b_eq = self.constraints(
            fixed_retained_mass=fixed_retained_mass
        )
        return linprog(
            objective,
            A_ub=a_ub,
            b_ub=b_ub,
            A_eq=a_eq,
            b_eq=b_eq,
            bounds=self.bounds(),
            method="highs",
            options={"dual_feasibility_tolerance": 1e-9, "primal_feasibility_tolerance": 1e-9},
        )


def _coordinate_lowers(
    empirical: np.ndarray, radii: np.ndarray
) -> np.ndarray:
    source_count, token_count = empirical.shape
    indicators = np.eye(token_count, dtype=np.float64)
    lowers = np.asarray(
        [
            [
                l1_ball_expectation_lower(
                    empirical[source], indicators[token], l1_radius=float(radii[source])
                )
                for token in range(token_count)
            ]
            for source in range(source_count)
        ]
    )
    return np.clip(lowers, 0.0, 1.0)


def _certify_label(
    reference: np.ndarray,
    reference_radii: np.ndarray,
    bridge: np.ndarray,
    bridge_radii: np.ndarray,
    *,
    numerical_margin: float,
) -> BridgeLabelCertificate:
    lowers = _coordinate_lowers(bridge, bridge_radii)
    problem = _BridgeLP(reference, reference_radii, lowers)
    primary = problem.solve(maximize_trace=False)
    if not primary.success:
        raise RuntimeError(f"bridge retained-mass LP failed: {primary.message}")
    optimal_retained = float(primary.x[problem.retained_mass])
    retained = max(0.0, optimal_retained - numerical_margin)
    secondary = problem.solve(
        maximize_trace=True, fixed_retained_mass=retained
    )
    if not secondary.success:
        raise RuntimeError(f"bridge transform LP failed: {secondary.message}")
    if retained <= 1e-15:
        transform = np.eye(problem.token_count, dtype=np.float64)
    else:
        transform = (
            secondary.x[problem.transform_mass].reshape(
                problem.token_count, problem.token_count
            )
            / retained
        )
    transform = np.clip(transform, 0.0, 1.0)
    transform /= transform.sum(axis=1, keepdims=True)

    slacks = []
    for source in range(problem.source_count):
        for output in range(problem.token_count):
            support = l1_ball_expectation_upper(
                reference[source],
                transform[:, output],
                l1_radius=float(reference_radii[source]),
            )
            slacks.append(float(lowers[source, output] - retained * support))
    minimum_slack = min(slacks)
    if minimum_slack < -max(5e-8, 10.0 * numerical_margin):
        raise RuntimeError(
            f"bridge certificate violates independently recomputed support by {-minimum_slack}"
        )
    return BridgeLabelCertificate(
        transform=transform,
        retained_mass=retained,
        contamination=1.0 - retained,
        optimal_retained_mass_upper=optimal_retained,
        reference_l1_radii=tuple(float(value) for value in reference_radii),
        bridge_l1_radii=tuple(float(value) for value in bridge_radii),
        bridge_coordinate_lowers=tuple(
            tuple(float(value) for value in row) for row in lowers
        ),
        minimum_membership_slack=minimum_slack,
        transform_trace=float(np.trace(transform)),
        solver_status=str(secondary.message),
        solver_iterations=int(primary.nit + secondary.nit),
        method="exact_l1_bridge_membership_lp_dual",
    )


def certify_bridge_membership(
    reference_empirical_distributions: Sequence[Sequence[Sequence[float]]],
    *,
    reference_l1_radii: Sequence[Sequence[float]],
    bridge_empirical_distributions: Sequence[Sequence[Sequence[float]]],
    bridge_l1_radii: Sequence[Sequence[float]],
    numerical_margin: float = 1e-7,
) -> BridgeMembershipCertificate:
    """Certify a common source-blind transform for each task label.

    On the simultaneous reference and bridge confidence event, the returned
    transform ``T_y`` and retained mass ``t_y`` satisfy

        q_{s,y} = t_y p_{s,y} T_y + (1 - t_y) r_{s,y}

    for every source and some probability vector ``r_{s,y}``. The LP may select
    each transform from the same tables because its robust constraints cover
    the complete product of confidence sets.
    """

    reference = _probability_tensor(
        reference_empirical_distributions, name="reference distributions"
    )
    bridge = _probability_tensor(
        bridge_empirical_distributions, name="bridge distributions"
    )
    if bridge.shape != reference.shape:
        raise ValueError("reference and bridge distributions must share a shape")
    label_count, source_count, token_count = reference.shape
    reference_radii = _radius_matrix(
        reference_l1_radii,
        shape=(label_count, source_count),
        name="reference radii",
    )
    bridge_radii_array = _radius_matrix(
        bridge_l1_radii,
        shape=(label_count, source_count),
        name="bridge radii",
    )
    if not np.isfinite(numerical_margin) or not 0.0 < numerical_margin < 1e-3:
        raise ValueError("numerical_margin must lie in (0, 1e-3)")
    labels = tuple(
        _certify_label(
            reference[label],
            reference_radii[label],
            bridge[label],
            bridge_radii_array[label],
            numerical_margin=float(numerical_margin),
        )
        for label in range(label_count)
    )
    return BridgeMembershipCertificate(
        labels=labels,
        label_count=label_count,
        source_count=source_count,
        token_count=token_count,
        method="simultaneous_exact_l1_bridge_membership",
    )
