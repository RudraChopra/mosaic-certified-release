"""Deterministic additive evidence-allocation solvers with dual certificates."""

from __future__ import annotations

import hashlib
import json
import math
import platform
import sys
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import numpy as np
import scipy
from scipy.optimize import minimize


FTOL = 1e-12
MAXITER = 2_000
FEASIBILITY_TOLERANCE = 1e-8
DUAL_ORDER_TOLERANCE = 1e-9
GAP_TOLERANCE = 1e-8


@dataclass(frozen=True)
class Inputs:
    coefficients: np.ndarray
    floors: np.ndarray
    cell_keys: tuple[str, ...]


def validate_inputs(
    coefficients: np.ndarray,
    floors: np.ndarray,
    cell_keys: Sequence[str] | None = None,
) -> Inputs:
    values = np.asarray(coefficients, dtype=float)
    lower = np.asarray(floors, dtype=float)
    if values.ndim != 2 or not values.shape[0] or not values.shape[1]:
        raise ValueError("coefficients must be a nonempty J-by-C matrix")
    if lower.shape != (values.shape[1],):
        raise ValueError("floors do not match the coefficient cells")
    if not np.all(np.isfinite(values)) or np.any(values < 0.0):
        raise ValueError("coefficients must be finite and nonnegative")
    if not np.all(np.isfinite(lower)) or np.any(lower <= 0.0):
        raise ValueError("floors must be finite and positive")
    if not np.any(values > 0.0):
        raise ValueError("at least one allocation coefficient must be positive")
    keys = (
        tuple(str(index) for index in range(values.shape[1]))
        if cell_keys is None
        else tuple(map(str, cell_keys))
    )
    if len(keys) != values.shape[1] or len(set(keys)) != len(keys):
        raise ValueError("cell keys must be unique and match the cells")
    return Inputs(values, lower, keys)


def contract_slacks(coefficients: np.ndarray, counts: np.ndarray) -> np.ndarray:
    values = np.asarray(coefficients, dtype=float)
    n = np.asarray(counts, dtype=float)
    if n.ndim != 1 or values.ndim != 2 or values.shape[1] != len(n):
        raise ValueError("coefficient/count shape mismatch")
    if np.any(n <= 0.0) or not np.all(np.isfinite(n)):
        raise ValueError("counts must be finite and positive")
    return values @ np.power(n, -0.5)


def maximum_slack(coefficients: np.ndarray, counts: np.ndarray) -> float:
    return float(np.max(contract_slacks(coefficients, counts)))


