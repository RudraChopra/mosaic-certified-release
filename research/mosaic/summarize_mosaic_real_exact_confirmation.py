#!/usr/bin/env python3
"""Summarize the paired real-feature confirmation from authenticated receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
from scipy.stats import beta


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_MANIFEST = (
    REPOSITORY
    / "research"
    / "artifacts"
    / "mosaic_real_exact_confirmation_manifest_v1.json"
)
DEFAULT_OUTPUT = (
    REPOSITORY
    / "research"
    / "artifacts"
    / "mosaic_real_exact_confirmation_summary_v1.json"
)
VARIANTS = ("capacity_transfer", "transform_exact")
TOLERANCE = 1e-10


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_json_dump(payload: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def receipt_path(record: dict[str, object]) -> Path:
    stored = Path(str(record["path"]))
    if stored.is_file():
        return stored
    candidate = (
        REPOSITORY
        / "research"
        / "artifacts"
        / "mosaic_real_exact_confirmation_v1"
        / stored.name
    )
    if candidate.is_file():
        return candidate
    raise FileNotFoundError(f"missing receipt: {stored}")


def proportion_interval(successes: int, trials: int) -> dict[str, object]:
    if trials == 0:
        return {"successes": successes, "trials": trials, "estimate": None, "ci95": None}
    lower = 0.0 if successes == 0 else float(beta.ppf(0.025, successes, trials - successes + 1))
    upper = 1.0 if successes == trials else float(beta.ppf(0.975, successes + 1, trials - successes))
    return {
        "successes": successes,
        "trials": trials,
        "estimate": successes / trials,
        "ci95": [lower, upper],
        "method": "two-sided Clopper-Pearson",
    }


def selection_record(row: dict[str, object], variant: str) -> dict[str, object]:
    selected = row["selection"][variant]
    return {
        "seed": row["seed"],
        "decision": selected["decision"],
        "candidate": selected.get("candidate"),
        "method": selected.get("method"),
        "strength": selected.get("strength"),
        "certified_worst_conditional_error": selected.get(
            "certified_worst_conditional_error"
        ),
        "external_estimable": selected.get("external_estimable", False),
        "external_safe": selected.get("external_safe", False),
        "false_acceptance": selected.get("false_acceptance", False),
        "external_worst_privacy_advantage": selected.get(
            "external_worst_privacy_advantage"
        ),
        "external_worst_conditional_error": selected.get(
            "external_worst_conditional_error"
        ),
    }


def summarize_variant(rows: list[dict[str, object]], variant: str) -> dict[str, object]:
    selections = [selection_record(row, variant) for row in rows]
    deployed = [value for value in selections if value["decision"] == "deploy"]
    estimable = [value for value in deployed if value["external_estimable"]]
    family_counts = Counter(str(value["method"]) for value in deployed)
    minima = [
        min(
            float(result[variant]["certified_worst_conditional_error"])
            for result in row["results"]
        )
        for row in rows
    ]
    candidate_deployments = sum(
        bool(result[variant]["deployed"])
        for row in rows
        for result in row["results"]
    )
    candidate_estimable = sum(
        bool(result[variant]["external_estimable"])
        for row in rows
        for result in row["results"]
    )
    candidate_safe = sum(
        bool(result[variant]["external_safe"])
        for row in rows
        for result in row["results"]
    )
    candidate_false_acceptances = sum(
        bool(result[variant]["false_acceptance"])
        for row in rows
        for result in row["results"]
    )
    false_acceptances = sum(bool(value["false_acceptance"]) for value in estimable)
    safe = sum(bool(value["external_safe"]) for value in estimable)
    return {
        "jobs": len(rows),
        "selected_deployments": len(deployed),
        "estimable_selected_deployments": len(estimable),
        "safe_estimable_selected_deployments": safe,
        "selected_false_acceptances": false_acceptances,
        "candidate_deployments": candidate_deployments,
        "candidate_estimable": candidate_estimable,
        "candidate_safe": candidate_safe,
        "candidate_false_acceptances": candidate_false_acceptances,
        "selected_method_counts": dict(sorted(family_counts.items())),
        "mean_best_certified_error": float(np.mean(minima)),
        "false_acceptance_interval": proportion_interval(false_acceptances, len(estimable)),
        "safe_selection_interval": proportion_interval(safe, len(estimable)),
        "selections": selections,
    }


def summarize_dataset(rows: list[dict[str, object]]) -> dict[str, object]:
    return {variant: summarize_variant(rows, variant) for variant in VARIANTS}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows = []
    for record in manifest["outputs"]:
        path = receipt_path(record)
        actual = sha256(path)
        if actual != record["sha256"]:
            raise ValueError(
                f"receipt hash mismatch for {path.name}: expected {record['sha256']}, found {actual}"
            )
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    if len(rows) != 25 or sum(len(row["results"]) for row in rows) != 325:
        raise ValueError("summary requires the complete 25-job, 325-row confirmation")

    by_dataset: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        by_dataset.setdefault(str(row["dataset"]), []).append(row)

    gains = np.asarray(
        [
            float(result["capacity_transfer"]["certified_worst_conditional_error"])
            - float(result["transform_exact"]["certified_worst_conditional_error"])
            for row in rows
            for result in row["results"]
        ],
        dtype=np.float64,
    )
    crossings = [
        {
            "dataset": row["dataset"],
            "seed": row["seed"],
            "exact_selection": selection_record(row, "transform_exact"),
        }
        for row in rows
        if row["selection"]["capacity_transfer"]["decision"] == "abstain"
        and row["selection"]["transform_exact"]["decision"] == "deploy"
    ]
    safe_crossings = [
        value
        for value in crossings
        if value["exact_selection"]["external_estimable"]
        and value["exact_selection"]["external_safe"]
    ]
    exact_estimable = [
        row["selection"]["transform_exact"]
        for row in rows
        if row["selection"]["transform_exact"]["decision"] == "deploy"
        and row["selection"]["transform_exact"]["external_estimable"]
    ]
    exact_false_acceptances = sum(
        bool(value["false_acceptance"]) for value in exact_estimable
    )

    summary: dict[str, object] = {
        "name": "MOSAIC paired exact real-feature confirmation summary",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": {"path": str(args.manifest), "sha256": sha256(args.manifest)},
        "prereg_sha256": manifest["prereg_sha256"],
        "all_registered_gates_pass": manifest["all_pass"],
        "registered_gates": manifest["gates"],
        "jobs": len(rows),
        "candidate_rows": int(gains.size),
        "paired_objective_comparison": {
            "pointwise_exact_no_worse": bool(np.all(gains >= -2e-7)),
            "strict_exact_improvements": int(np.sum(gains > TOLERANCE)),
            "mean_gain": float(np.mean(gains)),
            "median_gain": float(np.median(gains)),
            "maximum_gain": float(np.max(gains)),
            "minimum_gain": float(np.min(gains)),
        },
        "selection_crossings": crossings,
        "safe_estimable_selection_crossings": len(safe_crossings),
        "exact_selected_false_acceptance_interval": proportion_interval(
            exact_false_acceptances, len(exact_estimable)
        ),
        "datasets": {
            dataset: summarize_dataset(sorted(values, key=lambda row: int(row["seed"])))
            for dataset, values in sorted(by_dataset.items())
        },
    }
    atomic_json_dump(summary, args.output)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
