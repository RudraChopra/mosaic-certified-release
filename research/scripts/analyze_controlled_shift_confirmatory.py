"""Execute the locked confirmatory analysis for the supported-shift study."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.stats import beta, binomtest

from analyze_vera_attacker_ablation import load_candidates
from analyze_vera_secondary_ablations import load_json, sha256
from design_vera_controlled_shift_study import (
    ATTACKERS,
    DATASETS,
    RULES,
    allocation_scores,
    candidate_arrays,
    evaluate_configuration,
    q_metrics,
    sampled_metrics,
    summarize,
    validate_shared_metadata,
)
from vera_controlled_shift import allocate_integer_budget, design_controlled_shift_from_fold


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PREREG = ROOT / "prereg_controlled_shift.json"
DEFAULT_HASH = ROOT / "prereg_controlled_shift.sha256"
DEFAULT_RECEIPTS = Path(
    "/Volumes/Backups/FARO/artifacts/vera_controlled_shift_receipts"
)
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_controlled_shift_confirmatory.json"
PRIMARY_GAMMA = 1.1
PRIMARY_BUDGET = 4000
PRIMARY_ALLOCATION = "targeted_floor_0.15"
GAMMAS = (1.1, 1.25, 1.5)
BUDGETS = (1000, 2000, 4000, 8000)
FRESH_SEEDS = tuple(range(45, 109))
SENTINEL_ROTATION = (
    "Bios",
    "CivilComments-WILDS",
    "GaitPDB",
    "Waterbirds",
)


def array_sha256(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).view(np.uint8)).hexdigest()


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def exact_interval(events: int, n: int, alpha: float = 0.05) -> list[float]:
    if n <= 0:
        return [0.0, 1.0]
    lower = 0.0 if events == 0 else float(beta.ppf(alpha / 2, events, n - events + 1))
    upper = 1.0 if events == n else float(beta.ppf(1 - alpha / 2, events + 1, n - events))
    return [lower, upper]


def one_sided_upper(events: int, n: int, alpha: float = 0.05) -> float:
    if events == n:
        return 1.0
    return float(beta.ppf(1 - alpha, events + 1, n - events))


def holm(p_values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(p_values, key=lambda key: (p_values[key], key))
    adjusted: dict[str, float] = {}
    running = 0.0
    total = len(ordered)
    for rank, key in enumerate(ordered):
        running = max(running, min(1.0, (total - rank) * p_values[key]))
        adjusted[key] = running
    return adjusted


def heldout_balanced_leakage(
    arrays: Mapping[str, np.ndarray], probabilities: np.ndarray
) -> float:
    correct = arrays[
        "heldout_leakage_correct_certification__boosted_tree"
    ]
    source = arrays["source_certification"]
    recalls = []
    for source_class in (0, 1):
        mask = source == source_class
        conditional = probabilities[mask] / probabilities[mask].sum()
        recalls.append(float(np.dot(conditional, correct[mask])))
    return float(np.mean(recalls))


def attacker_q_values(
    candidate: Mapping[str, np.ndarray], probabilities: np.ndarray
) -> dict[str, float]:
    output = {}
    for attacker in ATTACKERS:
        recalls = []
        for source_class in (0, 1):
            mask = candidate["source"] == source_class
            conditional = probabilities[mask] / probabilities[mask].sum()
            recalls.append(
                float(
                    np.dot(
                        conditional,
                        candidate[f"leakage::{attacker}"][mask],
                    )
                )
            )
        output[attacker] = float(np.mean(recalls))
    return output


def attach_stress_metrics(
    decisions: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    probabilities: np.ndarray,
    leakage_threshold: float,
) -> None:
    by_key = {candidate["candidate"]: candidate for candidate in candidates}
    for decision in decisions.values():
        selected_key = str(decision["selected_candidate"])
        if not selected_key:
            decision["heldout_leakage"] = None
            decision["heldout_stress_violation"] = False
            decision["registered_attacker_q"] = {}
            continue
        selected = by_key[selected_key]
        heldout = heldout_balanced_leakage(
            selected["raw_arrays"], probabilities
        )
        decision["heldout_leakage"] = heldout
        decision["heldout_stress_violation"] = heldout > leakage_threshold
        decision["registered_attacker_q"] = attacker_q_values(
            selected["reference"], probabilities
        )


def bootstrap_primary(
    rows: list[dict[str, Any]], *, replicates: int = 20_000
) -> dict[str, Any]:
    by_key = {
        (int(row["seed"]), str(row["dataset"]), str(row["rule"])): row
        for row in rows
    }
    seeds = np.asarray(sorted({int(row["seed"]) for row in rows}), dtype=int)

    def statistic(sample: np.ndarray) -> dict[str, float]:
        opportunities = vector_safe = common_safe = 0
        point_violations = vector_violations = 0
        point_deployments = vector_deployments = 0
        for seed in sample:
            for dataset in DATASETS:
                oracle = by_key[(int(seed), dataset, "external_oracle")]
                point = by_key[(int(seed), dataset, "validation_point_selection")]
                vector = by_key[(int(seed), dataset, "vera_vector_envelope")]
                common = by_key[(int(seed), dataset, "vera_common_radius")]
                opportunities += bool(oracle["deployed"])
                vector_safe += bool(vector["safe"])
                common_safe += bool(common["safe"])
                point_violations += bool(point["violation"])
                vector_violations += bool(vector["violation"])
                point_deployments += bool(point["deployed"])
                vector_deployments += bool(vector["deployed"])
        decisions = len(sample) * len(DATASETS)
        return {
            "vector_safe_retention": (
                np.nan if opportunities == 0 else vector_safe / opportunities
            ),
            "common_safe_retention": (
                np.nan if opportunities == 0 else common_safe / opportunities
            ),
            "vector_to_common_ratio": (
                np.nan if common_safe == 0 else vector_safe / common_safe
            ),
            "point_violation_rate": point_violations / decisions,
            "vector_violation_rate": vector_violations / decisions,
            "absolute_violation_reduction": (
                point_violations - vector_violations
            ) / decisions,
            "point_deployment_rate": point_deployments / decisions,
            "vector_deployment_rate": vector_deployments / decisions,
        }

    point = statistic(seeds)
    rng = np.random.default_rng(2_027_071_601)
    samples = [
        statistic(rng.choice(seeds, size=len(seeds), replace=True))
        for _ in range(replicates)
    ]
    intervals: dict[str, list[float | None]] = {}
    for key in point:
        values = np.asarray([sample[key] for sample in samples], dtype=float)
        finite = values[np.isfinite(values)]
        intervals[key] = (
            [None, None]
            if not len(finite)
            else [
                float(np.quantile(finite, 0.025)),
                float(np.quantile(finite, 0.975)),
            ]
        )
    return {
        "unit": "seed cluster across all supported datasets",
        "replicates": replicates,
        "random_seed": 2_027_071_601,
        "point_estimates": {
            key: None if not np.isfinite(value) else value
            for key, value in point.items()
        },
        "confidence_intervals_95": intervals,
    }


def primary_inference(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_key = {
        (int(row["seed"]), str(row["dataset"]), str(row["rule"])): row
        for row in rows
    }
    cluster_differences = []
    for seed in FRESH_SEEDS:
        point_count = sum(
            bool(by_key[(seed, dataset, "validation_point_selection")]["violation"])
            for dataset in DATASETS
        )
        vector_count = sum(
            bool(by_key[(seed, dataset, "vera_vector_envelope")]["violation"])
            for dataset in DATASETS
        )
        cluster_differences.append(point_count - vector_count)
    favorable = sum(value > 0 for value in cluster_differences)
    adverse = sum(value < 0 for value in cluster_differences)
    non_ties = favorable + adverse
    sign_p = 1.0 if non_ties == 0 else float(
        binomtest(favorable, non_ties, p=0.5, alternative="two-sided").pvalue
    )

    sentinel_events = []
    for seed in FRESH_SEEDS:
        dataset = SENTINEL_ROTATION[(seed - FRESH_SEEDS[0]) % len(SENTINEL_ROTATION)]
        sentinel_events.append(
            bool(by_key[(seed, dataset, "vera_vector_envelope")]["violation"])
        )
    event_count = sum(sentinel_events)
    bootstrap = bootstrap_primary(rows)
    estimates = bootstrap["point_estimates"]
    intervals = bootstrap["confidence_intervals_95"]
    point_rate = float(estimates["point_violation_rate"])
    vector_rate = float(estimates["vector_violation_rate"])
    relative_reduction = (
        None if point_rate == 0.0 else (point_rate - vector_rate) / point_rate
    )

    dataset_raw_p: dict[str, float] = {}
    per_dataset: dict[str, Any] = {}
    for dataset in DATASETS:
        point_only = vector_only = 0
        for seed in FRESH_SEEDS:
            point_event = bool(
                by_key[(seed, dataset, "validation_point_selection")]["violation"]
            )
            vector_event = bool(
                by_key[(seed, dataset, "vera_vector_envelope")]["violation"]
            )
            point_only += point_event and not vector_event
            vector_only += vector_event and not point_event
        discordant = point_only + vector_only
        raw_p = 1.0 if discordant == 0 else float(
            binomtest(point_only, discordant, p=0.5, alternative="two-sided").pvalue
        )
        dataset_raw_p[dataset] = raw_p
        per_dataset[dataset] = {
            "point_only_violation_seeds": point_only,
            "vector_only_violation_seeds": vector_only,
            "raw_exact_p": raw_p,
        }
    adjusted = holm(dataset_raw_p)
    for dataset in per_dataset:
        per_dataset[dataset]["holm_adjusted_p"] = adjusted[dataset]

    radii = [
        float(row["certified_common_radius"])
        for row in rows
        if row["rule"] == "vera_vector_envelope" and row["deployed"]
    ]
    limiting = Counter(
        coordinate
        for row in rows
        if row["rule"] == "vera_vector_envelope" and row["deployed"]
        for coordinate in row["limiting_coordinates"]
    )
    vector_when_common_abstains = sum(
        bool(by_key[(seed, dataset, "vera_vector_envelope")]["deployed"])
        and not bool(by_key[(seed, dataset, "vera_common_radius")]["deployed"])
        for seed in FRESH_SEEDS
        for dataset in DATASETS
    )
    vector_deployments = [
        row
        for row in rows
        if row["rule"] == "vera_vector_envelope" and row["deployed"]
    ]
    heldout_deployments = [row for row in vector_deployments if row["safe"]]
    heldout_failures = sum(
        bool(row["heldout_stress_violation"]) for row in heldout_deployments
    )

    safety_upper = one_sided_upper(event_count, len(FRESH_SEEDS))
    paired_pass = favorable > adverse and sign_p < 0.05
    safety_pass = safety_upper <= 0.05
    usefulness_lower = intervals["vector_safe_retention"][0]
    usefulness_pass = usefulness_lower is not None and usefulness_lower >= 0.20
    ratio = estimates["vector_to_common_ratio"]
    vector_advantage_pass = ratio is not None and ratio >= 2.0
    return {
        "paired_reduction": {
            "favorable_seed_clusters": favorable,
            "adverse_seed_clusters": adverse,
            "ties": len(FRESH_SEEDS) - non_ties,
            "exact_two_sided_p": sign_p,
            "passed": paired_pass,
        },
        "safety": {
            "sentinel_event_count": event_count,
            "sentinel_decision_count": len(FRESH_SEEDS),
            "one_sided_cp95_upper": safety_upper,
            "exact_two_sided_interval": exact_interval(event_count, len(FRESH_SEEDS)),
            "passed": safety_pass,
        },
        "usefulness": {
            "point_estimate": estimates["vector_safe_retention"],
            "confidence_interval_95": intervals["vector_safe_retention"],
            "passed": usefulness_pass,
        },
        "vector_advantage": {
            "point_ratio": ratio,
            "confidence_interval_95": intervals["vector_to_common_ratio"],
            "vector_deploys_when_common_abstains": vector_when_common_abstains,
            "passed": vector_advantage_pass,
        },
        "overall_confirmatory_success": bool(
            paired_pass and safety_pass and usefulness_pass and vector_advantage_pass
        ),
        "effect_sizes": {
            **bootstrap,
            "relative_violation_reduction": relative_reduction,
        },
        "per_dataset_paired_effects": per_dataset,
        "common_radius_distribution_on_vector_deployments": {
            "count": len(radii),
            "minimum": None if not radii else min(radii),
            "median": None if not radii else float(np.median(radii)),
            "maximum": None if not radii else max(radii),
        },
        "limiting_coordinate_counts": dict(sorted(limiting.items())),
        "heldout_attacker_stress": {
            "all_vector_deployment_count": len(vector_deployments),
            "portfolio_safe_deployment_count": len(heldout_deployments),
            "heldout_violation_count": heldout_failures,
            "heldout_safe_fraction": (
                None
                if not heldout_deployments
                else 1.0 - heldout_failures / len(heldout_deployments)
            ),
            "formal_guarantee": False,
        },
    }


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    prereg = load_json(args.prereg)
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    if sha256(args.prereg) != expected_hash:
        raise RuntimeError("controlled-shift preregistration hash mismatch")
    if prereg.get("status") != "locked_before_claim_grade_runs":
        raise RuntimeError("controlled-shift preregistration is not locked")
    study = prereg["real_study"]
    seeds = tuple(int(seed) for seed in study["seeds"])
    if seeds != FRESH_SEEDS:
        raise RuntimeError("fresh seed block differs from the locked analysis")

    rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    for dataset in DATASETS:
        contract = study["locked_dataset_contracts"][dataset]
        target_threshold = float(contract["target_harm_threshold"])
        leakage_threshold = float(contract["balanced_leakage_threshold"])
        for seed in seeds:
            loaded, _ = load_candidates(args.receipt_dir, study, dataset, seed)
            metadata, design_metadata = validate_shared_metadata(loaded)
            candidates = [
                {
                    "candidate": candidate["candidate"],
                    "method": candidate["method"],
                    "reference": candidate_arrays(
                        candidate["arrays"], "certification"
                    ),
                    "design": candidate_arrays(candidate["arrays"], "external"),
                    "raw_arrays": candidate["arrays"],
                }
                for candidate in loaded
            ]
            design_rng = np.random.default_rng(
                2_027_071_500 + 1009 * seed + sum(map(ord, dataset))
            )
            design_size = min(1000, len(design_metadata["source"]))
            design_indices = np.sort(
                design_rng.choice(
                    len(design_metadata["source"]),
                    size=design_size,
                    replace=False,
                )
            )
            for requested_gamma in GAMMAS:
                probabilities, shift = design_controlled_shift_from_fold(
                    metadata["environment"],
                    metadata["source"],
                    metadata["target"],
                    design_metadata["environment"][design_indices],
                    design_metadata["source"][design_indices],
                    design_metadata["target"][design_indices],
                    requested_gamma=requested_gamma,
                    minimum_design_cell_count=max(2, min(8, design_size // 20)),
                )
                evaluation_rng = np.random.default_rng(
                    6_000_000_000
                    + 1_000_003 * seed
                    + 10_007 * int(round(100 * requested_gamma))
                    + sum(map(ord, dataset))
                )
                evaluation_indices = evaluation_rng.choice(
                    len(metadata["source"]),
                    size=50_000,
                    replace=True,
                    p=probabilities,
                )
                density_ratio = probabilities * len(probabilities)
                membership_verified = bool(
                    np.isclose(probabilities.sum(), 1.0)
                    and np.all(probabilities >= 0.0)
                    and density_ratio.max() <= requested_gamma + 1e-10
                )
                if not membership_verified:
                    raise RuntimeError("controlled shift left the declared ambiguity class")
                profiles.append({
                    "dataset": dataset,
                    "seed": seed,
                    **shift.to_dict(),
                    "reference_probability_sha256": array_sha256(probabilities),
                    "design_indices_sha256": array_sha256(design_indices),
                    "evaluation_indices_sha256": array_sha256(evaluation_indices),
                    "evaluation_size": int(len(evaluation_indices)),
                    "membership_verified": membership_verified,
                })
                for candidate in candidates:
                    candidate["q_metrics"] = q_metrics(
                        candidate["reference"], probabilities
                    )
                    candidate["evaluation_metrics"] = sampled_metrics(
                        candidate["reference"], evaluation_indices
                    )
                scores, pilot_candidate = allocation_scores(
                    candidates,
                    design_indices,
                    shift.target_profile,
                    shift.source_profile,
                    target_threshold=target_threshold,
                    leakage_threshold=leakage_threshold,
                )
                for budget in BUDGETS:
                    plans = {
                        "uniform": allocate_integer_budget(
                            {key: 1.0 for key in scores},
                            total_budget=budget,
                            minimum_per_cell=1,
                        ),
                        "targeted_floor_0.15": allocate_integer_budget(
                            scores,
                            total_budget=budget,
                            minimum_per_cell=max(1, int(np.ceil(0.15 * budget))),
                        ),
                    }
                    for allocation_name, allocation in plans.items():
                        allocations.append({
                            "dataset": dataset,
                            "seed": seed,
                            "requested_gamma": requested_gamma,
                            "total_budget": budget,
                            "allocation": allocation_name,
                            "pilot_candidate": pilot_candidate,
                            "cell_allocation": allocation,
                            "scores": scores,
                        })
                        rng = np.random.default_rng(
                            8_000_000_000
                            + 1_000_003 * seed
                            + 10_007 * int(round(100 * requested_gamma))
                            + 101 * budget
                            + sum(map(ord, dataset))
                        )
                        decisions = evaluate_configuration(
                            candidates,
                            metadata,
                            probabilities,
                            shift.target_profile,
                            shift.source_profile,
                            allocation,
                            rng=rng,
                            delta=float(study["delta"]),
                            target_threshold=target_threshold,
                            leakage_threshold=leakage_threshold,
                        )
                        attach_stress_metrics(
                            decisions,
                            candidates,
                            probabilities,
                            leakage_threshold,
                        )
                        oracle_deployed = decisions["external_oracle"]["deployed"]
                        for rule, decision in decisions.items():
                            rows.append({
                                "dataset": dataset,
                                "seed": seed,
                                "requested_gamma": requested_gamma,
                                "total_budget": budget,
                                "allocation": allocation_name,
                                "rule": rule,
                                "oracle_deployed": oracle_deployed,
                                **decision,
                            })

    summaries = summarize(rows)
    primary_rows = [
        row
        for row in rows
        if row["requested_gamma"] == PRIMARY_GAMMA
        and row["total_budget"] == PRIMARY_BUDGET
        and row["allocation"] == PRIMARY_ALLOCATION
    ]
    inference = primary_inference(primary_rows)
    return {
        "schema_version": 1,
        "name": "VERA prospective controlled-shift confirmatory analysis",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_git_commit": git_commit(),
        "preregistration_sha256": sha256(args.prereg),
        "analysis_tier": "confirmatory primary plus preregistered secondary analyses",
        "fresh_seeds": list(seeds),
        "datasets": list(DATASETS),
        "gammas": list(GAMMAS),
        "budgets": list(BUDGETS),
        "allocations": ["targeted_floor_0.15", "uniform"],
        "rules": list(RULES),
        "profile_count": len(profiles),
        "allocation_count": len(allocations),
        "row_count": len(rows),
        "all_profiles_membership_verified": all(
            bool(profile["membership_verified"]) for profile in profiles
        ),
        "primary_setting": {
            "requested_gamma": PRIMARY_GAMMA,
            "total_budget": PRIMARY_BUDGET,
            "allocation": PRIMARY_ALLOCATION,
        },
        "primary_inference": inference,
        "profiles": profiles,
        "allocation_receipts": allocations,
        "rows": rows,
        "summaries": summaries,
        "claim_boundary": (
            "Confirmatory inference concerns the locked finite-reference controlled "
            "shift experiment. Held-out attacker results are stress evidence only."
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = analyze(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    inference = report["primary_inference"]
    print(json.dumps({
        "output": str(args.output),
        "overall_confirmatory_success": inference["overall_confirmatory_success"],
        "paired_reduction": inference["paired_reduction"],
        "safety": inference["safety"],
        "usefulness": inference["usefulness"],
        "vector_advantage": inference["vector_advantage"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