def allocation_input_sha256(
    program: str,
    inputs: Inputs,
    budget_or_cap: float | int,
) -> str:
    payload = json.dumps(
        {
            "program": program,
            "coefficients": inputs.coefficients.tolist(),
            "floors": inputs.floors.tolist(),
            "cell_keys": list(inputs.cell_keys),
            "budget_or_cap": budget_or_cap,
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def square_score_start(
    coefficients: np.ndarray, floors: np.ndarray, budget: float
) -> np.ndarray:
    remaining = float(budget - np.sum(floors))
    if remaining < -FEASIBILITY_TOLERANCE:
        raise ValueError("budget is below the sum of floors")
    if remaining <= 0.0:
        return np.asarray(floors, dtype=float).copy()
    scores = np.max(coefficients, axis=0)
    weights = np.square(scores)
    if float(np.sum(weights)) == 0.0:
        weights = np.ones_like(weights)
    return np.asarray(floors, dtype=float) + remaining * weights / np.sum(weights)


def fixed_primal_objective(x: np.ndarray) -> tuple[float, np.ndarray]:
    gradient = np.zeros_like(x, dtype=float)
    gradient[-1] = 1.0
    return float(x[-1]), gradient


def fixed_constraint_values(
    x: np.ndarray, coefficients: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    counts, threshold = x[:-1], float(x[-1])
    values = threshold - contract_slacks(coefficients, counts)
    jacobian = np.empty((coefficients.shape[0], len(x)), dtype=float)
    jacobian[:, :-1] = 0.5 * coefficients * np.power(counts, -1.5)
    jacobian[:, -1] = 1.0
    return values, jacobian


def _solve_fixed_primal(inputs: Inputs, budget: float) -> dict[str, Any]:
    if not np.isfinite(budget) or budget < np.sum(inputs.floors) - FEASIBILITY_TOLERANCE:
        raise ValueError("invalid fixed evidence budget")
    if abs(budget - np.sum(inputs.floors)) <= FEASIBILITY_TOLERANCE:
        counts = inputs.floors.copy()
        return {
            "counts": counts,
            "objective": maximum_slack(inputs.coefficients, counts),
            "success": True,
            "status": 0,
            "message": "exact floor-budget boundary",
            "iterations": 0,
            "function_evaluations": 0,
            "jacobian_evaluations": 0,
        }
    start_counts = square_score_start(inputs.coefficients, inputs.floors, budget)
    start = np.concatenate(
        [start_counts, [maximum_slack(inputs.coefficients, start_counts)]]
    )

    result = minimize(
        lambda x: fixed_primal_objective(x)[0],
        start,
        jac=lambda x: fixed_primal_objective(x)[1],
        method="SLSQP",
        bounds=[*(zip(inputs.floors, [None] * len(inputs.floors))), (0.0, None)],
        constraints=[
            {
                "type": "eq",
                "fun": lambda x: float(np.sum(x[:-1]) - budget),
                "jac": lambda x: np.concatenate(
                    [np.ones(len(inputs.floors)), [0.0]]
                ),
            },
            {
                "type": "ineq",
                "fun": lambda x: fixed_constraint_values(
                    x, inputs.coefficients
                )[0],
                "jac": lambda x: fixed_constraint_values(
                    x, inputs.coefficients
                )[1],
            },
        ],
        options={"ftol": FTOL, "maxiter": MAXITER, "disp": False},
    )
    counts = np.asarray(result.x[:-1], dtype=float)
    objective = maximum_slack(inputs.coefficients, counts)
    budget_error = abs(float(np.sum(counts)) - budget)
    floor_error = max(0.0, float(np.max(inputs.floors - counts)))
    constraint_error = max(
        0.0, float(np.max(contract_slacks(inputs.coefficients, counts) - result.x[-1]))
    )
    finite = bool(np.all(np.isfinite(result.x)) and np.isfinite(objective))
    if (
        not result.success
        or not finite
        or budget_error > FEASIBILITY_TOLERANCE
        or floor_error > FEASIBILITY_TOLERANCE
        or constraint_error > FEASIBILITY_TOLERANCE
    ):
        raise RuntimeError(
            "fixed-budget primal failed: "
            f"success={result.success}, budget={budget_error:.3g}, "
            f"floor={floor_error:.3g}, constraint={constraint_error:.3g}"
        )
    return {
        "counts": counts,
        "objective": objective,
        "success": bool(result.success),
        "status": int(result.status),
        "message": str(result.message),
        "iterations": int(result.nit),
        "function_evaluations": int(result.nfev),
        "jacobian_evaluations": int(result.njev),
    }


def fixed_dual_value_gradient(
    variables: np.ndarray,
    coefficients: np.ndarray,
    floors: np.ndarray,
    budget: float,
) -> tuple[float, np.ndarray, np.ndarray, float]:
    contract_count = coefficients.shape[0]
    mu = np.asarray(variables[:contract_count], dtype=float)
    log_nu = float(variables[-1])
    nu = math.exp(log_nu)
    aggregate = mu @ coefficients
    unconstrained = np.zeros_like(aggregate)
    positive = aggregate > 0.0
    unconstrained[positive] = np.power(
        aggregate[positive] / (2.0 * nu), 2.0 / 3.0
    )
    counts = np.maximum(floors, unconstrained)
    value = float(
        np.sum(aggregate / np.sqrt(counts) + nu * counts) - nu * budget
    )
    gradient = np.concatenate(
        [contract_slacks(coefficients, counts), [nu * (np.sum(counts) - budget)]]
    )
    return value, gradient, counts, nu


def _budget_matching_log_nu(
    mu: np.ndarray, coefficients: np.ndarray, floors: np.ndarray, budget: float
) -> float:
    if budget <= np.sum(floors) + FEASIBILITY_TOLERANCE:
        aggregate = mu @ coefficients
        needed = np.max(aggregate / (2.0 * np.power(floors, 1.5)))
        return math.log(max(1.0, float(needed) * 2.0))
    lower, upper = -50.0, 50.0
    for _ in range(240):
        midpoint = (lower + upper) / 2.0
        trial = np.concatenate([mu, [midpoint]])
        _, _, counts, _ = fixed_dual_value_gradient(
            trial, coefficients, floors, budget
        )
        if np.sum(counts) > budget:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def _fixed_dual(
    inputs: Inputs, budget: float, primal_counts: np.ndarray, primal: float
) -> dict[str, Any]:
    slacks = contract_slacks(inputs.coefficients, primal_counts)
    active = np.flatnonzero(slacks >= primal - 1e-7)
    starts: list[np.ndarray] = [
        np.full(inputs.coefficients.shape[0], 1.0 / inputs.coefficients.shape[0])
    ]
    starts.extend(np.eye(inputs.coefficients.shape[0]))
    if len(active):
        recovered = np.zeros(inputs.coefficients.shape[0], dtype=float)
        recovered[active] = 1.0 / len(active)
        starts.append(recovered)
    best: dict[str, Any] | None = None
    for mu_start in starts:
        log_nu = _budget_matching_log_nu(
            mu_start, inputs.coefficients, inputs.floors, budget
        )
        start = np.concatenate([mu_start, [log_nu]])
        result = minimize(
            lambda x: -fixed_dual_value_gradient(
                x, inputs.coefficients, inputs.floors, budget
            )[0],
            start,
            jac=lambda x: -fixed_dual_value_gradient(
                x, inputs.coefficients, inputs.floors, budget
            )[1],
            method="SLSQP",
            bounds=[
                *[(0.0, 1.0)] * inputs.coefficients.shape[0],
                (-50.0, 50.0),
            ],
            constraints=[
                {
                    "type": "eq",
                    "fun": lambda x: float(np.sum(x[:-1]) - 1.0),
                    "jac": lambda x: np.concatenate(
                        [np.ones(inputs.coefficients.shape[0]), [0.0]]
                    ),
                }
            ],
            options={"ftol": FTOL, "maxiter": MAXITER, "disp": False},
        )
        candidate = np.asarray(result.x, dtype=float)
        if (
            not np.all(np.isfinite(candidate))
            or np.any(candidate[:-1] < -FEASIBILITY_TOLERANCE)
            or abs(np.sum(candidate[:-1]) - 1.0) > FEASIBILITY_TOLERANCE
        ):
            continue
        value, _, dual_counts, nu = fixed_dual_value_gradient(
            candidate, inputs.coefficients, inputs.floors, budget
        )
        record = {
            "value": value,
            "mu": np.maximum(candidate[:-1], 0.0),
            "nu": nu,
            "counts": dual_counts,
            "success": bool(result.success),
            "status": int(result.status),
            "message": str(result.message),
            "iterations": int(result.nit),
            "function_evaluations": int(result.nfev),
            "jacobian_evaluations": int(result.njev),
        }
        if best is None or record["value"] > best["value"]:
            best = record
    if best is None:
        raise RuntimeError("fixed-budget dual produced no feasible iterate")
    return best


def _fixed_kkt(
    inputs: Inputs,
    budget: float,
    counts: np.ndarray,
    objective: float,
    dual: dict[str, Any],
) -> dict[str, float]:
    mu = np.asarray(dual["mu"], dtype=float)
    nu = float(dual["nu"])
    aggregate = mu @ inputs.coefficients
    gradient_without_floor = nu - 0.5 * aggregate * np.power(counts, -1.5)
    at_floor = counts <= inputs.floors + 1e-7
    floor_multipliers = np.where(at_floor, np.maximum(0.0, gradient_without_floor), 0.0)
    stationarity = gradient_without_floor - floor_multipliers
    slacks = contract_slacks(inputs.coefficients, counts)
    return {
        "stationarity_residual": float(
            max(abs(np.sum(mu) - 1.0), np.max(np.abs(stationarity)))
        ),
        "primal_feasibility_residual": float(
            max(
                abs(np.sum(counts) - budget),
                max(0.0, np.max(inputs.floors - counts)),
                max(0.0, np.max(slacks - objective)),
            )
        ),
        "complementarity_residual": float(
            max(
                np.max(np.abs(mu * (objective - slacks))),
                np.max(np.abs(floor_multipliers * (counts - inputs.floors))),
            )
        ),
    }


def solve_fixed_budget(
    coefficients: np.ndarray,
    floors: np.ndarray,
    budget: float,
    cell_keys: Sequence[str] | None = None,
) -> dict[str, Any]:
    inputs = validate_inputs(coefficients, floors, cell_keys)
    primal_record = _solve_fixed_primal(inputs, float(budget))
    counts = primal_record["counts"]
    primal = float(primal_record["objective"])
    dual = _fixed_dual(inputs, float(budget), counts, primal)
    gap = primal - float(dual["value"])
    if float(dual["value"]) > primal + DUAL_ORDER_TOLERANCE:
        raise RuntimeError("fixed-budget dual exceeds the primal")
    if gap > GAP_TOLERANCE * max(1.0, abs(primal)):
        raise RuntimeError(f"fixed-budget primal-dual gap is too large: {gap:.3g}")
    kkt = _fixed_kkt(inputs, float(budget), counts, primal, dual)
    slacks = contract_slacks(inputs.coefficients, counts)
    integer = round_fixed_budget(
        inputs.coefficients,
        counts,
        np.rint(inputs.floors).astype(int),
        int(round(budget)),
        inputs.cell_keys,
    )
    return {
        "program": "fixed_budget_additive_minimax",
        "input_sha256": allocation_input_sha256(
            "fixed_budget_additive_minimax", inputs, float(budget)
        ),
        "budget": float(budget),
        "floors": inputs.floors.tolist(),
        "cell_keys": list(inputs.cell_keys),
        "continuous_counts": counts.tolist(),
        "continuous_objective": primal,
        "contract_slacks": slacks.tolist(),
        "active_contracts": np.flatnonzero(slacks >= primal - 1e-7).tolist(),
        "active_floors": np.flatnonzero(
            counts <= inputs.floors + 1e-7
        ).tolist(),
        "dual_lower_bound": float(dual["value"]),
        "absolute_primal_dual_gap": gap,
        "relative_primal_dual_gap": gap / max(1.0, abs(primal)),
        "contract_multipliers": dual["mu"].tolist(),
        "nu": float(dual["nu"]),
        **kkt,
        "primal_solver": {
            key: value
            for key, value in primal_record.items()
            if key not in {"counts", "objective"}
        },
        "dual_solver": {
            key: value
            for key, value in dual.items()
            if key not in {"counts", "mu", "nu", "value"}
        },
        "integer": integer,
        "versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
        "tolerances": {
            "ftol": FTOL,
            "maxiter": MAXITER,
            "feasibility": FEASIBILITY_TOLERANCE,
            "dual_order": DUAL_ORDER_TOLERANCE,
            "gap": GAP_TOLERANCE,
        },
    }


def validate_fixed_result(
    report: dict[str, Any],
    coefficients: np.ndarray,
    floors: np.ndarray,
    budget: float,
    cell_keys: Sequence[str] | None = None,
) -> None:
    inputs = validate_inputs(coefficients, floors, cell_keys)
    if report.get("cell_keys") != list(inputs.cell_keys):
        raise RuntimeError("fixed result cell keys changed")
    if report.get("floors") != inputs.floors.tolist() or float(
        report.get("budget", float("nan"))
    ) != float(budget):
        raise RuntimeError("fixed result floor or budget changed")
    if report.get("input_sha256") != allocation_input_sha256(
        "fixed_budget_additive_minimax", inputs, float(budget)
    ):
        raise RuntimeError("fixed result input hash changed")
    if report.get("tolerances") != {
        "ftol": FTOL,
        "maxiter": MAXITER,
        "feasibility": FEASIBILITY_TOLERANCE,
        "dual_order": DUAL_ORDER_TOLERANCE,
        "gap": GAP_TOLERANCE,
    }:
        raise RuntimeError("fixed result tolerances changed")
    counts = np.asarray(report["continuous_counts"], dtype=float)
    if counts.shape != inputs.floors.shape:
        raise RuntimeError("fixed result count shape changed")
    primal = maximum_slack(inputs.coefficients, counts)
    if not np.isclose(
        primal, float(report["continuous_objective"]), atol=1e-12, rtol=1e-12
    ):
        raise RuntimeError("fixed result primal objective changed")
    if abs(np.sum(counts) - budget) > FEASIBILITY_TOLERANCE or np.any(
        counts < inputs.floors - FEASIBILITY_TOLERANCE
    ):
        raise RuntimeError("fixed result is primal infeasible")
    mu = np.asarray(report["contract_multipliers"], dtype=float)
    nu = float(report["nu"])
    if (
        mu.shape != (inputs.coefficients.shape[0],)
        or np.any(mu < -FEASIBILITY_TOLERANCE)
        or abs(np.sum(mu) - 1.0) > FEASIBILITY_TOLERANCE
        or not np.isfinite(nu)
        or nu <= 0.0
    ):
        raise RuntimeError("fixed result dual variables changed")
    dual_value, _, _, _ = fixed_dual_value_gradient(
        np.concatenate([mu, [math.log(nu)]]),
        inputs.coefficients,
        inputs.floors,
        float(budget),
    )
    if not np.isclose(
        dual_value,
        float(report["dual_lower_bound"]),
        atol=1e-10,
        rtol=1e-10,
    ):
        raise RuntimeError("fixed result dual value changed")
    gap = primal - dual_value
    if dual_value > primal + DUAL_ORDER_TOLERANCE or gap > GAP_TOLERANCE * max(
        1.0, abs(primal)
    ):
        raise RuntimeError("fixed result primal-dual certificate failed")
    integer = np.asarray(report["integer"]["counts"], dtype=int)
    if int(np.sum(integer)) != int(round(budget)) or np.any(
        integer < np.rint(inputs.floors).astype(int)
    ):
        raise RuntimeError("fixed result integer allocation changed")
    integer_objective = maximum_slack(inputs.coefficients, integer)
    if not np.isclose(
        integer_objective,
        float(report["integer"]["objective"]),
        atol=1e-12,
        rtol=1e-12,
    ):
        raise RuntimeError("fixed result integer objective changed")


def round_fixed_budget(
    coefficients: np.ndarray,
    continuous_counts: np.ndarray,
    floors: np.ndarray,
    budget: int,
    cell_keys: Sequence[str],
) -> dict[str, Any]:
    if not float(budget).is_integer():
        raise ValueError("integer rounding requires an integer budget")
    counts = np.floor(np.asarray(continuous_counts, dtype=float) + 1e-10).astype(int)
    integer_floors = np.asarray(floors, dtype=int)
    if np.any(counts < integer_floors):
        raise RuntimeError("continuous solution rounds below a registered floor")
    remaining = int(budget - np.sum(counts))
    if remaining < 0 or remaining >= len(counts) + 1:
        raise RuntimeError("continuous fixed-budget counts do not round to the budget")
    additions: list[str] = []
    for _ in range(remaining):
        before = maximum_slack(coefficients, counts)
        choices = []
        for index, key in enumerate(cell_keys):
            trial = counts.copy()
            trial[index] += 1
            decrease = before - maximum_slack(coefficients, trial)
            choices.append((-decrease, str(key), index))
        _, key, selected = min(choices)
        counts[selected] += 1
        additions.append(key)
    if int(np.sum(counts)) != int(budget) or np.any(counts < integer_floors):
        raise RuntimeError("integer fixed-budget checks failed")
    payload = json.dumps(additions, separators=(",", ":")).encode("utf-8")
    return {
        "counts": counts.tolist(),
        "objective": maximum_slack(coefficients, counts),
        "contract_slacks": contract_slacks(coefficients, counts).tolist(),
        "addition_count": len(additions),
        "addition_sequence_sha256": hashlib.sha256(payload).hexdigest(),
    }


def inverse_primal_objective(counts: np.ndarray) -> tuple[float, np.ndarray]:
    return float(np.sum(counts)), np.ones_like(counts, dtype=float)


def inverse_constraint_values(
    counts: np.ndarray, coefficients: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    values = 1.0 - contract_slacks(coefficients, counts)
    jacobian = 0.5 * coefficients * np.power(counts, -1.5)
    return values, jacobian


def _inverse_start(inputs: Inputs, cap: int) -> np.ndarray:
    budget = max(4_000, int(math.ceil(np.sum(inputs.floors))))
    while budget <= cap:
        if budget >= np.sum(inputs.floors):
            record = _solve_fixed_primal(inputs, float(budget))
            if record["objective"] <= 1.0 + FEASIBILITY_TOLERANCE:
                return np.asarray(record["counts"], dtype=float)
        budget *= 2
    raise RuntimeError("inverse initialization is right-censored at the budget cap")


def _solve_inverse_primal(inputs: Inputs, cap: int) -> dict[str, Any]:
    start = _inverse_start(inputs, cap)
    result = minimize(
        lambda n: inverse_primal_objective(n)[0],
        start,
        jac=lambda n: inverse_primal_objective(n)[1],
        method="SLSQP",
        bounds=list(zip(inputs.floors, [None] * len(inputs.floors))),
        constraints=[
            {
                "type": "ineq",
                "fun": lambda n: inverse_constraint_values(
                    n, inputs.coefficients
                )[0],
                "jac": lambda n: inverse_constraint_values(
                    n, inputs.coefficients
                )[1],
            }
        ],
        options={"ftol": FTOL, "maxiter": MAXITER, "disp": False},
    )
    counts = np.asarray(result.x, dtype=float)
    slacks = contract_slacks(inputs.coefficients, counts)
    floor_error = max(0.0, float(np.max(inputs.floors - counts)))
    contract_error = max(0.0, float(np.max(slacks - 1.0)))
    if (
        not result.success
        or not np.all(np.isfinite(counts))
        or floor_error > FEASIBILITY_TOLERANCE
        or contract_error > FEASIBILITY_TOLERANCE
        or np.sum(counts) > cap + FEASIBILITY_TOLERANCE
    ):
        raise RuntimeError(
            "inverse primal failed: "
            f"success={result.success}, floor={floor_error:.3g}, "
            f"constraint={contract_error:.3g}"
        )
    return {
        "counts": counts,
        "objective": float(np.sum(counts)),
        "success": bool(result.success),
        "status": int(result.status),
        "message": str(result.message),
        "iterations": int(result.nit),
        "function_evaluations": int(result.nfev),
        "jacobian_evaluations": int(result.njev),
    }


def inverse_dual_value_gradient(
    mu: np.ndarray, coefficients: np.ndarray, floors: np.ndarray
) -> tuple[float, np.ndarray, np.ndarray]:
    weights = np.asarray(mu, dtype=float)
    aggregate = weights @ coefficients
    unconstrained = np.zeros_like(aggregate)
    positive = aggregate > 0.0
    unconstrained[positive] = np.power(aggregate[positive] / 2.0, 2.0 / 3.0)
    counts = np.maximum(floors, unconstrained)
    value = float(np.sum(aggregate / np.sqrt(counts) + counts) - np.sum(weights))
    gradient = contract_slacks(coefficients, counts) - 1.0
    return value, gradient, counts


def _inverse_dual(
    inputs: Inputs, primal_counts: np.ndarray, primal: float
) -> dict[str, Any]:
    slacks = contract_slacks(inputs.coefficients, primal_counts)
    active = np.flatnonzero(slacks >= 1.0 - 1e-7)
    base = max(1.0, primal / max(1, inputs.coefficients.shape[0]))
    starts = [np.zeros(inputs.coefficients.shape[0], dtype=float)]
    for scale in (0.01, 0.1, 1.0, 10.0):
        starts.append(
            np.full(
                inputs.coefficients.shape[0],
                scale * base / inputs.coefficients.shape[0],
            )
        )
        starts.extend(scale * base * np.eye(inputs.coefficients.shape[0]))
    if len(active):
        recovered = np.zeros(inputs.coefficients.shape[0], dtype=float)
        recovered[active] = base / len(active)
        starts.append(recovered)
    best: dict[str, Any] | None = None
    for start in starts:
        result = minimize(
            lambda mu: -inverse_dual_value_gradient(
                mu, inputs.coefficients, inputs.floors
            )[0],
            start,
            jac=lambda mu: -inverse_dual_value_gradient(
                mu, inputs.coefficients, inputs.floors
            )[1],
            method="L-BFGS-B",
            bounds=[(0.0, None)] * inputs.coefficients.shape[0],
            options={"ftol": FTOL, "maxiter": MAXITER, "maxls": 100},
        )
        candidate = np.maximum(np.asarray(result.x, dtype=float), 0.0)
        if not np.all(np.isfinite(candidate)):
            continue
        value, _, dual_counts = inverse_dual_value_gradient(
            candidate, inputs.coefficients, inputs.floors
        )
        record = {
            "value": value,
            "mu": candidate,
            "counts": dual_counts,
            "success": bool(result.success),
            "status": int(result.status),
            "message": str(result.message),
            "iterations": int(result.nit),
            "function_evaluations": int(result.nfev),
            "jacobian_evaluations": int(result.njev),
        }
        if best is None or record["value"] > best["value"]:
            best = record
    if best is None:
        raise RuntimeError("inverse dual produced no feasible iterate")
    return best


def _inverse_kkt(
    inputs: Inputs, counts: np.ndarray, dual: dict[str, Any]
) -> dict[str, float]:
    mu = np.asarray(dual["mu"], dtype=float)
    aggregate = mu @ inputs.coefficients
    gradient_without_floor = 1.0 - 0.5 * aggregate * np.power(counts, -1.5)
    at_floor = counts <= inputs.floors + 1e-7
    floor_multipliers = np.where(at_floor, np.maximum(0.0, gradient_without_floor), 0.0)
    stationarity = gradient_without_floor - floor_multipliers
    slacks = contract_slacks(inputs.coefficients, counts)
    return {
        "stationarity_residual": float(np.max(np.abs(stationarity))),
        "primal_feasibility_residual": float(
            max(
                max(0.0, np.max(inputs.floors - counts)),
                max(0.0, np.max(slacks - 1.0)),
            )
        ),
        "complementarity_residual": float(
            max(
                np.max(np.abs(mu * (1.0 - slacks))),
                np.max(np.abs(floor_multipliers * (counts - inputs.floors))),
            )
        ),
    }


def solve_inverse_budget(
    coefficients: np.ndarray,
    floors: np.ndarray,
    cell_keys: Sequence[str] | None = None,
    cap: int = 1_000_000,
) -> dict[str, Any]:
    inputs = validate_inputs(coefficients, floors, cell_keys)
    if cap <= 0:
        raise ValueError("inverse cap must be positive")
    primal_record = _solve_inverse_primal(inputs, cap)
    counts = primal_record["counts"]
    primal = float(primal_record["objective"])
    dual = _inverse_dual(inputs, counts, primal)
    gap = primal - float(dual["value"])
    if float(dual["value"]) > primal + DUAL_ORDER_TOLERANCE:
        raise RuntimeError("inverse dual exceeds the primal")
    if gap > GAP_TOLERANCE * max(1.0, abs(primal)):
        raise RuntimeError(f"inverse primal-dual gap is too large: {gap:.3g}")
    kkt = _inverse_kkt(inputs, counts, dual)
    slacks = contract_slacks(inputs.coefficients, counts)
    integer = round_inverse_budget(
        inputs.coefficients,
        counts,
        np.rint(inputs.floors).astype(int),
        inputs.cell_keys,
        cap,
    )
    return {
        "program": "inverse_additive_evidence_requirement",
        "input_sha256": allocation_input_sha256(
            "inverse_additive_evidence_requirement", inputs, int(cap)
        ),
        "floors": inputs.floors.tolist(),
        "cell_keys": list(inputs.cell_keys),
        "continuous_counts": counts.tolist(),
        "continuous_total": primal,
        "contract_slacks": slacks.tolist(),
        "active_contracts": np.flatnonzero(slacks >= 1.0 - 1e-7).tolist(),
        "active_floors": np.flatnonzero(
            counts <= inputs.floors + 1e-7
        ).tolist(),
        "dual_lower_bound": float(dual["value"]),
        "absolute_primal_dual_gap": gap,
        "relative_primal_dual_gap": gap / max(1.0, abs(primal)),
        "contract_multipliers": dual["mu"].tolist(),
        **kkt,
        "primal_solver": {
            key: value
            for key, value in primal_record.items()
            if key not in {"counts", "objective"}
        },
        "dual_solver": {
            key: value
            for key, value in dual.items()
            if key not in {"counts", "mu", "value"}
        },
        "integer": integer,
        "right_censored": False,
        "cap": int(cap),
        "versions": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
        },
    }


def validate_inverse_result(
    report: dict[str, Any],
    coefficients: np.ndarray,
    floors: np.ndarray,
    cell_keys: Sequence[str] | None = None,
) -> None:
    inputs = validate_inputs(coefficients, floors, cell_keys)
    if report.get("cell_keys") != list(inputs.cell_keys):
        raise RuntimeError("inverse result cell keys changed")
    if report.get("floors") != inputs.floors.tolist():
        raise RuntimeError("inverse result floors changed")
    if report.get("input_sha256") != allocation_input_sha256(
        "inverse_additive_evidence_requirement", inputs, int(report["cap"])
    ):
        raise RuntimeError("inverse result input hash changed")
    counts = np.asarray(report["continuous_counts"], dtype=float)
    if counts.shape != inputs.floors.shape:
        raise RuntimeError("inverse result count shape changed")
    primal = float(np.sum(counts))
    if not np.isclose(
        primal, float(report["continuous_total"]), atol=1e-10, rtol=1e-12
    ):
        raise RuntimeError("inverse result primal objective changed")
    if np.any(counts < inputs.floors - FEASIBILITY_TOLERANCE) or np.max(
        contract_slacks(inputs.coefficients, counts)
    ) > 1.0 + FEASIBILITY_TOLERANCE:
        raise RuntimeError("inverse result is primal infeasible")
    mu = np.asarray(report["contract_multipliers"], dtype=float)
    if mu.shape != (inputs.coefficients.shape[0],) or np.any(
        mu < -FEASIBILITY_TOLERANCE
    ):
        raise RuntimeError("inverse result dual variables changed")
    dual_value, _, _ = inverse_dual_value_gradient(
        mu, inputs.coefficients, inputs.floors
    )
    if not np.isclose(
        dual_value,
        float(report["dual_lower_bound"]),
        atol=1e-8,
        rtol=1e-10,
    ):
        raise RuntimeError("inverse result dual value changed")
    gap = primal - dual_value
    if dual_value > primal + DUAL_ORDER_TOLERANCE or gap > GAP_TOLERANCE * max(
        1.0, abs(primal)
    ):
        raise RuntimeError("inverse result primal-dual certificate failed")
    integer = np.asarray(report["integer"]["counts"], dtype=int)
    if np.any(integer < np.rint(inputs.floors).astype(int)) or np.max(
        contract_slacks(inputs.coefficients, integer)
    ) > 1.0:
        raise RuntimeError("inverse result integer recommendation changed")
    if int(np.sum(integer)) != int(report["integer"]["total"]):
        raise RuntimeError("inverse result integer total changed")


def round_inverse_budget(
    coefficients: np.ndarray,
    continuous_counts: np.ndarray,
    floors: np.ndarray,
    cell_keys: Sequence[str],
    cap: int,
) -> dict[str, Any]:
    counts = np.maximum(
        np.asarray(floors, dtype=int),
        np.floor(np.asarray(continuous_counts, dtype=float) + 1e-10).astype(int),
    )
    additions: list[str] = []
    while maximum_slack(coefficients, counts) > 1.0 and int(np.sum(counts)) < cap:
        before = maximum_slack(coefficients, counts)
        choices = []
        for index, key in enumerate(cell_keys):
            trial = counts.copy()
            trial[index] += 1
            decrease = before - maximum_slack(coefficients, trial)
            choices.append((-decrease, str(key), index))
        _, key, selected = min(choices)
        counts[selected] += 1
        additions.append(key)
    censored = maximum_slack(coefficients, counts) > 1.0
    if censored:
        raise RuntimeError("inverse integer recommendation reached its cap")
    payload = json.dumps(additions, separators=(",", ":")).encode("utf-8")
    continuous_total = float(np.sum(continuous_counts))
    integer_total = int(np.sum(counts))
    return {
        "counts": counts.tolist(),
        "total": integer_total,
        "continuous_lower_bound": continuous_total,
        "absolute_rounding_gap": integer_total - continuous_total,
        "relative_rounding_gap": (integer_total - continuous_total)
        / max(1.0, continuous_total),
        "contract_slacks": contract_slacks(coefficients, counts).tolist(),
        "addition_count": len(additions),
        "addition_sequence_sha256": hashlib.sha256(payload).hexdigest(),
        "right_censored": False,
    }


def stream_seed(namespace_key: str) -> int:
    digest = hashlib.sha256(namespace_key.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def additive_stream_key(
    dataset: str, seed: int, gamma: float, cell_key: str
) -> str:
    return (
        "vera-additive-allocation-v1|"
        f"{dataset}|{int(seed)}|{float(gamma):g}|{cell_key}"
    )
