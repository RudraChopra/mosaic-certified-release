"""Build the reviewer-facing VERA result figure from frozen receipt products."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import beta


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STRESS_REPORT = ROOT / "artifacts" / "vera_independent_stress_report.json"
DEFAULT_RULE_ROWS = ROOT / "artifacts" / "vera_confirmatory_balanced_rule_rows.csv"
DEFAULT_CANDIDATE_ROWS = ROOT / "artifacts" / "vera_confirmatory_balanced_candidate_rows.csv"
DEFAULT_PDF = ROOT / "maintrack" / "figures" / "vera_killer_result.pdf"
DEFAULT_PNG = ROOT / "maintrack" / "figures" / "vera_killer_result.png"
DEFAULT_AUDIT = ROOT / "artifacts" / "vera_killer_figure_audit.json"

ORANGE = "#D55E00"
GOLD = "#E69F00"
BLUE = "#0072B2"
GREEN = "#009E73"
GRAY = "#666666"
PINK = "#CC79A7"
SUPPORTED = {"Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def cp_interval(successes: int, trials: int, alpha: float = 0.05) -> tuple[float, float]:
    if trials <= 0:
        return 0.0, 1.0
    lower = 0.0 if successes == 0 else float(beta.ppf(alpha / 2, successes, trials - successes + 1))
    upper = 1.0 if successes == trials else float(beta.ppf(1 - alpha / 2, successes + 1, trials - successes))
    return lower, upper


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7.2,
            "axes.labelsize": 7.5,
            "axes.titlesize": 8.4,
            "axes.titleweight": "bold",
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 6.8,
            "legend.fontsize": 6.2,
            "axes.linewidth": 0.7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def add_panel_label(axis: plt.Axes, label: str) -> None:
    axis.text(-0.17, 1.08, label, transform=axis.transAxes, fontsize=10, fontweight="bold", va="top")


def retention_curve(rows: list[dict[str, str]]) -> list[dict[str, float | int]]:
    output: list[dict[str, float | int]] = []
    for fraction in (0.05, 0.10, 0.25, 0.50, 1.00):
        tier = "primary" if fraction == 1.0 else "learning_curve"
        selected = [
            row
            for row in rows
            if row["analysis_tier"] == tier
            and row["dataset"] in SUPPORTED
            and abs(float(row["validation_fraction"]) - fraction) < 1e-12
        ]
        by_key = {(row["config_id"], row["rule"]): row for row in selected}
        configs = sorted({row["config_id"] for row in selected})
        opportunities = 0
        retained = 0
        for config in configs:
            oracle = by_key[(config, "external_balanced_oracle")]
            vera = by_key[(config, "vera_balanced_iut")]
            if as_bool(oracle["deployed"]):
                opportunities += 1
                retained += int(
                    as_bool(vera["deployed"])
                    and vera["external_contract_satisfied"] == "True"
                )
        if opportunities == 0:
            raise RuntimeError(f"no oracle opportunities at fraction {fraction}")
        lower, upper = cp_interval(retained, opportunities)
        output.append(
            {
                "fraction": fraction,
                "retained": retained,
                "opportunities": opportunities,
                "rate": retained / opportunities,
                "lower": lower,
                "upper": upper,
            }
        )
    return output


def paired_harm_curve(gamma: np.ndarray, p_positive: float, p_negative: float) -> np.ndarray:
    a = gamma * p_positive
    d = gamma * (1.0 - p_negative)
    return np.where(a >= 1.0, 1.0, np.where(d >= 1.0, a, a + d - 1.0))


def choose_real_envelope(rows: list[dict[str, str]]) -> dict[str, str]:
    eligible = [
        row
        for row in rows
        if row["analysis_tier"] == "primary"
        and row["dataset"] in SUPPORTED
        and float(row["envelope_radius"]) > 1.0
    ]
    if not eligible:
        raise RuntimeError("no positive real-data envelope is available")
    return max(
        eligible,
        key=lambda row: (
            float(row["envelope_radius"]),
            row["dataset"],
            int(row["seed"]),
            row["candidate"],
        ),
    )


def make_figure(
    report: dict[str, Any],
    rule_rows: list[dict[str, str]],
    candidate_rows: list[dict[str, str]],
    pdf_path: Path,
    png_path: Path,
) -> dict[str, Any]:
    configure_style()
    figure, axes = plt.subplots(1, 3, figsize=(7.15, 2.35))

    rules = [
        ("always_deploy_balanced", "Always", ORANGE, "//"),
        ("point_selection_balanced", "Point", GOLD, "xx"),
        ("vera_balanced_iut", "IID LTT", BLUE, ""),
        ("vera_balanced_envelope", "Envelope", GREEN, ".."),
        ("external_balanced_oracle", "Oracle", GRAY, ""),
    ]
    x = np.arange(len(rules), dtype=float)
    rates: list[float] = []
    errors: list[tuple[float, float]] = []
    counts: list[tuple[int, int]] = []
    for key, _, _, _ in rules:
        summary = report["supported_summaries"][key]
        rate = float(summary["measured_external_violation_rate"])
        lower, upper = map(float, summary["measured_external_violation_cp95"])
        rates.append(rate)
        errors.append((rate - lower, upper - rate))
        counts.append(
            (
                int(summary["measured_external_violation_count"]),
                int(summary["estimable_configuration_count"]),
            )
        )
    bars = axes[0].bar(
        x,
        rates,
        width=0.68,
        color=[item[2] for item in rules],
        edgecolor="black",
        linewidth=0.5,
    )
    for bar, item in zip(bars, rules):
        bar.set_hatch(item[3])
    axes[0].errorbar(x, rates, yerr=np.asarray(errors).T, fmt="none", ecolor="black", elinewidth=0.7, capsize=2)
    for index, (violations, total) in enumerate(counts):
        axes[0].text(index, rates[index] + errors[index][1] + 0.025, f"{violations}/{total}", ha="center", va="bottom", fontsize=6.2)
    axes[0].axhline(float(report["delta"]), color="black", linestyle=":", linewidth=0.8, label=r"$\delta=0.05$")
    axes[0].set_xticks(x, [item[1] for item in rules], rotation=28, ha="right")
    axes[0].set_ylabel("External violation rate")
    axes[0].set_title("Unsafe deployment")
    axes[0].set_ylim(0, 0.72)
    axes[0].legend(frameon=False, loc="upper right")

    learning = retention_curve(rule_rows)
    fractions = np.asarray([float(item["fraction"]) for item in learning]) * 100
    retention = np.asarray([float(item["rate"]) for item in learning])
    low = np.asarray([float(item["lower"]) for item in learning])
    high = np.asarray([float(item["upper"]) for item in learning])
    axes[1].plot(fractions, retention, color=GREEN, marker="o", linewidth=1.5, markersize=3.5)
    axes[1].fill_between(fractions, low, high, color=GREEN, alpha=0.18, linewidth=0)
    for fraction, item in zip(fractions, learning):
        axes[1].text(fraction, float(item["upper"]) + 0.025, f"{item['retained']}/{item['opportunities']}", ha="center", va="bottom", fontsize=6.0)
    axes[1].set_xscale("log")
    axes[1].set_xticks(fractions, ["5", "10", "25", "50", "100"])
    axes[1].set_xlabel("Certification data (%)")
    axes[1].set_ylabel("Safe opportunity retention")
    axes[1].set_title("More data increases retention")
    axes[1].set_ylim(0, max(0.46, float(high.max()) + 0.08))

    example = choose_real_envelope(candidate_rows)
    parameters = json.loads(example["simultaneous_curve_parameters"])
    radius = float(example["envelope_radius"])
    gamma = np.linspace(1.0, min(1.16, max(1.12, radius + 0.035)), 180)
    line_specs = {
        "target::environment=0": (BLUE, "Target env. 0"),
        "target::environment=1": (GREEN, "Target env. 1"),
        "balanced_leakage::linear": (ORANGE, "Linear"),
        "balanced_leakage::rbf": (GOLD, "RBF"),
        "balanced_leakage::forest": (PINK, "Forest"),
        "balanced_leakage::mlp": (GRAY, "MLP"),
    }
    for key, (color, label) in line_specs.items():
        values = parameters[key]
        threshold = float(values["threshold"])
        if key.startswith("target::"):
            curve = paired_harm_curve(
                gamma,
                float(values["positive_probability_upper"]),
                float(values["negative_probability_lower"]),
            )
        else:
            curve = 0.5 * np.minimum(1.0, gamma * float(values["class_0_probability_upper"]))
            curve += 0.5 * np.minimum(1.0, gamma * float(values["class_1_probability_upper"]))
        axes[2].plot(gamma, curve / threshold, color=color, linewidth=1.25, label=label)
    axes[2].axhline(1.0, color="black", linewidth=0.8)
    axes[2].axvline(radius, color="black", linestyle="--", linewidth=0.8)
    axes[2].text(radius - 0.002, 0.72, rf"$\widehat{{\Gamma}}={radius:.3f}$", rotation=90, ha="right", va="center", fontsize=6.2)
    axes[2].set_xlabel(r"Declared reweighting budget $\Gamma$")
    axes[2].set_ylabel("Upper bound / contract")
    axes[2].set_title("Real shift envelope")
    axes[2].set_xlim(float(gamma.min()), float(gamma.max()))
    axes[2].set_ylim(0.45, 1.18)
    axes[2].legend(frameon=False, ncol=2, loc="upper left", handlelength=1.5, columnspacing=0.7)

    for label, axis in zip("ABC", axes):
        add_panel_label(axis, label)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.65)
        axis.set_axisbelow(True)
    figure.tight_layout(w_pad=1.0)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    png_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    figure.savefig(png_path, dpi=400, bbox_inches="tight", facecolor="white")
    plt.close(figure)
    return {
        "dataset": example["dataset"],
        "seed": int(example["seed"]),
        "candidate": example["candidate"],
        "target_threshold": float(example["target_threshold"]),
        "leakage_threshold": float(example["leakage_threshold"]),
        "certified_radius": radius,
        "limiting_contracts": json.loads(example["envelope_limiting_contracts"]),
        "learning_curve": learning,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stress-report", type=Path, default=DEFAULT_STRESS_REPORT)
    parser.add_argument("--rule-rows", type=Path, default=DEFAULT_RULE_ROWS)
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATE_ROWS)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    args = parser.parse_args()

    report = load_json(args.stress_report)
    if report.get("confirmatory") is not True:
        raise RuntimeError("independent stress report is not confirmatory")
    example = make_figure(
        report,
        load_csv(args.rule_rows),
        load_csv(args.candidate_rows),
        args.pdf,
        args.png,
    )
    audit = {
        "name": "VERA killer result figure audit",
        "passed": True,
        "stress_report_sha256": sha256(args.stress_report),
        "rule_rows_sha256": sha256(args.rule_rows),
        "candidate_rows_sha256": sha256(args.candidate_rows),
        "figure_pdf_sha256": sha256(args.pdf),
        "figure_png_sha256": sha256(args.png),
        "supported_decision_count": int(
            report["supported_summaries"]["vera_balanced_iut"]["configuration_count"]
        ),
        "real_envelope_example": example,
    }
    args.audit.parent.mkdir(parents=True, exist_ok=True)
    args.audit.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
