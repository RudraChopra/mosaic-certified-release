#!/usr/bin/env python3
"""Render the audited path-to-deployment evidence figure."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ARTIFACTS = ROOT / "research/artifacts"
OUTPUT = HERE / "figures/figure6_mosaic_path9_evidence"

PROXY = ARTIFACTS / "mosaic_real_proxy_mass_confirmation_v1.json"
PROXY_AUDIT = (
    ARTIFACTS / "mosaic_real_proxy_mass_confirmation_audit_v1.json"
)
LOCAL_DP = ARTIFACTS / "mosaic_local_dp_baseline_v1.json"
LOCAL_DP_AUDIT = ARTIFACTS / "mosaic_local_dp_baseline_audit_v1.json"
ACS = ARTIFACTS / "mosaic_acs_scalar_confirmation_v1.json"
ACS_AUDIT = ARTIFACTS / "mosaic_acs_scalar_confirmation_audit_v1.json"

GREEN = "#009E73"
BLUE = "#0072B2"
SKY = "#56B4E9"
ORANGE = "#E69F00"
VERMILION = "#D55E00"
INK = "#202124"
MUTED = "#667085"
GRID = "#D9DEE7"


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def verify() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    proxy = load(PROXY)
    local_dp = load(LOCAL_DP)
    acs = load(ACS)
    audits = [
        load(PROXY_AUDIT),
        load(LOCAL_DP_AUDIT),
        load(ACS_AUDIT),
    ]
    if not all(
        audit.get("pass") is True or audit.get("passed") is True
        for audit in audits
    ):
        raise RuntimeError("path-to-deployment figure requires passing audits")
    if not proxy["passed"] or len(local_dp["rows"]) != 35:
        raise RuntimeError("path-to-deployment source reports are incomplete")
    if acs["summary"]["registered_interfaces"] != 2:
        raise RuntimeError("ACS scalar confirmation is incomplete")
    return proxy, local_dp, acs


def style_axis(ax: plt.Axes) -> None:
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(MUTED)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(width=0.5, colors=MUTED, labelcolor=INK)
    ax.grid(axis="y", color=GRID, linewidth=0.55, zorder=0)
    ax.set_axisbelow(True)


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.16,
        1.06,
        label,
        transform=ax.transAxes,
        fontsize=8.2,
        fontweight="bold",
        color="white",
        ha="center",
        va="center",
        bbox={
            "boxstyle": "square,pad=0.20",
            "facecolor": INK,
            "edgecolor": INK,
        },
    )


def proxy_panel(ax: plt.Axes, report: dict[str, Any]) -> None:
    rows = report["calibration_curve"]
    x = np.asarray([int(row["calibration_rows"]) for row in rows])
    radius = np.asarray(
        [float(row["maximum_conditional_l1_radius"]) for row in rows]
    )
    deployed = np.asarray([row["decision"] == "deploy" for row in rows])
    ax.plot(
        x,
        radius,
        color=BLUE,
        linewidth=1.5,
        marker="o",
        markersize=4.5,
        zorder=2,
    )
    ax.scatter(
        x[~deployed],
        radius[~deployed],
        color=VERMILION,
        marker="x",
        s=30,
        linewidth=1.3,
        label="Abstain",
        zorder=3,
    )
    ax.scatter(
        x[deployed],
        radius[deployed],
        color=GREEN,
        marker="o",
        s=28,
        edgecolor="white",
        linewidth=0.6,
        label="Release",
        zorder=3,
    )
    ax.axvline(58_700, color=GREEN, linestyle="--", linewidth=0.8)
    ax.text(
        58_700,
        0.565,
        "first release",
        fontsize=5.9,
        color=GREEN,
        ha="center",
        va="bottom",
    )
    ax.set_ylim(0.34, 0.59)
    ax.set_xticks(x, ["19.6k", "39.1k", "58.7k", "78.3k"])
    ax.set_xlabel("True-source calibration rows")
    ax.set_ylabel("Max conditional $\\ell_1$ radius")
    ax.set_title(
        "Proxy support unlocks release",
        loc="left",
        fontsize=7.7,
        fontweight="bold",
        color=INK,
        pad=7,
    )
    ax.legend(
        frameon=False,
        fontsize=5.8,
        loc="upper right",
        handletextpad=0.4,
    )
    panel_label(ax, "a")
    style_axis(ax)


def local_dp_panel(ax: plt.Axes, report: dict[str, Any]) -> None:
    mosaic = np.asarray(
        [
            float(row["mosaic_certified_worst_conditional_error_upper"])
            for row in report["rows"]
        ]
    )
    local_dp = np.asarray(
        [
            float(row["local_dp"]["worst_conditional_error_upper"])
            for row in report["rows"]
        ]
    )
    ax.scatter(
        mosaic,
        local_dp,
        s=18,
        color=BLUE,
        alpha=0.80,
        edgecolor="white",
        linewidth=0.4,
        zorder=3,
    )
    limits = (0.22, 0.47)
    ax.plot(limits, limits, color=MUTED, linestyle=":", linewidth=0.8)
    ax.axhline(0.40, color=VERMILION, linestyle="--", linewidth=0.9)
    ax.axvline(0.40, color=GREEN, linestyle="--", linewidth=0.9)
    ax.text(
        0.225,
        0.405,
        "utility contract",
        fontsize=5.9,
        color=VERMILION,
        ha="left",
        va="bottom",
    )
    ax.text(
        0.445,
        0.245,
        "35 / 35",
        fontsize=6.5,
        fontweight="bold",
        color=GREEN,
        ha="right",
    )
    ax.set_xlim(limits)
    ax.set_ylim(limits)
    ax.set_xlabel("MOSAIC certified error")
    ax.set_ylabel("Matched local-DP certified error")
    ax.set_title(
        "Local DP misses every utility contract",
        loc="left",
        fontsize=7.7,
        fontweight="bold",
        color=INK,
        pad=7,
    )
    panel_label(ax, "b")
    style_axis(ax)


def acs_panel(ax: plt.Axes, report: dict[str, Any]) -> None:
    rows = report["rows"]
    x = np.arange(len(rows))
    empirical = np.asarray(
        [float(row["worst_conditional_error_empirical"]) for row in rows]
    )
    lower = np.asarray(
        [
            float(row["worst_conditional_error_familywise_lower"])
            for row in rows
        ]
    )
    colors = [
        GREEN if row["utility_contract_violation_confirmed"] else ORANGE
        for row in rows
    ]
    ax.bar(
        x,
        empirical,
        color=colors,
        width=0.58,
        edgecolor="white",
        linewidth=0.6,
        zorder=2,
    )
    ax.errorbar(
        x,
        empirical,
        yerr=np.vstack((empirical - lower, np.zeros(len(rows)))),
        fmt="none",
        ecolor=INK,
        elinewidth=0.9,
        capsize=3,
        capthick=0.9,
        zorder=3,
    )
    ax.axhline(0.40, color=VERMILION, linestyle="--", linewidth=0.9)
    for index, (value, bound) in enumerate(zip(empirical, lower)):
        ax.text(
            index,
            value + 0.003,
            f"{value:.3f}",
            ha="center",
            va="bottom",
            fontsize=6.3,
            fontweight="bold",
            color=INK,
        )
        ax.text(
            index,
            bound - 0.004,
            f"LB {bound:.3f}",
            ha="center",
            va="top",
            fontsize=5.7,
            color=MUTED,
        )
    ax.set_ylim(0.36, 0.445)
    ax.set_xticks(x, ["TaCo", "R-LACE"])
    ax.set_ylabel("2023 worst-stratum error")
    ax.set_title(
        "Frozen direct releases fail in 2023",
        loc="left",
        fontsize=7.7,
        fontweight="bold",
        color=INK,
        pad=7,
    )
    ax.text(
        1.46,
        0.402,
        "$\\tau_U=.40$",
        fontsize=5.9,
        color=VERMILION,
        ha="right",
        va="bottom",
    )
    panel_label(ax, "c")
    style_axis(ax)


def main() -> None:
    proxy, local_dp, acs = verify()
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 6.4,
            "axes.labelsize": 6.5,
            "xtick.labelsize": 5.9,
            "ytick.labelsize": 5.9,
            "axes.linewidth": 0.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    figure = plt.figure(figsize=(7.08, 2.55), facecolor="white")
    grid = figure.add_gridspec(
        1,
        3,
        width_ratios=[1.14, 1.0, 0.92],
        wspace=0.47,
    )
    axes = [figure.add_subplot(grid[0, index]) for index in range(3)]
    proxy_panel(axes[0], proxy)
    local_dp_panel(axes[1], local_dp)
    acs_panel(axes[2], acs)
    figure.subplots_adjust(left=0.065, right=0.99, bottom=0.22, top=0.83)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT.with_suffix(".pdf"), bbox_inches="tight")
    figure.savefig(
        OUTPUT.with_suffix(".png"),
        dpi=400,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close(figure)
    print(OUTPUT.with_suffix(".pdf"))


if __name__ == "__main__":
    main()
