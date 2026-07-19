#!/usr/bin/env python3
"""Build the revision evidence table from audited MOSAIC artifacts.

This is a descriptive, post-outcome aggregation. It never changes a locked
decision and it keeps the direct target-table rule distinct from the bridge
certificate, since the two rules certify different law classes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np


PRIMARY_THRESHOLD = "0.40"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def outcome(selection: dict[str, Any]) -> dict[str, int]:
    deployed = selection.get("decision") == "deploy"
    estimable = deployed and bool(selection.get("diagnostic_estimable"))
    violation = estimable and bool(selection.get("false_acceptance"))
    return {
        "deployments": int(deployed),
        "estimable_deployments": int(estimable),
        "diagnostic_violations": int(violation),
    }


def summarize_direct_target(directory: Path) -> dict[str, Any]:
    paths = sorted(directory.glob("*.json"))
    if len(paths) != 100:
        raise ValueError("direct target comparator requires exactly 100 receipts")
    grouped: dict[str, list[dict[str, int]]] = defaultdict(list)
    for path in paths:
        payload = load(path)
        selection = payload.get("selection_by_utility_threshold", {}).get(PRIMARY_THRESHOLD)
        if not isinstance(selection, dict):
            raise ValueError(f"{path} lacks the primary direct-target decision")
        grouped[str(payload["dataset"])].append(outcome(selection))
    summary: dict[str, Any] = {}
    for dataset, rows in grouped.items():
        summary[dataset] = {
            "jobs": len(rows),
            **{key: sum(row[key] for row in rows) for key in rows[0]},
        }
    summary["all_datasets"] = {
        "jobs": sum(value["jobs"] for value in summary.values()),
        "deployments": sum(value["deployments"] for value in summary.values()),
        "estimable_deployments": sum(
            value["estimable_deployments"] for value in summary.values()
        ),
        "diagnostic_violations": sum(
            value["diagnostic_violations"] for value in summary.values()
        ),
    }
    return dict(sorted(summary.items()))


def summarize_bridge_strata(directory: Path) -> dict[str, Any]:
    paths = sorted(directory.glob("*.json"))
    if len(paths) != 100:
        raise ValueError("bridge strata require exactly 100 raw receipts")
    grouped: dict[str, list[list[int]]] = defaultdict(list)
    for path in paths:
        payload = load(path)
        rows = payload.get("results")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"{path} has no candidate rows")
        counts = rows[0].get("bridge_stratum_counts")
        if not isinstance(counts, list):
            raise ValueError(f"{path} lacks bridge stratum counts")
        flattened = [int(value) for source in counts for value in source]
        if any(
            [int(value) for source in row.get("bridge_stratum_counts", []) for value in source]
            != flattened
            for row in rows
        ):
            raise ValueError(f"{path} candidates disagree on bridge counts")
        grouped[str(payload["dataset"])].append(flattened)
    result: dict[str, Any] = {}
    for dataset, tables in grouped.items():
        if any(table != tables[0] for table in tables[1:]):
            raise ValueError(f"{dataset} has seed-dependent bridge count tables")
        values = tables[0]
        result[dataset] = {
            "source_label_strata": len(values),
            "counts": values,
            "minimum": min(values),
            "maximum": max(values),
            "median": float(np.median(values)),
        }
    return dict(sorted(result.items()))


def summarize_utility(report: dict[str, Any]) -> dict[str, Any]:
    rows = report.get("results")
    if not isinstance(rows, list) or len(rows) != 23:
        raise ValueError("utility report must contain the 23 selected releases")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        reconstruction = row.get("reconstruction", {})
        if reconstruction.get("diagnostic_token_count_receipt_match") is not True:
            raise ValueError("utility report includes an unmatched diagnostic table")
        grouped[str(row["dataset"])].append(row)
    result: dict[str, Any] = {}
    metrics = (
        ("released_interface", "expected_balanced_accuracy"),
        ("four_bin_tokenizer_before_channel", "balanced_accuracy"),
        ("full_feature_classifier_on_selected_edit", "balanced_accuracy"),
        ("full_feature_classifier_on_unedited_representation", "balanced_accuracy"),
    )
    for dataset, items in grouped.items():
        result[dataset] = {"releases": len(items)}
        for section, key in metrics:
            result[dataset][f"{section}_{key}_mean"] = float(
                np.mean([float(item[section][key]) for item in items])
            )
    return dict(sorted(result.items()))


def atomic_dump(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-summary", required=True, type=Path)
    parser.add_argument("--raw-dir", required=True, type=Path)
    parser.add_argument("--direct-dir", required=True, type=Path)
    parser.add_argument("--direct-audit", required=True, type=Path)
    parser.add_argument("--utility-report", required=True, type=Path)
    parser.add_argument("--utility-audit", required=True, type=Path)
    parser.add_argument("--off-event", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")

    real = load(args.real_summary)
    direct_audit = load(args.direct_audit)
    utility = load(args.utility_report)
    utility_audit = load(args.utility_audit)
    off_event = load(args.off_event)
    if real.get("status") != "complete":
        raise ValueError("real evidence summary is incomplete")
    if direct_audit.get("passed") is not True or direct_audit.get("file_count") != 100:
        raise ValueError("direct target comparator audit did not pass")
    if utility_audit.get("passed") is not True or utility_audit.get("release_count") != 23:
        raise ValueError("utility audit did not pass")
    formal_event = off_event.get("by_study", {}).get("formal_certificate_methods")
    if not isinstance(formal_event, dict) or formal_event.get("false_acceptances") != 0:
        raise ValueError("off-event certificate accounting did not pass")

    direct = summarize_direct_target(args.direct_dir)
    bridge_strata = summarize_bridge_strata(args.raw_dir)
    datasets = [str(value) for value in real["datasets"]]
    if datasets != sorted(key for key in direct if key != "all_datasets"):
        raise ValueError("direct and bridge datasets differ")
    if datasets != sorted(bridge_strata):
        raise ValueError("bridge stratum datasets differ")
    strict_primary = real["cells"]["strict_mosaic"]
    plugin_primary = real["cells"]["bridge_plugin"]
    per_dataset = {
        dataset: {
            "strict_mosaic": strict_primary[dataset][PRIMARY_THRESHOLD],
            "direct_target_table": direct[dataset],
            "bridge_plugin": plugin_primary[dataset][PRIMARY_THRESHOLD],
            "bridge_strata": bridge_strata[dataset],
        }
        for dataset in datasets
    }
    payload = {
        "name": "MOSAIC revision evidence summary",
        "primary_utility_threshold": PRIMARY_THRESHOLD,
        "direct_target_rule_scope": (
            "Direct target-table certification applies the same simultaneous envelope "
            "to the labeled bridge table alone. It certifies that table's target law, "
            "not the broader bridge-admitted class used by strict MOSAIC."
        ),
        "utility_scope": utility["claim_boundary"],
        "per_dataset": per_dataset,
        "all_datasets": {
            "strict_mosaic": strict_primary["all_datasets"][PRIMARY_THRESHOLD],
            "direct_target_table": direct["all_datasets"],
            "bridge_plugin": plugin_primary["all_datasets"][PRIMARY_THRESHOLD],
        },
        "real_release_frontier": {
            "thresholds": real["utility_thresholds"],
            "strict_mosaic": real["cells"]["strict_mosaic"]["all_datasets"],
            "bridge_plugin": real["cells"]["bridge_plugin"]["all_datasets"],
        },
        "diagnostic_anchored_interface_utility": summarize_utility(utility),
        "off_event_formal_certificates": formal_event,
        "authenticated_inputs": {
            "direct_target_audit_sha256": sha256(args.direct_audit),
            "utility_audit_sha256": sha256(args.utility_audit),
            "off_event_sha256": sha256(args.off_event),
        },
    }
    atomic_dump(payload, args.output)
    print(json.dumps(payload["all_datasets"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
