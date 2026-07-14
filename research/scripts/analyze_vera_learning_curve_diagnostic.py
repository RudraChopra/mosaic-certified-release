"""Run the locked full-certification plug-in abstention diagnostic."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import beta

from analyze_vera_attacker_ablation import load_candidates


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PREREG = ROOT / "prereg_confirmatory_balanced.json"
DEFAULT_DIAGNOSTIC = ROOT / "prereg_real_learning_curve_diagnostic.json"
DEFAULT_HASH = ROOT / "prereg_real_learning_curve_diagnostic.sha256"
DEFAULT_AUDIT = ROOT / "artifacts" / "confirmatory_balanced_receipt_audit.json"
DEFAULT_RECEIPTS = ROOT / "artifacts" / "confirmatory_balanced_receipts"
DEFAULT_ROWS = ROOT / "artifacts" / "vera_confirmatory_balanced_rule_rows.csv"
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_learning_curve_diagnostic.json"
DEFAULT_PDF = ROOT / "maintrack" / "figures" / "vera_real_learning_curve.pdf"
DEFAULT_PNG = ROOT / "maintrack" / "figures" / "vera_real_learning_curve.png"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def cp_upper(successes: np.ndarray, trials: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    output = np.ones(values.shape, dtype=np.float64)
    interior = values < trials
    output[interior] = beta.ppf(
        1.0 - alpha, values[interior] + 1, trials - values[interior]
    )
    return output


def cp_lower(successes: np.ndarray, trials: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    output = np.zeros(values.shape, dtype=np.float64)
    interior = values > 0
    output[interior] = beta.ppf(
        alpha, values[interior], trials - values[interior] + 1
    )
    return output


def as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def observed_curves(
    path: Path, datasets: list[str], fractions: list[float]
) -> dict[str, dict[float, float]]:
    grouped: dict[tuple[str, float], list[float]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["rule"] != "vera_balanced_iut":
                continue
            if not np.isclose(float(row["gamma"]), 1.0):
                continue
            grouped[(row["dataset"], float(row["validation_fraction"]))].append(
                float(not as_bool(row["deployed"]))
            )
    output: dict[str, dict[float, float]] = {}
    for dataset in datasets:
        output[dataset] = {}
        for fraction in fractions:
            values = grouped[(dataset, fraction)]
            if len(values) != 72:
                raise RuntimeError(
                    f"observed curve needs 72 rows for {dataset}/{fraction:g}"
                )
            output[dataset][fraction] = float(np.mean(values))
    return output


def strata_indices(
    target: np.ndarray, source: np.ndarray, environment: np.ndarray
) -> list[np.ndarray]:
    keys = sorted(
        set(zip(map(int, target), map(int, source), map(int, environment)))
    )
    return [
        np.flatnonzero(
            (target == target_value)
            & (source == source_value)
            & (environment == environment_value)
        )
        for target_value, source_value, environment_value in keys
    ]


def fraction_indices(
    sequences: list[np.ndarray], fraction: float
) -> np.ndarray:
    selected: list[np.ndarray] = []
    for sequence in sequences:
        take = (
            len(sequence)
            if fraction >= 1.0
            else max(1, int(np.floor(fraction * len(sequence))))
        )
        selected.append(sequence[:take])
    return np.concatenate(selected)


def candidate_bounds(
    target_harm: np.ndarray,
    leakage_correct: np.ndarray,
    source: np.ndarray,
    environment: np.ndarray,
    indices: np.ndarray,
    candidate_alpha: float,
) -> tuple[np.ndarray, np.ndarray]:
    candidate_count = target_harm.shape[0]
    max_target = np.full(candidate_count, -np.inf, dtype=np.float64)
    selected_environment = environment[indices]
    for group in sorted(map(int, np.unique(environment))):
        group_indices = indices[selected_environment == group]
        values = target_harm[:, group_indices]
        positives = np.sum(values == 1, axis=1)
        negatives = np.sum(values == -1, axis=1)
        n_group = values.shape[1]
        positive_upper = cp_upper(positives, n_group, candidate_alpha / 2.0)
        negative_lower = cp_lower(negatives, n_group, candidate_alpha / 2.0)
        positive_upper = np.minimum(positive_upper, 1.0 - negative_lower)
        max_target = np.maximum(max_target, positive_upper - negative_lower)

    selected_source = source[indices]
    class_bounds: list[np.ndarray] = []
    for source_class in (0, 1):
        class_indices = indices[selected_source == source_class]
        values = leakage_correct[:, :, class_indices]
        successes = np.sum(values == 1, axis=2)
        class_bounds.append(
            cp_upper(successes, values.shape[2], candidate_alpha / 2.0)
        )
    balanced = 0.5 * (class_bounds[0] + class_bounds[1])
    return max_target, np.max(balanced, axis=1)


def load_aligned_arrays(
    receipt_dir: Path,
    study: dict[str, Any],
    dataset: str,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    candidates, labels = load_candidates(receipt_dir, study, dataset, seed)
    if len(candidates) != 12:
        raise RuntimeError(f"expected 12 candidates for {dataset}/seed-{seed}")
    attacker_names = sorted(
        name.removeprefix("leakage_correct_certification__")
        for name in candidates[0]["arrays"]
        if name.startswith("leakage_correct_certification__")
    )
    if len(attacker_names) != 4:
        raise RuntimeError(f"expected four attackers for {dataset}/seed-{seed}")
    target_harm = np.stack(
        [candidate["arrays"]["target_harm_certification"] for candidate in candidates]
    )
    leakage_correct = np.stack(
        [
            np.stack(
                [
                    candidate["arrays"][
                        f"leakage_correct_certification__{attacker}"
                    ]
                    for attacker in attacker_names
                ]
            )
            for candidate in candidates
        ]
    )
    return target_harm, leakage_correct, labels


def predict_dataset(
    receipt_dir: Path,
    study: dict[str, Any],
    dataset: str,
    seeds: list[int],
    fractions: list[float],
    target_thresholds: np.ndarray,
    leakage_thresholds: np.ndarray,
    delta: float,
    replicates: int,
    bootstrap_seed: int,
    force_abstain: bool,
) -> np.ndarray:
    if force_abstain:
        return np.ones((replicates, len(fractions)), dtype=np.float64)
    abstentions = np.zeros((replicates, len(fractions)), dtype=np.float64)
    candidate_alpha = delta / 12.0
    denominator = len(seeds) * len(target_thresholds) * len(leakage_thresholds)
    for seed in seeds:
        target_harm, leakage_correct, labels = load_aligned_arrays(
            receipt_dir, study, dataset, seed
        )
        target, source, environment = labels
        strata = strata_indices(target, source, environment)
        rng = np.random.default_rng(
            bootstrap_seed + 1009 * seed + 100_003 * sum(map(ord, dataset))
        )
        for replicate in range(replicates):
            sequences = [
                rng.choice(indices, size=len(indices), replace=True)
                for indices in strata
            ]
            for fraction_index, fraction in enumerate(fractions):
                indices = fraction_indices(sequences, fraction)
                target_bound, leakage_bound = candidate_bounds(
                    target_harm,
                    leakage_correct,
                    source,
                    environment,
                    indices,
                    candidate_alpha,
                )
                eligible = (
                    target_bound[:, None, None]
                    <= target_thresholds[None, :, None]
                ) & (
                    leakage_bound[:, None, None]
                    <= leakage_thresholds[None, None, :]
                )
                deployed = np.any(eligible, axis=0)
                abstentions[replicate, fraction_index] += float(
                    np.count_nonzero(~deployed)
                )
    return abstentions / denominator


def configure_plot() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 7.5,
            "axes.labelsize": 8,
            "axes.titlesize": 8.5,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def build_figure(
    records: dict[str, Any], fractions: list[float], pdf: Path, png: Path
) -> None:
    configure_plot()
    datasets = list(records)
    fig, axes = plt.subplots(2, 3, figsize=(7.1, 4.0), sharex=True, sharey=True)
    axes_flat = axes.ravel()
    x = 100.0 * np.asarray(fractions)
    for axis, dataset in zip(axes_flat, datasets):
        record = records[dataset]
        predicted = np.asarray(record["predicted_mean"])
        lower = np.asarray(record["pointwise_95_lower"])
        upper = np.asarray(record["pointwise_95_upper"])
        observed = np.asarray(record["observed_abstention"])
        axis.fill_between(x, lower, upper, color="#9ECAE1", alpha=0.55, linewidth=0)
        axis.plot(x, predicted, color="#0072B2", linewidth=1.5, label="Plug-in mean")
        axis.plot(
            x,
            observed,
            color="#D55E00",
            marker="o",
            markersize=3.8,
            linewidth=1.1,
            label="Observed",
        )
        axis.set_title(dataset.replace("-WILDS", ""), loc="left", fontweight="bold")
        axis.set_ylim(-0.03, 1.03)
        axis.set_xscale("log")
        axis.set_xticks(x)
        axis.set_xticklabels(["5", "10", "25", "50", "100"])
        axis.grid(axis="y", color="#DDDDDD", linewidth=0.5)
    axes_flat[-1].axis("off")
    for axis in axes[:, 0]:
        axis.set_ylabel("Abstention rate")
    for axis in axes[-1, :2]:
        axis.set_xlabel("Certification fraction (%)")
    axes_flat[0].legend(frameon=False, loc="best")
    fig.tight_layout(w_pad=0.8, h_pad=0.9)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--diagnostic-prereg", type=Path, default=DEFAULT_DIAGNOSTIC)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--receipt-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--rule-rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    diagnostic_hash = sha256(args.diagnostic_prereg)
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    if diagnostic_hash != expected_hash:
        raise RuntimeError("learning-curve diagnostic hash mismatch")
    relative = args.diagnostic_prereg.relative_to(REPOSITORY).as_posix()
    committed = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    ).stdout
    if hashlib.sha256(committed).hexdigest() != diagnostic_hash:
        raise RuntimeError("learning-curve diagnostic is not committed at HEAD")

    prereg = load_json(args.prereg)
    diagnostic = load_json(args.diagnostic_prereg)
    if diagnostic["parent_preregistration_sha256"] != sha256(args.prereg):
        raise RuntimeError("diagnostic parent preregistration mismatch")
    receipt_audit = load_json(args.receipt_audit)
    if receipt_audit.get("passed") is not True:
        raise RuntimeError("confirmatory receipt audit has not passed")

    config = diagnostic["inputs"]
    bootstrap = diagnostic["bootstrap"]
    datasets = list(config["datasets"])
    seeds = list(map(int, config["confirmatory_seeds"]))
    fractions = list(map(float, config["validation_fractions"]))
    target_thresholds = np.asarray(
        config["target_harm_thresholds"], dtype=np.float64
    )
    leakage_thresholds = np.asarray(
        config["balanced_leakage_thresholds"], dtype=np.float64
    )
    replicates = int(bootstrap["replicates"])
    observed = observed_curves(args.rule_rows, datasets, fractions)
    records: dict[str, Any] = {}
    for dataset in datasets:
        force_abstain = bool(
            prereg["real_study"]["datasets"][dataset].get(
                "force_abstain_for_unsupported_environment"
            )
        )
        draws = predict_dataset(
            args.receipt_dir,
            prereg["real_study"],
            dataset,
            seeds,
            fractions,
            target_thresholds,
            leakage_thresholds,
            float(config["delta"]),
            replicates,
            int(bootstrap["seed"]),
            force_abstain,
        )
        lower = np.quantile(draws, 0.025, axis=0)
        upper = np.quantile(draws, 0.975, axis=0)
        observed_values = np.asarray(
            [observed[dataset][fraction] for fraction in fractions]
        )
        inside = (observed_values >= lower - 1e-12) & (
            observed_values <= upper + 1e-12
        )
        records[dataset] = {
            "observed_abstention": observed_values.tolist(),
            "predicted_mean": np.mean(draws, axis=0).tolist(),
            "pointwise_95_lower": lower.tolist(),
            "pointwise_95_upper": upper.tolist(),
            "inside_pointwise_band": inside.tolist(),
            "all_five_inside": bool(np.all(inside)),
            "support_mismatch_forced_abstention": force_abstain,
        }

    datasets_all_inside = sum(
        bool(record["all_five_inside"]) for record in records.values()
    )
    build_figure(records, fractions, args.pdf, args.png)
    report = {
        "name": "VERA real-data full-certification plug-in diagnostic",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "confirmatory": False,
        "descriptive_calibration_only": True,
        "diagnostic_preregistration_sha256": diagnostic_hash,
        "receipt_audit_sha256": sha256(args.receipt_audit),
        "rule_rows_sha256": sha256(args.rule_rows),
        "bootstrap_replicates": replicates,
        "datasets_with_all_five_points_inside": datasets_all_inside,
        "four_of_five_diagnostic_target_met": datasets_all_inside >= 4,
        "records": records,
        "figure_pdf_sha256": sha256(args.pdf),
        "figure_png_sha256": sha256(args.png),
        "claim_boundary": diagnostic["reporting"]["claim_boundary"],
    }
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "datasets_with_all_five_points_inside": datasets_all_inside,
                "target_met": datasets_all_inside >= 4,
                "output": str(args.output),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
