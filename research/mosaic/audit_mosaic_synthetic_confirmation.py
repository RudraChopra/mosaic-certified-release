#!/usr/bin/env python3
"""Independent replay of the hash-locked MOSAIC synthetic confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np
from scipy.stats import beta

from mosaic_exact import (
    exact_external_attacker_risk,
    exact_external_utility_risk,
)


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_PREREG = ROOT / "prereg_mosaic_synthetic_v1.json"
DEFAULT_SIDECAR = ROOT / "prereg_mosaic_synthetic_v1.sha256"
DEFAULT_REPORT = (
    REPOSITORY / "research" / "artifacts" / "mosaic_synthetic_confirmation_v1.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY
    / "research"
    / "artifacts"
    / "mosaic_synthetic_confirmation_audit_v1.json"
)
TOLERANCE = 5e-9


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


def cp_interval(successes: int, trials: int) -> tuple[float, float]:
    lower = 0.0 if successes == 0 else float(
        beta.ppf(0.025, successes, trials - successes + 1)
    )
    upper = 1.0 if successes == trials else float(
        beta.ppf(0.975, successes + 1, trials - successes)
    )
    return lower, upper


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
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    expected_prereg_hash = args.sidecar.read_text(encoding="utf-8").split()[0]
    actual_prereg_hash = sha256(args.prereg)
    if actual_prereg_hash != expected_prereg_hash:
        raise AssertionError("preregistration sidecar mismatch")
    prereg = load_json(args.prereg)
    report = load_json(args.report)
    if report["preregistration_sha256"] != actual_prereg_hash:
        raise AssertionError("report uses the wrong preregistration")
    if report["code_sha256"] != prereg["code_sha256"]:
        raise AssertionError("report code lock differs from preregistration")
    if report["pilot_artifact_sha256"] != prereg["pilot_artifact_sha256"]:
        raise AssertionError("report pilot lock differs from preregistration")
    for lock_name in ("code_sha256", "pilot_artifact_sha256"):
        for relative_path, expected_hash in prereg[lock_name].items():
            actual_hash = sha256(REPOSITORY / relative_path)
            if actual_hash != expected_hash:
                raise AssertionError(
                    f"current {lock_name} mismatch for {relative_path}"
                )
    if float(report["delta"]) != float(prereg["delta"]):
        raise AssertionError("report uses the wrong failure probability")
    if int(report["replicates_per_cell"]) != int(prereg["replicates_per_cell"]):
        raise AssertionError("report uses the wrong replicate count")
    if report["scenarios"] != prereg["scenarios"]:
        raise AssertionError("report scenario registry differs from preregistration")

    scenario_list = list(prereg["scenarios"])
    scenario_configs = {
        str(config["name"]): config for config in scenario_list
    }
    scenario_indices = {
        str(config["name"]): index
        for index, config in enumerate(scenario_list)
    }
    if len(scenario_configs) != len(scenario_list):
        raise AssertionError("scenario names must be unique")
    population_config = prereg["population"]
    population = np.asarray(population_config["laws"], dtype=np.float64)
    if population.ndim != 3 or np.any(population < 0.0) or not np.allclose(
        population.sum(axis=2), 1.0, atol=1e-12
    ):
        raise AssertionError("preregistered population laws are invalid")
    label_count, source_count, fine_count = population.shape
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
        raise AssertionError("preregistered common transforms are invalid")
    libraries = tuple(transforms for _ in range(label_count))
    released_count = int(population_config["released_token_count"])

    rows = report["replicate_results"]
    methods = tuple(str(method) for method in report["methods"])
    if len(methods) != len(set(methods)) or set(methods) != set(prereg["methods"]):
        raise AssertionError("report method registry differs from preregistration")
    replicate_count = int(prereg["replicates_per_cell"])
    expected_result_count = (
        sum(len(config["sample_sizes_per_stratum"]) for config in prereg["scenarios"])
        * replicate_count
        * len(methods)
    )
    if len(rows) != expected_result_count:
        raise AssertionError(
            f"expected {expected_result_count} replicate rows, found {len(rows)}"
        )
    expected_cell_keys = {
        (str(config["name"]), int(n), method)
        for config in scenario_list
        for n in config["sample_sizes_per_stratum"]
        for method in methods
    }

    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = defaultdict(list)
    seen: dict[tuple[str, int, str], set[int]] = defaultdict(set)
    risk_checks = 0
    decision_checks = 0
    seed_checks = 0
    row_stochastic_checks = 0
    worst_risk_mismatch = 0.0

    for row in rows:
        scenario_name = str(row["scenario"])
        if scenario_name not in scenario_configs:
            raise AssertionError("receipt contains an unregistered scenario")
        config = scenario_configs[scenario_name]
        n = int(row["sample_size_per_stratum"])
        method = str(row["method"])
        if n not in {int(value) for value in config["sample_sizes_per_stratum"]}:
            raise AssertionError("receipt contains an unregistered sample size")
        if method not in methods:
            raise AssertionError("receipt contains an unregistered method")
        seed = int(row["seed"])
        scenario_index = scenario_indices[scenario_name]
        expected_seed_start = (
            int(prereg["seed_base"])
            + scenario_index * 10_000_000
            + n * 10_000
        )
        if not expected_seed_start <= seed < expected_seed_start + replicate_count:
            raise AssertionError("receipt seed is outside its locked cell range")
        key = (scenario_name, n, method)
        if seed in seen[key]:
            raise AssertionError("duplicate seed within a method cell")
        seen[key].add(seed)
        seed_checks += 1

        channel = np.asarray(row["release_channel"], dtype=np.float64)
        decoder = tuple(int(value) for value in row["decoder"])
        if channel.shape != (fine_count, released_count):
            raise AssertionError("receipt channel has the wrong shape")
        if len(decoder) != released_count or any(
            value < 0 or value >= label_count for value in decoder
        ):
            raise AssertionError("receipt decoder is invalid")
        if not np.isfinite(channel).all() or np.any(channel < -1e-12):
            raise AssertionError("invalid channel in receipt")
        if not np.allclose(channel.sum(axis=1), 1.0, atol=1e-10):
            raise AssertionError("receipt channel is not row-stochastic")
        row_stochastic_checks += channel.shape[0]

        eta = float(config["contamination"])
        privacy_threshold = float(config["privacy_threshold"])
        utility_threshold = float(config["utility_threshold"])
        privacy_by_label = tuple(
            exact_external_attacker_risk(
                population[label],
                channel,
                libraries[label],
                contamination=eta,
            ).normalized_advantage
            for label in range(label_count)
        )
        worst_privacy = max(privacy_by_label)
        worst_utility = max(
            exact_external_utility_risk(
                population[label, source],
                channel,
                decoder,
                true_label=label,
                common_fine_token_channels=libraries[label],
                contamination=eta,
            ).error_probability
            for label in range(label_count)
            for source in range(source_count)
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
            all(value <= privacy_threshold + 1e-9 for value in privacy_by_label)
            and worst_utility <= utility_threshold + 1e-9
        )
        false_acceptance = bool(row["deployed"] and not safe)
        if bool(row["exact_safe"]) != safe:
            raise AssertionError("incorrect exact-safe label")
        if bool(row["false_acceptance"]) != false_acceptance:
            raise AssertionError("incorrect false-acceptance label")
        event = row["confidence_event"]
        if event not in (True, False, None):
            raise AssertionError("invalid confidence-event marker")
        expected_failure = None if event is None else bool(
            false_acceptance and event
        )
        if row["failure_on_confidence_event"] is not expected_failure:
            raise AssertionError("incorrect failure-on-event marker")
        decision_checks += 2
        grouped[key].append(row)

    if set(grouped) != expected_cell_keys:
        raise AssertionError("replicate rows do not cover the registered cell grid")

    reported_cells = {
        (str(cell["scenario"]), int(cell["sample_size_per_stratum"]), str(cell["method"])): cell
        for cell in report["cells"]
    }
    if len(reported_cells) != len(report["cells"]):
        raise AssertionError("report contains duplicate aggregate cells")
    if set(reported_cells) != set(grouped):
        raise AssertionError("aggregate-cell keys disagree with replicate rows")
    aggregate_checks = 0
    for key, subset in grouped.items():
        if len(subset) != replicate_count:
            raise AssertionError(f"cell {key} is incomplete")
        cell = reported_cells[key]
        counts = {
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
        if int(cell["replicates"]) != replicate_count:
            raise AssertionError(f"cell {key} has wrong replicate count")
        aggregate_checks += 1
        for field, value in counts.items():
            if int(cell[field]) != value:
                raise AssertionError(f"cell {key} has wrong {field}")
            aggregate_checks += 1
        for count_field, prefix in (
            ("deployments", "deployment"),
            ("false_acceptances", "false_acceptance"),
            ("safe_deployments", "safe_deployment"),
        ):
            lower, upper = cp_interval(counts[count_field], replicate_count)
            if (
                abs(float(cell[f"{prefix}_cp95_lower"]) - lower) > TOLERANCE
                or abs(float(cell[f"{prefix}_cp95_upper"]) - upper) > TOLERANCE
            ):
                raise AssertionError(f"cell {key} has wrong {prefix} interval")
            aggregate_checks += 2
        rates = {
            "deployment_rate": counts["deployments"] / replicate_count,
            "false_acceptance_rate": counts["false_acceptances"] / replicate_count,
            "safe_deployment_rate": counts["safe_deployments"] / replicate_count,
            "mean_exact_privacy_advantage": float(
                np.mean(
                    [float(row["exact_worst_privacy_advantage"]) for row in subset]
                )
            ),
            "mean_exact_worst_error": float(
                np.mean(
                    [float(row["exact_worst_conditional_error"]) for row in subset]
                )
            ),
            "mean_selection_criterion": float(
                np.mean([float(row["selection_criterion"]) for row in subset])
            ),
        }
        for field, expected_value in rates.items():
            if abs(float(cell[field]) - expected_value) > TOLERANCE:
                raise AssertionError(f"cell {key} has wrong {field}")
            aggregate_checks += 1

    delta = float(prereg["delta"])
    mosaic_cells = [cell for key, cell in reported_cells.items() if key[2] == "mosaic"]
    coverage = all(
        int(cell["false_acceptances"]) / replicate_count <= delta + 1e-12
        and int(cell["failures_on_confidence_event"]) == 0
        for cell in mosaic_cells
    )
    killer = prereg["pass_conditions"]["killer_contrast"]
    killer_key = (
        str(killer["scenario"]),
        int(killer["sample_size_per_stratum"]),
    )
    plugin_rate = float(reported_cells[killer_key + ("plugin_continuum",)]["false_acceptance_rate"])
    mosaic_false = float(reported_cells[killer_key + ("mosaic",)]["false_acceptance_rate"])
    killer_pass = bool(
        plugin_rate >= float(killer["minimum_plugin_false_acceptance"])
        and mosaic_false <= float(killer["maximum_mosaic_false_acceptance"])
    )
    retention = prereg["pass_conditions"]["retention"]
    retention_key = (
        str(retention["scenario"]),
        int(retention["sample_size_per_stratum"]),
    )
    comparator_methods = tuple(str(method) for method in retention["comparators"])
    if "deterministic_mosaic" not in comparator_methods:
        raise AssertionError("deterministic comparator is missing")
    rates = {
        method: float(
            reported_cells[retention_key + (method,)]["safe_deployment_rate"]
        )
        for method in ("mosaic", *comparator_methods)
    }
    margin = float(retention["minimum_absolute_margin"])
    retention_pass = bool(
        rates["mosaic"] >= float(retention["minimum_mosaic_safe_retention"])
        and all(
            rates["mosaic"] >= rates[method] + margin
            for method in comparator_methods
            if method != "deterministic_mosaic"
        )
    )
    stochastic_pass = bool(
        rates["mosaic"]
        >= rates["deterministic_mosaic"]
        + float(retention["minimum_stochastic_margin"])
    )
    oracle_pass = all(
        float(cell["safe_deployment_rate"]) == 1.0
        for key, cell in reported_cells.items()
        if key[2] == "population_oracle"
    )
    all_pass = bool(
        coverage and killer_pass and retention_pass and stochastic_pass and oracle_pass
    )
    expected_pass_conditions = {
        "coverage": coverage,
        "killer_contrast": killer_pass,
        "safe_retention": retention_pass,
        "stochastic_value": stochastic_pass,
        "oracle_opportunity_present": oracle_pass,
        "all_pass": all_pass,
        "killer_plugin_false_acceptance_rate": plugin_rate,
        "killer_mosaic_false_acceptance_rate": mosaic_false,
        "retention_mosaic_safe_deployment_rate": rates["mosaic"],
        "retention_heldout_safe_deployment_rate": rates[
            "heldout_fixed_channel"
        ],
        "retention_finite_ltt_safe_deployment_rate": rates["finite_ltt"],
        "retention_deterministic_safe_deployment_rate": rates[
            "deterministic_mosaic"
        ],
    }
    if set(report["pass_conditions"]) != set(expected_pass_conditions):
        raise AssertionError("report has the wrong pass-condition fields")
    for field, expected_value in expected_pass_conditions.items():
        reported_value = report["pass_conditions"][field]
        if isinstance(expected_value, bool):
            if reported_value is not expected_value:
                raise AssertionError(f"report has the wrong {field} decision")
        elif abs(float(reported_value) - float(expected_value)) > TOLERANCE:
            raise AssertionError(f"report has the wrong {field} value")

    payload: dict[str, object] = {
        "name": "MOSAIC synthetic confirmation independent replay v1",
        "status": "development_only_not_independent_human_review",
        "preregistration_sha256": actual_prereg_hash,
        "report_sha256": sha256(args.report),
        "expected_replicate_rows": expected_result_count,
        "seed_checks": seed_checks,
        "row_stochastic_checks": row_stochastic_checks,
        "risk_recomputations": risk_checks,
        "decision_label_checks": decision_checks,
        "aggregate_checks": aggregate_checks,
        "worst_risk_mismatch": worst_risk_mismatch,
        "independent_pass_conditions": {
            "coverage": coverage,
            "killer_contrast": killer_pass,
            "safe_retention": retention_pass,
            "stochastic_value": stochastic_pass,
            "oracle_opportunity_present": oracle_pass,
            "all_pass": all_pass,
        },
        "pass": True,
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
