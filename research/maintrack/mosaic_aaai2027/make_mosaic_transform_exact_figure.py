#!/usr/bin/env python3
"""Render the audited transform-exact confirmation figure."""

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
REPORT = ARTIFACTS / "mosaic_transform_exact_confirmation_v2.json"
AUDIT = ARTIFACTS / "mosaic_transform_exact_confirmation_audit_v2.json"
OUTPUT = ROOT / "figures" / "figure3_mosaic_transform_exact"

GREEN = "#009E73"
BLUE = "#0072B2"
ORANGE = "#E69F00"
INK = "#202124"
MUTED = "#667085"
GRID = "#D9DEE7"


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


def verify() -> dict[str, Any]:
    report = load(REPORT)
    audit = load(AUDIT)
    if audit.get("pass") is not True:
        raise AssertionError("transform-exact confirmation audit did not pass")
    if audit.get("report_sha256") != sha256(REPORT):
        raise AssertionError("audit does not match the transform-exact report")
    if report.get("name") != "MOSAIC transform-exact strict-decision confirmation v2":
        raise AssertionError("unexpected confirmation version")
    return report


def cell_index(report: dict[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    return {
        (int(cell["sample_size_per_stratum"]), str(cell["method"])): cell
        for cell in report["cells"]
        if cell["scenario"] == "retention_and_exactness_value"
    }


def retention_panel(ax: plt.Axes, report: dict[str, Any]) -> None:
    cells = cell_index(report)
    sizes = [125, 250, 500, 1000]
    positions = np.arange(len(sizes))
    for method, label, color, marker in (
        ("transform_exact", "Transform-exact", GREEN, "o"),
        ("capacity_transfer", "Capacity transfer", BLUE, "s"),
    ):
        rows = [cells[(n, method)] for n in sizes]
        rates = np.asarray([float(row["safe_deployment_rate"]) for row in rows])
        lower = np.asarray([float(row["safe_deployment_cp95_lower"]) for row in rows])
        upper = np.asarray([float(row["safe_deployment_cp95_upper"]) for row in rows])
        ax.errorbar(
            positions,
            rates,
            yerr=np.vstack((rates - lower, upper - rates)),
            color=color,
            marker=marker,
            markersize=4.2,
            linewidth=1.45,
            elinewidth=0.8,
            capsize=2.0,
            label=label,
            zorder=3,
        )
    ax.set_xticks(positions, [str(n) for n in sizes])
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0], ["0", "25", "50", "75", "100"])
    ax.set_ylim(-0.04, 1.05)
    ax.set_xlabel("Samples per source-label stratum")
    ax.set_ylabel("Safe deployments (%)")
    ax.set_title("Exact shift geometry prevents needless abstention", loc="left")
    ax.legend(frameon=False, fontsize=6.1, loc="lower right")
    ax.text(
        0.02,
        0.91,
        "+52.7 pp at n=125\n+42.1 pp at n=250",
        transform=ax.transAxes,
        fontsize=6.2,
        color=INK,
        va="top",
    )


def ecdf_panel(ax: plt.Axes, report: dict[str, Any]) -> None:
    rows = [
        row
        for row in report["replicate_results"]
        if row["scenario"] == "retention_and_exactness_value"
        and int(row["sample_size_per_stratum"]) == 125
    ]
    for method, label, color in (
        ("transform_exact", "Transform-exact", GREEN),
        ("capacity_transfer", "Capacity transfer", BLUE),
    ):
        values = np.sort(
            np.asarray(
                [
                    float(row["certified_worst_conditional_error"])
                    for row in rows
                    if row["method"] == method
                ]
            )
        )
        cumulative = np.arange(1, len(values) + 1) / len(values)
        ax.step(values, cumulative, where="post", color=color, linewidth=1.55, label=label)
    ax.axvline(0.45, color=ORANGE, linestyle=(0, (3, 2)), linewidth=1.0)
    ax.text(0.452, 0.07, "utility contract", color=ORANGE, fontsize=6.0, rotation=90)
    ax.set_xlim(0.41, 0.51)
    ax.set_ylim(-0.03, 1.03)
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0], ["0", "25", "50", "75", "100"])
    ax.set_xlabel("Certified worst conditional error")
    ax.set_ylabel("Tables at or below value (%)")
    ax.set_title("Pointwise-tight bounds cross the same contract", loc="left")
    ax.text(
        0.98,
        0.12,
        "530 vs. 3 safe deployments\nout of 1,000 paired tables",
        transform=ax.transAxes,
        fontsize=6.2,
        color=INK,
        ha="right",
        va="bottom",
    )


def style_axis(ax: plt.Axes, panel: str) -> None:
    ax.text(
        -0.14,
        1.06,
        panel,
        transform=ax.transAxes,
        fontsize=8.0,
        fontweight="bold",
        color="white",
        ha="center",
        va="center",
        bbox={"boxstyle": "square,pad=0.20", "facecolor": INK, "edgecolor": INK},
    )
    ax.grid(color=GRID, linewidth=0.55, zorder=0)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.set_axisbelow(True)


def main() -> None:
    report = verify()
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 6.5,
            "axes.titlesize": 8.0,
            "axes.titleweight": "bold",
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
    fig, axes = plt.subplots(1, 2, figsize=(7.08, 2.45), facecolor="white")
    retention_panel(axes[0], report)
    ecdf_panel(axes[1], report)
    style_axis(axes[0], "a")
    style_axis(axes[1], "b")
    fig.subplots_adjust(left=0.09, right=0.995, top=0.88, bottom=0.19, wspace=0.34)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT.with_suffix(".pdf"), bbox_inches="tight", pad_inches=0.02)
    fig.savefig(OUTPUT.with_suffix(".png"), dpi=600, bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)


if __name__ == "__main__":
    main()
