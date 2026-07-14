"""Build the publication Figure 1 for VERA as editable vector graphics."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = ROOT / "maintrack" / "figures" / "vera_method_overview.pdf"
DEFAULT_PNG = ROOT / "maintrack" / "figures" / "vera_method_overview.png"

BLUE = "#0072B2"
ORANGE = "#D55E00"
GREEN = "#009E73"
PURPLE = "#CC79A7"
GRAY = "#5B6573"
LIGHT_GRAY = "#E8EBEF"
BLACK = "#16191D"


def setup() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 8,
            "axes.titlesize": 9,
            "axes.labelsize": 8,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "text.color": BLACK,
            "axes.labelcolor": BLACK,
            "xtick.color": BLACK,
            "ytick.color": BLACK,
        }
    )


def panel_label(axis: plt.Axes, label: str, title: str) -> None:
    axis.text(
        0.0,
        1.04,
        label,
        transform=axis.transAxes,
        fontsize=9,
        fontweight="bold",
        va="bottom",
    )
    axis.text(
        0.09,
        1.04,
        title,
        transform=axis.transAxes,
        fontsize=7.1,
        fontweight="bold",
        va="bottom",
    )


def paired_panel(axis: plt.Axes) -> None:
    panel_label(axis, "A", "Paired intervention audit")
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    x = np.linspace(0.21, 0.92, 6)
    identity = np.asarray([0, 0, 1, 1, 0, 1])
    edited = np.asarray([0, 1, 1, 0, 0, 1])
    axis.text(0.01, 0.76, "Identity", color=GRAY, va="center")
    axis.text(0.01, 0.47, "Edited", color=GRAY, va="center")
    for index, location in enumerate(x):
        axis.plot([location, location], [0.51, 0.72], color="#C8CDD3", linewidth=0.8)
        for y, error in ((0.76, identity[index]), (0.47, edited[index])):
            axis.scatter(
                [location],
                [y],
                s=42,
                color=ORANGE if error else BLUE,
                edgecolor="white",
                linewidth=0.6,
                zorder=3,
            )
        harm = int(edited[index] - identity[index])
        axis.text(location, 0.34, f"{harm:+d}" if harm else "0", ha="center", fontsize=7)
    axis.text(0.01, 0.34, r"$H_e$", color=GRAY, va="center")
    axis.text(0.19, 0.14, "paired target harm", color=GRAY, ha="center", fontsize=6.5)
    axis.add_patch(
        FancyArrowPatch(
            (0.36, 0.14),
            (0.50, 0.14),
            arrowstyle="-|>",
            mutation_scale=8,
            color="#9BA3AC",
            linewidth=0.8,
        )
    )
    attacker_x = [0.56, 0.70, 0.84, 0.97]
    for location, label, color in zip(
        attacker_x, ("Lin.", "RBF", "RF", "MLP"), (BLUE, GREEN, PURPLE, ORANGE)
    ):
        axis.scatter([location], [0.14], s=32, facecolor="white", edgecolor=color, linewidth=1.2)
        axis.text(location, 0.035, label, ha="center", fontsize=5.5, color=GRAY)
    axis.text(
        0.76,
        0.26,
        "fresh attackers",
        ha="center",
        color=GRAY,
        fontsize=6.5,
    )
    axis.text(
        0.76,
        0.00,
        r"each: $\frac{1}{2}(\mathrm{recall}_0+\mathrm{recall}_1)$",
        ha="center",
        color=GRAY,
        fontsize=5.6,
    )
    axis.text(0.51, 0.91, "correct", color=BLUE, fontsize=6.5)
    axis.scatter([0.47], [0.925], s=16, color=BLUE)
    axis.text(0.84, 0.91, "error", color=ORANGE, fontsize=6.5)
    axis.scatter([0.80], [0.925], s=16, color=ORANGE)


def radius_panel(axis: plt.Axes) -> None:
    panel_label(axis, "B", "Fixed profile + envelope")
    gamma = np.linspace(1.0, 3.0, 200)
    curves = {
        "Target harm": (0.41 + 0.22 * (gamma - 1), BLUE, "-"),
        "Linear": (0.50 + 0.19 * (gamma - 1), GREEN, "--"),
        "RBF": (0.53 + 0.29 * (gamma - 1), ORANGE, "-"),
        "Forest": (0.45 + 0.23 * (gamma - 1), PURPLE, ":"),
        "MLP": (0.48 + 0.25 * (gamma - 1), GRAY, "-."),
    }
    limiting = curves["RBF"][0]
    radius = float(np.interp(1.0, limiting, gamma))
    axis.axhspan(0, 1, color=GREEN, alpha=0.055, zorder=0)
    axis.axvspan(1, radius, color=BLUE, alpha=0.07, zorder=0)
    for label, (values, color, style) in curves.items():
        axis.plot(gamma, values, label=label, color=color, linestyle=style, linewidth=1.25)
    axis.axhline(1.0, color=BLACK, linewidth=0.9)
    axis.axvline(radius, color=BLACK, linewidth=0.9, linestyle="--")
    axis.scatter([1.0], [0.50], marker="D", s=25, color=GREEN, zorder=4)
    axis.text(
        1.05,
        0.34,
        "fixed profile:\nall pass: EDIT",
        fontsize=5.5,
        color=GREEN,
        va="bottom",
    )
    axis.text(radius + 0.03, 0.36, rf"$\widehat{{\Gamma}}_e={radius:.2f}$", fontsize=5.8)
    axis.text(2.96, 1.03, "contract", fontsize=6.5, ha="right")
    axis.annotate(
        "limiting attacker",
        xy=(radius, 1.0),
        xytext=(2.14, 1.28),
        arrowprops={"arrowstyle": "->", "color": ORANGE, "linewidth": 0.8},
        fontsize=6.5,
        color=ORANGE,
    )
    axis.set_xlim(1, 3)
    axis.set_ylim(0.3, 1.48)
    axis.set_xlabel(r"Declared reweighting budget $\Gamma$")
    axis.set_ylabel(r"$U_k(\Gamma) / c_k$")
    axis.set_xticks((1, 2, 3))
    axis.set_yticks((0.5, 1.0, 1.5))
    axis.spines[["top", "right"]].set_visible(False)
    axis.legend(frameon=False, ncol=2, loc="upper left", fontsize=5.4, handlelength=1.5)


def rounded_box(
    axis: plt.Axes,
    xy: tuple[float, float],
    width: float,
    height: float,
    *,
    facecolor: str,
    edgecolor: str,
    text: str,
    text_color: str = BLACK,
    fontsize: float = 7,
) -> None:
    box = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.02",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=0.9,
    )
    axis.add_patch(box)
    axis.text(
        xy[0] + width / 2,
        xy[1] + height / 2,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=text_color,
        linespacing=1.25,
    )


def support_panel(axis: plt.Axes) -> None:
    panel_label(axis, "C", "Unsupported means abstain")
    axis.set_xlim(0, 1)
    axis.set_ylim(0, 1)
    axis.axis("off")
    axis.text(0.02, 0.91, "Real receipt: Camelyon17", fontsize=6.5, color=GRAY)
    rounded_box(
        axis,
        (0.02, 0.58),
        0.42,
        0.23,
        facecolor="#F6F8FA",
        edgecolor="#AAB2BB",
        text="Seen centers\n0, 1, 3, 4",
        fontsize=6.4,
    )
    rounded_box(
        axis,
        (0.57, 0.58),
        0.40,
        0.23,
        facecolor="#FFF5F0",
        edgecolor=ORANGE,
        text="Unseen\ncenter 2\n(one class)",
        text_color=ORANGE,
        fontsize=5.7,
    )
    axis.add_patch(
        FancyArrowPatch(
            (0.44, 0.695),
            (0.56, 0.695),
            arrowstyle="-|>",
            mutation_scale=9,
            color="#9BA3AC",
            linewidth=1.0,
        )
    )
    rounded_box(
        axis,
        (0.02, 0.18),
        0.42,
        0.23,
        facecolor="#EFF8F5",
        edgecolor=GREEN,
        text="Radius\nCERTIFIED",
        text_color=GREEN,
        fontsize=6.6,
    )
    rounded_box(
        axis,
        (0.57, 0.18),
        0.40,
        0.23,
        facecolor="#FFF5F0",
        edgecolor=ORANGE,
        text="New support\nABSTAIN",
        text_color=ORANGE,
        fontsize=6.6,
    )
    axis.add_patch(
        FancyArrowPatch(
            (0.23, 0.58),
            (0.23, 0.42),
            arrowstyle="-|>",
            mutation_scale=9,
            color=GREEN,
            linewidth=1.0,
        )
    )
    axis.add_patch(
        FancyArrowPatch(
            (0.77, 0.58),
            (0.77, 0.42),
            arrowstyle="-|>",
            mutation_scale=9,
            color=ORANGE,
            linewidth=1.0,
        )
    )
    axis.add_patch(Rectangle((0.485, 0.08), 0.002, 0.83, color=LIGHT_GRAY, linewidth=0))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--png", type=Path, default=DEFAULT_PNG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup()
    fig = plt.figure(figsize=(7.1, 2.35))
    grid = fig.add_gridspec(1, 3, width_ratios=(1.08, 1.0, 1.03), wspace=0.48)
    paired_panel(fig.add_subplot(grid[0, 0]))
    radius_panel(fig.add_subplot(grid[0, 1]))
    support_panel(fig.add_subplot(grid[0, 2]))
    args.pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.pdf, bbox_inches="tight", facecolor="white")
    fig.savefig(args.png, dpi=350, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"wrote {args.pdf}")
    print(f"wrote {args.png}")


if __name__ == "__main__":
    main()
