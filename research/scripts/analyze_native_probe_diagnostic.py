"""Aggregate the fixed method-native-probe diagnostic at the seed level."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np


DATASETS = ("Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB")
METHODS = ("inlp", "rlace", "leace", "taco", "mance")
SEEDS = tuple(range(45, 61))
CANDIDATE_COUNTS = {"inlp": 4, "rlace": 2, "leace": 1, "taco": 4, "mance": 1}
EXPECTED_RECEIPTS = len(DATASETS) * len(METHODS) * len(SEEDS)
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_SEED = 202_707_160_4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def expected_name(dataset: str, method: str, seed: int) -> str:
    return f"{dataset}__{method}__seed-{seed}.json"


def interval(values: Iterable[float], rng: np.random.Generator) -> dict[str, Any]:
    observed = np.asarray(list(values), dtype=np.float64)
    if len(observed) == 0:
        return {
            "estimate": None,
            "lower": None,
            "upper": None,
            "level": 0.95,
            "method": "whole_seed_percentile_bootstrap",
            "independent_unit": "seed",
            "replicates": BOOTSTRAP_REPLICATES,
        }
    draws = rng.choice(
        observed, size=(BOOTSTRAP_REPLICATES, len(observed)), replace=True
    ).mean(axis=1)
    return {
        "estimate": float(observed.mean()),
        "lower": float(np.quantile(draws, 0.025)),
        "upper": float(np.quantile(draws, 0.975)),
        "level": 0.95,
        "method": "whole_seed_percentile_bootstrap",
        "independent_unit": "seed",
        "replicates": BOOTSTRAP_REPLICATES,
    }


def comparable_native(
    method: str, native: dict[str, Any]
) -> tuple[str | None, float | None]:
    if method in {"inlp", "taco"}:
        return "balanced_accuracy", native.get("external_balanced_accuracy")
    if method == "mance":
        return "ordinary_accuracy", native.get("external_accuracy")
    return None, None


def fresh_max(record: dict[str, Any], scale: str) -> float:
    field = (
        "external_balanced_accuracy"
        if scale == "balanced_accuracy"
        else "external_accuracy"
    )
    values = [
        metrics[field]
        for metrics in record["fresh_registered_attackers"].values()
        if metrics[field] is not None
    ]
    if not values:
        raise RuntimeError("comparable fresh-attacker metric is absent")
    return float(max(values))


def analyze(receipt_dir: Path) -> dict[str, Any]:
    expected = {
        expected_name(dataset, method, seed)
        for dataset in DATASETS
        for method in METHODS
        for seed in SEEDS
    }
    observed = {path.name for path in receipt_dir.iterdir() if path.is_file()}
    if observed != expected or len(observed) != EXPECTED_RECEIPTS:
        raise RuntimeError("native-probe diagnostic receipt set is incomplete")
    candidate_rows: list[dict[str, Any]] = []
    receipt_manifest: list[dict[str, str]] = []
    for dataset in DATASETS:
        for method in METHODS:
            for seed in SEEDS:
                path = receipt_dir / expected_name(dataset, method, seed)
                receipt = load_json(path)
                if (
                    receipt.get("dataset") != dataset
                    or receipt.get("method") != method
                    or receipt.get("seed") != seed
                    or receipt.get("formal_guarantee") is not False
                    or receipt.get("cross_method_native_probe_equivalence_claimed")
                    is not False
                ):
                    raise RuntimeError(f"native-probe receipt identity mismatch: {path}")
                records = receipt.get("records")
                if not isinstance(records, list) or len(records) != CANDIDATE_COUNTS[method]:
                    raise RuntimeError(f"native-probe candidate count mismatch: {path}")
                keys = [record["candidate_key"] for record in records]
                if len(keys) != len(set(keys)):
                    raise RuntimeError(f"duplicate candidate key: {path}")
                receipt_manifest.append({"name": path.name, "sha256": sha256(path)})
                for record in records:
                    native = record["method_native"]
                    scale, native_value = comparable_native(method, native)
                    if scale is None:
                        if method == "leace" and native.get("status") != "NA":
                            raise RuntimeError("LEACE must report native classifier as NA")
                        gap = None
                        fresh = None
                    else:
                        if native_value is None:
                            raise RuntimeError("comparable method-native metric is absent")
                        fresh = fresh_max(record, scale)
                        gap = fresh - float(native_value)
                    candidate_rows.append(
                        {
                            "dataset": dataset,
                            "method": method,
                            "seed": seed,
                            "candidate_key": record["candidate_key"],
                            "native_status": native["status"],
                            "comparison_scale": scale,
                            "native_external_score": native_value,
                            "strongest_fresh_external_score": fresh,
                            "fresh_minus_native": gap,
                        }
                    )
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    summaries: list[dict[str, Any]] = []
    for method in METHODS:
        for dataset in DATASETS:
            rows = [
                row
                for row in candidate_rows
                if row["method"] == method and row["dataset"] == dataset
            ]
            by_seed: dict[int, list[float]] = defaultdict(list)
            for row in rows:
                if row["fresh_minus_native"] is not None:
                    by_seed[int(row["seed"])].append(
                        float(row["fresh_minus_native"])
                    )
            seed_values = [
                float(np.mean(by_seed[seed])) for seed in sorted(by_seed)
            ]
            summaries.append(
                {
                    "method": method,
                    "dataset": dataset,
                    "candidate_rows": len(rows),
                    "comparable_seed_count": len(seed_values),
                    "fresh_minus_native_seed_mean": interval(seed_values, rng),
                    "fresh_stronger_seed_count": sum(value > 0 for value in seed_values),
                    "native_stronger_seed_count": sum(value < 0 for value in seed_values),
                    "tie_seed_count": sum(value == 0 for value in seed_values),
                }
            )
    return {
        "schema_version": 1,
        "name": "VERA method-native probe diagnostic analysis",
        "receipt_count": len(receipt_manifest),
        "candidate_row_count": len(candidate_rows),
        "expected_candidate_row_count": 768,
        "receipt_manifest_sha256": hashlib.sha256(
            json.dumps(
                receipt_manifest, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest(),
        "candidate_rows": candidate_rows,
        "seed_cluster_summaries": summaries,
        "comparability": {
            "inlp": "balanced_accuracy",
            "rlace": "NA_training_only_upstream_score",
            "leace": "NA_no_native_classifier",
            "taco": "balanced_accuracy",
            "mance": "ordinary_accuracy",
        },
        "independent_unit": "seed",
        "cross_method_native_probe_equivalence_claimed": False,
        "formal_guarantee": False,
        "can_change_primary_gate": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = analyze(args.receipt_dir)
    if report["candidate_row_count"] != report["expected_candidate_row_count"]:
        raise RuntimeError("native-probe candidate-row count mismatch")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "receipt_count": report["receipt_count"],
                "candidate_row_count": report["candidate_row_count"],
                "output": str(args.output),
                "output_sha256": sha256(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
