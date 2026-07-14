"""Create the publication figure for VERA's exact balanced theory study."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "artifacts" / "vera_exact_balanced_report.json"
OUTPUT_STEM = ROOT / "maintrack" / "figures" / "vera_exact_theory_match"


def configure_style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 8,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.linewidth": 0.7,
        "lines.linewidth": 1.4,
        "lines.markersize": 4,
        "savefig.bbox": "tight",
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def main() -> None:
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if not report.get("all_cells_pass"):
        raise RuntimeError("refusing to plot a report that did not pass every cell")
    cells = report["cells"]
    deltas = sorted({float(cell["delta"]) for cell in cells})
    gammas = sorted({float(cell["gamma"]) for cell in cells})
    if len(gammas) != 3:
        raise RuntimeError("the balanced figure requires three registered Gamma levels")
    colors = ["#0072B2", "#009E73", "#D55E00"]
    markers = ["o", "s", "^"]
    configure_style()
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(7.0, 4.7),
        constrained_layout=True,
    )
    abstention_axes = [axes[0, 0], axes[0, 1], axes[1, 0]]
    safety_axis = axes[1, 1]
    panel_labels = ("a", "b", "c")
    for gamma, axis, panel in zip(gammas, abstention_axes, panel_labels):
        for delta, color, marker in zip(deltas, colors, markers):
            selected = sorted(
                (
                    cell
                    for cell in cells
                    if float(cell["delta"]) == delta
                    and float(cell["gamma"]) == gamma
                ),
                key=lambda cell: int(cell["n"]),
            )
            sizes = np.asarray([int(cell["n"]) for cell in selected])
            predicted = np.asarray(
                [float(cell["predicted_abstention"]) for cell in selected]
            )
            observed = np.asarray(
                [float(cell["observed_abstention"]) for cell in selected]
            )
            lower = np.asarray(
                [float(cell["prediction_band_lower"]) for cell in selected]
            )
            upper = np.asarray(
                [float(cell["prediction_band_upper"]) for cell in selected]
            )
            axis.fill_between(
                sizes, lower, upper, color=color, alpha=0.14, linewidth=0
            )
            axis.plot(
                sizes,
                predicted,
                color=color,
                label=rf"Exact, $\delta={delta:g}$",
            )
            axis.scatter(
                sizes,
                observed,
                color=color,
                marker=marker,
                facecolors="white",
                linewidths=1.0,
                zorder=3,
                label=rf"Observed, $\delta={delta:g}$",
            )
        axis.set_title(
            rf"{panel}   Abstention at $\Gamma={gamma:g}$",
            loc="left",
            fontweight="bold",
        )
        axis.set_ylabel("Abstention rate")
        axis.set_ylim(-0.025, 1.025)

    gamma_styles = ["-", "--", ":"]
    for gamma, linestyle in zip(gammas, gamma_styles):
        for delta, color, marker in zip(deltas, colors, markers):
            selected = sorted(
                (
                    cell
                    for cell in cells
                    if float(cell["delta"]) == delta
                    and float(cell["gamma"]) == gamma
                ),
                key=lambda cell: int(cell["n"]),
            )
            sizes = np.asarray([int(cell["n"]) for cell in selected])
            normalized_upper = np.asarray(
                [
                    float(cell["false_acceptance_cp95_upper_simultaneous"])
                    / delta
                    for cell in selected
                ]
            )
            safety_axis.plot(
                sizes,
                normalized_upper,
                color=color,
                linestyle=linestyle,
                marker=marker,
                markerfacecolor="white",
                markeredgewidth=0.8,
                label=rf"$\delta={delta:g}$, $\Gamma={gamma:g}$",
            )

    for axis in (*abstention_axes, safety_axis):
        axis.set_xscale("log")
        axis.set_xticks([250, 500, 1000, 2000, 5000, 10000])
        axis.get_xaxis().set_major_formatter(mpl.ticker.ScalarFormatter())
        axis.set_xlabel("Certification examples, $n$")
        axis.grid(axis="y", color="#D9D9D9", linewidth=0.5)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)

    abstention_axes[0].legend(
        frameon=False,
        ncol=2,
        columnspacing=0.8,
        handlelength=1.5,
        loc="lower left",
    )
    safety_axis.axhline(1.0, color="#333333", linewidth=0.8)
    safety_axis.set_title("d   Simultaneous safety bound", loc="left", fontweight="bold")
    safety_axis.set_ylabel(r"False-acceptance upper bound / $\delta$")
    safety_axis.set_ylim(0.0, 1.08)
    safety_axis.text(
        0.98,
        0.08,
        "All 108,000 observed decisions:\nzero false acceptances",
        transform=safety_axis.transAxes,
        ha="right",
        va="bottom",
        fontsize=6.5,
    )

    OUTPUT_STEM.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_STEM.with_suffix(".pdf"))
    figure.savefig(OUTPUT_STEM.with_suffix(".png"), dpi=400)
    plt.close(figure)
    print(OUTPUT_STEM.with_suffix(".pdf"))
    print(OUTPUT_STEM.with_suffix(".png"))


if __name__ == "__main__":
    main()
