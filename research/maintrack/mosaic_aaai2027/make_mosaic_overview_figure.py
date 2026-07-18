#!/usr/bin/env python3
"""Render the result-independent MOSAIC overview figure."""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle
import numpy as np


OUTPUT = Path(__file__).resolve().parent / "figures" / "figure1_mosaic_overview"
BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"
VERMILION = "#D55E00"
SKY = "#56B4E9"
INK = "#202124"
MUTED = "#667085"
LIGHT = "#F5F7FA"
BORDER = "#B8C0CC"


def arrow(ax: plt.Axes, x0: float, x1: float, y: float = 0.50) -> None:
    ax.add_patch(
        FancyArrowPatch(
            (x0, y),
            (x1, y),
            arrowstyle="-|>",
            mutation_scale=10,
            linewidth=1.1,
            color=MUTED,
        )
    )


def panel_title(ax: plt.Axes, number: str, title: str, subtitle: str) -> None:
    ax.text(
        0.02,
        0.96,
        number,
        transform=ax.transAxes,
        fontsize=8.4,
        fontweight="bold",
        color="white",
        ha="left",
        va="top",
        bbox={"boxstyle": "square,pad=0.22", "facecolor": INK, "edgecolor": INK},
    )
    ax.text(
        0.16,
        0.96,
        title,
        transform=ax.transAxes,
        fontsize=8.2,
        fontweight="bold",
        color=INK,
        ha="left",
        va="top",
    )
    ax.text(
        0.16,
        0.84,
        subtitle,
        transform=ax.transAxes,
        fontsize=6.1,
        color=MUTED,
        ha="left",
        va="top",
        linespacing=1.15,
    )


def fine_table_panel(ax: plt.Axes) -> None:
    panel_title(ax, "1", "Certify fine-token laws", "One simultaneous event over\nsource-label strata")
    values = np.asarray([[0.80, 0.15, 0.05], [0.65, 0.30, 0.05]])
    x0, y0 = 0.09, 0.20
    width, height = 0.76, 0.47
    cell_w, cell_h = width / 3.0, height / 2.0
    for row in range(2):
        for column in range(3):
            alpha = 0.15 + 0.75 * values[row, column]
            color = BLUE if row == 0 else ORANGE
            ax.add_patch(
                Rectangle(
                    (x0 + column * cell_w, y0 + (1 - row) * cell_h),
                    cell_w,
                    cell_h,
                    facecolor=mpl.colors.to_rgba(color, alpha),
                    edgecolor="white",
                    linewidth=1.1,
                )
            )
            ax.text(
                x0 + (column + 0.5) * cell_w,
                y0 + (1.5 - row) * cell_h,
                f"{values[row, column]:.2f}",
                ha="center",
                va="center",
                fontsize=6.3,
                color=INK,
            )
    ax.text(x0 - 0.025, y0 + 1.5 * cell_h, "$S=0$", ha="right", va="center", fontsize=6.2, color=BLUE)
    ax.text(x0 - 0.025, y0 + 0.5 * cell_h, "$S=1$", ha="right", va="center", fontsize=6.2, color=ORANGE)
    for column in range(3):
        ax.text(x0 + (column + 0.5) * cell_w, y0 - 0.04, f"$c_{column+1}$", ha="center", va="top", fontsize=6.2)
    ax.text(0.47, 0.045, r"$\Pr(\mathcal{E})\geq1-\delta$", ha="center", va="center", fontsize=7.0, color=INK)


def continuum_panel(ax: plt.Axes) -> None:
    panel_title(ax, "2", "Optimize on the same table", "The event covers every stochastic\nrelease channel")
    matrices = [
        np.asarray([[0.95, 0.05], [0.65, 0.35], [0.10, 0.90]]),
        np.asarray([[0.80, 0.20], [0.45, 0.55], [0.02, 0.98]]),
        np.asarray([[1.00, 0.00], [0.50, 0.50], [0.00, 1.00]]),
    ]
    starts = [0.07, 0.36, 0.65]
    for matrix, start in zip(matrices, starts):
        for row in range(3):
            for column in range(2):
                ax.add_patch(
                    Rectangle(
                        (start + column * 0.09, 0.35 + (2 - row) * 0.10),
                        0.09,
                        0.10,
                        facecolor=mpl.colors.to_rgba(SKY, 0.12 + 0.78 * matrix[row, column]),
                        edgecolor="white",
                        linewidth=0.8,
                    )
                )
        ax.add_patch(Rectangle((start, 0.35), 0.18, 0.30, facecolor="none", edgecolor=BORDER, linewidth=0.7))
    ax.text(0.50, 0.28, r"$M\in\mathrm{Stoch}(K,L)$", ha="center", va="center", fontsize=7.0, color=INK)
    ax.text(0.50, 0.17, "continuum-wide, no channel-count penalty", ha="center", va="center", fontsize=6.0, color=MUTED)
    ax.text(0.50, 0.07, "jointly select $M$ and decoder $g$", ha="center", va="center", fontsize=6.4, color=GREEN, fontweight="bold")


