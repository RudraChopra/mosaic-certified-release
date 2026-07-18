#!/usr/bin/env python3
"""Replay exact risk labels and aggregates in a MOSAIC synthetic pilot."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np

from mosaic_exact import (
    exact_external_attacker_risk,
    exact_external_utility_risk,
)


TOLERANCE = 5e-9


def load_json(path: Path) -> dict[str, object]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def atomic_json_dump(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("research/artifacts/mosaic_synthetic_design_pilot_v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("research/artifacts/mosaic_synthetic_design_pilot_audit_v1.json"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = load_json(args.report)
    scenario = report["scenario"]
    if not isinstance(scenario, dict):
        raise ValueError("scenario must be an object")
    population = np.asarray(scenario["population"], dtype=np.float64)
    libraries = tuple(
        tuple(np.asarray(transform, dtype=np.float64) for transform in library)
        for library in scenario["common_transform_libraries"]
    )
    contaminations = tuple(float(value) for value in scenario["contaminations"])
    privacy_thresholds = tuple(
        float(value) for value in scenario["privacy_advantage_thresholds"]
    )
    utility_threshold = float(scenario["utility_threshold"])
    rows = report["replicate_results"]
    if not isinstance(rows, list) or not rows:
        raise ValueError("replicate_results must be a non-empty list")
    methods = tuple(str(method) for method in report["methods"])
    sample_sizes = tuple(int(value) for value in report["sample_sizes_per_stratum"])
    replicates = int(report["replicates_per_sample_size"])
    expected_rows = len(methods) * len(sample_sizes) * replicates
    if len(rows) != expected_rows:
        raise AssertionError(
            f"expected {expected_rows} replicate rows, found {len(rows)}"
        )

    risk_checks = 0
    decision_checks = 0
    stochastic_row_checks = 0
    failures_on_confidence_event = 0
    grouped: dict[tuple[int, str], list[dict[str, object]]] = defaultdict(list)
    seen_seeds: dict[tuple[int, str], set[int]] = defaultdict(set)
    worst_risk_mismatch = 0.0

    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("every replicate result must be an object")
        channel = np.asarray(row["release_channel"], dtype=np.float64)
        decoder = tuple(int(value) for value in row["decoder"])
        if channel.shape != (population.shape[2], int(scenario["released_token_count"])):
            raise AssertionError("receipt channel has the wrong shape")
        if len(decoder) != channel.shape[1] or any(
            value < 0 or value >= population.shape[0] for value in decoder
        ):
            raise AssertionError("receipt decoder is invalid")
        if not np.isfinite(channel).all() or np.any(channel < -1e-12):
            raise AssertionError("receipt contains an invalid release channel")
        if not np.allclose(channel.sum(axis=1), 1.0, atol=1e-10):
            raise AssertionError("receipt release channel is not row-stochastic")
        stochastic_row_checks += channel.shape[0]

        privacy_by_label = tuple(
            exact_external_attacker_risk(
                population[label],
                channel,
                libraries[label],
                contamination=contaminations[label],
            ).normalized_advantage
            for label in range(population.shape[0])
        )
        worst_privacy = max(privacy_by_label)
        worst_utility = max(
            exact_external_utility_risk(
                population[label, source],
                channel,
                decoder,
                true_label=label,
                common_fine_token_channels=libraries[label],
                contamination=contaminations[label],
            ).error_probability
            for label in range(population.shape[0])
            for source in range(population.shape[1])
        )
        privacy_gap = abs(
            worst_privacy - float(row["exact_worst_privacy_advantage"])
        )
        utility_gap = abs(
            worst_utility - float(row["exact_worst_conditional_error"])
        )
        worst_risk_mismatch = max(worst_risk_mismatch, privacy_gap, utility_gap)
        if privacy_gap > TOLERANCE or utility_gap > TOLERANCE:
            raise AssertionError("stored exact risk disagrees with replay")
        risk_checks += 2

        safe = bool(
            all(
                value <= privacy_thresholds[label] + 1e-9
                for label, value in enumerate(privacy_by_label)
            )
            and worst_utility <= utility_threshold + 1e-9
        )
        deployed = bool(row["deployed"])
        false_acceptance = bool(deployed and not safe)
        if bool(row["exact_safe"]) != safe:
            raise AssertionError("stored exact-safe label is wrong")
        if bool(row["false_acceptance"]) != false_acceptance:
            raise AssertionError("stored false-acceptance label is wrong")
        event = row["confidence_event"]
        if event not in (True, False, None):
            raise AssertionError("invalid confidence-event marker")
        expected_failure = None if event is None else bool(
            false_acceptance and event
        )
        if row["failure_on_confidence_event"] is not expected_failure:
            raise AssertionError("invalid failure-on-event marker")
        if expected_failure is True:
            failures_on_confidence_event += 1
        decision_checks += 2
        key = (int(row["sample_size_per_stratum"]), str(row["method"]))
        if key[0] not in sample_sizes or key[1] not in methods:
            raise AssertionError("receipt row is outside the registered pilot grid")
        seed = int(row["seed"])
        if seed in seen_seeds[key]:
            raise AssertionError("duplicate seed within a pilot cell")
        seen_seeds[key].add(seed)
        grouped[key].append(row)

    reported_cells = {
        (int(cell["sample_size_per_stratum"]), str(cell["method"])): cell
        for cell in report["cells"]
    }
    if len(reported_cells) != len(report["cells"]):
        raise AssertionError("report contains duplicate aggregate cells")
    aggregate_checks = 0
    for key, subset in grouped.items():
        cell = reported_cells.get(key)
        if cell is None:
            raise AssertionError(f"missing aggregate cell {key}")
        count = len(subset)
        expected = {
            "replicates": count,
            "deployments": sum(bool(row["deployed"]) for row in subset),
            "false_acceptances": sum(
                bool(row["false_acceptance"]) for row in subset
            ),
            "safe_deployments": sum(
                bool(row["deployed"]) and bool(row["exact_safe"])
                for row in subset
            ),
            "confidence_event_count": sum(
                row["confidence_event"] is True for row in subset
            ),
            "failures_on_confidence_event": sum(
                row["failure_on_confidence_event"] is True for row in subset
            ),
        }
        for field, value in expected.items():
            if int(cell[field]) != value:
                raise AssertionError(f"aggregate {key} has wrong {field}")
            aggregate_checks += 1
        expected_rates = {
            "deployment_rate": expected["deployments"] / count,
            "false_acceptance_rate": expected["false_acceptances"] / count,
            "safe_deployment_rate": expected["safe_deployments"] / count,
        }
        for field, value in expected_rates.items():
            if abs(float(cell[field]) - float(value)) > TOLERANCE:
                raise AssertionError(f"aggregate {key} has wrong {field}")
            aggregate_checks += 1
        expected_means = {
            "mean_exact_privacy_advantage": np.mean(
                [float(row["exact_worst_privacy_advantage"]) for row in subset]
            ),
            "mean_exact_worst_error": np.mean(
                [float(row["exact_worst_conditional_error"]) for row in subset]
            ),
            "mean_selection_criterion": np.mean(
                [float(row["selection_criterion"]) for row in subset]
            ),
        }
        for field, value in expected_means.items():
            if abs(float(cell[field]) - float(value)) > TOLERANCE:
                raise AssertionError(f"aggregate {key} has wrong {field}")
            aggregate_checks += 1

    if set(reported_cells) != set(grouped):
        raise AssertionError("report contains missing or extra aggregate cells")
    payload: dict[str, object] = {
        "name": "MOSAIC synthetic pilot exact-risk replay v1",
        "status": "development_only_not_independent_review",
        "report": str(args.report),
        "risk_recomputations": risk_checks,
        "decision_label_checks": decision_checks,
        "stochastic_row_checks": stochastic_row_checks,
        "aggregate_checks": aggregate_checks,
        "failures_on_confidence_event": failures_on_confidence_event,
        "worst_risk_mismatch": worst_risk_mismatch,
        "pass": True,
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
