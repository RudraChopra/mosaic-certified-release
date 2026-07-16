"""Export paper-facing controlled-shift artifacts from sealed analyses."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping

import matplotlib.pyplot as plt


MACROS = (
    "ControlledShiftAbstractResult",
    "ControlledPrimaryResult",
    "ControlledSafetyResult",
    "ControlledRetentionResult",
    "ControlledAllocationResult",
    "ControlledEvidenceResult",
    "ControlledGaitResult",
    "ControlledHeldoutResult",
    "ControlledNegativeResults",
    "ControlledMainResultTable",
    "ControlledMainResultFigure",
)

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


def frac(field: Mapping[str, Any]) -> str:
    estimate = field.get("estimate")
    return f"{int(field['numerator'])}/{int(field['denominator'])} ({pct(estimate)})"


def compact_frac(field: Mapping[str, Any]) -> str:
    estimate = field.get("estimate")
    return f"{int(field['numerator'])}/{int(field['denominator'])} ({pct(estimate)})"


def main_results_table(sensitivity: Mapping[str, Any]) -> str:
    rows = []
    for row in sensitivity["rule_results"]:
        label = RULE_LABELS[str(row["rule"])]
        radius = row["common_radius"]
        radius_text = "NA" if radius["median"] is None else f"{float(radius['median']):.2f}"
        rows.append(
            " & ".join(
                [
                    label,
                    frac(row["deployments"]),
                    frac(row["violations_deployed"]),
                    frac(row["retained_opportunities"]),
                    radius_text,
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
        "\\caption{Primary controlled-shift results at $\\Gamma=1.1$, budget 4,000, "
        "and targeted allocation with a 15\\% evidence floor. Safe retention is "
        "retained oracle-safe opportunities over all oracle-safe opportunities. "
        "The primary result is mixed: VERA has zero deployed violations, but "
        "the preregistered usefulness lower bound is below the 20\\% gate.}\n"
        "\\label{tab:controlled-main}\n"
        "\\end{table*}\n"
    )


def aggregate_budget_rows(cap8: Mapping[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int, str], dict[str, int]] = defaultdict(
        lambda: {"deploy": 0, "viol": 0, "safe": 0, "oracle": 0}
    )
    for row in cap8["summaries"]:
        if abs(float(row["requested_gamma"]) - 1.1) > 1e-12:
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
            vector = grouped[(allocation, budget, "vera_vector_envelope")]
            common = grouped[(allocation, budget, "vera_common_radius")]
            output.append(
                {
                    "allocation": allocation,
                    "budget": budget,
                    "vector": dict(vector),
                    "common": dict(common),
                }
            )
    return output


def budget_table(rows: list[dict[str, Any]]) -> str:
    table_rows = []
    for row in rows:
        allocation = "targeted" if row["allocation"] == "targeted_floor_0.15" else "uniform"
        vector = row["vector"]
        common = row["common"]
        vector_retention = vector["safe"] / vector["oracle"] if vector["oracle"] else None
        common_retention = common["safe"] / common["oracle"] if common["oracle"] else None
        table_rows.append(
            f"{allocation} & {row['budget']:,} & "
            f"{vector['safe']}/{vector['oracle']} ({pct(vector_retention)}) & "
            f"{vector['viol']}/{vector['deploy']} & "
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
        "\\caption{Preregistered secondary evidence-size sensitivity at $\\Gamma=1.1$. "
        "These rows do not replace the failed primary usefulness gate. They show "
        "that retention increases with more certification evidence while deployed "
        "VERA vector-envelope violations remain zero in these settings.}\n"
        "\\label{tab:controlled-budget}\n"
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
        for rule in ("vector", "common"):
            subset = [row for row in rows if row["allocation"] == allocation]
            x = [row["budget"] for row in subset]
            y = [
                row[rule]["safe"] / row[rule]["oracle"] if row[rule]["oracle"] else 0.0
                for row in subset
            ]
            line_style = "-" if allocation == "targeted_floor_0.15" else "--"
            ax.plot(
                x,
                y,
                color=colors[rule],
                marker=markers[allocation],
                linestyle=line_style,
                linewidth=1.5,
                markersize=4,
                label=labels[(allocation, rule)],
            )
    ax.axhline(0.20, color="#666666", linewidth=1.0, linestyle=":", label="primary gate")
    ax.scatter([4000], [38 / 187], s=58, facecolors="none", edgecolors="#000000", zorder=5)
    ax.set_xscale("log", base=2)
    ax.set_xticks([1000, 2000, 4000, 8000])
    ax.set_xticklabels(["1k", "2k", "4k", "8k"])
    ax.set_ylim(0.0, 0.32)
    ax.set_xlabel("Certification budget")
    ax.set_ylabel("Safe retention")
    ax.legend(frameon=False, ncol=2, loc="upper left")
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_stem.with_suffix(".pdf"))
    fig.savefig(output_stem.with_suffix(".png"), dpi=300)
    plt.close(fig)


def format_macro(value: str) -> str:
    return " ".join(value.strip().split())


def macro_block(macros: Mapping[str, str]) -> str:
    return "\n".join(
        f"\\providecommand{{\\{name}}}{{{format_macro(macros[name])}}}"
        for name in MACROS
    ) + "\n"


def replace_macros(path: Path, macros: Mapping[str, str]) -> None:
    text = path.read_text(encoding="utf-8")
    for name in MACROS:
        pattern = re.compile(
            rf"^\\providecommand\{{\\{re.escape(name)}\}}\{{.*\}}$",
            flags=re.MULTILINE,
        )
        replacement = f"\\providecommand{{\\{name}}}{{{format_macro(macros[name])}}}"
        text, count = pattern.subn(lambda _match: replacement, text, count=1)
        if count != 1:
            raise RuntimeError(f"did not replace {name} in {path}")
    path.write_text(text, encoding="utf-8")


def wrapper_title_update(path: Path) -> None:
    replacements = {
        "VERAPaperPDFTitle": (
            "VERA: Support-Aware Certification of Representation Edits "
            "Under Deployment Shift"
        ),
        "VERAPaperDisplayTitle": (
            "VERA: Support-Aware Certification of Representation Edits\\\\"
            "Under Deployment Shift"
        ),
        "VERAPaperPDFSubject": (
            "Support-aware certification of representation edits under deployment shift"
        ),
    }
    text = path.read_text(encoding="utf-8")
    for name, value in replacements.items():
        pattern = re.compile(
            rf"^\\providecommand\{{\\{name}\}}\{{.*\}}$",
            flags=re.MULTILINE,
        )
        replacement = f"\\providecommand{{\\{name}}}{{{value}}}"
        text, count = pattern.subn(lambda _match: replacement, text, count=1)
        if count != 1:
            raise RuntimeError(f"did not update title macro {name} in {path}")
    path.write_text(text, encoding="utf-8")


def build_macros(
    primary: Mapping[str, Any],
    sensitivity: Mapping[str, Any],
    *,
    table_prefix: str,
    figure_path: str,
) -> dict[str, str]:
    safety = primary["safety"]
    usefulness = primary["usefulness"]
    reduction = primary["paired_reduction"]
    advantage = primary["vector_advantage"]
    heldout = primary["heldout_attacker_stress"]
    effects = primary["effect_sizes"]["point_estimates"]
    intervals = primary["effect_sizes"]["confidence_intervals_95"]
    threshold = sensitivity["threshold_stress"]["readiness"]
    retention_ci = usefulness["confidence_interval_95"]
    ratio_ci = advantage["confidence_interval_95"]
    vector_rule = next(
        row for row in sensitivity["rule_results"] if row["rule"] == "vera_vector_envelope"
    )
    gait = next(row for row in vector_rule["per_dataset"] if row["dataset"] == "GaitPDB")
    primary_miss = (
        "The primary controlled-shift result is mixed, not a confirmatory pass: "
        f"validation selection violated 19/186 deployed decisions, whereas the VERA "
        f"vector envelope deployed 38 edits with 0 violations; the paired sign test "
        f"favored VERA ({reduction['favorable_seed_clusters']} favorable, "
        f"{reduction['adverse_seed_clusters']} adverse, "
        f"$p={reduction['exact_two_sided_p']:.2g}$), "
        f"but the preregistered usefulness gate failed because safe retention was "
        f"38/187 ({pct(effects['vector_safe_retention'])}) with 95\\% seed-bootstrap "
        f"CI [{pct(retention_ci[0])}, {pct(retention_ci[1])}], whose lower endpoint "
        "is below 20\\%."
    )
    return {
        "ControlledShiftAbstractResult": (
            "In the prospectively registered controlled-shift study, VERA made "
            "38 deployments with 0 shifted-contract violations, while validation "
            "selection violated 19/186 deployed decisions. The result is not an "
            "overall confirmatory success because the preregistered usefulness "
            "lower bound was 15.1\\%, below the 20\\% gate."
        ),
        "ControlledPrimaryResult": primary_miss,
        "ControlledSafetyResult": (
            f"The registered rotating-sentinel safety gate passed with "
            f"{safety['sentinel_event_count']}/{safety['sentinel_decision_count']} "
            f"false acceptances and a one-sided 95\\% Clopper--Pearson upper bound "
            f"of {pct(safety['one_sided_cp95_upper'])}. Across all primary VERA "
            "vector deployments, shifted-law violations were 0/38."
        ),
        "ControlledRetentionResult": (
            f"Safe retention was 38/187 ({pct(effects['vector_safe_retention'])}), "
            f"below the registered lower-bound requirement, while the common-radius "
            f"rule retained 6/187 ({pct(effects['common_safe_retention'])}); the "
            f"vector/common ratio was {advantage['point_ratio']:.2f} with 95\\% "
            f"interval [{ratio_ci[0]:.1f}, {ratio_ci[1]:.1f}], so the vector "
            "advantage gate passed even though usefulness did not."
        ),
        "ControlledAllocationResult": (
            "The preregistered secondary evidence-size sweep shows higher retention "
            "at larger budgets: at $\\Gamma=1.1$ and budget 8,000, the vector rule "
            "retained 49/187 targeted-allocation opportunities and 51/187 uniform-"
            "allocation opportunities with zero deployed violations. These "
            "secondary rows do not replace the failed primary gate."
        ),
        "ControlledEvidenceResult": (
            "The primary geometry shows a narrow supported envelope: among 38 "
            "vector deployments, the median common radius was 1.030, with range "
            "[1.001, 1.182]. The most frequent limiting coordinate was "
            "target::environment=0 (27 of 38 deployments), followed by source::0."
        ),
        "ControlledGaitResult": (
            f"GaitPDB was not an all-abstain failure: the vector rule deployed "
            f"{gait['deployments']['numerator']}/64 seeds and retained "
            f"{gait['retained_opportunities']['numerator']}/"
            f"{gait['retained_opportunities']['denominator']} oracle-safe "
            "opportunities with zero deployed violations, but its result remains "
            "secondary and cannot rescue the primary usefulness miss."
        ),
        "ControlledHeldoutResult": (
            f"The held-out boosted-tree stress is outside the formal registered "
            f"attacker guarantee: it found {heldout['heldout_violation_count']} "
            f"violations among {heldout['all_vector_deployment_count']} vector "
            f"deployments ({pct(1.0 - heldout['heldout_safe_fraction'])} unsafe), "
            "so the paper reports it as portfolio-scope stress rather than as a "
            "coverage claim."
        ),
        "ControlledNegativeResults": (
            f"The failed usefulness gate is mandatory negative evidence. The "
            f"threshold-stress headline is therefore ineligible despite severe "
            f"naive failures at $\\kappa=1$ (always deploy max "
            f"{pct(threshold['always_deploy_max_registered_rate'])}, validation "
            f"selection max {pct(threshold['validation_selection_max_registered_rate'])}) "
            "and VERA's measured 0.0\\% violation rate in every stress cell. No "
            "secondary budget, held-out attacker, or dataset-specific result is "
            "promoted to a primary success."
        ),
        "ControlledMainResultTable": (
            f"\\input{{{table_prefix}vera_main_results_table}}"
            f"\\input{{{table_prefix}vera_controlled_budget_table}}"
        ),
        "ControlledMainResultFigure": (
            "\\begin{figure}[t]\\centering"
            f"\\includegraphics[width=\\columnwidth]{{{figure_path}}}"
            "\\caption{Preregistered secondary evidence-size sensitivity at "
            "$\\Gamma=1.1$. The circled point is the locked primary vector rule "
            "(budget 4,000, targeted allocation), which missed the 20\\% usefulness "
            "lower-bound gate despite zero violations. Higher budgets improve "
            "descriptive retention but do not replace the primary result.}"
            "\\label{fig:controlled-budget}\\end{figure}"
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", type=Path, required=True)
    parser.add_argument("--cap8", type=Path, required=True)
    parser.add_argument("--sensitivity", type=Path, required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo = args.repo.resolve()
    comparison = load_json(args.comparison)
    cap8 = load_json(args.cap8)
    sensitivity = load_json(args.sensitivity)
    first_read = comparison["scientific_first_read"]["authoritative_cap8_primary_inference"]
    author_kit = repo / "research/maintrack/aaai2027_template/AuthorKit27"
    figures = repo / "research/maintrack/figures"
    budget_rows = aggregate_budget_rows(cap8)
    (author_kit / "vera_main_results_table.tex").write_text(
        main_results_table(sensitivity), encoding="utf-8"
    )
    (author_kit / "vera_controlled_budget_table.tex").write_text(
        budget_table(budget_rows), encoding="utf-8"
    )
    budget_figure(budget_rows, figures / "vera_controlled_shift_budget_curve")
    summary = {
        "schema_version": 1,
        "name": "VERA controlled-shift paper summary",
        "analysis_status": "complete_primary_mixed",
        "overall_confirmatory_success": bool(first_read["overall_confirmatory_success"]),
        "failed_primary_gates": ["usefulness"],
        "comparison_sha256": sha256(args.comparison),
        "cap8_sha256": sha256(args.cap8),
        "sensitivity_sha256": sha256(args.sensitivity),
        "primary_inference": first_read,
        "primary_rule_results": sensitivity["rule_results"],
        "budget_sensitivity_gamma_1_1": budget_rows,
    }
    summary_path = repo / "research/maintrack/CONTROLLED_SHIFT_RESULT_SUMMARY.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    shared_macros = build_macros(
        first_read,
        sensitivity,
        table_prefix="",
        figure_path="../../figures/vera_controlled_shift_budget_curve.pdf",
    )
    (author_kit / "vera_shared_controlled_results.tex").write_text(
        "\\renewcommand{\\VERAPaperPDFTitle}{VERA: Support-Aware Certification of "
        "Representation Edits Under Deployment Shift}\n"
        "\\renewcommand{\\VERAPaperDisplayTitle}{VERA: Support-Aware Certification "
        "of Representation Edits\\\\Under Deployment Shift}\n"
        "\\renewcommand{\\VERAPaperPDFSubject}{Support-aware certification of "
        "representation edits under deployment shift}\n"
        + macro_block(shared_macros),
        encoding="utf-8",
    )
    for wrapper in (
        author_kit / "vera_aaai2027_anonymous.tex",
        author_kit / "vera_aaai2027_named.tex",
    ):
        wrapper_title_update(wrapper)
    replace_macros(
        author_kit / "vera_paper_body.tex",
        shared_macros,
    )
    variant_macros = build_macros(
        first_read,
        sensitivity,
        table_prefix="../aaai2027_template/AuthorKit27/",
        figure_path="../figures/vera_controlled_shift_budget_curve.pdf",
    )
    replace_macros(
        repo / "research/maintrack/venue_variants/ICLR_2027_SCIENTIFIC_CONTENT.tex",
        variant_macros,
    )
    replace_macros(
        repo / "research/maintrack/venue_variants/NEURIPS_2027_SCIENTIFIC_CONTENT.tex",
        variant_macros,
    )
    print(
        json.dumps(
            {
                "status": "exported",
                "summary": str(summary_path),
                "main_table": str(author_kit / "vera_main_results_table.tex"),
                "budget_table": str(author_kit / "vera_controlled_budget_table.tex"),
                "figure_pdf": str(figures / "vera_controlled_shift_budget_curve.pdf"),
                "figure_png": str(figures / "vera_controlled_shift_budget_curve.png"),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
