"""Compare observed real-data abstention curves with plug-in bootstrap predictions.

This is a calibration diagnostic, not an independent theorem validation. The
bootstrap uses only the full certification fold, preserves each resampled
example jointly across candidates and attackers, and never reads external
outcomes. Exact synthetic-law coverage remains the primary theory check.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import beta

from analyze_vera_real_study import load_json, nested_stratified_indices


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_real.json"
DEFAULT_HASH = ROOT / "prereg_real.sha256"
DEFAULT_RECEIPTS = ROOT / "artifacts" / "real_study_receipts"
DEFAULT_DEPLOYMENT_ROWS = ROOT / "artifacts" / "vera_deployment_rule_rows.csv"
DEFAULT_SYNTHETIC_AUDIT = ROOT / "artifacts" / "vera_exact_synthetic_audit.json"
DEFAULT_CELLS = ROOT / "artifacts" / "vera_real_theory_match_cells.csv"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_real_theory_match_report.json"
DEFAULT_PDF = ROOT / "maintrack" / "figures" / "vera_real_theory_match.pdf"
DEFAULT_PNG = ROOT / "maintrack" / "figures" / "vera_real_theory_match.png"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@lru_cache(maxsize=None)
def cp_upper_table(n: int, alpha: float) -> np.ndarray:
    counts = np.arange(n + 1)
    values = np.ones(n + 1, dtype=np.float64)
    mask = counts < n
    values[mask] = beta.ppf(1.0 - alpha, counts[mask] + 1, n - counts[mask])
    return values


@lru_cache(maxsize=None)
def cp_lower_table(n: int, alpha: float) -> np.ndarray:
    counts = np.arange(n + 1)
    values = np.zeros(n + 1, dtype=np.float64)
    mask = counts > 0
    values[mask] = beta.ppf(alpha, counts[mask], n - counts[mask] + 1)
    return values


def paired_ucb(
    positive: np.ndarray,
    negative: np.ndarray,
    n: int,
    alpha: float,
    gamma: float,
) -> np.ndarray:
    positive_probability = np.minimum(
        cp_upper_table(n, alpha / 2.0)[positive],
        1.0 - cp_lower_table(n, alpha / 2.0)[negative],
    )
    negative_probability = cp_lower_table(n, alpha / 2.0)[negative]
    zero_probability = np.maximum(
        0.0, 1.0 - positive_probability - negative_probability
    )
    positive_mass = np.minimum(1.0, gamma * positive_probability)
    remaining = 1.0 - positive_mass
    zero_mass = np.minimum(remaining, gamma * zero_probability)
    return positive_mass - np.maximum(0.0, remaining - zero_mass)


def leakage_ucb(successes: np.ndarray, n: int, alpha: float, gamma: float) -> np.ndarray:
    return np.minimum(1.0, gamma * cp_upper_table(n, alpha)[successes])


def load_seed_arrays(
    dataset: str,
    seed: int,
    methods: dict[str, dict[str, Any]],
    receipt_dir: Path,
) -> dict[str, Any]:
    harms: list[np.ndarray] = []
    leakage: dict[str, list[np.ndarray]] = {}
    labels: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
    candidate_keys: list[str] = []
    for method_key, method_config in methods.items():
        receipt = load_json(receipt_dir / f"{dataset}__{method_key}__seed-{seed}.json")
        for candidate in receipt["candidates"]:
            with np.load(candidate["audit_npz"]) as archive:
                current_labels = (
                    np.asarray(archive["target_certification"], dtype=np.int64),
                    np.asarray(archive["source_certification"], dtype=np.int64),
                    np.asarray(archive["environment_certification"], dtype=np.int64),
                )
                if labels is None:
                    labels = current_labels
                elif not all(
                    np.array_equal(left, right)
                    for left, right in zip(labels, current_labels)
                ):
                    raise RuntimeError(f"certification labels differ for {dataset}/seed-{seed}")
                harms.append(
                    np.asarray(archive["target_harm_certification"], dtype=np.int8)
                )
                attacker_names = sorted(
                    name.removeprefix("leakage_correct_certification__")
                    for name in archive.files
                    if name.startswith("leakage_correct_certification__")
                )
                for attacker in attacker_names:
                    leakage.setdefault(attacker, []).append(
                        np.asarray(
                            archive[f"leakage_correct_certification__{attacker}"],
                            dtype=np.int8,
                        )
                    )
            candidate_keys.append(
                f"{method_config['display_name']}::{candidate['strength']}"
            )
    if labels is None or not harms:
        raise RuntimeError(f"no candidates found for {dataset}/seed-{seed}")
    if any(len(values) != len(harms) for values in leakage.values()):
        raise RuntimeError(f"attacker portfolio differs across candidates for {dataset}/seed-{seed}")
    return {
        "target": labels[0],
        "source": labels[1],
        "environment": labels[2],
        "harm": np.column_stack(harms),
        "leakage": {
            attacker: np.column_stack(values) for attacker, values in leakage.items()
        },
        "candidate_keys": candidate_keys,
    }


def family_size(arrays: dict[str, Any]) -> int:
    environments = np.asarray(arrays["environment"])
    sources = np.asarray(arrays["source"])
    target_contracts = len(np.unique(environments))
    leakage_strata = len(set(zip(map(int, environments), map(int, sources))))
    contracts_per_candidate = target_contracts + len(arrays["leakage"]) * leakage_strata
    return int(arrays["harm"].shape[1] * contracts_per_candidate)


def candidate_bounds(
    arrays: dict[str, Any], indices: np.ndarray, *, alpha: float, gamma: float
) -> tuple[np.ndarray, np.ndarray]:
    environments = np.asarray(arrays["environment"])[indices]
    sources = np.asarray(arrays["source"])[indices]
    harm = np.asarray(arrays["harm"])[indices]
    candidate_count = harm.shape[1]
    target_max = np.full(candidate_count, -np.inf)
    leakage_max = np.full(candidate_count, -np.inf)
    for group in sorted(map(int, np.unique(environments))):
        mask = environments == group
        group_harm = harm[mask]
        target_max = np.maximum(
            target_max,
            paired_ucb(
                np.sum(group_harm == 1, axis=0),
                np.sum(group_harm == -1, axis=0),
                len(group_harm),
                alpha,
                gamma,
            ),
        )
    for attacker_values in arrays["leakage"].values():
        selected_values = np.asarray(attacker_values)[indices]
        for group, source_class in sorted(
            set(zip(map(int, environments), map(int, sources)))
        ):
            mask = (environments == group) & (sources == source_class)
            group_values = selected_values[mask]
            leakage_max = np.maximum(
                leakage_max,
                leakage_ucb(
                    np.sum(group_values == 1, axis=0),
                    len(group_values),
                    alpha,
                    gamma,
                ),
            )
    return target_max, leakage_max


def abstention_over_thresholds(
    target_bounds: np.ndarray,
    leakage_bounds: np.ndarray,
    target_thresholds: list[float],
    leakage_thresholds: list[float],
) -> float:
    abstentions = 0
    total = 0
    for target_threshold in target_thresholds:
        for leakage_threshold in leakage_thresholds:
            deployed = np.any(
                (target_bounds <= target_threshold)
                & (leakage_bounds <= leakage_threshold)
            )
            abstentions += int(not deployed)
            total += 1
    return abstentions / total


def bootstrap_prefixes(
    arrays: dict[str, Any], fractions: list[float], rng: np.random.Generator
) -> dict[float, np.ndarray]:
    target = np.asarray(arrays["target"])
    source = np.asarray(arrays["source"])
    environment = np.asarray(arrays["environment"])
    strata: dict[tuple[int, int, int], np.ndarray] = {}
    for key in sorted(set(zip(map(int, target), map(int, source), map(int, environment)))):
        indices = np.flatnonzero(
            (target == key[0]) & (source == key[1]) & (environment == key[2])
        )
        strata[key] = rng.choice(indices, size=len(indices), replace=True)
    outputs: dict[float, np.ndarray] = {}
    for fraction in sorted(fractions):
        selected: list[int] = []
        for sequence in strata.values():
            take = (
                len(sequence)
                if fraction >= 1.0
                else max(1, int(np.floor(fraction * len(sequence))))
            )
            selected.extend(sequence[:take].tolist())
        outputs[fraction] = np.asarray(selected, dtype=np.int64)
    return outputs


def observed_curves_from_rows(path: Path) -> tuple[dict[tuple[str, float], float], dict[tuple[str, int], float]]:
    grouped: dict[tuple[str, float], list[float]] = {}
    external_violations: dict[tuple[str, int], list[float]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["rule"] != "vera":
                continue
            dataset = row["dataset"]
            fraction = float(row["validation_fraction"])
            seed = int(row["seed"])
            grouped.setdefault((dataset, fraction), []).append(
                float(row["deployed"].lower() != "true")
            )
            external_violations.setdefault((dataset, seed), []).append(
                float(row["measured_external_contract_violation"].lower() == "true")
            )
    return (
        {key: float(np.mean(values)) for key, values in grouped.items()},
        {key: float(np.mean(values)) for key, values in external_violations.items()},
    )


def configure_plot() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 7.5,
            "axes.labelsize": 8,
            "axes.titlesize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 6.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def plot_cells(cells: list[dict[str, Any]], pdf: Path, png: Path) -> None:
    configure_plot()
    datasets = list(dict.fromkeys(cell["dataset"] for cell in cells))
    fig, axes = plt.subplots(1, len(datasets), figsize=(7.1, 1.9), sharey=True)
    colors = {"observed": "#0072B2", "predicted": "#D55E00"}
    for axis, dataset in zip(np.atleast_1d(axes), datasets):
        subset = [cell for cell in cells if cell["dataset"] == dataset]
        x = np.asarray([cell["mean_certification_n"] for cell in subset])
        observed = np.asarray([cell["observed_abstention"] for cell in subset])
        predicted = np.asarray([cell["predicted_abstention"] for cell in subset])
        lower = np.asarray([cell["simultaneous_band_lower"] for cell in subset])
        upper = np.asarray([cell["simultaneous_band_upper"] for cell in subset])
        axis.fill_between(x, lower, upper, color=colors["predicted"], alpha=0.18, linewidth=0)
        axis.plot(x, predicted, color=colors["predicted"], linestyle="--", linewidth=1.3)
        axis.plot(x, observed, color=colors["observed"], marker="o", markersize=3, linewidth=1.3)
        axis.set_xscale("log")
        axis.set_ylim(-0.03, 1.03)
        axis.set_title(dataset.replace("-WILDS", ""), pad=3)
        axis.set_xlabel("Certification examples")
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.5)
    axes = np.atleast_1d(axes)
    axes[0].set_ylabel("Edit-level abstention rate")
    axes[0].plot([], [], color=colors["observed"], marker="o", label="Observed")
    axes[0].plot([], [], color=colors["predicted"], linestyle="--", label="Plug-in prediction")
    axes[0].legend(frameon=False, loc="lower left")
    fig.tight_layout(w_pad=0.7)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(pdf, bbox_inches="tight")
    fig.savefig(png, dpi=300, bbox_inches="tight")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--deployment-rows", type=Path, default=DEFAULT_DEPLOYMENT_ROWS)
    parser.add_argument("--synthetic-audit", type=Path, default=DEFAULT_SYNTHETIC_AUDIT)
    parser.add_argument("--cells", type=Path, default=DEFAULT_CELLS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    parser.add_argument("--replicates", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20270715)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.replicates < 200:
        raise ValueError("at least 200 bootstrap replicates are required")
    prereg = load_json(args.prereg)
    prereg_hash = sha256(args.prereg)
    if prereg_hash != args.hash_file.read_text(encoding="utf-8").split()[0]:
        raise RuntimeError("preregistration hash mismatch")
    synthetic_audit = load_json(args.synthetic_audit)
    observed, external_violations = observed_curves_from_rows(args.deployment_rows)
    study = prereg["real_study"]
    datasets = study["datasets"]
    methods = study["methods"]
    seeds = [int(value) for value in study["seeds"]]
    fractions = [float(value) for value in study["validation_fractions"]]
    target_thresholds = [float(value) for value in study["target_harm_thresholds"]]
    leakage_thresholds = [float(value) for value in study["leakage_thresholds"]]
    gamma = float(study["deployment_gamma"])
    delta = float(study["delta"])
    cells: list[dict[str, Any]] = []
    tracking_count = 0
    analysis_consistency = True

    for dataset_index, (dataset, dataset_config) in enumerate(datasets.items()):
        seed_predictions = np.empty((len(seeds), args.replicates, len(fractions)))
        recomputed_observed = np.empty((len(seeds), len(fractions)))
        certification_sizes = np.empty((len(seeds), len(fractions)), dtype=int)
        for seed_index, seed in enumerate(seeds):
            arrays = load_seed_arrays(dataset, seed, methods, args.receipt_dir)
            denominator = family_size(arrays)
            alpha = delta / denominator
            subsets = nested_stratified_indices(
                arrays["target"],
                arrays["source"],
                arrays["environment"],
                fractions,
                seed=2_027_071_300 + 1009 * seed + sum(map(ord, dataset)),
            )
            for fraction_index, fraction in enumerate(fractions):
                certification_sizes[seed_index, fraction_index] = len(subsets[fraction])
            rng = np.random.default_rng(
                args.seed + 100_003 * dataset_index + 1009 * seed
            )
            if bool(dataset_config.get("force_abstain_for_unsupported_environment")):
                seed_predictions[seed_index, :, :] = 1.0
                recomputed_observed[seed_index, :] = 1.0
                continue
            for fraction_index, fraction in enumerate(fractions):
                target_bounds, leakage_bounds = candidate_bounds(
                    arrays,
                    subsets[fraction],
                    alpha=alpha,
                    gamma=gamma,
                )
                recomputed_observed[seed_index, fraction_index] = (
                    abstention_over_thresholds(
                        target_bounds,
                        leakage_bounds,
                        target_thresholds,
                        leakage_thresholds,
                    )
                )
            for replicate in range(args.replicates):
                bootstrap = bootstrap_prefixes(arrays, fractions, rng)
                for fraction_index, fraction in enumerate(fractions):
                    target_bounds, leakage_bounds = candidate_bounds(
                        arrays,
                        bootstrap[fraction],
                        alpha=alpha,
                        gamma=gamma,
                    )
                    seed_predictions[seed_index, replicate, fraction_index] = (
                        abstention_over_thresholds(
                            target_bounds,
                            leakage_bounds,
                            target_thresholds,
                            leakage_thresholds,
                        )
                    )
        aggregate = seed_predictions.mean(axis=0)
        predicted = aggregate.mean(axis=0)
        max_deviation = np.max(np.abs(aggregate - predicted[None, :]), axis=1)
        simultaneous_radius = float(np.quantile(max_deviation, 0.95, method="higher"))
        dataset_pass = True
        for fraction_index, fraction in enumerate(fractions):
            observed_value = observed[(dataset, fraction)]
            recomputed_value = float(recomputed_observed[:, fraction_index].mean())
            consistent = bool(np.isclose(observed_value, recomputed_value, atol=1e-12))
            analysis_consistency = analysis_consistency and consistent
            lower = max(0.0, float(predicted[fraction_index] - simultaneous_radius))
            upper = min(1.0, float(predicted[fraction_index] + simultaneous_radius))
            in_band = lower <= observed_value <= upper
            dataset_pass = dataset_pass and in_band
            cells.append(
                {
                    "dataset": dataset,
                    "validation_fraction": fraction,
                    "mean_certification_n": float(
                        certification_sizes[:, fraction_index].mean()
                    ),
                    "observed_abstention": observed_value,
                    "recomputed_abstention": recomputed_value,
                    "deployment_analysis_consistent": consistent,
                    "predicted_abstention": float(predicted[fraction_index]),
                    "simultaneous_band_lower": lower,
                    "simultaneous_band_upper": upper,
                    "observed_in_simultaneous_band": in_band,
                }
            )
        tracking_count += int(dataset_pass)

    observed_external_violations_below_delta = all(
        rate <= delta for rate in external_violations.values()
    ) and set(external_violations) == {
        (dataset, seed) for dataset in datasets for seed in seeds
    }
    plot_cells(cells, args.pdf, args.png)
    figure_verified = args.pdf.is_file() and args.png.is_file()
    report = {
        "name": "VERA real-data abstention learning-curve diagnostic",
        "passed": (
            tracking_count >= 4
            and observed_external_violations_below_delta
            and synthetic_audit.get("passed") is True
            and figure_verified
            and analysis_consistency
        ),
        "prereg_sha256": prereg_hash,
        "diagnostic_not_independent_validation": True,
        "prediction_method": (
            "Full-certification stratified nonparametric plug-in bootstrap; each resampled "
            "example is shared jointly across candidates and attackers."
        ),
        "replicates": args.replicates,
        "datasets": list(datasets),
        "dataset_count": len(datasets),
        "validation_fractions": fractions,
        "datasets_tracking_predicted_band": tracking_count,
        "measured_external_violation_below_delta_every_dataset_seed": (
            observed_external_violations_below_delta
        ),
        "false_acceptance_below_delta_every_dataset_seed": (
            observed_external_violations_below_delta
        ),
        "dataset_seed_measured_external_violation_rates": {
            f"{dataset}|seed={seed}": rate
            for (dataset, seed), rate in sorted(external_violations.items())
        },
        "external_violation_rate_caution": (
            "Rates average correlated threshold/fraction configurations within a seed. "
            "They are descriptive external checks, not repeated-sampling estimates of "
            "the theorem's false-acceptance probability."
        ),
        "delta": delta,
        "synthetic_overlay_verified": synthetic_audit.get("passed") is True,
        "real_overlay_figure_verified": figure_verified,
        "deployment_analysis_consistent": analysis_consistency,
        "figure_pdf": str(args.pdf),
        "figure_png": str(args.png),
        "cells": cells,
    }
    args.cells.parent.mkdir(parents=True, exist_ok=True)
    with args.cells.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(cells[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(cells)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "datasets_tracking_predicted_band": tracking_count,
                "all_dataset_seed_external_violation_rates_below_delta": (
                    observed_external_violations_below_delta
                ),
                "report": str(args.report),
            },
            indent=2,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
