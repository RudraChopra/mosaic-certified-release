#!/usr/bin/env python3
"""Generate the outcome-independent VERA method overview figure."""

from datetime import datetime, timezone
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


OUT_DIR = Path(__file__).resolve().parent
PDF_METADATA = {
    "Title": "VERA method overview",
    "Subject": "Outcome-independent schematic of evidence allocation, certification, and abstention",
    "Author": "Anonymous",
    "Creator": "generate_vera_method_overview.py",
    "CreationDate": datetime(2026, 7, 15, tzinfo=timezone.utc),
    "ModDate": datetime(2026, 7, 15, tzinfo=timezone.utc),
}

# Okabe-Ito colors plus neutral grays. Line styles and markers carry the same
# distinctions so the figure remains readable without color.
BLUE = "#0072B2"
GREEN = "#009E73"
ORANGE = "#D55E00"
PINK = "#CC79A7"
YELLOW = "#F0E442"
INK = "#202124"
MID = "#5F6368"
LIGHT = "#E5E7EB"
PALE_BLUE = "#EAF4F8"
PALE_GREEN = "#EAF6F1"
PALE_ORANGE = "#FBEFE9"


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 7.2,
            "axes.titlesize": 8.4,
            "axes.labelsize": 7.3,
            "xtick.labelsize": 7.0,
            "ytick.labelsize": 7.0,
            "legend.fontsize": 7.0,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.55,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "savefig.transparent": False,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.025,
        }
    )


def box(
    ax,
    xy,
    width,
    height,
    label,
    *,
    edge=MID,
    face="white",
    fontsize=7.0,
    weight="normal",
    linewidth=0.9,
    radius=0.025,
    color=INK,
):
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle=f"round,pad=0.012,rounding_size={radius}",
        linewidth=linewidth,
        edgecolor=edge,
        facecolor=face,
        transform=ax.transAxes,
        clip_on=False,
    )
    ax.add_patch(patch)
    ax.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        label,
        ha="center",
        va="center",
        fontsize=fontsize,
        fontweight=weight,
        color=color,
        transform=ax.transAxes,
    )
    return patch


def arrow(ax, start, end, *, color=MID, linewidth=1.0, mutation=8):
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=mutation,
        linewidth=linewidth,
        color=color,
        transform=ax.transAxes,
        clip_on=False,
    )
    ax.add_patch(patch)
    return patch


