"""Analyze VERA's final P0 protocol without pooling earlier seed blocks."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.stats import beta, binomtest

from vera_p0_evaluator import (
    RULES,
    allocation_from_construction,
    candidate_arrays,
    choose_construction_design,
    evaluate_configuration,
    focus_cell_shift,
    q_metrics,
    validate_shared_metadata,
)


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PREREG = ROOT / "prereg_vera_p0_confirmation_v3.json"
DEFAULT_HASH = ROOT / "prereg_vera_p0_confirmation_v3.sha256"
DEFAULT_RECEIPTS = Path(
    "/Volumes/Backups/FARO/artifacts/vera_p0_confirmation_v3_receipts"
)
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_p0_confirmation_v3.json"
DATASETS = ("Bios", "CivilComments-WILDS", "GaitPDB", "Waterbirds")
PRIMARY_GAMMA = 1.25
PRIMARY_BUDGET = 12000
USEFULNESS_GAMMAS = (1.1, 1.25)
BOOTSTRAP_REPLICATES = 20_000


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).view(np.uint8)).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def one_sided_upper(events: int, n: int, alpha: float = 0.05) -> float:
    if n <= 0 or events < 0 or events > n:
        raise ValueError("invalid binomial event count")
    return 1.0 if events == n else float(beta.ppf(1.0 - alpha, events + 1, n - events))


def one_sided_lower(events: int, n: int, alpha: float = 0.05) -> float:
    if n <= 0 or events < 0 or events > n:
        raise ValueError("invalid binomial event count")
    return 0.0 if events == 0 else float(beta.ppf(alpha, events, n - events + 1))


def _required_construction_arrays(study: Mapping[str, Any]) -> set[str]:
    schema = study.get("construction_receipt_schema", {})
    arrays = schema.get("required_arrays", []) if isinstance(schema, dict) else []
    if not isinstance(arrays, list) or not arrays:
        raise RuntimeError("P0 preregistration lacks a construction receipt schema")
    return {str(value) for value in arrays}


def load_candidates(
    receipt_dir: Path,
    study: Mapping[str, Any],
    prereg_hash: str,
    dataset: str,
    seed: int,
    attackers: tuple[str, ...],
    heldout_name: str,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, np.ndarray]]]:
    """Load a complete P0 frontier and verify its receipt/audit identities."""

    expected_arrays = _required_construction_arrays(study)
    loaded: list[dict[str, Any]] = []
    observed_keys: set[str] = set()
    for method in study["methods"]:
        receipt_path = receipt_dir / f"{dataset}__{method}__seed-{seed}.json"
        receipt = load_json(receipt_path)
        if (
            receipt.get("claim_grade") is not True
            or receipt.get("smoke") is not False
            or receipt.get("prereg_sha256") != prereg_hash
            or receipt.get("claim_configuration_verified") is not True
        ):
            raise RuntimeError(f"receipt is not a locked P0 claim-grade run: {receipt_path}")
        if receipt.get("dataset") != dataset or int(receipt.get("seed", -1)) != seed:
            raise RuntimeError(f"receipt identity mismatch: {receipt_path}")
        candidates = receipt.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise RuntimeError(f"receipt has no candidates: {receipt_path}")
        for candidate in candidates:
            candidate_key = str(candidate.get("candidate_key", ""))
            audit_path = Path(str(candidate.get("audit_npz", "")))
            if not candidate_key or candidate_key in observed_keys:
                raise RuntimeError(f"candidate frontier key mismatch: {receipt_path}")
            if sha256(audit_path) != candidate.get("audit_npz_sha256"):
                raise RuntimeError(f"audit hash mismatch: {candidate_key}")
            with np.load(audit_path, allow_pickle=False) as archive:
                arrays = {key: np.asarray(archive[key]) for key in archive.files}
            missing = sorted(expected_arrays.difference(arrays))
            if missing:
                raise RuntimeError(
                    f"P0 receipt misses construction arrays for {candidate_key}: {missing}"
                )
            heldout_key = f"heldout_leakage_correct_certification__{heldout_name}"
            if heldout_key not in arrays:
                raise RuntimeError(f"P0 receipt misses held-out KNN: {candidate_key}")
            reference = candidate_arrays(arrays, "certification", attackers)
            reference[f"heldout::{heldout_name}"] = np.asarray(arrays[heldout_key])
            loaded.append(
                {
                    "candidate": candidate_key,
                    "method": str(candidate.get("method", "")),
                    "raw_arrays": arrays,
                    "reference": reference,
                    "audit_npz_sha256": str(candidate["audit_npz_sha256"]),
                    "receipt_certification_split_sha256": receipt["indices"]
                    ["certification"]["sha256"],
                }
            )
            observed_keys.add(candidate_key)
    expected_count = int(study["candidate_count_total"])
    if len(loaded) != expected_count:
        raise RuntimeError(
            f"candidate count mismatch for {dataset}/seed-{seed}: "
            f"{len(loaded)} != {expected_count}"
        )
    metadata = validate_shared_metadata(loaded, attackers)
    return sorted(loaded, key=lambda row: str(row["candidate"])), metadata


def _native_mixture(values: np.ndarray) -> dict[str, float]:
    labels, counts = np.unique(values.astype(int), return_counts=True)
    return {str(label): float(count / counts.sum()) for label, count in zip(labels, counts)}


def natural_metrics(
    candidate: Mapping[str, Any],
    attackers: tuple[str, ...],
    heldout_name: str,
    *,
    target_threshold: float,
    leakage_threshold: float,
) -> dict[str, Any]:
    """Describe, but do not certify, the untouched native external mixture."""

    external = candidate_arrays(candidate["raw_arrays"], "external", attackers)
    cert = candidate_arrays(candidate["raw_arrays"], "certification", attackers)
    if f"heldout_leakage_correct_external__{heldout_name}" not in candidate["raw_arrays"]:
        raise RuntimeError("native diagnostic lacks the held-out KNN array")
    external[f"leakage::{heldout_name}"] = np.asarray(
        candidate["raw_arrays"][f"heldout_leakage_correct_external__{heldout_name}"]
    )
    q = np.full(len(external["source"]), 1.0 / len(external["source"]))
    max_target, max_leakage, attacker_risks = q_metrics(external, q, attackers)
    _, heldout_leakage, _ = q_metrics(external, q, (heldout_name,))
    by_environment = {
        str(environment): float(
            external["target_harm"][external["environment"] == environment].mean()
        )
        for environment in sorted(map(int, np.unique(external["environment"])))
    }
    cert_mix = _native_mixture(cert["environment"])
    external_mix = _native_mixture(external["environment"])
    all_environments = sorted(set(cert_mix) | set(external_mix), key=int)
    ratios = {
        environment: (
            None
            if cert_mix.get(environment, 0.0) == 0.0
            else external_mix.get(environment, 0.0) / cert_mix[environment]
        )
        for environment in all_environments
    }
    finite_ratios = [value for value in ratios.values() if value is not None]
    return {
        "native_target_harm_pooled": float(external["target_harm"].mean()),
        "native_target_harm_by_environment": by_environment,
        "native_target_harm_max_environment": max_target,
        "native_registered_attacker_balanced_leakage": attacker_risks,
        "native_registered_attacker_max_leakage": max_leakage,
        "native_heldout_knn_balanced_leakage": heldout_leakage,
        "validation_environment_mixture": cert_mix,
        "external_environment_mixture": external_mix,
        "environment_mixture_ratio_external_over_validation": ratios,
        "environment_mixture_ratio_cap": None if not finite_ratios else max(finite_ratios),
        "support_overlap": set(cert_mix) == set(external_mix),
        "contract_like_violation": bool(
            max_target > target_threshold or max_leakage > leakage_threshold
        ),
    }


def retention_bootstrap(
    rows: list[dict[str, Any]], seeds: tuple[int, ...], *, rng_seed: int
) -> dict[str, Any]:
    by_key = {
        (int(row["seed"]), str(row["dataset"]), str(row["rule"])): row for row in rows
    }

    def statistic(sample: np.ndarray) -> float:
        opportunities = retained = 0
        for seed in sample:
            for dataset in DATASETS:
                oracle = by_key[(int(seed), dataset, "exact_shift_oracle")]
                vector = by_key[(int(seed), dataset, "vera_vector_envelope")]
                opportunities += bool(oracle["deployed"])
                retained += bool(vector["safe"])
        return np.nan if opportunities == 0 else retained / opportunities

    point = statistic(np.asarray(seeds, dtype=int))
    rng = np.random.default_rng(rng_seed)
    draws = np.asarray(
        [
            statistic(rng.choice(np.asarray(seeds), size=len(seeds), replace=True))
            for _ in range(BOOTSTRAP_REPLICATES)
        ],
        dtype=float,
    )
    finite = draws[np.isfinite(draws)]
    return {
        "point_estimate": None if not np.isfinite(point) else float(point),
        "confidence_interval_95": (
            [None, None]
            if not len(finite)
            else [float(np.quantile(finite, 0.025)), float(np.quantile(finite, 0.975))]
        ),
        "replicates": BOOTSTRAP_REPLICATES,
        "unit": "seed cluster aggregated across four supported datasets",
    }


def primary_inference(
    rows: list[dict[str, Any]], seeds: tuple[int, ...]
) -> dict[str, Any]:
    def subset(gamma: float) -> list[dict[str, Any]]:
        return [
            row
            for row in rows
            if row["requested_gamma"] == gamma
            and row["total_budget"] == PRIMARY_BUDGET
            and row["allocation"] == "targeted_floor_0.15"
        ]

    iid_exposure: dict[str, Any] = {}
    for gamma in (1.0, 1.1, 1.25, 1.5):
        iid_rows = [row for row in subset(gamma) if row["rule"] == "iid_ltt"]
        deployed = sum(bool(row["deployed"]) for row in iid_rows)
        violations = sum(bool(row["violation"]) for row in iid_rows)
        iid_exposure[f"gamma_{gamma:g}"] = {
            "deployment_count": deployed,
            "shifted_contract_violation_count": violations,
            "violation_rate_conditional_on_deployment": (
                None if deployed == 0 else violations / deployed
            ),
            "one_sided_95_lower": None if deployed == 0 else one_sided_lower(violations, deployed),
            "success": bool(deployed and violations / deployed >= 0.20),
        }
    iid_pass = any(record["success"] for record in iid_exposure.values())

    primary = subset(PRIMARY_GAMMA)
    primary_by_key = {
        (int(row["seed"]), str(row["dataset"]), str(row["rule"])): row
        for row in primary
    }
    sentinel_events = []
    for index, seed in enumerate(seeds):
        dataset = DATASETS[index % len(DATASETS)]
        sentinel_events.append(
            bool(primary_by_key[(seed, dataset, "vera_vector_envelope")]["violation"])
        )
    safety_events = sum(sentinel_events)
    safety_upper = one_sided_upper(safety_events, len(seeds))
    safety = {
        "sentinel_event_count": safety_events,
        "sentinel_decision_count": len(seeds),
        "one_sided_cp95_upper": safety_upper,
        "success": safety_events == 0 and safety_upper <= 0.05,
    }

    usefulness = {
        f"gamma_{gamma:g}": retention_bootstrap(
            subset(gamma), seeds, rng_seed=2_027_071_700 + int(100 * gamma)
        )
        for gamma in USEFULNESS_GAMMAS
    }
    usefulness_pass = True
    for record in usefulness.values():
        lower = record["confidence_interval_95"][0]
        record["success"] = lower is not None and lower >= 0.20
        usefulness_pass = usefulness_pass and bool(record["success"])

    differences = []
    for seed in seeds:
        iid = sum(
            bool(primary_by_key[(seed, dataset, "iid_ltt")]["violation"])
            for dataset in DATASETS
        )
        vector = sum(
            bool(primary_by_key[(seed, dataset, "vera_vector_envelope")]["violation"])
            for dataset in DATASETS
        )
        differences.append(iid - vector)
    favorable = sum(value > 0 for value in differences)
    adverse = sum(value < 0 for value in differences)
    non_ties = favorable + adverse
    sign_p = 1.0 if non_ties == 0 else float(
        binomtest(favorable, non_ties, p=0.5, alternative="two-sided").pvalue
    )
    paired = {
        "favorable_seed_clusters": favorable,
        "adverse_seed_clusters": adverse,
        "ties": len(seeds) - non_ties,
        "exact_two_sided_p": sign_p,
        "success": favorable > adverse and sign_p < 0.05,
    }

    vector = [row for row in primary if row["rule"] == "vera_vector_envelope" and row["deployed"]]
    knn_events = sum(bool(row["heldout_knn_stress_violation"]) for row in vector)
    heldout_knn = {
        "formal_guarantee": False,
        "deployment_count": len(vector),
        "stress_violation_count": knn_events,
        "one_sided_cp95_upper": None if not vector else one_sided_upper(knn_events, len(vector)),
    }
    return {
        "iid_ltt_exposure": iid_exposure,
        "iid_ltt_exposure_success": iid_pass,
        "vera_safety": safety,
        "vera_usefulness": usefulness,
        "vera_usefulness_success": usefulness_pass,
        "paired_comparison": paired,
        "heldout_knn_stress": heldout_knn,
        "overall_p0_success": bool(
            iid_pass and safety["success"] and usefulness_pass and paired["success"]
        ),
    }


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    prereg = load_json(args.prereg)
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    prereg_hash = sha256(args.prereg)
    if prereg_hash != expected_hash:
        raise RuntimeError("P0 preregistration hash mismatch")
    if prereg.get("status") != "locked_before_claim_grade_runs":
        raise RuntimeError("P0 preregistration is not locked")
    study = prereg["real_study"]
    seeds = tuple(int(value) for value in study["seeds"])
    if not seeds or tuple(sorted(seeds)) != seeds:
        raise RuntimeError("P0 seed block is not a sorted nonempty sequence")
    attackers = tuple(str(name) for name in study["leakage_attackers"])
    heldout_name = str(study["heldout_attacker"]["name"])
    gamma_cap = float(study["gamma_cap"])
    floor_fraction = float(study["evidence_allocation"]["minimum_fraction_per_registered_cell"])
    gammas = tuple(float(value) for value in prereg["real_study"]["controlled_shift_protocol"]["secondary_requested_gammas"])
    gammas = tuple(sorted(set((*gammas, float(PRIMARY_GAMMA)))))
    budgets = tuple(
        sorted(
            set(
                (*map(int, study["evidence_allocation"]["secondary_budgets"]), PRIMARY_BUDGET)
            )
        )
    )

    rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    natural_rows: list[dict[str, Any]] = []
    receipt_audit = {"receipt_count": 0, "candidate_count": 0, "audit_hashes_verified": True}
    for dataset in DATASETS:
        contract = study["locked_dataset_contracts"][dataset]
        target_threshold = float(contract["target_harm_threshold"])
        leakage_threshold = float(contract["balanced_leakage_threshold"])
        for seed in seeds:
            candidates, metadata = load_candidates(
                args.receipt_dir,
                study,
                prereg_hash,
                dataset,
                seed,
                attackers,
                heldout_name,
            )
            receipt_audit["receipt_count"] += len(study["methods"])
            receipt_audit["candidate_count"] += len(candidates)
            for requested_gamma in gammas:
                selected_key, focus = choose_construction_design(
                    candidates,
                    metadata["certification"],
                    attackers,
                    target_threshold=target_threshold,
                    leakage_threshold=leakage_threshold,
                    requested_gamma=requested_gamma,
                )
                probabilities, shift = focus_cell_shift(
                    metadata["certification"], focus, requested_gamma=requested_gamma
                )
                density_ratio = probabilities * len(probabilities)
                membership = bool(
                    np.isclose(probabilities.sum(), 1.0)
                    and np.all(probabilities >= 0.0)
                    and density_ratio.max() <= requested_gamma + 1e-10
                )
                if not membership:
                    raise RuntimeError("constructed P0 shift violates its declared cap")
                profiles.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "selected_construction_candidate": selected_key,
                        "focus": focus,
                        **shift.to_dict(),
                        "reference_probability_sha256": array_sha256(probabilities),
                        "membership_verified": membership,
                    }
                )
                selected = next(
                    candidate for candidate in candidates if candidate["candidate"] == selected_key
                )
                construction = candidate_arrays(selected["raw_arrays"], "construction", attackers)
                for budget in budgets:
                    allocation, scores = allocation_from_construction(
                        construction,
                        shift,
                        attackers,
                        target_threshold=target_threshold,
                        leakage_threshold=leakage_threshold,
                        total_budget=budget,
                        floor_fraction=floor_fraction,
                    )
                    rng = np.random.default_rng(
                        7_100_000_000
                        + 1_000_003 * seed
                        + 10_007 * int(round(100 * requested_gamma))
                        + 101 * budget
                        + sum(map(ord, dataset))
                    )
                    decisions, candidate_details = evaluate_configuration(
                        candidates,
                        metadata["certification"],
                        probabilities,
                        shift,
                        allocation,
                        attackers,
                        fixed_design_candidate=selected_key,
                        rng=rng,
                        delta=float(study["delta"]),
                        target_threshold=target_threshold,
                        leakage_threshold=leakage_threshold,
                        gamma_cap=gamma_cap,
                        heldout_name=heldout_name,
                    )
                    configuration = {
                        "dataset": dataset,
                        "seed": seed,
                        "requested_gamma": requested_gamma,
                        "total_budget": budget,
                        "allocation": "targeted_floor_0.15",
                    }
                    allocations.append({**configuration, "cell_allocation": allocation, "scores": scores})
                    for detail in candidate_details:
                        details.append({**configuration, **detail})
                    for rule, decision in decisions.items():
                        rows.append({**configuration, "rule": rule, **decision})
                    if requested_gamma == PRIMARY_GAMMA and budget == PRIMARY_BUDGET:
                        by_key = {candidate["candidate"]: candidate for candidate in candidates}
                        for rule, decision in decisions.items():
                            selected_candidate = decision["selected_candidate"]
                            natural_rows.append(
                                {
                                    **configuration,
                                    "rule": rule,
                                    "deployed": decision["deployed"],
                                    "selected_candidate": selected_candidate,
                                    "natural_metrics": (
                                        None
                                        if not selected_candidate
                                        else natural_metrics(
                                            by_key[selected_candidate],
                                            attackers,
                                            heldout_name,
                                            target_threshold=target_threshold,
                                            leakage_threshold=leakage_threshold,
                                        )
                                    ),
                                }
                            )

    rows.sort(key=lambda row: (row["dataset"], row["seed"], row["requested_gamma"], row["total_budget"], row["rule"]))
    profiles.sort(key=lambda row: (row["dataset"], row["seed"], row["requested_gamma"]))
    allocations.sort(key=lambda row: (row["dataset"], row["seed"], row["requested_gamma"], row["total_budget"]))
    details.sort(key=lambda row: (row["dataset"], row["seed"], row["requested_gamma"], row["total_budget"], row["candidate"]))
    natural_rows.sort(key=lambda row: (row["dataset"], row["seed"], row["rule"]))
    expected_settings = len(DATASETS) * len(seeds) * len(gammas) * len(budgets)
    if len(rows) != expected_settings * len(RULES):
        raise RuntimeError("P0 decision row count is incomplete")
    if len(details) != expected_settings * int(study["candidate_count_total"]):
        raise RuntimeError("P0 candidate-detail count is incomplete")
    inference = primary_inference(rows, seeds)
    return {
        "schema_version": 1,
        "name": "VERA P0 independent controlled-shift and natural-mixture confirmation",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_git_commit": git_commit(),
        "preregistration_sha256": prereg_hash,
        "analysis_boundary": (
            "The controlled study concerns exact risks on its declared finite "
            "reference laws. Natural-mixture rows are descriptive diagnostics under "
            "their separately stated conditional-stability assumption."
        ),
        "fresh_seeds": list(seeds),
        "datasets": list(DATASETS),
        "registered_attackers": list(attackers),
        "heldout_attacker": {"name": heldout_name, "formal_guarantee": False},
        "gammas": list(gammas),
        "budgets": list(budgets),
        "rules": list(RULES),
        "receipt_audit": receipt_audit,
        "profile_count": len(profiles),
        "allocation_count": len(allocations),
        "row_count": len(rows),
        "candidate_detail_count": len(details),
        "all_profiles_membership_verified": all(row["membership_verified"] for row in profiles),
        "primary_inference": inference,
        "profiles": profiles,
        "allocation_receipts": allocations,
        "rows": rows,
        "candidate_details": details,
        "natural_group_mixture_diagnostic": natural_rows,
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
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite analysis output: {args.output}")
    result = analyze(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
