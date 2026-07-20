#!/usr/bin/env python3
"""Audit the complementary direct-region/bridge-rejection stress cell."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np

from mosaic_real import sha256
from run_mosaic_bridge_misspecification import scenario_registry


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_REPORT = REPOSITORY / "research/artifacts/mosaic_bridge_misspecification_v1.json"
DEFAULT_SPEC = ROOT / "MOSAIC_SYMMETRIC_SCOPE_STRESS_SPEC.md"
DEFAULT_OUTPUT = REPOSITORY / "research/artifacts/mosaic_symmetric_scope_stress_v1.json"
INVALID_SCENARIOS = ("underdeclared_contamination", "source_specific_transform")
TOLERANCE = 1e-10


def direct_target_region_status(
    target_law: np.ndarray,
    target_empirical: np.ndarray,
    target_radii: np.ndarray,
) -> tuple[bool, float]:
    """Return rowwise direct-region membership and its largest excess."""

    distances = np.abs(target_law - target_empirical).sum(axis=2)
    excess = float(np.max(distances - target_radii))
    return bool(excess <= TOLERANCE), excess


def atomic_json_dump(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not args.spec.is_file():
        raise FileNotFoundError(args.spec)
    targets = {scenario.name: np.asarray(scenario.target, dtype=np.float64) for scenario in scenario_registry()}
    if not set(INVALID_SCENARIOS).issubset(targets):
        raise RuntimeError("invalid scenario registry changed")
    minimum_retained = float(report["minimum_retained_mass"])
    rows = [
        row
        for row in report["replicate_results"]
        if str(row["scenario"]) in INVALID_SCENARIOS
    ]
    if len(rows) != 8000:
        raise RuntimeError(f"expected 8,000 invalid rows, found {len(rows)}")

    totals: Counter[str] = Counter()
    by_scenario: dict[str, Counter[str]] = {}
    maximum_excess_inside = -np.inf
    maximum_excess_all = -np.inf
    for row in rows:
        scenario = str(row["scenario"])
        target = targets[scenario]
        inside_direct_region, excess = direct_target_region_status(
            target,
            np.asarray(row["target_empirical"], dtype=np.float64),
            np.asarray(row["target_radii"], dtype=np.float64),
        )
        outside_bridge = bool(
            float(row["population_minimum_retained_mass"])
            < minimum_retained - TOLERANCE
        )
        mosaic_abstains = not bool(row["accepted_membership"])
        counters = by_scenario.setdefault(scenario, Counter())
        for current in (totals, counters):
            current["invalid_rows"] += 1
            current["direct_region_events"] += int(inside_direct_region)
            current["bridge_violations"] += int(outside_bridge)
            current["mosaic_abstentions"] += int(mosaic_abstains)
            current["direct_region_bridge_violations"] += int(
                inside_direct_region and outside_bridge
            )
            current["direct_region_mosaic_abstentions"] += int(
                inside_direct_region and mosaic_abstains
            )
            current["direct_region_validated_scope_rows"] += int(
                inside_direct_region and outside_bridge and mosaic_abstains
            )
        maximum_excess_all = max(maximum_excess_all, excess)
        if inside_direct_region:
            maximum_excess_inside = max(maximum_excess_inside, excess)

    summary = {key: int(value) for key, value in totals.items()}
    pass_conditions = {
        "all_invalid_rows_retained": summary["invalid_rows"] == 8000,
        "all_invalid_rows_violate_declared_bridge": summary["bridge_violations"]
        == summary["invalid_rows"],
        "mosaic_abstains_on_every_invalid_row": summary["mosaic_abstentions"]
        == summary["invalid_rows"],
        "every_direct_region_event_is_out_of_class_and_abstained": summary[
            "direct_region_validated_scope_rows"
        ]
        == summary["direct_region_events"],
    }
    payload = {
        "name": "MOSAIC symmetric direct-region bridge-rejection scope stress v1",
        "status": "complete" if all(pass_conditions.values()) else "failed",
        "pass": all(pass_conditions.values()),
        "analysis_status": "post-review deterministic analysis of a prelocked 12,000-table study",
        "claim_boundary": (
            "This audit does not claim a failure of direct target-table certification. "
            "It verifies that prelocked bridge-invalid target laws can fall inside "
            "the direct target region, while the MOSAIC membership gate abstains."
        ),
        "source_report": str(args.report.relative_to(REPOSITORY)),
        "source_report_sha256": sha256(args.report),
        "specification": str(args.spec.relative_to(REPOSITORY)),
        "specification_sha256": sha256(args.spec),
        "minimum_retained_mass": minimum_retained,
        "invalid_scenarios": list(INVALID_SCENARIOS),
        "summary": summary,
        "by_scenario": {
            name: {key: int(value) for key, value in values.items()}
            for name, values in sorted(by_scenario.items())
        },
        "maximum_l1_excess_over_direct_region_all_rows": maximum_excess_all,
        "maximum_l1_excess_over_direct_region_among_events": maximum_excess_inside,
        "pass_conditions": pass_conditions,
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps({"output": str(args.output), "pass": payload["pass"], "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