def panel_a(ax) -> None:
    ax.set_axis_off()
    ax.set_title("A  Allocate, then audit the edit", loc="left", fontweight="bold", pad=4)

    ax.text(
        0.01,
        0.88,
        "Design margins",
        transform=ax.transAxes,
        color=MID,
        fontsize=7.0,
        fontweight="bold",
    )
    cells = [("target", "small"), ("S=0", "tight"), ("S=1", "wide")]
    x_positions = [0.01, 0.15, 0.29]
    margin_heights = [0.34, 0.70, 0.48]
    for x, (label, margin), h in zip(x_positions, cells, margin_heights):
        box(ax, (x, 0.67), 0.12, 0.12, label, edge=LIGHT, face="#F8F9FA", fontsize=7.0)
        ax.add_patch(
            Rectangle(
                (x + 0.012, 0.635),
                0.096,
                0.018,
                transform=ax.transAxes,
                facecolor="#ECEFF1",
                edgecolor="none",
            )
        )
        ax.add_patch(
            Rectangle(
                (x + 0.012, 0.635),
                0.096 * h,
                0.018,
                transform=ax.transAxes,
                facecolor=BLUE if label == "target" else GREEN,
                edgecolor="none",
            )
        )
        ax.text(x + 0.060, 0.605, margin, ha="center", transform=ax.transAxes, fontsize=7.0, color=MID)

    arrow(ax, (0.415, 0.72), (0.455, 0.72), mutation=7)
    ax.text(
        0.59,
        0.775,
        r"$\min_{\mathbf{n}}\;\max_j$",
        ha="center",
        va="center",
        transform=ax.transAxes,
        fontsize=7.0,
        color=INK,
    )
    ax.text(
        0.59,
        0.690,
        r"$\sum_c a_{jc}/\sqrt{n_c}$",
        ha="center",
        transform=ax.transAxes,
        fontsize=7.0,
        color=INK,
    )
    arrow(ax, (0.725, 0.72), (0.755, 0.72), mutation=7)

    count_x = [0.77, 0.835, 0.90]
    count_h = [0.09, 0.18, 0.135]
    for x, h, color in zip(count_x, count_h, [BLUE, GREEN, GREEN]):
        ax.add_patch(
            Rectangle(
                (x, 0.62),
                0.038,
                h,
                transform=ax.transAxes,
                facecolor=color,
                edgecolor=INK,
                linewidth=0.45,
            )
        )
        ax.add_patch(
            Rectangle(
                (x, 0.62),
                0.038,
                0.052,
                transform=ax.transAxes,
                facecolor=YELLOW,
                edgecolor=INK,
                linewidth=0.35,
                hatch="////",
            )
        )
    ax.text(0.845, 0.575, "cell counts", ha="center", transform=ax.transAxes, fontsize=7.0, color=MID)

    ax.plot([0.01, 0.98], [0.50, 0.50], color=LIGHT, linewidth=0.8, transform=ax.transAxes)
    ax.text(
        0.01,
        0.45,
        "Audit disjoint streams",
        transform=ax.transAxes,
        color=MID,
        fontsize=7.0,
        fontweight="bold",
    )

    box(ax, (0.01, 0.17), 0.12, 0.115, "identity", edge=BLUE, face=PALE_BLUE, fontsize=7.0)
    box(ax, (0.17, 0.17), 0.12, 0.115, "edited", edge=ORANGE, face=PALE_ORANGE, fontsize=7.0)
    ax.text(0.01, 0.345, "paired target", transform=ax.transAxes, fontsize=7.0, color=MID)
    ax.plot([0.13, 0.17], [0.228, 0.228], color=MID, linewidth=0.8, transform=ax.transAxes)
    arrow(ax, (0.30, 0.228), (0.33, 0.228), mutation=7)
    box(ax, (0.34, 0.17), 0.11, 0.115, r"$H_e=+1$", edge=INK, face="#F8F9FA", fontsize=7.0)

    box(ax, (0.51, 0.17), 0.12, 0.115, "source\ndraw", edge=GREEN, face=PALE_GREEN, fontsize=7.0)
    ax.text(0.57, 0.345, "shared source", ha="center", transform=ax.transAxes, fontsize=7.0, color=MID)
    arrow(ax, (0.64, 0.228), (0.68, 0.228), mutation=7)
    attacker_specs = [(0.72, BLUE), (0.79, GREEN), (0.86, PINK), (0.93, ORANGE)]
    for x, color in attacker_specs:
        ax.scatter(
            [x],
            [0.23],
            s=42,
            marker="o",
            facecolor="white",
            edgecolor=color,
            linewidth=1.3,
            transform=ax.transAxes,
            zorder=3,
        )
    ax.text(
        0.825,
        0.085,
        "4 fresh attackers",
        ha="center",
        transform=ax.transAxes,
        fontsize=7.0,
        color=MID,
    )
    ax.text(
        0.01,
        0.02,
        "Fixed before outcomes",
        transform=ax.transAxes,
        fontsize=7.0,
        color=INK,
        fontweight="bold",
    )


def panel_b(ax) -> None:
    ax.set_title("B  Test one profile; report the envelope", loc="left", fontweight="bold", pad=4)

    gamma = np.linspace(1.0, 3.0, 160)
    curves = [
        (0.34 + 0.20 * gamma, BLUE, "-", "Harm"),
        (0.35 + 0.205 * gamma, GREEN, "--", "Linear"),
        (0.29 + 0.31 * gamma, ORANGE, "-", "Radial"),
        (0.33 + 0.215 * gamma, PINK, ":", "Forest"),
        (0.30 + 0.235 * gamma, MID, "-.", "Neural"),
    ]
    maximum = np.max(np.vstack([values for values, _, _, _ in curves]), axis=0)
    crossing_indices = np.where(maximum >= 1.0)[0]
    radius = gamma[crossing_indices[0]] if len(crossing_indices) else gamma[-1]
    declared = 1.45

    feasible = (gamma <= radius) & (maximum <= 1.0)
    ax.fill_between(gamma, 0.40, 1.0, where=feasible, color=PALE_GREEN, alpha=1.0, zorder=0)
    ax.axhline(1.0, color=INK, linewidth=0.9)
    ax.text(2.98, 1.015, "contract", ha="right", va="bottom", fontsize=7.0, color=INK)

    for values, color, linestyle, _ in curves:
        ax.plot(gamma, values, color=color, linestyle=linestyle, linewidth=1.45)

    ax.axvline(declared, color=GREEN, linewidth=1.0, linestyle="--")
    ax.scatter([declared], [0.46], s=22, marker="o", facecolor="white", edgecolor=GREEN, linewidth=1.1, zorder=5)
    ax.text(declared + 0.04, 0.475, "registered profile\nIUT passes", color=GREEN, fontsize=7.0, va="bottom")

    ax.axvline(radius, color=INK, linewidth=1.0, linestyle=(0, (4, 2)))
    ax.scatter([radius], [1.0], s=25, marker="D", facecolor=ORANGE, edgecolor=INK, linewidth=0.45, zorder=6)
    ax.annotate(
        "limiting contract",
        xy=(radius, 1.0),
        xytext=(2.48, 1.17),
        fontsize=7.0,
        color=ORANGE,
        arrowprops={"arrowstyle": "->", "color": ORANGE, "linewidth": 0.8},
    )
    ax.text(radius + 0.045, 0.415, r"$\widehat{\Gamma}$", va="bottom", fontsize=7.0, color=INK)

    legend_handles = [
        Line2D([0], [0], color=color, linestyle=linestyle, linewidth=1.4, label=label)
        for _, color, linestyle, label in curves
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper left",
        ncol=2,
        frameon=False,
        handlelength=2.1,
        columnspacing=0.8,
        borderaxespad=0.25,
    )
    ax.set_xlim(1.0, 3.0)
    ax.set_ylim(0.40, 1.30)
    ax.set_xticks([1, 2, 3])
    ax.set_yticks([0.5, 1.0, 1.25])
    ax.set_xlabel(r"Declared reweighting budget $\Gamma$")
    ax.set_ylabel("Contract-normalized upper bound", labelpad=1)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color=LIGHT, linewidth=0.5, zorder=-1)


