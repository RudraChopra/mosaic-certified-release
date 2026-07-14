"""Build deterministic figures and TeX tables for VERA's locked ablations."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts"
FIGURES = ROOT / "maintrack" / "figures"
TEX_DIR = ROOT / "maintrack" / "aaai2027_template" / "AuthorKit27"
DEFAULT_SECONDARY = ARTIFACTS / "vera_secondary_ablation_report.json"
DEFAULT_ATTACKER = ARTIFACTS / "vera_attacker_ablation_report.json"
DEFAULT_FIGURE_PDF = FIGURES / "vera_locked_ablations.pdf"
DEFAULT_FIGURE_PNG = FIGURES / "vera_locked_ablations.png"
DEFAULT_TEX = TEX_DIR / "vera_ablation_results.tex"
DEFAULT_AUDIT = ARTIFACTS / "vera_ablation_package_audit.json"


COLORS = {
    "deploy": "#0072B2",
    "violate": "#D55E00",
    "retain": "#009E73",
    "point": "#E69F00",
}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def configure_plot() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.size": 7.3,
        "axes.labelsize": 7.8,
        "axes.titlesize": 8.4,
        "xtick.labelsize": 6.8,
        "ytick.labelsize": 6.8,
        "legend.fontsize": 6.8,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })


def estimate(cell: dict[str, Any], metric: str) -> tuple[float, float, float]:
    value = cell[metric]
    interval = cell["seed_cluster_bootstrap95"][metric]
    if value is None or interval is None:
        return np.nan, np.nan, np.nan
    return float(value), float(interval[0]), float(interval[1])


def errorbar(
    axis: plt.Axes,
    x: np.ndarray,
    cells: list[dict[str, Any]],
    metric: str,
    *,
    label: str,
    color: str,
    marker: str,
) -> None:
    values = np.asarray([estimate(cell, metric) for cell in cells], dtype=float)
    axis.errorbar(
        x,
        values[:, 0],
        yerr=np.vstack((values[:, 0] - values[:, 1], values[:, 2] - values[:, 0])),
        color=color,
        marker=marker,
        markersize=4,
        linewidth=1.1,
        capsize=2,
        label=label,
    )


def short_frontier_label(label: str) -> str:
    return {
        "all": "All",
        "without_INLP": "-INLP",
        "without_RLACE": "-R-LACE",
        "without_LEACE": "-LEACE",
        "without_TaCo": "-TaCo",
        "without_MANCE++": "-MANCE++",
    }.get(label, label.replace("without_", "-"))


def build_figure(
    secondary: dict[str, Any],
    attacker: dict[str, Any],
    pdf: Path,
    png: Path,
) -> None:
    configure_plot()
    fig, axes = plt.subplots(2, 2, figsize=(7.1, 4.25))

    budget_keys = sorted(secondary["deployment_budget"], key=float)
    budgets = np.asarray([float(value) for value in budget_keys])
    budget_cells = [secondary["deployment_budget"][key]["all_datasets"] for key in budget_keys]
    errorbar(
        axes[0, 0], budgets, budget_cells, "deployment_rate",
        label="Deploy", color=COLORS["deploy"], marker="o",
    )
    errorbar(
        axes[0, 0], budgets, budget_cells, "measured_external_violation_rate",
        label="External violation", color=COLORS["violate"], marker="s",
    )
    axes[0, 0].axvline(1.25, color="#555555", linestyle="--", linewidth=0.8)
    axes[0, 0].set_xlabel(r"Declared budget $\Gamma$")
    axes[0, 0].set_ylabel("Rate")
    axes[0, 0].set_title("A  Shift-budget sensitivity", loc="left", fontweight="bold")
    axes[0, 0].legend(frameon=False)

    fractions = [0.05, 0.10, 0.25, 0.50, 1.00]
    vera_cells = [
        secondary["validation_size"][f"vera|fraction={fraction:g}"]["all_datasets"]
        for fraction in fractions
    ]
    point_cells = [
        secondary["validation_size"][f"point_selection|fraction={fraction:g}"]["all_datasets"]
        for fraction in fractions
    ]
    errorbar(
        axes[0, 1], np.asarray(fractions), vera_cells, "deployment_rate",
        label="VERA deploy", color=COLORS["deploy"], marker="o",
    )
    errorbar(
        axes[0, 1], np.asarray(fractions), vera_cells,
        "measured_external_violation_rate", label="VERA violation",
        color=COLORS["violate"], marker="s",
    )
    point_values = [cell["measured_external_violation_rate"] for cell in point_cells]
    axes[0, 1].plot(
        fractions, point_values, color=COLORS["point"], marker="D",
        markersize=3.8, linewidth=1.0, label="Point violation",
    )
    axes[0, 1].set_xlabel("Certification fraction")
    axes[0, 1].set_ylabel("Rate")
    axes[0, 1].set_title("B  Validation-size sensitivity", loc="left", fontweight="bold")
    axes[0, 1].legend(frameon=False, ncol=2)

    portfolio_order = [
        "linear_only", "linear_rbf", "drop_linear", "drop_rbf",
        "drop_forest", "drop_mlp", "full",
    ]
    portfolio_labels = [
        "Linear", "Lin.+RBF", "-Linear", "-RBF", "-Forest", "-MLP", "Full",
    ]
    portfolio_cells = [attacker["portfolios"][key]["all_datasets"] for key in portfolio_order]
    x = np.arange(len(portfolio_order), dtype=float)
    errorbar(
        axes[1, 0], x, portfolio_cells, "deployment_rate",
        label="Deploy", color=COLORS["deploy"], marker="o",
    )
    errorbar(
        axes[1, 0], x, portfolio_cells, "measured_external_violation_rate",
        label="Full-contract violation", color=COLORS["violate"], marker="s",
    )
    axes[1, 0].set_xticks(x)
    axes[1, 0].set_xticklabels(portfolio_labels, rotation=24, ha="right")
    axes[1, 0].set_ylabel("Rate")
    axes[1, 0].set_title("C  Attacker-portfolio ablation", loc="left", fontweight="bold")
    axes[1, 0].legend(frameon=False)

    frontier_order = [
        "all", "without_INLP", "without_RLACE", "without_LEACE",
        "without_TaCo", "without_MANCE++",
    ]
    frontier_cells = [
        secondary["frontier_coverage"][key]["all_datasets"] for key in frontier_order
    ]
    x = np.arange(len(frontier_order), dtype=float)
    errorbar(
        axes[1, 1], x, frontier_cells, "deployment_rate",
        label="Deploy", color=COLORS["deploy"], marker="o",
    )
    errorbar(
        axes[1, 1], x, frontier_cells, "safe_deployment_retention",
        label="Safe retention", color=COLORS["retain"], marker="^",
    )
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(
        [short_frontier_label(value) for value in frontier_order], rotation=24, ha="right"
    )
    axes[1, 1].set_ylabel("Rate")
    axes[1, 1].set_title("D  Leave-one-eraser frontier", loc="left", fontweight="bold")
    axes[1, 1].legend(frameon=False)

    for axis in axes.flat:
        axis.set_ylim(-0.04, 1.04)
        axis.grid(axis="y", color="#DDDDDD", linewidth=0.5)
    fig.tight_layout(h_pad=1.4, w_pad=1.1)
    pdf.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    fig.savefig(png, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def percent(value: float | None) -> str:
    return "--" if value is None else f"{100.0 * float(value):.1f}\\%"


def write_tex(
    secondary: dict[str, Any], attacker: dict[str, Any], path: Path
) -> None:
    lines = [
        r"\section{Locked Secondary Ablations}",
        (
            "All analyses in this section were hashed before aggregate external-outcome "
            "analysis. They are secondary and do not replace the primary endpoints."
        ),
        r"\begin{figure*}[t]",
        r"\centering",
        r"\includegraphics[width=\textwidth]{../../figures/vera_locked_ablations.pdf}",
        r"\caption{Locked sensitivity analyses. Intervals resample seed clusters; correlated threshold and nested-fraction rows remain inside their seed cluster. External safety always uses the full four-attacker contract.}",
        r"\label{fig:supp-ablations}",
        r"\end{figure*}",
        r"\begin{table}[t]",
        r"\centering\small",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        r"Portfolio & Deploy & Ext. violation & Safe retention \\",
        r"\midrule",
    ]
    order = [
        ("linear_only", "Linear only"),
        ("linear_rbf", "Linear + RBF"),
        ("drop_linear", "Drop linear"),
        ("drop_rbf", "Drop RBF"),
        ("drop_forest", "Drop forest"),
        ("drop_mlp", "Drop MLP"),
        ("full", "Full"),
    ]
    for key, label in order:
        cell = attacker["portfolios"][key]["all_datasets"]
        lines.append(
            f"{label} & {percent(cell['deployment_rate'])} & "
            f"{percent(cell['measured_external_violation_rate'])} & "
            f"{percent(cell['safe_deployment_retention'])} \\\\"
        )
    lines.extend([
        r"\bottomrule",
        r"\end{tabular}",
        r"\caption{Attacker-portfolio ablation over every registered dataset, seed, threshold pair, and certification fraction. Success is never redefined when attackers are removed.}",
        r"\label{tab:supp-attacker-ablation}",
        r"\end{table}",
        (
            "The leave-one-eraser analysis retains the original full-family confidence "
            "allocation, isolating candidate-frontier coverage from multiplicity. "
            f"Every unsupported required environment had radius zero in "
            f"{secondary['certificate_geometry']['unsupported_zero_radius_rows']} of "
            f"{secondary['certificate_geometry']['unsupported_candidate_rows']} relevant "
            "candidate rows."
        ),
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--secondary", type=Path, default=DEFAULT_SECONDARY)
    parser.add_argument("--attacker", type=Path, default=DEFAULT_ATTACKER)
    parser.add_argument("--figure-pdf", type=Path, default=DEFAULT_FIGURE_PDF)
    parser.add_argument("--figure-png", type=Path, default=DEFAULT_FIGURE_PNG)
    parser.add_argument("--tex", type=Path, default=DEFAULT_TEX)
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    secondary = load_json(args.secondary)
    attacker = load_json(args.attacker)
    if secondary.get("passed") is not True or attacker.get("passed") is not True:
        raise RuntimeError("both locked ablation reports must pass before packaging")
    if secondary["ablation_prereg_sha256"] != attacker["ablation_prereg_sha256"]:
        raise RuntimeError("ablation reports use different preregistration hashes")
    build_figure(secondary, attacker, args.figure_pdf, args.figure_png)
    write_tex(secondary, attacker, args.tex)
    generated = [args.figure_pdf, args.figure_png, args.tex]
    audit = {
        "name": "VERA locked ablation package audit",
        "passed": all(path.is_file() and path.stat().st_size > 0 for path in generated),
        "ablation_prereg_sha256": secondary["ablation_prereg_sha256"],
        "source_sha256": {
            "secondary": sha256(args.secondary),
            "attacker": sha256(args.attacker),
        },
        "generated_files": [str(path) for path in generated],
        "unfavorable_cells_filtered": False,
        "configuration_rows_treated_as_independent": False,
    }
    args.audit.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
