"""Analyze matched deployment-rule ablations from the sealed cap-8 replay."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


DATASETS = ("Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB")
SEEDS = tuple(range(45, 109))
GAMMAS = (1.1, 1.25, 1.5)
BUDGETS = (1_000, 2_000, 4_000, 8_000)
ALLOCATIONS = ("targeted_floor_0.15", "uniform")
RULES = (
    "always_deploy",
    "validation_point_selection",
    "iid_ltt",
    "robust_point_estimate",
    "generic_scalar_robust_certificate",
    "vera_fixed_profile",
    "vera_vector_envelope",
    "vera_common_radius",
    "external_oracle",
)
PRIMARY_GAMMA = 1.1
PRIMARY_BUDGET = 4_000
PRIMARY_ALLOCATION = "targeted_floor_0.15"
BOOTSTRAP_REPLICATES = 20_000
BOOTSTRAP_SEED = 202_707_160_5


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


def fraction(numerator: int, denominator: int) -> dict[str, Any]:
    if numerator < 0 or denominator < 0 or numerator > denominator:
        raise RuntimeError("invalid fraction")
    return {
        "numerator": numerator,
        "denominator": denominator,
        "estimate": None if denominator == 0 else numerator / denominator,
    }


def seed_bootstrap(
    values: Iterable[float], rng: np.random.Generator
) -> dict[str, Any]:
    observed = np.asarray(list(values), dtype=np.float64)
    if len(observed) == 0:
        return {
            "estimate": None,
            "lower": None,
            "upper": None,
            "level": 0.95,
            "method": "whole_seed_percentile_bootstrap",
            "replicates": BOOTSTRAP_REPLICATES,
            "independent_unit": "seed",
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
        "replicates": BOOTSTRAP_REPLICATES,
        "independent_unit": "seed",
    }


def exact_setting(
    rows: Sequence[Mapping[str, Any]],
    *,
    gamma: float,
    budget: int,
    allocation: str,
    rule: str,
) -> list[Mapping[str, Any]]:
    selected = [
        row
        for row in rows
        if abs(float(row["requested_gamma"]) - gamma) <= 1e-12
        and int(row["total_budget"]) == budget
        and row["allocation"] == allocation
        and row["rule"] == rule
    ]
    if len(selected) != len(DATASETS) * len(SEEDS):
        raise RuntimeError(
            f"matched row count mismatch for {gamma}/{budget}/{allocation}/{rule}"
        )
    keys = {(row["dataset"], int(row["seed"])) for row in selected}
    expected = {(dataset, seed) for dataset in DATASETS for seed in SEEDS}
    if keys != expected:
        raise RuntimeError("matched row key set is incomplete")
    return selected


def summarize(
    rows: Sequence[Mapping[str, Any]], rng: np.random.Generator
) -> dict[str, Any]:
    decisions = len(rows)
    deployed = sum(bool(row["deployed"]) for row in rows)
    violations = sum(bool(row["violation"]) for row in rows)
    deployed_violations = sum(
        bool(row["deployed"]) and bool(row["violation"]) for row in rows
    )
    opportunities = sum(bool(row["oracle_deployed"]) for row in rows)
    retained = sum(
        bool(row["deployed"]) and bool(row["oracle_deployed"]) for row in rows
    )
    by_seed: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        by_seed[int(row["seed"])].append(row)
    if sorted(by_seed) != list(SEEDS):
        raise RuntimeError("seed partition changed")
    deployment_seed_rates = [
        np.mean([bool(row["deployed"]) for row in by_seed[seed]])
        for seed in SEEDS
    ]
    violation_seed_rates = [
        np.mean([bool(row["violation"]) for row in by_seed[seed]])
        for seed in SEEDS
    ]
    retention_seed_values: list[float] = []
    for seed in SEEDS:
        seed_opportunities = sum(
            bool(row["oracle_deployed"]) for row in by_seed[seed]
        )
        if seed_opportunities:
            seed_retained = sum(
                bool(row["deployed"]) and bool(row["oracle_deployed"])
                for row in by_seed[seed]
            )
            retention_seed_values.append(seed_retained / seed_opportunities)
    radii = [
        float(row["certified_common_radius"])
        for row in rows
        if row.get("certified_common_radius") is not None
    ]
    return {
        "decisions": decisions,
        "deployments": fraction(deployed, decisions),
        "violations_all_decisions": fraction(violations, decisions),
        "violations_deployed": fraction(deployed_violations, deployed),
        "retained_opportunities": fraction(retained, opportunities),
        "deployment_seed_interval": seed_bootstrap(deployment_seed_rates, rng),
        "violation_seed_interval": seed_bootstrap(violation_seed_rates, rng),
        "retention_seed_interval": seed_bootstrap(retention_seed_values, rng),
        "common_radius": {
            "count": len(radii),
            "median": None if not radii else float(np.median(radii)),
            "lower_quartile": None if not radii else float(np.quantile(radii, 0.25)),
            "upper_quartile": None if not radii else float(np.quantile(radii, 0.75)),
        },
    }


def selected_attacker_predictor(
    rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    usable = [
        row
        for row in rows
        if bool(row["deployed"])
        and bool(row["safe"])
        and isinstance(row.get("registered_attacker_q"), Mapping)
    ]
    failures = [row for row in usable if bool(row["heldout_stress_violation"])]
    successes = [row for row in usable if not bool(row["heldout_stress_violation"])]
    if not failures or not successes:
        return {
            "status": "not_estimable",
            "reason": "held-out outcomes do not contain both classes",
        }
    attackers = sorted(usable[0]["registered_attacker_q"])
    contrasts: dict[str, float] = {}
    for attacker in attackers:
        failure_mean = np.mean(
            [float(row["registered_attacker_q"][attacker]) for row in failures]
        )
        success_mean = np.mean(
            [float(row["registered_attacker_q"][attacker]) for row in successes]
        )
        contrasts[attacker] = float(failure_mean - success_mean)
    best = max(attackers, key=lambda name: (contrasts[name], name))
    return {
        "status": "estimable",
        "definition": "largest_failure_minus_success_mean_registered_leakage",
        "selected_attacker": best,
        "contrasts": contrasts,
    }


def analyze(replay: Mapping[str, Any]) -> dict[str, Any]:
    if replay.get("counts", {}).get("decision_rows") != 55_296:
        raise RuntimeError("replay decision-row count mismatch")
    rows = replay["decision_rows"]
    keys = {
        (
            row["dataset"],
            int(row["seed"]),
            float(row["requested_gamma"]),
            int(row["total_budget"]),
            row["allocation"],
            row["rule"],
        )
        for row in rows
    }
    expected_keys = {
        (dataset, seed, gamma, budget, allocation, rule)
        for dataset in DATASETS
        for seed in SEEDS
        for gamma in GAMMAS
        for budget in BUDGETS
        for allocation in ALLOCATIONS
        for rule in RULES
    }
    if keys != expected_keys or len(keys) != len(rows):
        raise RuntimeError("replay decision-row key set is incomplete or duplicated")
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    primary_rules = (
        "iid_ltt",
        "robust_point_estimate",
        "generic_scalar_robust_certificate",
        "vera_fixed_profile",
        "vera_vector_envelope",
        "vera_common_radius",
    )
    primary = {
        rule: exact_setting(
            rows,
            gamma=PRIMARY_GAMMA,
            budget=PRIMARY_BUDGET,
            allocation=PRIMARY_ALLOCATION,
            rule=rule,
        )
        for rule in primary_rules
    }
    iid_shifted = {
        rule: summarize(primary[rule], rng)
        for rule in (
            "iid_ltt",
            "robust_point_estimate",
            "vera_fixed_profile",
            "vera_vector_envelope",
        )
    }
    scalar = primary["generic_scalar_robust_certificate"]
    vector = primary["vera_vector_envelope"]
    scalar_vector = {
        "generic_scalar": summarize(scalar, rng),
        "vera_vector": summarize(vector, rng),
        "scalar_deployments_with_required_coordinate_violation": sum(
            bool(row["deployed"]) and bool(row["violation"]) for row in scalar
        ),
        "matched_decisions": len(scalar),
    }
    common = primary["vera_common_radius"]
    paired = {
        (row["dataset"], row["seed"]): row for row in common
    }
    vector_only = [
        row
        for row in vector
        if bool(row["deployed"])
        and not bool(paired[(row["dataset"], row["seed"])]["deployed"])
    ]
    vector_common = {
        "vera_vector": summarize(vector, rng),
        "vera_common_radius": summarize(common, rng),
        "vector_only_deployments": len(vector_only),
        "vector_only_safe_deployments": sum(bool(row["safe"]) for row in vector_only),
        "vector_only_violations": sum(bool(row["violation"]) for row in vector_only),
        "limiting_coordinates": dict(
            sorted(
                Counter(
                    coordinate
                    for row in vector
                    for coordinate in row.get("limiting_coordinates", [])
                ).items()
            )
        ),
    }
    allocation = {
        name: summarize(
            exact_setting(
                rows,
                gamma=PRIMARY_GAMMA,
                budget=PRIMARY_BUDGET,
                allocation=name,
                rule="vera_vector_envelope",
            ),
            rng,
        )
        for name in ("uniform", "targeted_floor_0.15")
    }
    evidence = {
        str(budget): summarize(
            exact_setting(
                rows,
                gamma=PRIMARY_GAMMA,
                budget=budget,
                allocation=PRIMARY_ALLOCATION,
                rule="vera_vector_envelope",
            ),
            rng,
        )
        for budget in (1_000, 2_000, 4_000, 8_000)
    }
    portfolio_safe = [
        row for row in vector if bool(row["deployed"]) and bool(row["safe"])
    ]
    heldout_failures = sum(
        bool(row["heldout_stress_violation"]) for row in portfolio_safe
    )
    heldout = {
        "portfolio_safe_deployments": len(portfolio_safe),
        "heldout_violation_count": heldout_failures,
        "heldout_safe_fraction": (
            None
            if not portfolio_safe
            else 1.0 - heldout_failures / len(portfolio_safe)
        ),
        "registered_attacker_predictor": selected_attacker_predictor(vector),
        "formal_guarantee": False,
    }
    return {
        "schema_version": 1,
        "name": "VERA matched replay ablations",
        "iid_vs_shifted_certification": iid_shifted,
        "scalar_vs_vector_contracts": scalar_vector,
        "common_radius_vs_anisotropic_profile": vector_common,
        "uniform_vs_prospective_allocation": allocation,
        "evidence_budget": evidence,
        "registered_vs_heldout_attacker": heldout,
        "registered_ids": [
            "iid_vs_shifted_certification",
            "scalar_vs_vector_contracts",
            "common_radius_vs_anisotropic_profile",
            "uniform_vs_prospective_allocation",
            "evidence_budget",
            "registered_vs_heldout_attacker",
        ],
        "independent_unit": "seed",
        "can_change_primary_gate": False,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = analyze(load_json(args.replay))
    report["input_sha256"] = sha256(args.replay)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "registered_ablation_count": len(report["registered_ids"]),
                "output": str(args.output),
                "output_sha256": sha256(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
