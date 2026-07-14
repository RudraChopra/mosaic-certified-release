"""Generate the outcome-blindly locked secondary VERA ablations.

This script consumes only the audited primary analysis tables. The expensive
attacker-portfolio recomputation lives in ``analyze_vera_attacker_ablation.py``.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_real.json"
DEFAULT_PREREG_HASH = ROOT / "prereg_real.sha256"
DEFAULT_ABLATION_PREREG = ROOT / "prereg_secondary_ablations.json"
DEFAULT_ABLATION_HASH = ROOT / "prereg_secondary_ablations.sha256"
DEFAULT_AUDIT = ROOT / "artifacts" / "official_eraser_receipt_audit.json"
DEFAULT_RULE_ROWS = ROOT / "artifacts" / "vera_deployment_rule_rows.csv"
DEFAULT_CANDIDATE_ROWS = ROOT / "artifacts" / "vera_candidate_certificate_rows.csv"
DEFAULT_OUTPUT_ROWS = ROOT / "artifacts" / "vera_secondary_ablation_rows.csv"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_secondary_ablation_report.json"


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


def expected_hash(path: Path) -> str:
    return path.read_text(encoding="utf-8").split()[0]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_bool(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"expected serialized Boolean, got {value!r}")


def select_candidate(
    candidates: Iterable[dict[str, str]],
    *,
    gamma: float,
    excluded_method: str | None = None,
) -> dict[str, str] | None:
    eligible = [
        candidate
        for candidate in candidates
        if candidate["method"] != excluded_method
        and not as_bool(candidate["support_mismatch"])
        and float(candidate["certified_radius"]) >= gamma - 1e-12
    ]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda candidate: (
            float(candidate["validation_max_leakage"]),
            float(candidate["validation_max_target_harm"]),
            candidate["candidate"],
        ),
    )


def deployment_record(
    candidate: dict[str, str] | None,
    oracle_deployed: bool,
    base: dict[str, str],
) -> dict[str, Any]:
    deployed = candidate is not None
    safe = deployed and as_bool(candidate["external_contract_satisfied"])
    return {
        "config_id": base["config_id"],
        "dataset": base["dataset"],
        "seed": int(base["seed"]),
        "validation_fraction": float(base["validation_fraction"]),
        "target_threshold": float(base["target_threshold"]),
        "leakage_threshold": float(base["leakage_threshold"]),
        "deployed": deployed,
        "violation": deployed and not safe,
        "safe": safe,
        "oracle_deployed": oracle_deployed,
        "selected_candidate": candidate["candidate"] if deployed else "",
        "selected_method": candidate["method"] if deployed else "",
        "certified_radius": float(candidate["certified_radius"]) if deployed else 0.0,
    }


def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator <= 0 else numerator / denominator


def cluster_summary(
    records: list[dict[str, Any]],
    *,
    bootstrap_seed: int,
    replicates: int = 5000,
) -> dict[str, Any]:
    if not records:
        raise ValueError("cannot summarize an empty ablation cell")
    blocks: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        blocks[(row["dataset"], int(row["seed"]))].append(row)
    totals = np.asarray(
        [
            [
                len(rows),
                sum(row["deployed"] for row in rows),
                sum(row["violation"] for row in rows),
                sum(row["safe"] and row["oracle_deployed"] for row in rows),
                sum(row["oracle_deployed"] for row in rows),
            ]
            for rows in blocks.values()
        ],
        dtype=np.float64,
    )

    def metrics(values: np.ndarray) -> np.ndarray:
        total = values.sum(axis=0)
        return np.asarray(
            [
                total[1] / total[0],
                total[2] / total[0],
                np.nan if total[1] == 0 else total[2] / total[1],
                np.nan if total[4] == 0 else total[3] / total[4],
            ],
            dtype=np.float64,
        )

    estimates = metrics(totals)
    rng = np.random.default_rng(bootstrap_seed)
    draws = np.empty((replicates, 4), dtype=np.float64)
    for index in range(replicates):
        sampled = totals[rng.integers(0, len(totals), size=len(totals))]
        draws[index] = metrics(sampled)
    intervals: list[list[float] | None] = []
    for column in range(draws.shape[1]):
        finite = draws[:, column][np.isfinite(draws[:, column])]
        intervals.append(
            None
            if finite.size == 0
            else [float(np.quantile(finite, 0.025)), float(np.quantile(finite, 0.975))]
        )
    names = [
        "deployment_rate",
        "measured_external_violation_rate",
        "violation_rate_conditional_on_deployment",
        "safe_deployment_retention",
    ]
    return {
        "configuration_count": len(records),
        "seed_cluster_count": len(blocks),
        **{
            name: None if not np.isfinite(value) else float(value)
            for name, value in zip(names, estimates)
        },
        "seed_cluster_bootstrap95": dict(zip(names, intervals)),
    }


def summarize_by_dataset(
    records: list[dict[str, Any]], *, bootstrap_seed: int
) -> dict[str, Any]:
    datasets = sorted({str(row["dataset"]) for row in records})
    return {
        "all_datasets": cluster_summary(
            records, bootstrap_seed=bootstrap_seed
        ),
        "by_dataset": {
            dataset: cluster_summary(
                [row for row in records if row["dataset"] == dataset],
                bootstrap_seed=bootstrap_seed + 101 * (index + 1),
            )
            for index, dataset in enumerate(datasets)
        },
    }


def group_records(
    records: list[dict[str, Any]], key: Callable[[dict[str, Any]], str]
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[key(record)].append(record)
    return dict(grouped)


def analyze(args: argparse.Namespace) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parent_hash = sha256(args.prereg)
    ablation_hash = sha256(args.ablation_prereg)
    if parent_hash != expected_hash(args.prereg_hash):
        raise RuntimeError("parent preregistration hash mismatch")
    if ablation_hash != expected_hash(args.ablation_hash):
        raise RuntimeError("secondary-ablation preregistration hash mismatch")
    receipt_audit = load_json(args.receipt_audit)
    if receipt_audit.get("passed") is not True:
        raise RuntimeError("official receipt matrix has not passed its audit")
    prereg = load_json(args.prereg)
    ablation_prereg = load_json(args.ablation_prereg)
    study = prereg["real_study"]
    gamma_values = [
        float(value)
        for value in ablation_prereg["ablations"]["deployment_budget"]["gamma_values"]
    ]
    deployment_gamma = float(study["deployment_gamma"])
    candidate_rows = read_csv(args.candidate_rows)
    rule_rows = read_csv(args.rule_rows)
    expected_configs = (
        len(study["datasets"])
        * len(study["seeds"])
        * len(study["validation_fractions"])
        * len(study["target_harm_thresholds"])
        * len(study["leakage_thresholds"])
    )
    expected_candidates = expected_configs * sum(
        int(method["candidate_count"]) for method in study["methods"].values()
    )
    expected_rules = expected_configs * len(study["deployment_rules"])
    if len(candidate_rows) != expected_candidates or len(rule_rows) != expected_rules:
        raise RuntimeError(
            f"primary table shape mismatch: candidates={len(candidate_rows)}/"
            f"{expected_candidates}, rules={len(rule_rows)}/{expected_rules}"
        )

    candidates_by_config: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in candidate_rows:
        candidates_by_config[row["config_id"]].append(row)
    rules = {(row["config_id"], row["rule"]): row for row in rule_rows}
    base_by_config = {
        config_id: candidates[0] for config_id, candidates in candidates_by_config.items()
    }
    oracle_by_config = {
        config_id: as_bool(rules[(config_id, "oracle")]["deployed"])
        for config_id in candidates_by_config
    }

    output_rows: list[dict[str, Any]] = []
    budget_records: dict[str, list[dict[str, Any]]] = {}
    for gamma in gamma_values:
        records = []
        for config_id, candidates in candidates_by_config.items():
            record = deployment_record(
                select_candidate(candidates, gamma=gamma),
                oracle_by_config[config_id],
                base_by_config[config_id],
            )
            record.update({"ablation": "deployment_budget", "level": f"{gamma:g}"})
            records.append(record)
        budget_records[f"{gamma:g}"] = records
        output_rows.extend(records)

    methods = [method["display_name"] for method in study["methods"].values()]
    frontier_conditions: list[tuple[str, str | None]] = [("all", None)] + [
        (f"without_{method}", method) for method in methods
    ]
    frontier_records: dict[str, list[dict[str, Any]]] = {}
    for label, excluded in frontier_conditions:
        records = []
        for config_id, candidates in candidates_by_config.items():
            record = deployment_record(
                select_candidate(
                    candidates, gamma=deployment_gamma, excluded_method=excluded
                ),
                oracle_by_config[config_id],
                base_by_config[config_id],
            )
            record.update({"ablation": "frontier_coverage", "level": label})
            records.append(record)
        frontier_records[label] = records
        output_rows.extend(records)

    primary_vera = {
        config_id: rules[(config_id, "vera")] for config_id in candidates_by_config
    }
    parity_errors = []
    for record in budget_records[f"{deployment_gamma:g}"]:
        primary = primary_vera[record["config_id"]]
        if record["deployed"] != as_bool(primary["deployed"]):
            parity_errors.append(record["config_id"])
        elif record["deployed"] and record["selected_candidate"] != primary["selected_candidate"]:
            parity_errors.append(record["config_id"])
    for record in frontier_records["all"]:
        primary = primary_vera[record["config_id"]]
        if record["deployed"] != as_bool(primary["deployed"]):
            parity_errors.append(record["config_id"])
        elif record["deployed"] and record["selected_candidate"] != primary["selected_candidate"]:
            parity_errors.append(record["config_id"])

    primary_records: list[dict[str, Any]] = []
    for row in rule_rows:
        if row["rule"] not in {"point_selection", "vera"}:
            continue
        record = {
            "config_id": row["config_id"],
            "dataset": row["dataset"],
            "seed": int(row["seed"]),
            "validation_fraction": float(row["validation_fraction"]),
            "target_threshold": float(row["target_threshold"]),
            "leakage_threshold": float(row["leakage_threshold"]),
            "deployed": as_bool(row["deployed"]),
            "violation": as_bool(row["measured_external_contract_violation"]),
            "safe": as_bool(row["deployed"]) and as_bool(row["external_contract_satisfied"]),
            "oracle_deployed": oracle_by_config[row["config_id"]],
            "selected_candidate": row["selected_candidate"],
            "selected_method": row["selected_method"],
            "certified_radius": float(row["certified_radius"]),
            "rule": row["rule"],
        }
        primary_records.append(record)

    validation_groups = group_records(
        primary_records,
        lambda row: f"{row['rule']}|fraction={row['validation_fraction']:g}",
    )
    threshold_groups = group_records(
        [row for row in primary_records if row["rule"] == "vera"],
        lambda row: (
            f"tau={row['target_threshold']:g}|lambda={row['leakage_threshold']:g}"
        ),
    )

    limiting = Counter()
    group_radius_values: dict[str, list[float]] = defaultdict(list)
    unsupported_rows = 0
    unsupported_zero_rows = 0
    for row in candidate_rows:
        for contract in json.loads(row["limiting_contracts"]):
            family = "target" if contract.startswith("target::") else contract.split("::")[1]
            limiting[family] += 1
        radii = json.loads(row["certified_group_radii"])
        unsupported = set(json.loads(row["unsupported_environment_classes"]))
        for group, radius in radii.items():
            geometry_key = f"{row['dataset']}|environment={group}"
            group_radius_values[geometry_key].append(float(radius))
        if unsupported:
            unsupported_rows += 1
            if all(float(radii[str(group)]) == 0.0 for group in unsupported):
                unsupported_zero_rows += 1

    report = {
        "name": "VERA locked secondary ablations",
        "passed": not parity_errors and unsupported_rows == unsupported_zero_rows,
        "claim_status": "secondary outcome-blindly locked sensitivity analysis",
        "parent_prereg_sha256": parent_hash,
        "ablation_prereg_sha256": ablation_hash,
        "receipt_audit_sha256": sha256(args.receipt_audit),
        "source_table_sha256": {
            "rule_rows": sha256(args.rule_rows),
            "candidate_rows": sha256(args.candidate_rows),
        },
        "table_shapes": {
            "rule_rows": len(rule_rows),
            "candidate_rows": len(candidate_rows),
            "output_rows": len(output_rows),
        },
        "parity_with_primary_vera": {
            "passed": not parity_errors,
            "error_count": len(parity_errors),
            "first_errors": parity_errors[:20],
        },
        "deployment_budget": {
            level: summarize_by_dataset(records, bootstrap_seed=9200 + index)
            for index, (level, records) in enumerate(budget_records.items())
        },
        "validation_size": {
            level: summarize_by_dataset(records, bootstrap_seed=10200 + index)
            for index, (level, records) in enumerate(sorted(validation_groups.items()))
        },
        "contract_thresholds": {
            level: summarize_by_dataset(records, bootstrap_seed=11200 + index)
            for index, (level, records) in enumerate(sorted(threshold_groups.items()))
        },
        "frontier_coverage": {
            level: {
                **summarize_by_dataset(records, bootstrap_seed=12200 + index),
                "selected_method_counts": dict(
                    sorted(Counter(row["selected_method"] for row in records if row["deployed"]).items())
                ),
            }
            for index, (level, records) in enumerate(frontier_records.items())
        },
        "certificate_geometry": {
            "limiting_contract_family_counts": dict(sorted(limiting.items())),
            "group_radius_quantiles": {
                group: {
                    "count": len(values),
                    "q10": float(np.quantile(values, 0.10)),
                    "median": float(np.median(values)),
                    "q90": float(np.quantile(values, 0.90)),
                }
                for group, values in sorted(group_radius_values.items())
            },
            "unsupported_candidate_rows": unsupported_rows,
            "unsupported_zero_radius_rows": unsupported_zero_rows,
            "all_unsupported_radii_zero": unsupported_rows == unsupported_zero_rows,
        },
        "statistical_caution": (
            "Intervals resample seed clusters and are descriptive. Nested fractions "
            "and thresholds share fits and examples; no ablation p-value is confirmatory."
        ),
    }
    return output_rows, report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--prereg-hash", type=Path, default=DEFAULT_PREREG_HASH)
    parser.add_argument("--ablation-prereg", type=Path, default=DEFAULT_ABLATION_PREREG)
    parser.add_argument("--ablation-hash", type=Path, default=DEFAULT_ABLATION_HASH)
    parser.add_argument("--receipt-audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--rule-rows", type=Path, default=DEFAULT_RULE_ROWS)
    parser.add_argument("--candidate-rows", type=Path, default=DEFAULT_CANDIDATE_ROWS)
    parser.add_argument("--output-rows", type=Path, default=DEFAULT_OUTPUT_ROWS)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows, report = analyze(args)
    args.output_rows.parent.mkdir(parents=True, exist_ok=True)
    with args.output_rows.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    args.report.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({
        "passed": report["passed"],
        "output_rows": len(rows),
        "parity_errors": report["parity_with_primary_vera"]["error_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
