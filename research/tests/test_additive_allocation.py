from __future__ import annotations

import copy
import itertools
import sys
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parent))

from additive_allocation import (  # noqa: E402
    additive_stream_key,
    contract_slacks,
    fixed_constraint_values,
    fixed_dual_value_gradient,
    inverse_constraint_values,
    inverse_dual_value_gradient,
    maximum_slack,
    solve_fixed_budget,
    solve_inverse_budget,
    stream_seed,
    validate_fixed_result,
    validate_inverse_result,
)


def assert_close(left, right, atol=1e-8, rtol=1e-8) -> None:
    assert np.allclose(left, right, atol=atol, rtol=rtol), (left, right)


def finite_difference(function, values, step=1e-6):
    values = np.asarray(values, dtype=float)
    output = np.empty_like(values)
    for index in range(len(values)):
        upper = values.copy()
        lower = values.copy()
        upper[index] += step
        lower[index] -= step
        output[index] = (function(upper) - function(lower)) / (2.0 * step)
    return output


def integer_allocations(total: int, floors: tuple[int, ...]):
    remainder = total - sum(floors)
    for first in range(remainder + 1):
        for second in range(remainder - first + 1):
            third = remainder - first - second
            yield np.asarray(
                [floors[0] + first, floors[1] + second, floors[2] + third],
                dtype=int,
            )


def test_one_contract_formula() -> None:
    coefficients = np.asarray([[2.0, 1.0, 3.0]])
    floors = np.ones(3)
    budget = 100.0
    report = solve_fixed_budget(coefficients, floors, budget, ["a", "b", "c"])
    weights = np.power(coefficients[0], 2.0 / 3.0)
    expected = budget * weights / np.sum(weights)
    expected_objective = np.power(np.sum(weights), 1.5) / np.sqrt(budget)
    assert_close(report["continuous_counts"], expected, atol=1e-6, rtol=1e-8)
    assert_close(report["continuous_objective"], expected_objective, atol=1e-10)
    validate_fixed_result(report, coefficients, floors, budget, ["a", "b", "c"])


def test_one_cell_per_contract_formula() -> None:
    coefficients = np.diag([1.0, 2.0, 3.0])
    floors = np.ones(3)
    budget = 140.0
    report = solve_fixed_budget(coefficients, floors, budget, ["a", "b", "c"])
    scores = np.asarray([1.0, 2.0, 3.0])
    expected = budget * np.square(scores) / np.sum(np.square(scores))
    assert_close(report["continuous_counts"], expected, atol=1e-6, rtol=1e-8)


def test_gradients() -> None:
    coefficients = np.asarray([[2.0, 1.0, 3.0], [0.5, 2.5, 1.0]])
    counts = np.asarray([20.0, 30.0, 40.0])
    x = np.concatenate([counts, [1.2]])
    _, jacobian = fixed_constraint_values(x, coefficients)
    for contract in range(len(coefficients)):
        observed = finite_difference(
            lambda value: fixed_constraint_values(value, coefficients)[0][contract],
            x,
        )
        assert_close(observed, jacobian[contract], atol=1e-7)
    _, inverse_jacobian = inverse_constraint_values(counts, coefficients)
    for contract in range(len(coefficients)):
        observed = finite_difference(
            lambda value: inverse_constraint_values(value, coefficients)[0][contract],
            counts,
        )
        assert_close(observed, inverse_jacobian[contract], atol=1e-7)
    fixed_variables = np.asarray([0.4, 0.6, -3.0])
    _, fixed_gradient, _, _ = fixed_dual_value_gradient(
        fixed_variables, coefficients, np.ones(3), 100.0
    )
    observed = finite_difference(
        lambda value: fixed_dual_value_gradient(
            value, coefficients, np.ones(3), 100.0
        )[0],
        fixed_variables,
    )
    assert_close(observed, fixed_gradient, atol=1e-6)
    inverse_mu = np.asarray([8.0, 5.0])
    _, inverse_gradient, _ = inverse_dual_value_gradient(
        inverse_mu, coefficients, np.ones(3)
    )
    observed = finite_difference(
        lambda value: inverse_dual_value_gradient(
            value, coefficients, np.ones(3)
        )[0],
        inverse_mu,
    )
    assert_close(observed, inverse_gradient, atol=1e-6)


