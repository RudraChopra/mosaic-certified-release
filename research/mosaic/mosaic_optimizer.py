"""Globally optimize MOSAIC finite stochastic release channels.

For a fixed released alphabet, each decoder assignment is solved by a mixed-
integer linear program.  Continuous variables describe the stochastic release
channel and exact robust-confidence epigraphs.  Binary variables choose the
tighter of the channel-capacity and coupled-shift branches for privacy and
utility.  Enumerating the finite decoder family therefore gives a global
optimum for the stated finite problem, subject to the MILP solver certificate.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from itertools import product
from typing import Sequence

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

from mosaic_channel import MAX_EXACT_ASSIGNMENTS
from mosaic_exact import (
    ExactExternalAttackerRisk,
    ExactExternalUtilityRisk,
    exact_external_attacker_risk,
    exact_external_utility_risk,
)
from mosaic_invariant import (
    PreReleaseAttackerCertificate,
    PreReleaseUtilityCertificate,
    adaptive_pre_release_attacker_certificate,
    pre_release_utility_certificate,
)


BIG_M = 2.0
MAX_DECODER_ASSIGNMENTS = 100_000
POSTHOC_TOLERANCE = 2e-7
GLOBAL_MIP_GAP_TOLERANCE = 1e-10
MIP_FEASIBILITY_TOLERANCE = 1e-9


@dataclass(frozen=True)
class InvariantChannelSolution:
    """Globally optimized channel plus independently recomputed certificates."""

    release_channel: np.ndarray
    decoder: tuple[int, ...]
    certified_worst_conditional_error: float
    solver_objective: float
    privacy_certificates: tuple[PreReleaseAttackerCertificate, ...]
    utility_certificates: tuple[tuple[PreReleaseUtilityCertificate, ...], ...]
    privacy_branches: tuple[str, ...]
    utility_branches: tuple[tuple[str, ...], ...]
    solved_decoder_assignments: int
    source_count: int
    label_count: int
    fine_token_count: int
    released_token_count: int
    solver_status: str
    solver_mip_gap: float
    solver_dual_bound: float
    solver_mip_feasibility_tolerance: float
    max_constraint_violation: float
    method: str


@dataclass(frozen=True)
class PopulationExternalChannelSolution:
    """Population-law optimum used only as a plug-in rule or oracle."""

    release_channel: np.ndarray
    decoder: tuple[int, ...]
    exact_worst_conditional_error: float
    solver_objective: float
    privacy_risks: tuple[ExactExternalAttackerRisk, ...]
    utility_risks: tuple[tuple[ExactExternalUtilityRisk, ...], ...]
    solved_decoder_assignments: int
    source_count: int
    label_count: int
    fine_token_count: int
    released_token_count: int
    solver_status: str
    max_constraint_violation: float
    method: str


class _MILPBuilder:
    def __init__(self) -> None:
        self.objective: list[float] = []
        self.lower_bounds: list[float] = []
        self.upper_bounds: list[float] = []
        self.integrality: list[int] = []
        self.rows: list[dict[int, float]] = []
        self.row_lower: list[float] = []
        self.row_upper: list[float] = []

    def add_variable(
        self,
        *,
        lower: float = 0.0,
        upper: float = np.inf,
        objective: float = 0.0,
        integer: bool = False,
    ) -> int:
        index = len(self.objective)
        self.objective.append(float(objective))
        self.lower_bounds.append(float(lower))
        self.upper_bounds.append(float(upper))
        self.integrality.append(1 if integer else 0)
        return index

    def add_upper(self, coefficients: dict[int, float], upper: float) -> None:
        self.rows.append(_clean_expression(coefficients))
        self.row_lower.append(-np.inf)
        self.row_upper.append(float(upper))

    def add_equality(self, coefficients: dict[int, float], value: float) -> None:
        self.rows.append(_clean_expression(coefficients))
        self.row_lower.append(float(value))
        self.row_upper.append(float(value))

    def matrices(self) -> tuple[np.ndarray, Bounds, LinearConstraint]:
        row_indices: list[int] = []
        column_indices: list[int] = []
        data: list[float] = []
        for row_index, row in enumerate(self.rows):
            for column_index, value in row.items():
                row_indices.append(row_index)
                column_indices.append(column_index)
                data.append(value)
        matrix = coo_matrix(
            (data, (row_indices, column_indices)),
            shape=(len(self.rows), len(self.objective)),
            dtype=np.float64,
        ).tocsr()
        bounds = Bounds(
            np.asarray(self.lower_bounds), np.asarray(self.upper_bounds)
        )
        constraints = LinearConstraint(
            matrix,
            np.asarray(self.row_lower),
            np.asarray(self.row_upper),
        )
        return np.asarray(self.objective), bounds, constraints


def _clean_expression(coefficients: dict[int, float]) -> dict[int, float]:
    return {
        int(index): float(value)
        for index, value in coefficients.items()
        if abs(value) > 1e-15
    }


def _add_term(expression: dict[int, float], index: int, value: float) -> None:
    expression[index] = expression.get(index, 0.0) + float(value)


def _validated_problem(
    empirical_distributions: Sequence[Sequence[Sequence[float]]],
    l1_radii: Sequence[Sequence[float]],
    common_channels_by_label: Sequence[
        Sequence[Sequence[Sequence[float]]]
    ],
    contaminations: Sequence[float],
    privacy_advantage_thresholds: Sequence[float],
) -> tuple[
    np.ndarray,
    np.ndarray,
    tuple[tuple[np.ndarray, ...], ...],
    np.ndarray,
    np.ndarray,
]:
    empirical = np.asarray(empirical_distributions, dtype=np.float64)
    if empirical.ndim != 3:
        raise ValueError("empirical laws must have shape (labels, sources, tokens)")
    label_count, source_count, fine_count = empirical.shape
    if label_count < 2 or source_count < 2 or fine_count < 2:
        raise ValueError("at least two labels, sources, and fine tokens are required")
    if not np.isfinite(empirical).all() or np.any(empirical < -1e-12):
        raise ValueError("empirical probabilities must be finite and non-negative")
    if not np.allclose(empirical.sum(axis=2), 1.0, atol=1e-10):
        raise ValueError("every empirical source-label law must sum to one")
    empirical = np.clip(empirical, 0.0, 1.0)

    radii = np.asarray(l1_radii, dtype=np.float64)
    if radii.shape != (label_count, source_count):
        raise ValueError("l1_radii must have shape (labels, sources)")
    if not np.isfinite(radii).all() or np.any(radii < 0.0):
        raise ValueError("L1 radii must be finite and non-negative")
    radii = np.minimum(radii, 2.0)

    if len(common_channels_by_label) != label_count:
        raise ValueError("provide one common-channel library per label")
    libraries = []
    for library in common_channels_by_label:
        if not library:
            raise ValueError("every label needs at least one common channel")
        checked = []
        for channel in library:
            matrix = np.asarray(channel, dtype=np.float64)
            if matrix.shape != (fine_count, fine_count):
                raise ValueError("common channels must have shape (K, K)")
            if not np.isfinite(matrix).all() or np.any(matrix < -1e-12):
                raise ValueError("common channels must be finite and non-negative")
            if not np.allclose(matrix.sum(axis=1), 1.0, atol=1e-10):
                raise ValueError("every common-channel row must sum to one")
            checked.append(np.clip(matrix, 0.0, 1.0))
        libraries.append(tuple(checked))

    eta = np.asarray(contaminations, dtype=np.float64)
    thresholds = np.asarray(privacy_advantage_thresholds, dtype=np.float64)
    if eta.shape != (label_count,) or thresholds.shape != (label_count,):
        raise ValueError("contaminations and thresholds need one value per label")
    if (
        not np.isfinite(eta).all()
        or np.any(eta < 0.0)
        or np.any(eta > 1.0)
    ):
        raise ValueError("contaminations must lie in [0, 1]")
    if (
        not np.isfinite(thresholds).all()
        or np.any(thresholds < 0.0)
        or np.any(thresholds > 1.0)
    ):
        raise ValueError("normalized privacy thresholds must lie in [0, 1]")
    return empirical, radii, tuple(libraries), eta, thresholds


def _add_linear_score(
    expression: dict[int, float],
    channel_indices: np.ndarray,
    fine_token: int,
    output_weights: np.ndarray,
    coefficient: float = 1.0,
) -> None:
    for output, weight in enumerate(output_weights):
        _add_term(
            expression,
            int(channel_indices[fine_token, output]),
            coefficient * float(weight),
        )


def _add_l1_support_epigraph(
    builder: _MILPBuilder,
    channel_indices: np.ndarray,
    empirical: np.ndarray,
    radius: float,
    output_weights: np.ndarray,
) -> int:
    """Add the exact support-function dual and return its epigraph variable."""

    fine_count = empirical.size
    phi = builder.add_variable(lower=0.0, upper=1.0)
    nu_positive = builder.add_variable(lower=0.0)
    nu_negative = builder.add_variable(lower=0.0)
    lam = builder.add_variable(lower=0.0)
    theta = np.asarray(
        [builder.add_variable(lower=-np.inf, upper=np.inf) for _ in range(fine_count)]
    )

    for token in range(fine_count):
        # score[token] <= nu + theta[token]
        expression: dict[int, float] = {
            nu_positive: -1.0,
            nu_negative: 1.0,
            int(theta[token]): -1.0,
        }
        _add_linear_score(
            expression, channel_indices, token, output_weights
        )
        builder.add_upper(expression, 0.0)

        builder.add_upper(
            {int(theta[token]): 1.0, lam: -1.0}, 0.0
        )
        builder.add_upper(
            {int(theta[token]): -1.0, lam: -1.0}, 0.0
        )

    # nu + p_hat^T theta + epsilon lambda <= phi
    expression = {
        nu_positive: 1.0,
        nu_negative: -1.0,
        lam: float(radius),
        phi: -1.0,
    }
    for token, probability in enumerate(empirical):
        _add_term(expression, int(theta[token]), float(probability))
    builder.add_upper(expression, 0.0)
    return phi


def _build_decoder_problem(
    empirical: np.ndarray,
    radii: np.ndarray,
    libraries: tuple[tuple[np.ndarray, ...], ...],
    eta: np.ndarray,
    thresholds: np.ndarray,
    *,
    released_count: int,
    decoder: tuple[int, ...],
) -> tuple[
    _MILPBuilder,
    np.ndarray,
    list[int],
    list[list[int]],
    int,
]:
    label_count, source_count, fine_count = empirical.shape
    builder = _MILPBuilder()
    channel_indices = np.asarray(
        [
            [
                builder.add_variable(lower=0.0, upper=1.0)
                for _ in range(released_count)
            ]
            for _ in range(fine_count)
        ]
    )
    for token in range(fine_count):
        builder.add_equality(
            {
                int(channel_indices[token, output]): 1.0
                for output in range(released_count)
            },
            1.0,
        )

    attacker_assignments = tuple(
        product(range(source_count), repeat=released_count)
    )

    reference_bounds: list[int] = []
    for label in range(label_count):
        reference_bound = builder.add_variable(
            lower=1.0 / source_count, upper=1.0
        )
        reference_bounds.append(reference_bound)
        for assignment in attacker_assignments:
            assignment_array = np.asarray(assignment, dtype=np.int64)
            expression = {reference_bound: -1.0}
            for source in range(source_count):
                correct_outputs = (assignment_array == source).astype(float)
                phi = _add_l1_support_epigraph(
                    builder,
                    channel_indices,
                    empirical[label, source],
                    float(radii[label, source]),
                    correct_outputs,
                )
                _add_term(expression, phi, 1.0 / source_count)
            builder.add_upper(expression, 0.0)

    capacity = builder.add_variable(
        lower=1.0 / source_count, upper=1.0
    )
    for assignment in attacker_assignments:
        assignment_array = np.asarray(assignment, dtype=np.int64)
        expression = {capacity: -1.0}
        for source in range(source_count):
            row_maximum = builder.add_variable(lower=0.0, upper=1.0)
            correct_outputs = (assignment_array == source).astype(float)
            for token in range(fine_count):
                row_expression = {row_maximum: -1.0}
                _add_linear_score(
                    row_expression,
                    channel_indices,
                    token,
                    correct_outputs,
                )
                builder.add_upper(row_expression, 0.0)
            _add_term(expression, row_maximum, 1.0 / source_count)
        builder.add_upper(expression, 0.0)

    invariance_bounds: list[int] = []
    directional_bounds: list[int] = []
    error_capacities: list[int] = []
    reference_errors: list[list[int]] = []
    decoder_array = np.asarray(decoder, dtype=np.int64)

    for label in range(label_count):
        loss = (decoder_array != label).astype(float)
        rho = builder.add_variable(lower=0.0, upper=1.0)
        kappa = builder.add_variable(lower=0.0, upper=1.0)
        error_capacity = builder.add_variable(lower=0.0, upper=1.0)
        invariance_bounds.append(rho)
        directional_bounds.append(kappa)
        error_capacities.append(error_capacity)

        for token in range(fine_count):
            expression = {error_capacity: -1.0}
            _add_linear_score(expression, channel_indices, token, loss)
            builder.add_upper(expression, 0.0)

        for transform in libraries[label]:
            for token in range(fine_count):
                absolute_differences = []
                directional_expression = {kappa: -1.0}
                for output in range(released_count):
                    absolute = builder.add_variable(lower=0.0, upper=1.0)
                    absolute_differences.append(absolute)
                    difference: dict[int, float] = {}
                    for shifted_token in range(fine_count):
                        _add_term(
                            difference,
                            int(channel_indices[shifted_token, output]),
                            float(transform[token, shifted_token]),
                        )
                    _add_term(
                        difference,
                        int(channel_indices[token, output]),
                        -1.0,
                    )
                    positive = dict(difference)
                    _add_term(positive, absolute, -1.0)
                    builder.add_upper(positive, 0.0)
                    negative = {
                        index: -value for index, value in difference.items()
                    }
                    _add_term(negative, absolute, -1.0)
                    builder.add_upper(negative, 0.0)
                    for index, value in difference.items():
                        _add_term(
                            directional_expression,
                            index,
                            float(loss[output]) * value,
                        )
                rho_expression = {rho: -1.0}
                for absolute in absolute_differences:
                    _add_term(rho_expression, absolute, 0.5)
                builder.add_upper(rho_expression, 0.0)
                builder.add_upper(directional_expression, 0.0)

        label_reference_errors = []
        for source in range(source_count):
            error_bound = _add_l1_support_epigraph(
                builder,
                channel_indices,
                empirical[label, source],
                float(radii[label, source]),
                loss,
            )
            label_reference_errors.append(error_bound)
        reference_errors.append(label_reference_errors)

    privacy_branch_indices: list[int] = []
    chance = 1.0 / source_count
    privacy_ba_thresholds = chance + (1.0 - chance) * thresholds
    for label in range(label_count):
        branch = builder.add_variable(lower=0.0, upper=1.0, integer=True)
        privacy_branch_indices.append(branch)
        # branch=0: capacity is active.
        builder.add_upper(
            {capacity: 1.0, branch: -BIG_M},
            float(privacy_ba_thresholds[label]),
        )
        # branch=1: coupled reference-plus-invariance bound is active.
        coupled_expression = {
            reference_bounds[label]: 1.0 - float(eta[label]),
            invariance_bounds[label]: 1.0 - float(eta[label]),
            capacity: float(eta[label]),
            branch: BIG_M,
        }
        builder.add_upper(
            coupled_expression,
            float(privacy_ba_thresholds[label]) + BIG_M,
        )

    worst_error = builder.add_variable(
        lower=0.0, upper=1.0, objective=1.0
    )
    utility_branch_indices: list[list[int]] = []
    for label in range(label_count):
        label_branches = []
        for source in range(source_count):
            branch = builder.add_variable(
                lower=0.0, upper=1.0, integer=True
            )
            label_branches.append(branch)
            # branch=0: the channel's distribution-free error capacity is active.
            builder.add_upper(
                {
                    error_capacities[label]: 1.0,
                    worst_error: -1.0,
                    branch: -BIG_M,
                },
                0.0,
            )
            # branch=1: coupled reference-plus-directional-defect is active.
            coupled_expression = {
                reference_errors[label][source]: 1.0 - float(eta[label]),
                directional_bounds[label]: 1.0 - float(eta[label]),
                error_capacities[label]: float(eta[label]),
                worst_error: -1.0,
                branch: BIG_M,
            }
            builder.add_upper(coupled_expression, BIG_M)
        utility_branch_indices.append(label_branches)

    return (
        builder,
        channel_indices,
        privacy_branch_indices,
        utility_branch_indices,
        worst_error,
    )


def _constraint_violation(
    values: np.ndarray, constraints: LinearConstraint, bounds: Bounds
) -> float:
    activity = np.asarray(constraints.A @ values).reshape(-1)
    lower_violation = np.maximum(0.0, constraints.lb - activity)
    upper_violation = np.maximum(0.0, activity - constraints.ub)
    variable_lower = np.maximum(0.0, bounds.lb - values)
    variable_upper = np.maximum(0.0, values - bounds.ub)
    return float(
        max(
            np.max(lower_violation, initial=0.0),
            np.max(upper_violation, initial=0.0),
            np.max(variable_lower, initial=0.0),
            np.max(variable_upper, initial=0.0),
        )
    )


def optimize_invariant_channel(
    empirical_distributions: Sequence[Sequence[Sequence[float]]],
    *,
    l1_radii: Sequence[Sequence[float]],
    common_channels_by_label: Sequence[
        Sequence[Sequence[Sequence[float]]]
    ],
    contaminations: Sequence[float],
    privacy_advantage_thresholds: Sequence[float],
    released_token_count: int,
    decoder_candidates: Sequence[Sequence[int]] | None = None,
    maximum_worst_conditional_error: float | None = None,
    solver_time_limit_seconds: float | None = None,
    mip_relative_gap: float = 0.0,
) -> InvariantChannelSolution:
    """Globally optimize the finite MOSAIC channel/decoder problem.

    The objective is the worst certified conditional task error over all
    source-label strata.  Privacy thresholds are normalized attacker
    advantages.  A solution is returned only after exact post-hoc certificate
    recomputation confirms every requested threshold.
    """

    empirical, radii, libraries, eta, thresholds = _validated_problem(
        empirical_distributions,
        l1_radii,
        common_channels_by_label,
        contaminations,
        privacy_advantage_thresholds,
    )
    label_count, source_count, fine_count = empirical.shape
    if released_token_count < 2:
        raise ValueError("released_token_count must be at least two")
    assignment_count = source_count**released_token_count
    if assignment_count > MAX_EXACT_ASSIGNMENTS:
        raise ValueError(
            f"exact enumeration requires {assignment_count:,} attacker "
            f"assignments; cap is {MAX_EXACT_ASSIGNMENTS:,}"
        )

    if decoder_candidates is None:
        decoder_count = label_count**released_token_count
        if decoder_count > MAX_DECODER_ASSIGNMENTS:
            raise ValueError(
                f"decoder enumeration requires {decoder_count:,} assignments; "
                f"cap is {MAX_DECODER_ASSIGNMENTS:,}"
            )
        decoders = tuple(
            product(range(label_count), repeat=released_token_count)
        )
    else:
        decoders = tuple(
            tuple(int(value) for value in decoder)
            for decoder in decoder_candidates
        )
        if not decoders:
            raise ValueError("decoder_candidates cannot be empty")
        for decoder in decoders:
            if len(decoder) != released_token_count:
                raise ValueError("each decoder needs one label per released token")
            if any(value < 0 or value >= label_count for value in decoder):
                raise ValueError("decoder labels are out of range")

    if not np.isfinite(mip_relative_gap) or mip_relative_gap != 0.0:
        raise ValueError(
            "global optimization requires mip_relative_gap=0.0; approximate "
            "MILP solutions cannot be labeled globally optimal"
        )
    if maximum_worst_conditional_error is not None and (
        not np.isfinite(maximum_worst_conditional_error)
        or maximum_worst_conditional_error < 0.0
        or maximum_worst_conditional_error > 1.0
    ):
        raise ValueError("maximum_worst_conditional_error must lie in [0, 1]")
    if solver_time_limit_seconds is not None and (
        not np.isfinite(solver_time_limit_seconds)
        or solver_time_limit_seconds <= 0.0
    ):
        raise ValueError("solver time limit must be positive")

    best: dict[str, object] | None = None
    solver_messages = []
    for decoder in decoders:
        (
            builder,
            channel_indices,
            privacy_branch_indices,
            utility_branch_indices,
            _,
        ) = _build_decoder_problem(
            empirical,
            radii,
            libraries,
            eta,
            thresholds,
            released_count=released_token_count,
            decoder=decoder,
        )
        objective, bounds, constraints = builder.matrices()
        options: dict[str, float] = {"mip_rel_gap": float(mip_relative_gap)}
        options["mip_feasibility_tolerance"] = MIP_FEASIBILITY_TOLERANCE
        if solver_time_limit_seconds is not None:
            options["time_limit"] = float(solver_time_limit_seconds)
        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Unrecognized options detected.*mip_feasibility_tolerance",
                category=RuntimeWarning,
            )
            result = milp(
                objective,
                integrality=np.asarray(builder.integrality, dtype=np.int32),
                bounds=bounds,
                constraints=constraints,
                options=options,
            )
        solver_messages.append(str(result.message))
        if not result.success or result.x is None or result.fun is None:
            continue
        solver_mip_gap = float(getattr(result, "mip_gap", np.nan))
        solver_dual_bound = float(getattr(result, "mip_dual_bound", np.nan))
        if (
            not np.isfinite(solver_mip_gap)
            or solver_mip_gap > GLOBAL_MIP_GAP_TOLERANCE
        ):
            solver_messages.append(
                f"rejected non-global solution with MIP gap {solver_mip_gap}"
            )
            continue
        values = np.asarray(result.x, dtype=np.float64)
        channel = values[channel_indices]
        channel = np.clip(channel, 0.0, 1.0)
        channel /= channel.sum(axis=1, keepdims=True)
        privacy_certificates = tuple(
            adaptive_pre_release_attacker_certificate(
                empirical[label],
                channel,
                l1_radii=radii[label],
                common_fine_token_channels=libraries[label],
                contamination=float(eta[label]),
            )
            for label in range(label_count)
        )
        if any(
            certificate.normalized_advantage
            > float(thresholds[label]) + POSTHOC_TOLERANCE
            for label, certificate in enumerate(privacy_certificates)
        ):
            raise RuntimeError(
                "POSTHOC_CERTIFICATE_MISMATCH: MILP solution violates a "
                "registered privacy threshold"
            )
        utility_certificates = tuple(
            tuple(
                pre_release_utility_certificate(
                    empirical[label, source],
                    channel,
                    decoder,
                    true_label=label,
                    l1_radius=float(radii[label, source]),
                    common_fine_token_channels=libraries[label],
                    contamination=float(eta[label]),
                )
                for source in range(source_count)
            )
            for label in range(label_count)
        )
        certified_worst_error = max(
            certificate.error_probability
            for label_certificates in utility_certificates
            for certificate in label_certificates
        )
        violation = _constraint_violation(values, constraints, bounds)
        if violation > POSTHOC_TOLERANCE:
            raise RuntimeError(
                "POSTHOC_CONSTRAINT_MISMATCH: solver returned maximum "
                f"constraint violation {violation:.3e}"
            )
        objective_mismatch = abs(float(result.fun) - certified_worst_error)
        if objective_mismatch > POSTHOC_TOLERANCE:
            raise RuntimeError(
                "POSTHOC_OBJECTIVE_MISMATCH: MILP objective and independently "
                f"recomputed certificate differ by {objective_mismatch:.3e}"
            )
        candidate = {
            "channel": channel,
            "decoder": decoder,
            "solver_objective": float(result.fun),
            "certified_worst_error": certified_worst_error,
            "privacy_certificates": privacy_certificates,
            "utility_certificates": utility_certificates,
            "privacy_branches": tuple(
                "coupled_invariance"
                if values[index] >= 0.5
                else "distribution_free_capacity"
                for index in privacy_branch_indices
            ),
            "utility_branches": tuple(
                tuple(
                    "coupled_invariance"
                    if values[index] >= 0.5
                    else "distribution_free_capacity"
                    for index in label_indices
                )
                for label_indices in utility_branch_indices
            ),
            "message": str(result.message),
            "mip_gap": solver_mip_gap,
            "dual_bound": solver_dual_bound,
            "violation": violation,
        }
        if best is None or (
            float(candidate["solver_objective"])
            < float(best["solver_objective"]) - 1e-10
        ):
            best = candidate

    if best is None:
        unique_messages = "; ".join(dict.fromkeys(solver_messages))
        raise RuntimeError(
            "ABSTAIN_NO_FEASIBLE_CHANNEL: no decoder produced a certified "
            f"solution. Solver messages: {unique_messages}"
        )

    if (
        maximum_worst_conditional_error is not None
        and float(best["certified_worst_error"])
        > maximum_worst_conditional_error + POSTHOC_TOLERANCE
    ):
        raise RuntimeError(
            "ABSTAIN_NO_FEASIBLE_CHANNEL: the globally best privacy-feasible "
            "channel has certified worst conditional error "
            f"{float(best['certified_worst_error']):.8f}, above the registered "
            f"limit {maximum_worst_conditional_error:.8f}"
        )

    return InvariantChannelSolution(
        release_channel=np.asarray(best["channel"]),
        decoder=tuple(best["decoder"]),
        certified_worst_conditional_error=float(best["certified_worst_error"]),
        solver_objective=float(best["solver_objective"]),
        privacy_certificates=tuple(best["privacy_certificates"]),
        utility_certificates=tuple(best["utility_certificates"]),
        privacy_branches=tuple(best["privacy_branches"]),
        utility_branches=tuple(best["utility_branches"]),
        solved_decoder_assignments=len(decoders),
        source_count=source_count,
        label_count=label_count,
        fine_token_count=fine_count,
        released_token_count=released_token_count,
        solver_status=str(best["message"]),
        solver_mip_gap=float(best["mip_gap"]),
        solver_dual_bound=float(best["dual_bound"]),
        solver_mip_feasibility_tolerance=MIP_FEASIBILITY_TOLERANCE,
        max_constraint_violation=float(best["violation"]),
        method="global_decoder_enumeration_plus_exact_branch_milp",
    )


def _build_population_decoder_problem(
    population: np.ndarray,
    libraries: tuple[tuple[np.ndarray, ...], ...],
    eta: np.ndarray,
    thresholds: np.ndarray,
    *,
    released_count: int,
    decoder: tuple[int, ...],
) -> tuple[_MILPBuilder, np.ndarray]:
    """Build the exact known-population external-risk LP for one decoder."""

    label_count, source_count, fine_count = population.shape
    builder = _MILPBuilder()
    channel_indices = np.asarray(
        [
            [
                builder.add_variable(lower=0.0, upper=1.0)
                for _ in range(released_count)
            ]
            for _ in range(fine_count)
        ]
    )
    for token in range(fine_count):
        builder.add_equality(
            {
                int(channel_indices[token, output]): 1.0
                for output in range(released_count)
            },
            1.0,
        )

    assignments = tuple(product(range(source_count), repeat=released_count))
    residual_maxima: list[list[int]] = []
    for assignment in assignments:
        assignment_array = np.asarray(assignment, dtype=np.int64)
        source_maxima = []
        for source in range(source_count):
            maximum = builder.add_variable(lower=0.0, upper=1.0)
            source_maxima.append(maximum)
            correct_outputs = (assignment_array == source).astype(np.float64)
            for token in range(fine_count):
                expression = {maximum: -1.0}
                _add_linear_score(
                    expression,
                    channel_indices,
                    token,
                    correct_outputs,
                )
                builder.add_upper(expression, 0.0)
        residual_maxima.append(source_maxima)

    chance = 1.0 / source_count
    privacy_ba_thresholds = chance + (1.0 - chance) * thresholds
    for label in range(label_count):
        retained = 1.0 - float(eta[label])
        for transform in libraries[label]:
            shifted = population[label] @ transform
            for assignment_index, assignment in enumerate(assignments):
                assignment_array = np.asarray(assignment, dtype=np.int64)
                expression: dict[int, float] = {}
                for source in range(source_count):
                    correct_outputs = (
                        assignment_array == source
                    ).astype(np.float64)
                    for token in range(fine_count):
                        _add_linear_score(
                            expression,
                            channel_indices,
                            token,
                            correct_outputs,
                            retained
                            * float(shifted[source, token])
                            / source_count,
                        )
                    _add_term(
                        expression,
                        residual_maxima[assignment_index][source],
                        float(eta[label]) / source_count,
                    )
                builder.add_upper(
                    expression, float(privacy_ba_thresholds[label])
                )

    worst_error = builder.add_variable(
        lower=0.0, upper=1.0, objective=1.0
    )
    decoder_array = np.asarray(decoder, dtype=np.int64)
    for label in range(label_count):
        loss = (decoder_array != label).astype(np.float64)
        error_capacity = builder.add_variable(lower=0.0, upper=1.0)
        for token in range(fine_count):
            expression = {error_capacity: -1.0}
            _add_linear_score(
                expression, channel_indices, token, loss
            )
            builder.add_upper(expression, 0.0)

        retained = 1.0 - float(eta[label])
        for transform in libraries[label]:
            shifted = population[label] @ transform
            for source in range(source_count):
                expression = {
                    error_capacity: float(eta[label]),
                    worst_error: -1.0,
                }
                for token in range(fine_count):
                    _add_linear_score(
                        expression,
                        channel_indices,
                        token,
                        loss,
                        retained * float(shifted[source, token]),
                    )
                builder.add_upper(expression, 0.0)

    return builder, channel_indices


def optimize_population_external_channel(
    population_distributions: Sequence[Sequence[Sequence[float]]],
    *,
    common_channels_by_label: Sequence[
        Sequence[Sequence[Sequence[float]]]
    ],
    contaminations: Sequence[float],
    privacy_advantage_thresholds: Sequence[float],
    released_token_count: int,
    decoder_candidates: Sequence[Sequence[int]] | None = None,
    maximum_worst_conditional_error: float | None = None,
    solver_time_limit_seconds: float | None = None,
) -> PopulationExternalChannelSolution:
    """Globally solve the exact known-population external-risk problem.

    This function has no statistical guarantee: empirical laws supplied here
    produce a plug-in baseline, while true laws produce an unattainable oracle.
    It exists to make both comparisons as strong as the finite shift model
    permits.
    """

    raw = np.asarray(population_distributions, dtype=np.float64)
    if raw.ndim != 3:
        raise ValueError("population laws must have shape (labels, sources, tokens)")
    zero_radii = np.zeros(raw.shape[:2], dtype=np.float64)
    population, _, libraries, eta, thresholds = _validated_problem(
        raw,
        zero_radii,
        common_channels_by_label,
        contaminations,
        privacy_advantage_thresholds,
    )
    label_count, source_count, fine_count = population.shape
    if released_token_count < 2:
        raise ValueError("released_token_count must be at least two")
    assignment_count = source_count**released_token_count
    if assignment_count > MAX_EXACT_ASSIGNMENTS:
        raise ValueError(
            f"exact enumeration requires {assignment_count:,} attacker "
            f"assignments; cap is {MAX_EXACT_ASSIGNMENTS:,}"
        )

    if decoder_candidates is None:
        decoder_count = label_count**released_token_count
        if decoder_count > MAX_DECODER_ASSIGNMENTS:
            raise ValueError(
                f"decoder enumeration requires {decoder_count:,} assignments; "
                f"cap is {MAX_DECODER_ASSIGNMENTS:,}"
            )
        decoders = tuple(product(range(label_count), repeat=released_token_count))
    else:
        decoders = tuple(
            tuple(int(value) for value in decoder)
            for decoder in decoder_candidates
        )
        if not decoders:
            raise ValueError("decoder_candidates cannot be empty")
        for decoder in decoders:
            if len(decoder) != released_token_count:
                raise ValueError("each decoder needs one label per released token")
            if any(value < 0 or value >= label_count for value in decoder):
                raise ValueError("decoder labels are out of range")

    if maximum_worst_conditional_error is not None and (
        not np.isfinite(maximum_worst_conditional_error)
        or maximum_worst_conditional_error < 0.0
        or maximum_worst_conditional_error > 1.0
    ):
        raise ValueError("maximum_worst_conditional_error must lie in [0, 1]")
    if solver_time_limit_seconds is not None and (
        not np.isfinite(solver_time_limit_seconds)
        or solver_time_limit_seconds <= 0.0
    ):
        raise ValueError("solver time limit must be positive")

    best: dict[str, object] | None = None
    solver_messages = []
    for decoder in decoders:
        builder, channel_indices = _build_population_decoder_problem(
            population,
            libraries,
            eta,
            thresholds,
            released_count=released_token_count,
            decoder=decoder,
        )
        objective, bounds, constraints = builder.matrices()
        options: dict[str, float] = {}
        if solver_time_limit_seconds is not None:
            options["time_limit"] = float(solver_time_limit_seconds)
        result = milp(
            objective,
            integrality=np.asarray(builder.integrality, dtype=np.int32),
            bounds=bounds,
            constraints=constraints,
            options=options,
        )
        solver_messages.append(str(result.message))
        if not result.success or result.x is None or result.fun is None:
            continue
        values = np.asarray(result.x, dtype=np.float64)
        channel = np.clip(values[channel_indices], 0.0, 1.0)
        channel /= channel.sum(axis=1, keepdims=True)
        privacy_risks = tuple(
            exact_external_attacker_risk(
                population[label],
                channel,
                libraries[label],
                contamination=float(eta[label]),
            )
            for label in range(label_count)
        )
        if any(
            risk.normalized_advantage
            > float(thresholds[label]) + POSTHOC_TOLERANCE
            for label, risk in enumerate(privacy_risks)
        ):
            raise RuntimeError(
                "POSTHOC_POPULATION_PRIVACY_MISMATCH: LP solution violates "
                "a registered privacy threshold"
            )
        utility_risks = tuple(
            tuple(
                exact_external_utility_risk(
                    population[label, source],
                    channel,
                    decoder,
                    true_label=label,
                    common_fine_token_channels=libraries[label],
                    contamination=float(eta[label]),
                )
                for source in range(source_count)
            )
            for label in range(label_count)
        )
        exact_worst_error = max(
            risk.error_probability
            for label_risks in utility_risks
            for risk in label_risks
        )
        objective_mismatch = abs(float(result.fun) - exact_worst_error)
        if objective_mismatch > POSTHOC_TOLERANCE:
            raise RuntimeError(
                "POSTHOC_POPULATION_OBJECTIVE_MISMATCH: LP objective and exact "
                f"external evaluator differ by {objective_mismatch:.3e}"
            )
        violation = _constraint_violation(values, constraints, bounds)
        if violation > POSTHOC_TOLERANCE:
            raise RuntimeError(
                "POSTHOC_POPULATION_CONSTRAINT_MISMATCH: solver returned "
                f"maximum constraint violation {violation:.3e}"
            )
        candidate = {
            "channel": channel,
            "decoder": decoder,
            "solver_objective": float(result.fun),
            "exact_worst_error": exact_worst_error,
            "privacy_risks": privacy_risks,
            "utility_risks": utility_risks,
            "message": str(result.message),
            "violation": violation,
        }
        if best is None or float(candidate["solver_objective"]) < (
            float(best["solver_objective"]) - 1e-10
        ):
            best = candidate

    if best is None:
        unique_messages = "; ".join(dict.fromkeys(solver_messages))
        raise RuntimeError(
            "NO_POPULATION_FEASIBLE_CHANNEL: no decoder produced a solution. "
            f"Solver messages: {unique_messages}"
        )
    if (
        maximum_worst_conditional_error is not None
        and float(best["exact_worst_error"])
        > maximum_worst_conditional_error + POSTHOC_TOLERANCE
    ):
        raise RuntimeError(
            "ABSTAIN_POPULATION_UTILITY: the best privacy-feasible channel has "
            f"exact worst error {float(best['exact_worst_error']):.8f}, above "
            f"the registered limit {maximum_worst_conditional_error:.8f}"
        )

    return PopulationExternalChannelSolution(
        release_channel=np.asarray(best["channel"]),
        decoder=tuple(best["decoder"]),
        exact_worst_conditional_error=float(best["exact_worst_error"]),
        solver_objective=float(best["solver_objective"]),
        privacy_risks=tuple(best["privacy_risks"]),
        utility_risks=tuple(best["utility_risks"]),
        solved_decoder_assignments=len(decoders),
        source_count=source_count,
        label_count=label_count,
        fine_token_count=fine_count,
        released_token_count=released_token_count,
        solver_status=str(best["message"]),
        max_constraint_violation=float(best["violation"]),
        method="global_decoder_enumeration_exact_population_shift_lp",
    )
