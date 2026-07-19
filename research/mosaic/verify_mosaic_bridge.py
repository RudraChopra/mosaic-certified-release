#!/usr/bin/env python3
"""Independent falsification checks for MOSAIC bridge certification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from scipy.optimize import linprog

from mosaic_bridge import certify_bridge_membership
from mosaic_channel import l1_ball_expectation_upper
from mosaic_envelope import weissman_l1_radius


TOLERANCE = 3e-7


def atomic_json_dump(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def explicit_primal_support(
    empirical: np.ndarray, scores: np.ndarray, radius: float
) -> float:
    """Solve the multinomial L1 support from its primal definition."""

    token_count = len(empirical)
    objective = np.r_[-scores, np.zeros(token_count)]
    inequalities = []
    values = []
    for token in range(token_count):
        row = np.zeros(2 * token_count)
        row[token] = 1.0
        row[token_count + token] = -1.0
        inequalities.append(row)
        values.append(float(empirical[token]))
        row = np.zeros(2 * token_count)
        row[token] = -1.0
        row[token_count + token] = -1.0
        inequalities.append(row)
        values.append(float(-empirical[token]))
    row = np.zeros(2 * token_count)
    row[token_count:] = 1.0
    inequalities.append(row)
    values.append(float(radius))
    equality = np.zeros((1, 2 * token_count))
    equality[0, :token_count] = 1.0
    solution = linprog(
        objective,
        A_ub=np.asarray(inequalities),
        b_ub=np.asarray(values),
        A_eq=equality,
        b_eq=np.ones(1),
        bounds=[(0.0, 1.0)] * token_count + [(0.0, None)] * token_count,
        method="highs",
    )
    if not solution.success:
        raise AssertionError(f"independent support primal failed: {solution.message}")
    return float(-solution.fun)


def support_function_checks(
    rng: np.random.Generator, repetitions: int
) -> dict[str, float | int]:
    worst_gap = 0.0
    for _ in range(repetitions):
        token_count = int(rng.integers(2, 9))
        empirical = rng.dirichlet(np.ones(token_count))
        scores = rng.uniform(-2.0, 3.0, size=token_count)
        radius = float(rng.uniform(0.0, 2.0))
        direct = explicit_primal_support(empirical, scores, radius)
        transport = l1_ball_expectation_upper(
            empirical, scores, l1_radius=radius
        )
        gap = abs(direct - transport)
        worst_gap = max(worst_gap, gap)
        if gap > 2e-9:
            raise AssertionError("L1 support function disagrees with explicit primal")
    return {"checks": repetitions, "worst_absolute_gap": worst_gap}


def binary_grid_checks(
    rng: np.random.Generator, repetitions: int, grid_size: int
) -> dict[str, float | int]:
    """Compare the bridge LP with an independent dense transform grid."""

    grid = np.linspace(0.0, 1.0, grid_size)
    first, second = np.meshgrid(grid, grid, indexing="ij")
    transforms = np.stack(
        (
            np.stack((first, 1.0 - first), axis=-1),
            np.stack((second, 1.0 - second), axis=-1),
        ),
        axis=-2,
    ).reshape(-1, 2, 2)
    smallest_lp_minus_grid = np.inf
    largest_margin_loss = 0.0
    for _ in range(repetitions):
        reference_label = rng.dirichlet(np.ones(2), size=2)
        bridge_label = rng.dirichlet(np.ones(2), size=2)
        reference = np.stack((reference_label, reference_label))
        bridge = np.stack((bridge_label, bridge_label))
        certificate = certify_bridge_membership(
            reference,
            reference_l1_radii=np.zeros((2, 2)),
            bridge_empirical_distributions=bridge,
            bridge_l1_radii=np.zeros((2, 2)),
        )
        pushed = np.einsum("sk,nkl->nsl", reference_label, transforms)
        ratios = np.divide(
            bridge_label[None, :, :],
            pushed,
            out=np.full_like(pushed, np.inf),
            where=pushed > 1e-14,
        )
        grid_best = float(np.minimum(1.0, np.min(ratios, axis=(1, 2))).max())
        optimum = certificate.labels[0].optimal_retained_mass_upper
        retained = certificate.labels[0].retained_mass
        smallest_lp_minus_grid = min(smallest_lp_minus_grid, optimum - grid_best)
        largest_margin_loss = max(largest_margin_loss, optimum - retained)
        if optimum + TOLERANCE < grid_best:
            raise AssertionError("bridge LP is worse than a feasible grid transform")
    return {
        "checks": repetitions,
        "grid_size_per_transform_row": grid_size,
        "smallest_lp_minus_grid": smallest_lp_minus_grid,
        "largest_numerical_margin_loss": largest_margin_loss,
    }


def known_membership_checks(
    rng: np.random.Generator, repetitions: int
) -> dict[str, float | int]:
    smallest_recovered_margin = np.inf
    smallest_membership_slack = np.inf
    for _ in range(repetitions):
        labels, sources = 2, 2
        token_count = int(rng.integers(2, 7))
        reference = rng.dirichlet(
            np.ones(token_count), size=(labels, sources)
        )
        transform = rng.dirichlet(np.ones(token_count), size=token_count)
        residual = rng.dirichlet(
            np.ones(token_count), size=(labels, sources)
        )
        retained_truth = float(rng.uniform(0.05, 0.95))
        bridge = retained_truth * (reference @ transform) + (
            1.0 - retained_truth
        ) * residual
        certificate = certify_bridge_membership(
            reference,
            reference_l1_radii=np.zeros((labels, sources)),
            bridge_empirical_distributions=bridge,
            bridge_l1_radii=np.zeros((labels, sources)),
        )
        for label_index, label in enumerate(certificate.labels):
            smallest_recovered_margin = min(
                smallest_recovered_margin,
                label.optimal_retained_mass_upper - retained_truth,
            )
            difference = bridge[label_index] - label.retained_mass * (
                reference[label_index] @ label.transform
            )
            smallest_membership_slack = min(
                smallest_membership_slack, float(np.min(difference))
            )
            if label.optimal_retained_mass_upper + TOLERANCE < retained_truth:
                raise AssertionError("LP failed to recover a known feasible bridge")
            if np.min(difference) < -TOLERANCE:
                raise AssertionError("returned bridge lacks a population residual")
    return {
        "checks": repetitions * 2,
        "smallest_recovered_margin": smallest_recovered_margin,
        "smallest_population_membership_slack": smallest_membership_slack,
    }


def confidence_event_checks(
    rng: np.random.Generator, repetitions: int, sample_size: int, delta: float
) -> dict[str, float | int]:
    event_count = 0
    implication_count = 0
    minimum_true_slack = np.inf
    stratum_delta = delta / 8.0
    radius = weissman_l1_radius(sample_size, 4, stratum_delta)
    for _ in range(repetitions):
        reference = rng.dirichlet(np.ones(4), size=(2, 2))
        transform = rng.dirichlet(np.ones(4), size=4)
        residual = rng.dirichlet(np.ones(4), size=(2, 2))
        retained_truth = float(rng.uniform(0.25, 0.9))
        bridge = retained_truth * (reference @ transform) + (
            1.0 - retained_truth
        ) * residual
        reference_counts = np.asarray(
            [
                [rng.multinomial(sample_size, reference[y, s]) for s in range(2)]
                for y in range(2)
            ]
        )
        bridge_counts = np.asarray(
            [
                [rng.multinomial(sample_size, bridge[y, s]) for s in range(2)]
                for y in range(2)
            ]
        )
        reference_empirical = reference_counts / sample_size
        bridge_empirical = bridge_counts / sample_size
        event = bool(
            np.all(np.abs(reference_empirical - reference).sum(axis=2) <= radius)
            and np.all(np.abs(bridge_empirical - bridge).sum(axis=2) <= radius)
        )
        if not event:
            continue
        event_count += 1
        certificate = certify_bridge_membership(
            reference_empirical,
            reference_l1_radii=np.full((2, 2), radius),
            bridge_empirical_distributions=bridge_empirical,
            bridge_l1_radii=np.full((2, 2), radius),
        )
        valid = True
        for label_index, label in enumerate(certificate.labels):
            difference = bridge[label_index] - label.retained_mass * (
                reference[label_index] @ label.transform
            )
            minimum_true_slack = min(minimum_true_slack, float(np.min(difference)))
            valid = valid and bool(np.min(difference) >= -TOLERANCE)
        if not valid:
            raise AssertionError("bridge implication failed on its confidence event")
        implication_count += 1
    if event_count == 0:
        raise AssertionError("confidence-event simulation produced no covered tables")
    return {
        "tables": repetitions,
        "confidence_event_tables": event_count,
        "verified_implications": implication_count,
        "minimum_true_membership_slack": minimum_true_slack,
        "sample_size_per_stratum": sample_size,
        "familywise_delta": delta,
    }


def missing_support_check() -> dict[str, object]:
    reference = np.asarray(
        [
            [[0.8, 0.2], [0.3, 0.7]],
            [[0.6, 0.4], [0.1, 0.9]],
        ]
    )
    bridge = np.full_like(reference, 0.5)
    radii = np.zeros((2, 2))
    bridge_radii = np.zeros((2, 2))
    bridge_radii[:, 1] = 2.0
    certificate = certify_bridge_membership(
        reference,
        reference_l1_radii=radii,
        bridge_empirical_distributions=bridge,
        bridge_l1_radii=bridge_radii,
    )
    if any(value != 0.0 for value in certificate.retained_masses):
        raise AssertionError("a missing required bridge source certified positive mass")
    return {
        "retained_masses": certificate.retained_masses,
        "passed": True,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=20270718)
    parser.add_argument("--support-repetitions", type=int, default=1000)
    parser.add_argument("--grid-repetitions", type=int, default=40)
    parser.add_argument("--grid-size", type=int, default=201)
    parser.add_argument("--membership-repetitions", type=int, default=250)
    parser.add_argument("--coverage-repetitions", type=int, default=500)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    payload: dict[str, object] = {
        "name": "MOSAIC bridge independent falsification audit",
        "seed": args.seed,
        "support_function": support_function_checks(
            rng, args.support_repetitions
        ),
        "binary_transform_grid": binary_grid_checks(
            rng, args.grid_repetitions, args.grid_size
        ),
        "known_membership": known_membership_checks(
            rng, args.membership_repetitions
        ),
        "confidence_event_implication": confidence_event_checks(
            rng,
            args.coverage_repetitions,
            sample_size=300,
            delta=0.05,
        ),
        "missing_support": missing_support_check(),
        "pass": True,
    }
    if args.output is not None:
        atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