def test_inverse_formulas() -> None:
    coefficients = np.asarray([[2.0, 1.0, 3.0]])
    floors = np.ones(3)
    report = solve_inverse_budget(coefficients, floors, ["a", "b", "c"])
    weights = np.power(coefficients[0], 2.0 / 3.0)
    expected_total = np.power(np.sum(weights), 3.0)
    expected_counts = np.square(np.sum(weights)) * weights
    assert_close(report["continuous_total"], expected_total, atol=1e-6)
    assert_close(report["continuous_counts"], expected_counts, atol=1e-6)
    validate_inverse_result(report, coefficients, floors, ["a", "b", "c"])

    diagonal = np.diag([1.0, 2.0, 3.0])
    diagonal_report = solve_inverse_budget(diagonal, floors, ["a", "b", "c"])
    assert_close(diagonal_report["continuous_counts"], [1.0, 4.0, 9.0], atol=1e-6)
    assert_close(diagonal_report["continuous_total"], 14.0, atol=1e-6)


def test_integer_grid() -> None:
    fixtures = (
        np.asarray([[1.0, 2.0, 3.0]]),
        np.asarray([[2.0, 0.5, 1.0], [0.5, 2.0, 1.5]]),
        np.asarray([[1.0, 0.0, 2.0], [0.0, 3.0, 1.0], [1.5, 1.5, 0.0]]),
    )
    largest_gap = 0.0
    for coefficients in fixtures:
        for budget in range(6, 41):
            report = solve_fixed_budget(
                coefficients, np.ones(3), budget, ["a", "b", "c"]
            )
            rounded = float(report["integer"]["objective"])
            optimum = min(
                maximum_slack(coefficients, counts)
                for counts in integer_allocations(budget, (1, 1, 1))
            )
            assert rounded >= optimum - 1e-12
            largest_gap = max(largest_gap, rounded - optimum)
    assert np.isfinite(largest_gap)


def test_inverse_integer_grid() -> None:
    coefficients = np.asarray([[0.8, 0.6, 0.7], [0.4, 0.9, 0.5]])
    report = solve_inverse_budget(coefficients, np.ones(3), ["a", "b", "c"])
    rounded_total = int(report["integer"]["total"])
    true_total = None
    for total in range(3, rounded_total + 1):
        if any(
            maximum_slack(coefficients, counts) <= 1.0
            for counts in integer_allocations(total, (1, 1, 1))
        ):
            true_total = total
            break
    assert true_total is not None
    assert rounded_total >= true_total


def test_boundaries_scaling_and_permutations() -> None:
    coefficients = np.asarray(
        [[3.0, 0.0, 1.0], [0.0, 2.0, 0.0], [1.5, 1.0, 0.5]]
    )
    floors = np.asarray([2.0, 4.0, 3.0])
    boundary = solve_fixed_budget(coefficients, floors, 9, ["a", "b", "c"])
    assert_close(boundary["continuous_counts"], floors)

    report = solve_fixed_budget(coefficients, floors, 80, ["a", "b", "c"])
    scaled = solve_fixed_budget(7.0 * coefficients, floors, 80, ["a", "b", "c"])
    assert_close(report["continuous_counts"], scaled["continuous_counts"], atol=1e-5)
    assert_close(
        scaled["continuous_objective"],
        7.0 * report["continuous_objective"],
        atol=1e-8,
    )
    assert_close(scaled["dual_lower_bound"], 7.0 * report["dual_lower_bound"], atol=1e-8)

    no_floor = np.full(3, 1e-6)
    inverse = solve_inverse_budget(coefficients, no_floor, ["a", "b", "c"])
    inverse_scaled = solve_inverse_budget(
        3.0 * coefficients, no_floor, ["a", "b", "c"]
    )
    assert_close(
        inverse_scaled["continuous_counts"],
        9.0 * np.asarray(inverse["continuous_counts"]),
        atol=1e-5,
        rtol=1e-6,
    )

    row_order = [2, 0, 1]
    cell_order = [2, 0, 1]
    permuted = solve_fixed_budget(
        coefficients[row_order][:, cell_order],
        floors[cell_order],
        80,
        ["c", "a", "b"],
    )
    keyed = dict(zip(report["cell_keys"], report["continuous_counts"]))
    permuted_keyed = dict(
        zip(permuted["cell_keys"], permuted["continuous_counts"])
    )
    for key in keyed:
        assert_close(keyed[key], permuted_keyed[key], atol=1e-5)