def panel_c(ax) -> None:
    ax.set_axis_off()
    ax.set_title("C  New support means abstain", loc="left", fontweight="bold", fontsize=8.0, pad=4)
    ax.text(
        0.50,
        0.89,
        "Camelyon17 support boundary",
        ha="center",
        transform=ax.transAxes,
        fontsize=7.0,
        color=MID,
        fontweight="bold",
    )

    box(ax, (0.03, 0.60), 0.42, 0.17, "Centers\n0, 1, 3, 4", edge=MID, face="#F8F9FA", fontsize=7.0)
    arrow(ax, (0.24, 0.595), (0.24, 0.48), color=GREEN, mutation=8)
    box(
        ax,
        (0.03, 0.28),
        0.42,
        0.17,
        "Supported:\ncertifiable",
        edge=GREEN,
        face=PALE_GREEN,
        fontsize=7.0,
        weight="bold",
        color=GREEN,
    )

    box(
        ax,
        (0.55, 0.60),
        0.42,
        0.17,
        "Center 2 absent\nfrom support",
        edge=ORANGE,
        face=PALE_ORANGE,
        fontsize=7.0,
        color=ORANGE,
    )
    ax.text(0.76, 0.535, "one observed class", ha="center", transform=ax.transAxes, fontsize=7.0, color=ORANGE)
    arrow(ax, (0.76, 0.515), (0.76, 0.45), color=ORANGE, mutation=8)
    box(
        ax,
        (0.55, 0.28),
        0.42,
        0.14,
        "New support:\nABSTAIN",
        edge=ORANGE,
        face=PALE_ORANGE,
        fontsize=7.0,
        weight="bold",
        color=ORANGE,
    )

    ax.plot([0.5, 0.5], [0.20, 0.80], color=LIGHT, linewidth=0.8, transform=ax.transAxes)
    ax.text(
        0.50,
        0.11,
        "Identification boundary;\nnot evidence of clinical harm",
        ha="center",
        transform=ax.transAxes,
        fontsize=7.0,
        color=INK,
        fontweight="bold",
    )
    ax.text(
        0.50,
        0.015,
        "Needs assumptions or new data",
        ha="center",
        transform=ax.transAxes,
        fontsize=7.0,
        color=MID,
    )


def main() -> None:
    configure_style()
    fig = plt.figure(figsize=(7.05, 2.42), constrained_layout=False)
    grid = fig.add_gridspec(
        1,
        3,
        width_ratios=[1.28, 1.08, 0.96],
        left=0.012,
        right=0.993,
        bottom=0.17,
        top=0.90,
        wspace=0.32,
    )
    axes = [fig.add_subplot(grid[0, i]) for i in range(3)]
    panel_a(axes[0])
    panel_b(axes[1])
    panel_c(axes[2])

    fig.savefig(
        OUT_DIR / "vera_method_overview.pdf",
        format="pdf",
        dpi=600,
        facecolor="white",
        transparent=False,
        metadata=PDF_METADATA,
    )
    fig.savefig(OUT_DIR / "vera_method_overview.png", format="png", dpi=450, facecolor="white", transparent=False)
    plt.close(fig)


if __name__ == "__main__":
    main()
