"""Export paper-facing artifacts for the controlled-shift follow-up."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt


RULE_LABELS = {
    "always_deploy": "Always deploy",
    "validation_point_selection": "Validation selection",
    "iid_ltt": "IID LTT",
    "robust_point_estimate": "Robust point estimate",
    "generic_scalar_robust_certificate": "Scalar robust certificate",
    "vera_fixed_profile": "VERA fixed profile",
    "vera_vector_envelope": "VERA vector envelope",
    "vera_common_radius": "VERA common radius",
    "external_oracle": "External oracle",
}
RULE_ORDER = tuple(RULE_LABELS)
PRIMARY_GAMMA = 1.1
PRIMARY_BUDGET = 8000
PRIMARY_ALLOCATION = "targeted_floor_0.15"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} is not a JSON object")
    return value


def pct(value: float | None) -> str:
    if value is None:
        return "NA"
    return f"{100.0 * value:.1f}\\%"


def count_ratio(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "--"
    return f"{numerator}/{denominator}"


def summarize_rule_rows(cap8: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, int]] = defaultdict(
        lambda: {"deploy": 0, "viol": 0, "oracle": 0}
    )
    for row in cap8["summaries"]:
        if (
            abs(float(row["requested_gamma"]) - PRIMARY_GAMMA) > 1e-12
            or int(row["total_budget"]) != PRIMARY_BUDGET
            or str(row["allocation"]) != PRIMARY_ALLOCATION
        ):
            continue
        group = grouped[str(row["rule"])]
        group["deploy"] += int(row["deployment_count"])
        group["viol"] += int(row["violation_count"])
        group["oracle"] += int(row["oracle_opportunity_count"])
    return [{"rule": rule, **grouped[rule]} for rule in RULE_ORDER]


def followup_results_table(rule_rows: list[dict[str, Any]], primary: Mapping[str, Any]) -> str:
    vector_radius = primary["common_radius_distribution_on_vector_deployments"]
    radius_text = {
        "vera_vector_envelope": f"{float(vector_radius['median']):.2f}",
    }
    rows = []
    for row in rule_rows:
        safe = int(row["deploy"]) - int(row["viol"])
        oracle = int(row["oracle"])
        retention = None if oracle == 0 else safe / oracle
        deployed = int(row["deploy"])
        violations = int(row["viol"])
        violation_rate = None if deployed == 0 else violations / deployed
        rows.append(
            " & ".join(
                [
                    RULE_LABELS[str(row["rule"])],
                    f"{deployed}/256 ({pct(deployed / 256)})",
                    f"{count_ratio(violations, deployed)} ({pct(violation_rate)})",
                    f"{safe}/{oracle} ({pct(retention)})",
                    radius_text.get(str(row["rule"]), "NA"),
                ]
            )
            + r" \\"
        )
    return (
        "\\begin{table*}[t]\n"
        "\\centering\n"
        "\\small\n"
        "\\begin{tabular}{@{}lrrrr@{}}\n"
        "\\toprule\n"
        "Rule & Deployments & Viol./deployed & Safe retention & Median radius \\\\\n"
        "\\midrule\n"
        + "\n".join(rows)
        + "\n\\bottomrule\n"
        "\\end{tabular}\n"
        "\\caption{Independent post-failure controlled-shift follow-up at "
        "$\\Gamma=1.1$, budget 8,000, and targeted allocation with a 15\\% "
        "evidence floor. Safe retention is retained oracle-safe opportunities "
        "over all oracle-safe opportunities. Unlike the first 64-seed primary, "
        "this independently locked follow-up passes every registered gate.}\n"
        "\\label{tab:controlled-followup}\n"
        "\\end{table*}\n"
    )


def aggregate_budget_rows(cap8: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], dict[str, int]] = defaultdict(
        lambda: {"deploy": 0, "viol": 0, "safe": 0, "oracle": 0}
    )
    for row in cap8["summaries"]:
        if abs(float(row["requested_gamma"]) - PRIMARY_GAMMA) > 1e-12:
            continue
        if row["rule"] not in {"vera_vector_envelope", "vera_common_radius"}:
            continue
        key = (str(row["allocation"]), int(row["total_budget"]), str(row["rule"]))
        grouped[key]["deploy"] += int(row["deployment_count"])
        grouped[key]["viol"] += int(row["violation_count"])
        grouped[key]["safe"] += int(row["deployment_count"]) - int(row["violation_count"])
        grouped[key]["oracle"] += int(row["oracle_opportunity_count"])
    output: list[dict[str, Any]] = []
    for allocation in ("targeted_floor_0.15", "uniform"):
        for budget in (1000, 2000, 4000, 8000):
            output.append(
                {
                    "allocation": allocation,
                    "budget": budget,
                    "vector": dict(grouped[(allocation, budget, "vera_vector_envelope")]),
                    "common": dict(grouped[(allocation, budget, "vera_common_radius")]),
                }
            )
    return output


def followup_budget_table(rows: list[dict[str, Any]]) -> str:
    table_rows = []
    for row in rows:
        allocation = "targeted" if row["allocation"] == "targeted_floor_0.15" else "uniform"
        vector = row["vector"]
        common = row["common"]
        vector_retention = None if not vector["oracle"] else vector["safe"] / vector["oracle"]
        common_retention = None if not common["oracle"] else common["safe"] / common["oracle"]
        table_rows.append(
            f"{allocation} & {row['budget']:,} & "
            f"{vector['safe']}/{vector['oracle']} ({pct(vector_retention)}) & "
            f"{count_ratio(vector['viol'], vector['deploy'])} & "
            f"{common['safe']}/{common['oracle']} ({pct(common_retention)}) \\\\"
        )
    return (
        "\\begin{table}[t]\n"
        "\\centering\n"
        "\\small\n"
        "\\begin{tabular}{@{}lrrrr@{}}\n"
        "\\toprule\n"
        "Allocation & Budget & Vector retention & Vector viol. & Common retention \\\\\n"
        "\\midrule\n"
        + "\n".join(table_rows)
        + "\n\\bottomrule\n"
        "\\end{tabular}\n"
        "\\caption{Follow-up evidence-size sensitivity at $\\Gamma=1.1$. The "
        "primary follow-up point is budget 8,000 with targeted allocation; other "
        "rows are reported as sensitivity analyses.}\n"
        "\\label{tab:controlled-followup-budget}\n"
        "\\end{table}\n"
    )


def budget_figure(rows: list[dict[str, Any]], output_stem: Path) -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 8,
            "axes.labelsize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    colors = {"vector": "#0072B2", "common": "#D55E00"}
    markers = {"targeted_floor_0.15": "o", "uniform": "s"}
    labels = {
        ("targeted_floor_0.15", "vector"): "vector, targeted",
        ("targeted_floor_0.15", "common"): "common, targeted",
        ("uniform", "vector"): "vector, uniform",
        ("uniform", "common"): "common, uniform",
    }
    fig, ax = plt.subplots(figsize=(3.5, 2.45), constrained_layout=True)
    for allocation in ("targeted_floor_0.15", "uniform"):
        subset = [row for row in rows if row["allocation"] == allocation]
        for rule in ("vector", "common"):
            x = [row["budget"] for row in subset]
            y = [
                row[rule]["safe"] / row[rule]["oracle"] if row[rule]["oracle"] else 0.0
                for row in subset
            ]
            ax.plot(
                x,
                y,
                color=colors[rule],
                marker=markers[allocation],
                linestyle="-" if allocation == "targeted_floor_0.15" else "--",
                linewidth=1.5,
                markersize=4,
                label=labels[(allocation, rule)],
            )
    ax.axhline(0.20, color="#666666", linewidth=1.0, linestyle=":", label="gate")
    ax.scatter([8000], [59 / 183], s=58, facecolors="none", edgecolors="#000000", zorder=5)
    ax.set_xscale("log", base=2)
    ax.set_xticks([1000, 2000, 4000, 8000])
    ax.set_xticklabels(["1k", "2k", "4k", "8k"])
    ax.set_ylim(0.0, 0.42)
    ax.set_xlabel("Certification budget")
    ax.set_ylabel("Safe retention")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_stem.with_suffix(".pdf"))
    fig.savefig(output_stem.with_suffix(".png"), dpi=300)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--cap8", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    comparison = load_json(args.comparison)
    cap8 = load_json(args.cap8)
    primary = comparison["primary_setting"]
    rule_rows = summarize_rule_rows(cap8)
    budget_rows = aggregate_budget_rows(cap8)
    author_kit = repo / "research/maintrack/aaai2027_template/AuthorKit27"
    figures = repo / "research/maintrack/figures"
    (author_kit / "vera_followup_results_table.tex").write_text(
        followup_results_table(rule_rows, primary), encoding="utf-8"
    )
    (author_kit / "vera_followup_budget_table.tex").write_text(
        followup_budget_table(budget_rows), encoding="utf-8"
    )
    budget_figure(budget_rows, figures / "vera_controlled_shift_followup_budget_curve")
    summary = {
        "schema_version": 1,
        "name": "VERA controlled-shift follow-up paper summary",
        "analysis_status": "complete_independent_followup_success",
        "first_primary_status": "complete_primary_mixed_failed_usefulness",
        "followup_may_rescue_or_pool_first_primary": False,
        "overall_confirmatory_success": bool(primary["overall_confirmatory_success"]),
        "comparison_sha256": sha256(args.comparison),
        "cap8_sha256": sha256(args.cap8),
        "primary_inference": primary,
        "primary_rule_results": rule_rows,
        "budget_sensitivity_gamma_1_1": budget_rows,
    }
    summary_path = repo / "research/maintrack/CONTROLLED_SHIFT_FOLLOWUP_RESULT_SUMMARY.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "exported_followup",
                "summary": str(summary_path),
                "results_table": str(author_kit / "vera_followup_results_table.tex"),
                "budget_table": str(author_kit / "vera_followup_budget_table.tex"),
                "figure_pdf": str(figures / "vera_controlled_shift_followup_budget_curve.pdf"),
                "figure_png": str(figures / "vera_controlled_shift_followup_budget_curve.png"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