def test_tied_contracts_and_clamped_scale() -> None:
    coefficients = np.asarray([[100.0, 2.0, 1.0], [100.0, 2.0, 1.0]])
    report = solve_fixed_budget(coefficients, np.ones(3), 4_000, ["a", "b", "c"])
    assert set(report["active_contracts"]) == {0, 1}
    assert report["absolute_primal_dual_gap"] <= 1e-8


def test_corruptions_fail() -> None:
    coefficients = np.asarray([[2.0, 1.0, 3.0], [1.0, 2.0, 0.5]])
    floors = np.ones(3)
    fixed = solve_fixed_budget(coefficients, floors, 100, ["a", "b", "c"])
    inverse = solve_inverse_budget(coefficients, floors, ["a", "b", "c"])

    fixed_mutations = []
    for field in (
        "continuous_objective",
        "dual_lower_bound",
    ):
        value = copy.deepcopy(fixed)
        value[field] += 0.01
        fixed_mutations.append((value, coefficients, floors, 100))
    value = copy.deepcopy(fixed)
    value["contract_multipliers"][0] += 0.1
    fixed_mutations.append((value, coefficients, floors, 100))
    value = copy.deepcopy(fixed)
    value["tolerances"]["gap"] = 1.0
    fixed_mutations.append((value, coefficients, floors, 100))
    fixed_mutations.append((fixed, coefficients, floors + 1.0, 100))
    fixed_mutations.append((fixed, coefficients, floors, 101))
    changed_coefficients = coefficients.copy()
    changed_coefficients[0, 0] += 0.2
    fixed_mutations.append((fixed, changed_coefficients, floors, 100))
    for mutation_index, (report, matrix, lower, budget) in enumerate(fixed_mutations):
        try:
            validate_fixed_result(report, matrix, lower, budget, ["a", "b", "c"])
        except RuntimeError:
            pass
        else:
            raise AssertionError(
                f"corrupt fixed certificate passed: {mutation_index}"
            )

    inverse_mutations = []
    value = copy.deepcopy(inverse)
    value["continuous_total"] += 0.1
    inverse_mutations.append((value, coefficients, floors))
    value = copy.deepcopy(inverse)
    value["dual_lower_bound"] += 0.1
    inverse_mutations.append((value, coefficients, floors))
    value = copy.deepcopy(inverse)
    value["contract_multipliers"][0] += 0.2
    inverse_mutations.append((value, coefficients, floors))
    inverse_mutations.append((inverse, changed_coefficients, floors))
    inverse_mutations.append((inverse, coefficients, floors + 1.0))
    for mutation_index, (report, matrix, lower) in enumerate(inverse_mutations):
        try:
            validate_inverse_result(report, matrix, lower, ["a", "b", "c"])
        except RuntimeError:
            pass
        else:
            raise AssertionError(
                f"corrupt inverse certificate passed: {mutation_index}"
            )

    invalid_inputs = (
        (np.asarray([[-1.0, 1.0, 2.0]]), floors, 100, ["a", "b", "c"]),
        (coefficients, floors, 2, ["a", "b", "c"]),
        (coefficients, floors, 100, ["a", "a", "c"]),
    )
    for matrix, lower, budget, keys in invalid_inputs:
        try:
            solve_fixed_budget(matrix, lower, budget, keys)
        except (RuntimeError, ValueError):
            pass
        else:
            raise AssertionError("invalid solver input passed")


def test_stream_namespace() -> None:
    key = additive_stream_key("Waterbirds", 45, 1.1, "target::0")
    assert key == "vera-additive-allocation-v1|Waterbirds|45|1.1|target::0"
    assert stream_seed(key) == stream_seed(key)
    assert stream_seed(key) != stream_seed(key + "|changed")
    assert 0 <= stream_seed(key) < 2**64


def main() -> None:
    tests = (
        test_one_contract_formula,
        test_one_cell_per_contract_formula,
        test_gradients,
        test_inverse_formulas,
        test_integer_grid,
        test_inverse_integer_grid,
        test_boundaries_scaling_and_permutations,
        test_tied_contracts_and_clamped_scale,
        test_corruptions_fail,
        test_stream_namespace,
    )
    for test in tests:
        test()
        print(f"PASS {test.__name__}")


if __name__ == "__main__":
    main()
