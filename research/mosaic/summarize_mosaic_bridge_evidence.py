#!/usr/bin/env python3
"""Aggregate audited strict MOSAIC and matched real-data deployment rules."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from scipy.stats import beta

from mosaic_real import sha256
from run_mosaic_official_frontier_exact_confirmation import atomic_json_dump


PRIMARY_RULE = "strict_mosaic"
COMPARATOR_RULES = (
    "capacity_transfer",
    "bridge_plugin",
    "validation_plugin",
    "always_deploy_validation",
)


def exact_interval(successes: int, trials: int, confidence: float = 0.95) -> list[float] | None:
    if trials == 0:
        return None
    alpha = 1.0 - confidence
    lower = (
        0.0
        if successes == 0
        else float(beta.ppf(alpha / 2.0, successes, trials - successes + 1))
    )
    upper = (
        1.0
        if successes == trials
        else float(beta.ppf(1.0 - alpha / 2.0, successes + 1, trials - successes))
    )
    return [lower, upper]


def one_sided_upper(successes: int, trials: int, confidence: float = 0.95) -> float | None:
    if trials == 0:
        return None
    if successes == trials:
        return 1.0
    return float(beta.ppf(confidence, successes + 1, trials - successes))


def load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def outcome_row(
    *,
    dataset: str,
    seed: int,
    rule: str,
    threshold: str,
    selection: dict[str, object],
) -> dict[str, object]:
    deployed = selection.get("decision") == "deploy"
    estimable = bool(selection.get("diagnostic_estimable")) if deployed else False
    false_acceptance = bool(selection.get("false_acceptance")) if estimable else False
    return {
        "dataset": dataset,
        "seed": seed,
        "rule": rule,
        "utility_threshold": threshold,
        "deployed": deployed,
        "diagnostic_estimable": estimable,
        "false_acceptance": false_acceptance,
        "candidate": selection.get("candidate"),
        "method": selection.get("method"),
    }


def load_outcomes(
    strict_dir: Path, comparator_dir: Path
) -> tuple[list[dict[str, object]], list[str], list[str]]:
    strict_paths = sorted(strict_dir.glob("*.json"))
    comparators = {path.name: path for path in comparator_dir.glob("*.json")}
    if len(strict_paths) != 100 or set(comparators) != {
        path.name for path in strict_paths
    }:
        raise ValueError("strict and comparator directories must contain the same 100 files")
    rows: list[dict[str, object]] = []
    datasets: set[str] = set()
    thresholds: set[str] = set()
    seen: set[tuple[str, int]] = set()
    for strict_path in strict_paths:
        strict = load_object(strict_path)
        comparator = load_object(comparators[strict_path.name])
        key = (str(strict["dataset"]), int(strict["seed"]))
        if key in seen:
            raise ValueError(f"duplicate dataset-seed receipt: {key}")
        seen.add(key)
        if (comparator.get("dataset"), comparator.get("seed")) != key:
            raise ValueError(f"strict/comparator metadata mismatch: {strict_path.name}")
        datasets.add(key[0])
        strict_selections = strict["selection_by_utility_threshold"]
        comparator_selections = comparator[
            "selection_by_rule_and_utility_threshold"
        ]
        thresholds.update(str(value) for value in strict_selections)
        for threshold, selection in strict_selections.items():
            rows.append(
                outcome_row(
                    dataset=key[0],
                    seed=key[1],
                    rule=PRIMARY_RULE,
                    threshold=str(threshold),
                    selection=selection,
                )
            )
        for rule in COMPARATOR_RULES:
            if rule not in comparator_selections:
                raise ValueError(f"missing comparator rule: {rule}")
            for threshold, selection in comparator_selections[rule].items():
                rows.append(
                    outcome_row(
                        dataset=key[0],
                        seed=key[1],
                        rule=rule,
                        threshold=str(threshold),
                        selection=selection,
                    )
                )
    return rows, sorted(datasets), sorted(thresholds, key=float)


def aggregate_cell(rows: list[dict[str, object]]) -> dict[str, object]:
    trials = len(rows)
    deployments = sum(bool(row["deployed"]) for row in rows)
    estimable = sum(bool(row["diagnostic_estimable"]) for row in rows)
    false_acceptances = sum(bool(row["false_acceptance"]) for row in rows)
    method_counts = Counter(
        str(row["method"])
        for row in rows
        if row["deployed"] and row["method"] is not None
    )
    return {
        "trials": trials,
        "deployments": deployments,
        "deployment_rate": deployments / trials if trials else None,
        "deployment_exact_95_interval": exact_interval(deployments, trials),
        "estimable_deployments": estimable,
        "unestimable_deployments": deployments - estimable,
        "false_acceptances": false_acceptances,
        "false_acceptance_rate_among_estimable": (
            false_acceptances / estimable if estimable else None
        ),
        "false_acceptance_exact_95_interval": exact_interval(
            false_acceptances, estimable
        ),
        "false_acceptance_one_sided_95_upper": one_sided_upper(
            false_acceptances, estimable
        ),
        "selected_method_counts": dict(sorted(method_counts.items())),
    }


def aggregate(
    rows: list[dict[str, object]], datasets: list[str], thresholds: list[str]
) -> dict[str, object]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[
            (str(row["rule"]), str(row["dataset"]), str(row["utility_threshold"]))
        ].append(row)
    rules = (PRIMARY_RULE, *COMPARATOR_RULES)
    cells: dict[str, object] = {}
    for rule in rules:
        cells[rule] = {}
        for dataset in datasets:
            cells[rule][dataset] = {
                threshold: aggregate_cell(grouped[(rule, dataset, threshold)])
                for threshold in thresholds
            }
        cells[rule]["all_datasets"] = {
            threshold: aggregate_cell(
                [
                    row
                    for dataset in datasets
                    for row in grouped[(rule, dataset, threshold)]
                ]
            )
            for threshold in thresholds
        }
    return cells


def paired_contrasts(
    rows: list[dict[str, object]], thresholds: list[str]
) -> dict[str, object]:
    indexed = {
        (
            str(row["rule"]),
            str(row["dataset"]),
            int(row["seed"]),
            str(row["utility_threshold"]),
        ): row
        for row in rows
    }
    contrasts: dict[str, object] = {}
    keys = sorted(
        {
            (str(row["dataset"]), int(row["seed"]))
            for row in rows
            if row["rule"] == PRIMARY_RULE
        }
    )
    for comparator in COMPARATOR_RULES:
        contrasts[comparator] = {}
        for threshold in thresholds:
            mosaic_only = 0
            comparator_only = 0
            both = 0
            neither = 0
            for dataset, seed in keys:
                mosaic = bool(
                    indexed[(PRIMARY_RULE, dataset, seed, threshold)]["deployed"]
                )
                other = bool(
                    indexed[(comparator, dataset, seed, threshold)]["deployed"]
                )
                mosaic_only += int(mosaic and not other)
                comparator_only += int(other and not mosaic)
                both += int(mosaic and other)
                neither += int(not mosaic and not other)
            contrasts[comparator][threshold] = {
                "mosaic_only_deployments": mosaic_only,
                "comparator_only_deployments": comparator_only,
                "both_deploy": both,
                "neither_deploys": neither,
                "paired_deployment_difference": (mosaic_only - comparator_only)
                / len(keys),
            }
    return contrasts


def verify_audits(paths: dict[str, Path]) -> dict[str, object]:
    receipts: dict[str, object] = {}
    for name, path in paths.items():
        report = load_object(path)
        if report.get("passed") is not True:
            raise ValueError(f"required audit did not pass: {name}")
        receipts[name] = {
            "path": str(path),
            "sha256": sha256(path),
            "name": report.get("name"),
        }
    return receipts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-dir", required=True, type=Path)
    parser.add_argument("--comparator-dir", required=True, type=Path)
    parser.add_argument("--strict-audit", required=True, type=Path)
    parser.add_argument("--rational-audit", required=True, type=Path)
    parser.add_argument("--comparator-audit", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    audit_receipts = verify_audits(
        {
            "strict": args.strict_audit,
            "rational": args.rational_audit,
            "comparator": args.comparator_audit,
        }
    )
    rows, datasets, thresholds = load_outcomes(
        args.strict_dir, args.comparator_dir
    )
    cells = aggregate(rows, datasets, thresholds)
    primary_threshold = "0.40"
    payload = {
        "name": "MOSAIC audited real bridge evidence summary",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete",
        "primary_rule": PRIMARY_RULE,
        "primary_utility_threshold": primary_threshold,
        "datasets": datasets,
        "utility_thresholds": thresholds,
        "rules": [PRIMARY_RULE, *COMPARATOR_RULES],
        "audit_receipts": audit_receipts,
        "strict_receipt_count": len(list(args.strict_dir.glob("*.json"))),
        "comparator_receipt_count": len(list(args.comparator_dir.glob("*.json"))),
        "outcome_rows": len(rows),
        "cells": cells,
        "paired_contrasts": paired_contrasts(rows, thresholds),
        "primary_cell": cells[PRIMARY_RULE]["all_datasets"][primary_threshold],
        "reporting_policy": (
            "All registered datasets, seeds, thresholds, abstentions, unestimable "
            "deployments, and comparator orderings are retained. False-acceptance "
            "rates use estimable deployed diagnostics as their denominator."
        ),
    }
    atomic_json_dump(payload, args.output)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
