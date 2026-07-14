"""Audit frozen VERA rows without requiring the omitted per-example arrays."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_confirmatory_balanced.json"
DEFAULT_ROWS = ROOT / "artifacts" / "vera_confirmatory_balanced_rule_rows.csv"
DEFAULT_CANDIDATES = (
    ROOT / "artifacts" / "vera_confirmatory_balanced_candidate_rows.csv"
)
DEFAULT_REPORT = ROOT / "artifacts" / "vera_confirmatory_balanced_report.json"
DEFAULT_ABSTRACT = ROOT / "artifacts" / "vera_confirmatory_abstract_numbers.json"
DEFAULT_FULL_AUDIT = ROOT / "artifacts" / "vera_confirmatory_analysis_audit.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_confirmatory_compact_audit.json"

RULE_PREDICATES = {
    "always_deploy_balanced": None,
    "point_selection_balanced": "point_feasible",
    "vera_balanced_iut": "iut_eligible",
    "vera_balanced_envelope": "envelope_eligible",
    "external_balanced_oracle": "external_contract_satisfied",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_bool(value: str | bool) -> bool:
    return value if isinstance(value, bool) else value.strip().lower() == "true"


def values_match(observed: Any, expected: Any) -> bool:
    if observed is None or expected is None:
        return observed is expected
    if isinstance(expected, bool) or isinstance(expected, (str, int)):
        return observed == expected
    return abs(float(observed) - float(expected)) <= 1e-12


def choose(
    candidates: list[dict[str, str]], predicate: str | None
) -> dict[str, str] | None:
    eligible = candidates
    if predicate is not None:
        eligible = [candidate for candidate in candidates if as_bool(candidate[predicate])]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda candidate: (
            float(candidate["validation_max_balanced_leakage"]),
            float(candidate["validation_max_target_harm"]),
            candidate["candidate"],
        ),
    )


def summary(rows: list[dict[str, str]]) -> dict[str, Any]:
    estimable = [row for row in rows if as_bool(row["external_contract_estimable"])]
    deployments = sum(as_bool(row["deployed"]) for row in rows)
    estimable_deployments = sum(as_bool(row["deployed"]) for row in estimable)
    violations = sum(
        as_bool(row["measured_external_contract_violation"]) for row in estimable
    )
    safe = sum(
        as_bool(row["deployed"]) and row["external_contract_satisfied"] == "True"
        for row in estimable
    )
    return {
        "configuration_count": len(rows),
        "estimable_configuration_count": len(estimable),
        "deployment_count": deployments,
        "deployment_rate": deployments / len(rows),
        "estimable_deployment_count": estimable_deployments,
        "safe_deployment_count": safe,
        "measured_external_violation_count": violations,
        "measured_external_violation_rate": (
            None if not estimable else violations / len(estimable)
        ),
        "violation_rate_conditional_on_estimable_deployment": (
            None if estimable_deployments == 0 else violations / estimable_deployments
        ),
        "procedurally_unsupported_deployment_count": sum(
            as_bool(row["procedurally_unsupported_deployment"]) for row in rows
        ),
    }


def compare_summary(
    observed: dict[str, Any], expected: dict[str, Any], prefix: str, failures: list[str]
) -> None:
    for key, value in expected.items():
        if key not in observed or not values_match(observed[key], value):
            failures.append(f"{prefix}.{key} differs from compact replay")


def expected_headline(
    prereg: dict[str, Any],
    report: dict[str, Any],
    primary: list[dict[str, str]],
) -> dict[str, Any]:
    regimes = {
        (
            str(item["dataset"]),
            float(item["target_harm_threshold"]),
            float(item["leakage_threshold"]),
        )
        for item in prereg["real_study"]["headline_stress_family"]["regimes"]
    }
    point = [
        row
        for row in primary
        if row["rule"] == "point_selection_balanced"
        and (
            row["dataset"],
            float(row["target_threshold"]),
            float(row["leakage_threshold"]),
        )
        in regimes
    ]
    vera = [
        row
        for row in primary
        if row["rule"] == "vera_balanced_iut"
        and (
            row["dataset"],
            float(row["target_threshold"]),
            float(row["leakage_threshold"]),
        )
        in regimes
    ]
    point_rate = sum(as_bool(row["measured_external_contract_violation"]) for row in point) / len(point)
    vera_rate = sum(as_bool(row["measured_external_contract_violation"]) for row in vera) / len(vera)
    oracle_by_id = {
        row["config_id"]: row
        for row in primary
        if row["rule"] == "external_balanced_oracle"
    }
    vera_by_id = {
        row["config_id"]: row
        for row in primary
        if row["rule"] == "vera_balanced_iut"
    }
    opportunities = [
        config_id for config_id, row in oracle_by_id.items() if as_bool(row["deployed"])
    ]
    retained = sum(
        as_bool(vera_by_id[config_id]["deployed"])
        and vera_by_id[config_id]["external_contract_satisfied"] == "True"
        for config_id in opportunities
    )
    retention = 0.0 if not opportunities else retained / len(opportunities)
    camelyon = [
        row
        for row in primary
        if row["dataset"] == "Camelyon17-WILDS"
        and row["rule"] in {"vera_balanced_iut", "vera_balanced_envelope"}
    ]
    forced_count = sum(
        not as_bool(row["deployed"])
        and as_bool(row["support_mismatch_forced_abstention"])
        for row in camelyon
    )
    camelyon_pass = bool(camelyon) and forced_count == len(camelyon)
    gap_pass = point_rate - vera_rate >= 0.15
    if report.get("passed") is True and gap_pass:
        mode = "empirical_gap"
        sentence = (
            f"Across {len(point)} prespecified stress configurations, "
            f"validation-only selection deployed contract-violating edits in "
            f"{100 * point_rate:.1f}% of configurations versus "
            f"{100 * vera_rate:.1f}% for VERA, while VERA retained "
            f"{100 * retention:.1f}% of external-oracle opportunities."
        )
    else:
        mode = "theory_forced_abstention"
        sentence = (
            "VERA gives finite-sample false-acceptance control over its declared "
            "shift class and identifies when certification is impossible; on "
            f"Camelyon17 it forced abstention in all {forced_count} registered "
            "VERA configurations because the deployment hospital was outside "
            "certification support."
        )
    return {
        "stress_configuration_count": len(point),
        "point_selection_violation_rate": point_rate,
        "vera_iut_violation_rate": vera_rate,
        "safe_retention": retention,
        "headline_mode": mode,
        "headline_gap_condition_met": gap_pass,
        "theory_forced_abstention_lead_verified": (
            mode == "theory_forced_abstention" and camelyon_pass
        ),
        "unsupported_camelyon_abstention_verified": camelyon_pass,
        "camelyon_forced_abstention_configuration_count": forced_count,
        "registered_pass_conditions_met": report.get("passed") is True,
        "sentence": sentence,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--rows", type=Path, default=DEFAULT_ROWS)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--abstract", type=Path, default=DEFAULT_ABSTRACT)
    parser.add_argument("--full-audit", type=Path, default=DEFAULT_FULL_AUDIT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prereg = load_json(args.prereg)
    report = load_json(args.report)
    abstract = load_json(args.abstract)
    full_audit = load_json(args.full_audit)
    rows = load_csv(args.rows)
    candidates = load_csv(args.candidates)
    failures: list[str] = []

    frozen_expectations = {
        "rule_rows_sha256": sha256(args.rows),
        "candidate_rows_sha256": sha256(args.candidates),
        "report_sha256": sha256(args.report),
        "abstract_sha256": sha256(args.abstract),
    }
    if full_audit.get("passed") is not True:
        failures.append("full raw-array audit did not pass before freezing")
    for key, expected in frozen_expectations.items():
        if full_audit.get(key) != expected:
            failures.append(f"full audit hash mismatch: {key}")
    for key, expected in (
        ("raw_candidate_rows_recomputed", 25_920),
        ("raw_npz_files_recomputed", 480),
        ("raw_npz_checksums_verified", 480),
        ("raw_candidate_mismatches", 0),
        ("selection_mismatches", 0),
        ("semantic_mismatches", 0),
    ):
        if int(full_audit.get(key, -1)) != expected:
            failures.append(f"full raw-array audit field mismatch: {key}")
    if len(rows) != 10_800 or len(candidates) != 25_920:
        failures.append("frozen row dimensions differ from the locked protocol")

    candidates_by_config: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
    rows_by_config: defaultdict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for candidate in candidates:
        candidates_by_config[candidate["config_id"]].append(candidate)
    for row in rows:
        rows_by_config[row["config_id"]][row["rule"]] = row
    if set(candidates_by_config) != set(rows_by_config):
        failures.append("candidate and rule configuration sets differ")
    selection_mismatches = 0
    for config_id, config_candidates in candidates_by_config.items():
        if len(config_candidates) != 12:
            failures.append(f"{config_id} does not contain 12 candidates")
            continue
        if set(rows_by_config[config_id]) != set(RULE_PREDICATES):
            failures.append(f"{config_id} does not contain all deployment rules")
            continue
        for rule, predicate in RULE_PREDICATES.items():
            selected = choose(config_candidates, predicate)
            observed = rows_by_config[config_id][rule]
            expected_candidate = "" if selected is None else selected["candidate"]
            if (
                as_bool(observed["deployed"]) != (selected is not None)
                or observed["selected_candidate"] != expected_candidate
            ):
                selection_mismatches += 1
    if selection_mismatches:
        failures.append(f"{selection_mismatches} compact rule selections differ")

    primary = [row for row in rows if row["analysis_tier"] == "primary"]
    for rule in RULE_PREDICATES:
        expected = summary([row for row in primary if row["rule"] == rule])
        compare_summary(
            report.get("primary_summaries", {}).get(rule, {}),
            expected,
            f"primary.{rule}",
            failures,
        )
    headline = expected_headline(prereg, report, primary)
    for key, expected in headline.items():
        if key not in abstract or not values_match(abstract[key], expected):
            failures.append(f"abstract field differs from compact replay: {key}")
    if abstract.get("verified") is not True:
        failures.append("abstract is not marked receipt-verified")

    audit = {
        "name": "VERA compact frozen-row audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not failures,
        "full_raw_audit_sha256": sha256(args.full_audit),
        "full_raw_audit_verified": full_audit.get("passed") is True,
        "rule_rows_replayed": len(rows),
        "candidate_rows_replayed": len(candidates),
        "selection_mismatches": selection_mismatches,
        "headline_verified": not any(
            failure.startswith("abstract field") for failure in failures
        ),
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
