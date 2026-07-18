#!/usr/bin/env python3
"""Run the hash-locked MOSAIC synthetic confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
from scipy.stats import beta

from mosaic_optimizer import optimize_population_external_channel
from run_mosaic_synthetic_pilot import (
    METHODS,
    ReplicateResult,
    Scenario,
    aggregate,
    run_replicate,
    selection_from_population_solution,
)


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_PREREG = ROOT / "prereg_mosaic_synthetic_v1.json"
DEFAULT_SIDECAR = ROOT / "prereg_mosaic_synthetic_v1.sha256"
DEFAULT_OUTPUT = (
    REPOSITORY / "research" / "artifacts" / "mosaic_synthetic_confirmation_v1.json"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def verify_lock(prereg: Path, sidecar: Path) -> tuple[dict[str, Any], str]:
    expected = sidecar.read_text(encoding="utf-8").strip().split()[0]
    actual = sha256(prereg)
    if actual != expected:
        raise RuntimeError(
            f"preregistration hash mismatch: expected {expected}, found {actual}"
        )
    config = load_json(prereg)
    for lock_name in ("code_sha256", "pilot_artifact_sha256"):
        for relative_path, expected_hash in config[lock_name].items():
            path = REPOSITORY / relative_path
            actual_hash = sha256(path)
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"locked {lock_name} mismatch for {relative_path}: "
                    f"expected {expected_hash}, found {actual_hash}"
                )
    return config, actual


def scenario_from_config(
    config: dict[str, Any], population_config: dict[str, Any]
) -> Scenario:
    family = str(population_config["family"])
    if config["population_family"] != family:
        raise ValueError("scenario references the wrong population family")
    if family != "stochastic_middle_token_v1":
        raise ValueError("unknown population family")
    population = np.asarray(population_config["laws"], dtype=np.float64)
    if population.ndim != 3 or population.shape[0] < 2 or population.shape[1] < 2:
        raise ValueError("registered population must have label, source, and token axes")
    if np.any(population < 0.0) or not np.allclose(
        population.sum(axis=2), 1.0, atol=1e-12
    ):
        raise ValueError("registered source-label laws must be probabilities")
    fine_count = population.shape[2]
    transforms = tuple(
        np.asarray(transform, dtype=np.float64)
        for transform in population_config["common_transform_extremes"]
    )
    if not transforms or any(
        transform.shape != (fine_count, fine_count)
        or np.any(transform < 0.0)
        or not np.allclose(transform.sum(axis=1), 1.0, atol=1e-12)
        for transform in transforms
    ):
        raise ValueError("registered common transforms must be stochastic K-by-K matrices")
    contamination = float(config["contamination"])
    privacy_threshold = float(config["privacy_threshold"])
    return Scenario(
        name=str(config["name"]),
        population=population,
        libraries=tuple(transforms for _ in range(population.shape[0])),
        contaminations=tuple(contamination for _ in range(population.shape[0])),
        privacy_thresholds=tuple(
            privacy_threshold for _ in range(population.shape[0])
        ),
        utility_threshold=float(config["utility_threshold"]),
        released_token_count=int(population_config["released_token_count"]),
    )


def clopper_pearson(
    successes: int, trials: int, *, alpha: float
) -> tuple[float, float]:
    lower = 0.0 if successes == 0 else float(
        beta.ppf(alpha / 2.0, successes, trials - successes + 1)
    )
    upper = 1.0 if successes == trials else float(
        beta.ppf(1.0 - alpha / 2.0, successes + 1, trials - successes)
    )
    return lower, upper


def add_intervals(cells: list[dict[str, object]]) -> None:
    for cell in cells:
        trials = int(cell["replicates"])
        for count_field, prefix in (
            ("deployments", "deployment"),
            ("false_acceptances", "false_acceptance"),
            ("safe_deployments", "safe_deployment"),
        ):
            lower, upper = clopper_pearson(
                int(cell[count_field]), trials, alpha=0.05
            )
            cell[f"{prefix}_cp95_lower"] = lower
            cell[f"{prefix}_cp95_upper"] = upper


def cell_index(
    cells: list[dict[str, object]], scenario_name: str, n: int, method: str
) -> dict[str, object]:
    matches = [
        cell
        for cell in cells
        if cell["scenario"] == scenario_name
        and int(cell["sample_size_per_stratum"]) == n
        and cell["method"] == method
    ]
    if len(matches) != 1:
        raise AssertionError(
            f"expected one cell for {(scenario_name, n, method)}, found {len(matches)}"
        )
    return matches[0]


def evaluate_pass_conditions(
    cells: list[dict[str, object]], config: dict[str, Any]
) -> dict[str, object]:
    delta = float(config["delta"])
    mosaic_cells = [cell for cell in cells if cell["method"] == "mosaic"]
    coverage = all(
        float(cell["false_acceptance_rate"]) <= delta + 1e-12
        and int(cell["failures_on_confidence_event"]) == 0
        for cell in mosaic_cells
    )

    killer = config["pass_conditions"]["killer_contrast"]
    plugin_cell = cell_index(
        cells,
        str(killer["scenario"]),
        int(killer["sample_size_per_stratum"]),
        "plugin_continuum",
    )
    killer_mosaic = cell_index(
        cells,
        str(killer["scenario"]),
        int(killer["sample_size_per_stratum"]),
        "mosaic",
    )
    killer_pass = bool(
        float(plugin_cell["false_acceptance_rate"])
        >= float(killer["minimum_plugin_false_acceptance"])
        and float(killer_mosaic["false_acceptance_rate"])
        <= float(killer["maximum_mosaic_false_acceptance"])
    )

    retention = config["pass_conditions"]["retention"]
    retention_mosaic = cell_index(
        cells,
        str(retention["scenario"]),
        int(retention["sample_size_per_stratum"]),
        "mosaic",
    )
    comparator_cells = {
        str(method): cell_index(
            cells,
            str(retention["scenario"]),
            int(retention["sample_size_per_stratum"]),
            str(method),
        )
        for method in retention["comparators"]
    }
    if "deterministic_mosaic" not in comparator_cells:
        raise ValueError("retention comparators must include deterministic_mosaic")
    mosaic_rate = float(retention_mosaic["safe_deployment_rate"])
    margin = float(retention["minimum_absolute_margin"])
    finite_comparator_rates = {
        method: float(cell["safe_deployment_rate"])
        for method, cell in comparator_cells.items()
        if method != "deterministic_mosaic"
    }
    retention_pass = bool(
        mosaic_rate >= float(retention["minimum_mosaic_safe_retention"])
        and all(
            mosaic_rate >= comparator_rate + margin
            for comparator_rate in finite_comparator_rates.values()
        )
    )
    stochastic_pass = bool(
        mosaic_rate
        >= float(comparator_cells["deterministic_mosaic"]["safe_deployment_rate"])
        + float(retention["minimum_stochastic_margin"])
    )
    oracle_cells = [cell for cell in cells if cell["method"] == "population_oracle"]
    oracle_pass = all(
        float(cell["safe_deployment_rate"]) == 1.0 for cell in oracle_cells
    )
    all_pass = bool(
        coverage and killer_pass and retention_pass and stochastic_pass and oracle_pass
    )
    return {
        "coverage": coverage,
        "killer_contrast": killer_pass,
        "safe_retention": retention_pass,
        "stochastic_value": stochastic_pass,
        "oracle_opportunity_present": oracle_pass,
        "all_pass": all_pass,
        "killer_plugin_false_acceptance_rate": plugin_cell[
            "false_acceptance_rate"
        ],
        "killer_mosaic_false_acceptance_rate": killer_mosaic[
            "false_acceptance_rate"
        ],
        "retention_mosaic_safe_deployment_rate": mosaic_rate,
        "retention_heldout_safe_deployment_rate": comparator_cells[
            "heldout_fixed_channel"
        ]["safe_deployment_rate"],
        "retention_finite_ltt_safe_deployment_rate": comparator_cells[
            "finite_ltt"
        ]["safe_deployment_rate"],
        "retention_deterministic_safe_deployment_rate": comparator_cells[
            "deterministic_mosaic"
        ]["safe_deployment_rate"],
    }


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
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--sidecar", type=Path, default=DEFAULT_SIDECAR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.workers <= 0:
        raise ValueError("workers must be positive")
    config, prereg_hash = verify_lock(args.prereg, args.sidecar)
    if set(config["methods"]) != set(METHODS):
        raise ValueError("locked method registry does not match the implementation")
    delta = float(config["delta"])
    replicate_count = int(config["replicates_per_cell"])
    if replicate_count < 1000:
        raise ValueError("locked confirmation requires at least 1,000 replicates")

    all_rows: list[dict[str, object]] = []
    all_cells: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for scenario_index, scenario_config in enumerate(config["scenarios"]):
            scenario = scenario_from_config(scenario_config, config["population"])
            oracle_solution = optimize_population_external_channel(
                scenario.population,
                common_channels_by_label=scenario.libraries,
                contaminations=scenario.contaminations,
                privacy_advantage_thresholds=scenario.privacy_thresholds,
                released_token_count=scenario.released_token_count,
            )
            oracle = selection_from_population_solution(oracle_solution)
            for n in scenario_config["sample_sizes_per_stratum"]:
                n = int(n)
                seeds = [
                    int(config["seed_base"])
                    + scenario_index * 10_000_000
                    + n * 10_000
                    + replicate
                    for replicate in range(replicate_count)
                ]
                payloads = [
                    (seed, n, scenario, delta, oracle) for seed in seeds
                ]
                nested = list(executor.map(run_replicate, payloads))
                results: list[ReplicateResult] = [
                    result for group in nested for result in group
                ]
                cells = aggregate(results)
                add_intervals(cells)
                for cell in cells:
                    cell["scenario"] = scenario_config["name"]
                    all_cells.append(cell)
                for result in results:
                    row = asdict(result)
                    row["scenario"] = scenario_config["name"]
                    all_rows.append(row)

    pass_conditions = evaluate_pass_conditions(all_cells, config)
    report: dict[str, object] = {
        "name": "MOSAIC v2 hash-locked synthetic confirmation v1",
        "status": "complete_confirmatory_result",
        "preregistration": str(args.prereg),
        "preregistration_sha256": prereg_hash,
        "code_sha256": config["code_sha256"],
        "pilot_artifact_sha256": config["pilot_artifact_sha256"],
        "delta": delta,
        "replicates_per_cell": replicate_count,
        "methods": list(METHODS),
        "scenarios": config["scenarios"],
        "cells": all_cells,
        "pass_conditions": pass_conditions,
        "replicate_results": all_rows,
        "scope": (
            "Untouched-seed synthetic confirmation. Every selected channel is "
            "graded against exact population external risk under the locked "
            "common-transform plus differential-contamination model."
        ),
    }
    atomic_json_dump(report, args.output)
    print(
        json.dumps(
            {key: value for key, value in report.items() if key != "replicate_results"},
            indent=2,
            sort_keys=True,
        )
    )
    if not pass_conditions["all_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
