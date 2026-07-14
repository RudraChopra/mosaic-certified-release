"""Generate and hash the fixed VERA independent stress-replication preregistration."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PARENT = ROOT / "prereg_confirmatory_balanced.json"
DEFAULT_DESIGN = ROOT / "artifacts" / "vera_independent_stress_design.json"
DEFAULT_OUTPUT = ROOT / "prereg_independent_stress_replication.json"
DEFAULT_HASH = ROOT / "prereg_independent_stress_replication.sha256"
REPLICATION_SEEDS = list(range(13, 45))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT.parent,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()


def selected_contracts(design: dict[str, Any]) -> dict[str, dict[str, float]]:
    contracts: dict[str, dict[str, float]] = {}
    datasets = design.get("datasets", {})
    if not isinstance(datasets, dict):
        raise RuntimeError("design report has no dataset records")
    for dataset, record in sorted(datasets.items()):
        if not isinstance(record, dict):
            raise RuntimeError(f"invalid design record: {dataset}")
        if record.get("selection_passed_minimum_design_criteria") is not True:
            raise RuntimeError(f"design criteria failed: {dataset}")
        regime = record.get("selected_regime", {})
        contracts[str(dataset)] = {
            "target_harm_threshold": float(regime["target_threshold"]),
            "balanced_leakage_threshold": float(regime["leakage_threshold"]),
            "design_point_violation_rate": float(regime["point_violation_rate"]),
            "design_vera_violation_rate": float(regime["vera_violation_rate"]),
            "design_vera_safe_retention": float(regime["vera_safe_retention"]),
        }
    expected = {"Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB"}
    if set(contracts) != expected:
        raise RuntimeError("design contracts do not cover the four supported datasets")
    return contracts


def build(
    parent: dict[str, Any],
    design: dict[str, Any],
    parent_path: Path,
    design_path: Path,
) -> dict[str, Any]:
    study = copy.deepcopy(parent["real_study"])
    contracts = selected_contracts(design)
    study["seeds"] = REPLICATION_SEEDS
    study["validation_fractions"] = [1.0]
    study["primary_validation_fraction"] = 1.0
    study["target_harm_thresholds"] = sorted(
        {value["target_harm_threshold"] for value in contracts.values()}
    )
    study["leakage_thresholds"] = sorted(
        {value["balanced_leakage_threshold"] for value in contracts.values()}
    )
    study["threshold_pair_count"] = len(contracts)
    study["locked_dataset_contracts"] = contracts
    study["headline_stress_family"] = {
        "source": "deterministic design on seeds 5-12, frozen before seeds 13-44",
        "regimes": [
            {
                "dataset": dataset,
                "target_harm_threshold": values["target_harm_threshold"],
                "balanced_leakage_threshold": values[
                    "balanced_leakage_threshold"
                ],
            }
            for dataset, values in sorted(contracts.items())
        ],
    }
    study["analysis_tiers"] = {
        "primary": (
            "one locked full-certification contract per supported dataset on "
            "seeds 13-44"
        ),
        "support_boundary": (
            "Camelyon17-WILDS must remain nonestimable and force VERA abstention"
        ),
    }
    study["statistical_tests"] = {
        "unit": "algorithmic seed; one paired binary outcome per supported dataset",
        "primary": (
            "exact one-sided paired McNemar test, equivalent to a binomial sign "
            "test on point-only versus VERA-only external contract violations"
        ),
        "multiplicity": "Holm correction over four externally estimable datasets",
        "familywise_alpha": 0.05,
        "minimum_clean_point_only_discordances_for_four_way_holm": 7,
        "stopping_rule": (
            "run all 32 seeds; no interim testing, optional stopping, seed removal, "
            "or threshold changes"
        ),
    }
    study["pass_conditions"] = {
        "point_selection_violation_rate_each_supported_dataset": ">= 0.20",
        "vera_measured_violation_rate_each_supported_dataset": "<= 0.05",
        "holm_adjusted_mcnemar_each_supported_dataset": "<= 0.05",
        "minimum_supported_datasets_passing_all_three": 4,
        "global_vera_violation_rate": "<= 0.05",
        "camelyon_forced_abstention": "all registered configurations",
        "report_certification_tax": True,
    }
    return {
        "project": "VERA",
        "phase": "independent disjoint-seed stress replication",
        "status": "locked_before_claim_grade_runs",
        "locked_date": date.today().isoformat(),
        "parent_confirmatory_prereg_sha256": sha256(parent_path),
        "design_report": {
            "path": str(design_path.relative_to(ROOT.parent)),
            "sha256": sha256(design_path),
            "committed_at": git_head(),
            "analysis_tier": design.get("analysis_tier"),
            "design_data_seeds": design.get("design_data_seeds"),
        },
        "primary_claim": (
            "At the four dataset-specific contracts selected on disjoint design "
            "seeds, point selection violates external contracts in at least 20% "
            "of replication seeds while VERA remains at or below delta, with "
            "Holm-corrected paired significance on all four supported datasets."
        ),
        "real_study": study,
        "data_policy": {
            "design_seeds": list(range(5, 13)),
            "replication_seeds": REPLICATION_SEEDS,
            "disjoint": True,
            "external_outcomes_may_not_change_contracts": True,
            "all_outcomes_reported": True,
        },
        "claim_boundary": (
            "The replication may fail. A failed dataset or multiplicity condition "
            "remains failed; it may not be replaced by a post-hoc contract, seed "
            "subset, attacker subset, or alternate test."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=DEFAULT_PARENT)
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    parent = load_json(args.parent)
    design = load_json(args.design)
    if design.get("passed") is not True:
        raise RuntimeError("stress-design report did not pass")
    if design.get("future_replication_must_use_disjoint_seeds") is not True:
        raise RuntimeError("design report does not require disjoint replication")
    prereg = build(parent, design, args.parent, args.design)
    args.output.write_text(
        json.dumps(prereg, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    digest = sha256(args.output)
    args.hash_file.write_text(f"{digest}  {args.output.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": True,
                "output": str(args.output),
                "sha256": digest,
                "seed_count": len(REPLICATION_SEEDS),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