def shift_panel(ax: plt.Axes) -> None:
    panel_title(ax, "3", "Shift occurs before release", "Common drift plus bounded\nsource-specific contamination")
    ax.text(0.08, 0.59, "$p_s$", fontsize=8.0, color=INK, ha="center", va="center")
    ax.add_patch(Rectangle((0.20, 0.49), 0.17, 0.20, facecolor=LIGHT, edgecolor=BLUE, linewidth=1.0))
    ax.text(0.285, 0.59, "common\n$T_y$", fontsize=6.4, color=BLUE, ha="center", va="center")
    arrow(ax, 0.11, 0.20, 0.59)
    arrow(ax, 0.37, 0.45, 0.59)
    ax.text(0.50, 0.59, r"$\oplus$", fontsize=9.0, color=MUTED, ha="center", va="center")
    ax.add_patch(Rectangle((0.57, 0.49), 0.17, 0.20, facecolor=LIGHT, edgecolor=VERMILION, linewidth=1.0))
    ax.text(0.655, 0.59, "bounded\n" + r"$\eta_y r_s$", fontsize=6.2, color=VERMILION, ha="center", va="center")
    arrow(ax, 0.74, 0.82, 0.59)
    ax.add_patch(Rectangle((0.82, 0.49), 0.13, 0.20, facecolor=LIGHT, edgecolor=GREEN, linewidth=1.0))
    ax.text(0.885, 0.59, "$M$", fontsize=8.0, color=GREEN, ha="center", va="center", fontweight="bold")
    ax.text(0.50, 0.34, r"$q_s=t_y p_sT_y+(1-t_y)r_s$", ha="center", va="center", fontsize=7.0, color=INK)
    ax.text(0.50, 0.20, r"same $T_y,t_y$ across sources; $t_y\geq1-\eta_y$", ha="center", va="center", fontsize=6.0, color=MUTED)
    ax.text(0.50, 0.08, "nothing bypasses the software channel", ha="center", va="center", fontsize=6.2, color=GREEN, fontweight="bold")


def decision_panel(ax: plt.Axes) -> None:
    panel_title(ax, "4", "Release only with a certificate", "Exact Bayes attacker, worst-stratum\nutility, or abstain")
    ax.add_patch(Rectangle((0.07, 0.42), 0.37, 0.24, facecolor=mpl.colors.to_rgba(GREEN, 0.10), edgecolor=GREEN, linewidth=1.1))
    ax.text(0.255, 0.58, "PRIVACY", ha="center", va="center", fontsize=6.4, color=GREEN, fontweight="bold")
    ax.text(0.255, 0.48, r"$\overline{\mathrm{Adv}}\leq\tau_P$", ha="center", va="center", fontsize=7.0, color=INK)
    ax.add_patch(Rectangle((0.56, 0.42), 0.37, 0.24, facecolor=mpl.colors.to_rgba(BLUE, 0.10), edgecolor=BLUE, linewidth=1.1))
    ax.text(0.745, 0.58, "UTILITY", ha="center", va="center", fontsize=6.4, color=BLUE, fontweight="bold")
    ax.text(0.745, 0.48, r"$\overline{\mathrm{Err}}\leq\tau_U$", ha="center", va="center", fontsize=7.0, color=INK)
    arrow(ax, 0.26, 0.45, 0.31)
    arrow(ax, 0.74, 0.55, 0.31)
    ax.add_patch(Rectangle((0.37, 0.20), 0.26, 0.18, facecolor=INK, edgecolor=INK, linewidth=1.0))
    ax.text(0.50, 0.29, "DEPLOY", ha="center", va="center", fontsize=7.0, color="white", fontweight="bold")
    ax.text(0.50, 0.08, "otherwise: ABSTAIN", ha="center", va="center", fontsize=6.5, color=VERMILION, fontweight="bold")


def main() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7,
            "axes.linewidth": 0.6,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )
    fig, axes = plt.subplots(1, 4, figsize=(7.08, 2.25))
    for ax in axes:
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(0.0, 1.0)
        ax.axis("off")
        ax.add_patch(Rectangle((0.005, 0.005), 0.99, 0.99, facecolor="white", edgecolor=BORDER, linewidth=0.7))
    fine_table_panel(axes[0])
    continuum_panel(axes[1])
    shift_panel(axes[2])
    decision_panel(axes[3])
    fig.subplots_adjust(left=0.006, right=0.994, top=0.985, bottom=0.03, wspace=0.055)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.015)
    fig.savefig(OUTPUT.with_suffix(".png"), dpi=600, bbox_inches="tight", pad_inches=0.015)
    plt.close(fig)


if __name__ == "__main__":
    main()
