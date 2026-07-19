#!/usr/bin/env python3
"""Render the audited, hash-locked MOSAIC confirmation figure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[2]
ARTIFACTS = REPOSITORY / "research" / "artifacts"
OUTPUT = ROOT / "figures" / "figure2_mosaic_confirmation"
REPORT = ARTIFACTS / "mosaic_synthetic_confirmation_v1.json"
AUDIT = ARTIFACTS / "mosaic_synthetic_confirmation_audit_v1.json"
ALIGNMENT = ARTIFACTS / "mosaic_synthetic_theory_alignment_audit_v1.json"
SUMMARY = ARTIFACTS / "mosaic_synthetic_claim_summary_v1.json"

GREEN = "#009E73"
BLUE = "#0072B2"
SKY = "#56B4E9"
ORANGE = "#E69F00"
VERMILION = "#D55E00"
PURPLE = "#CC79A7"
INK = "#202124"
MUTED = "#667085"
GRID = "#D9DEE7"
LIGHT = "#F5F7FA"

DISPLAY_NAMES = {
    "shift_unaware_mosaic": "Shift-unaware",
    "always_deploy_plugin": "Always deploy",
    "plugin_continuum": "Plug-in",
    "mosaic": "Capacity fallback",
    "heldout_fixed_channel": "Held-out",
    "finite_ltt": "Finite LTT",
    "deterministic_mosaic": "Deterministic",
    "population_oracle": "Oracle",
}
COLORS = {
    "shift_unaware_mosaic": VERMILION,
    "always_deploy_plugin": ORANGE,
    "plugin_continuum": PURPLE,
    "mosaic": GREEN,
    "heldout_fixed_channel": BLUE,
    "finite_ltt": SKY,
    "deterministic_mosaic": MUTED,
    "population_oracle": INK,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def verify_receipts() -> tuple[dict[str, Any], dict[str, Any]]:
    report = load(REPORT)
    audit = load(AUDIT)
    alignment = load(ALIGNMENT)
    summary = load(SUMMARY)
    report_hash = sha256(REPORT)
    if audit.get("pass") is not True or audit.get("report_sha256") != report_hash:
        raise AssertionError("confirmation does not have a matching passing replay")
    if (
        alignment.get("pass") is not True
        or alignment.get("confirmation_sha256") != report_hash
    ):
        raise AssertionError("confirmation lacks a matching theory-alignment audit")
    if (
        summary.get("confirmation_sha256") != report_hash
        or summary.get("confirmation_audit_sha256") != sha256(AUDIT)
        or summary.get("theory_alignment_audit_sha256") != sha256(ALIGNMENT)
    ):
        raise AssertionError("paired summary does not match the audited confirmation")
    return report, alignment


def cell_index(report: dict[str, Any]) -> dict[tuple[str, int, str], dict[str, Any]]:
    return {
        (
            str(cell["scenario"]),
            int(cell["sample_size_per_stratum"]),
            str(cell["method"]),
        ): cell
        for cell in report["cells"]
    }


def rate_panel(
    ax: plt.Axes,
    *,
    cells: dict[tuple[str, int, str], dict[str, Any]],
    scenario: str,
    n: int,
    methods: list[str],
    rate_prefix: str,
    title: str,
    panel: str,
) -> None:
    rows = [cells[(scenario, n, method)] for method in methods]
    values = np.asarray([float(row[f"{rate_prefix}_rate"]) for row in rows])
    lower = np.asarray([float(row[f"{rate_prefix}_cp95_lower"]) for row in rows])
    upper = np.asarray([float(row[f"{rate_prefix}_cp95_upper"]) for row in rows])
    positions = np.arange(len(methods))
    bars = ax.barh(
        positions,
        values,
        color=[COLORS[method] for method in methods],
        height=0.64,
        edgecolor="white",
        linewidth=0.5,
        zorder=2,
    )
    ax.errorbar(
        values,
        positions,
        xerr=np.vstack((values - lower, upper - values)),
        fmt="none",
        ecolor=INK,
        elinewidth=0.75,
        capsize=1.8,
        capthick=0.75,
        zorder=3,
    )
    for bar, value in zip(bars, values):
        x = min(value + 0.025, 0.96)
        ha = "left" if value < 0.92 else "right"
        ax.text(
            x,
            bar.get_y() + bar.get_height() / 2,
            f"{100 * value:.1f}%",
            ha=ha,
            va="center",
            fontsize=6.1,
            color=INK,
            fontweight="bold" if bar.get_facecolor()[:3] == mpl.colors.to_rgb(GREEN) else "normal",
        )
    ax.set_yticks(positions, [DISPLAY_NAMES[method] for method in methods])
    ax.invert_yaxis()
    ax.set_xlim(0.0, 1.04)
    ax.set_xticks([0.0, 0.25, 0.5, 0.75, 1.0], ["0", "25", "50", "75", "100"])
    ax.set_xlabel("Replicates (%)", fontsize=6.5)
    ax.set_title(title, loc="left", fontsize=8.0, fontweight="bold", color=INK, pad=7)
    ax.text(-0.21, 1.055, panel, transform=ax.transAxes, fontsize=8.0, fontweight="bold", color="white", ha="center", va="center", bbox={"boxstyle": "square,pad=0.20", "facecolor": INK, "edgecolor": INK})
    ax.grid(axis="x", color=GRID, linewidth=0.55, zorder=0)
    ax.set_axisbelow(True)


def theory_panel(ax: plt.Axes, alignment: dict[str, Any]) -> None:
    rows = sorted(
        (
            row
            for row in alignment["rows"]
            if row["scenario"] == "retention_and_stochastic_value"
        ),
        key=lambda row: int(row["sample_size_per_stratum"]),
    )
    positions = np.arange(len(rows))
    predicted = np.asarray([float(row["predicted_deployment_rate"]) for row in rows])
    observed = np.asarray([float(row["observed_deployment_rate"]) for row in rows])
    lower = np.asarray([float(row["observed_deployment_cp95_lower"]) for row in rows])
    upper = np.asarray([float(row["observed_deployment_cp95_upper"]) for row in rows])
    ax.plot(
        positions,
        predicted,
        color=ORANGE,
        linewidth=1.6,
        marker="s",
        markersize=4.0,
        label="Pre-registered theory",
        zorder=2,
    )
    ax.errorbar(
        positions,
        observed,
        yerr=np.vstack((observed - lower, upper - observed)),
        color=GREEN,
        linewidth=0,
        marker="o",
        markersize=4.2,
        elinewidth=0.9,
        capsize=2.2,
        label="Observed (95% CI)",
        zorder=3,
    )
    ax.set_xticks(positions, [str(int(row["sample_size_per_stratum"])) for row in rows])
    ax.set_ylim(-0.04, 1.04)
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0], ["0", "25", "50", "75", "100"])
    ax.set_xlabel("Samples per source-label stratum", fontsize=6.5)
    ax.set_ylabel("Fallback deployments (%)", fontsize=6.5)
    ax.set_title("Theory predicts the abstention transition", loc="left", fontsize=8.0, fontweight="bold", color=INK, pad=7)
    ax.text(-0.17, 1.055, "c", transform=ax.transAxes, fontsize=8.0, fontweight="bold", color="white", ha="center", va="center", bbox={"boxstyle": "square,pad=0.20", "facecolor": INK, "edgecolor": INK})
    ax.grid(color=GRID, linewidth=0.55, zorder=0)
    ax.legend(loc="lower right", frameon=False, fontsize=5.9, borderaxespad=0.4, handlelength=1.8)
    ax.text(
        0.03,
        0.92,
        "mean absolute error = 0.20 pp",
        transform=ax.transAxes,
        fontsize=6.2,
        color=MUTED,
        ha="left",
        va="top",
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.0, "alpha": 0.88},
    )


def main() -> None:
    report, alignment = verify_receipts()
    cells = cell_index(report)
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 6.5,
            "axes.edgecolor": MUTED,
            "axes.linewidth": 0.6,
            "axes.labelcolor": INK,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "xtick.major.width": 0.5,
            "ytick.major.width": 0.0,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig = plt.figure(figsize=(7.08, 2.65), facecolor="white")
    grid = fig.add_gridspec(1, 3, width_ratios=[1.04, 1.04, 1.28], wspace=0.46)
    axes = [fig.add_subplot(grid[0, index]) for index in range(3)]
    methods = [
        "shift_unaware_mosaic",
        "always_deploy_plugin",
        "plugin_continuum",
        "mosaic",
        "heldout_fixed_channel",
        "finite_ltt",
        "deterministic_mosaic",
    ]
    rate_panel(
        axes[0],
        cells=cells,
        scenario="hard_safety_boundary",
        n=125,
        methods=methods,
        rate_prefix="false_acceptance",
        title="Naive rules violate the contract",
        panel="a",
    )
    rate_panel(
        axes[1],
        cells=cells,
        scenario="retention_and_stochastic_value",
        n=250,
        methods=methods,
        rate_prefix="safe_deployment",
        title="Certification retains useful releases",
        panel="b",
    )
    theory_panel(axes[2], alignment)
    for ax in axes:
        ax.spines[["top", "right", "left"]].set_visible(False)
    fig.subplots_adjust(left=0.105, right=0.995, top=0.90, bottom=0.18)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUTPUT.with_suffix(".png"), dpi=600, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    main()
