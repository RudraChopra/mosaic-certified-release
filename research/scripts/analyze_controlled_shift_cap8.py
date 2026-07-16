"""Protocol-compliant cap-8 analyzer for the VERA controlled-shift study."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from analyze_controlled_shift_confirmatory import (
    BUDGETS,
    DATASETS,
    FRESH_SEEDS,
    GAMMAS,
    PRIMARY_ALLOCATION,
    PRIMARY_BUDGET,
    PRIMARY_GAMMA,
    array_sha256,
    attach_stress_metrics,
    primary_inference,
)
from analyze_vera_secondary_ablations import load_json, sha256
from cap8_evaluator import evaluate_configuration_cap
from design_vera_controlled_shift_study import (
    RULES,
    allocation_scores,
    candidate_arrays,
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
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_controlled_shift_confirmatory_cap8.json"
EXPECTED_GAMMA_CAP = 8.0
EXPECTED_ROW_COUNT = 55_296
EXPECTED_CANDIDATE_DETAIL_COUNT = 73_728
LOCKED_FILE_SHA256 = {
    "analyze_controlled_shift_confirmatory.py": (
        "c4858136e189a4b9ecdbe55fd912c6cf83e6dce42a3320add581f18d596180ad"
    ),
    "design_vera_controlled_shift_study.py": (
        "0bfd96da6bfb7012eeae4fe8530a608009c3b397c405d858aae7697af0757966"
    ),
    "vera_robust_certificate.py": (
        "76b4e8aa03af09ffba6a44ddddf37f0d28e81365eb90d6cf2830cad6d3937f5b"
    ),
}
CANONICAL_METHOD = {
    "inlp": "INLP",
    "rlace": "R-LACE",
    "leace": "LEACE",
    "taco": "TaCo",
    "mance": "MANCE++",
}


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def verify_locked_dependencies() -> dict[str, str]:
    observed = {
        name: file_sha256(ROOT / "scripts" / name) for name in LOCKED_FILE_SHA256
    }
    if observed != LOCKED_FILE_SHA256:
        raise RuntimeError(
            "the locked cap-4 analyzer or one of its executable dependencies changed"
        )
    return observed


def canonical_strengths(method_key: str, config: dict[str, Any]) -> tuple[str, ...]:
    candidate = config["candidate_configuration"]
    if method_key in {"inlp", "rlace"}:
        return tuple(f"rank={int(value)}" for value in candidate["ranks"])
    if method_key == "leace":
        return (str(candidate["candidate"]),)
    if method_key == "taco":
        return tuple(
            f"components_removed={int(value)}" for value in candidate["removals"]
        )
    if method_key == "mance":
        return (
            f"epsilon={float(candidate['epsilon']):g},steps={int(candidate['steps'])}",
        )
    raise RuntimeError(f"unknown registered method key: {method_key}")


def verify_candidate_key_crosswalk(study: dict[str, Any]) -> dict[str, str]:
    canonical_keys = sorted(
        f"{CANONICAL_METHOD[method_key]}::{strength}"
        for method_key, config in study["methods"].items()
        for strength in canonical_strengths(method_key, config)
    )
    if len(canonical_keys) != 12 or len(canonical_keys) != len(set(canonical_keys)):
        raise RuntimeError("canonical candidate frontier is not the exact 12-key set")
    crosswalk = {
        key: (
            key.replace("R-LACE::", "RLACE::", 1)
            if key.startswith("R-LACE::")
            else key
        )
        for key in canonical_keys
    }
    if len(set(crosswalk.values())) != len(crosswalk):
        raise RuntimeError("candidate-key crosswalk is not one-to-one")
    legacy_order_mapped_back = [
        canonical
        for legacy in sorted(crosswalk.values())
        for canonical, mapped in crosswalk.items()
        if mapped == legacy
    ]
    if legacy_order_mapped_back != canonical_keys:
        raise RuntimeError("candidate-key crosswalk changes stable-key ordering")
    return crosswalk


def load_canonical_candidates(
    receipt_dir: Path,
    study: dict[str, Any],
    dataset: str,
    seed: int,
) -> list[dict[str, Any]]:
    loaded: list[dict[str, Any]] = []
    reference: tuple[np.ndarray, np.ndarray, np.ndarray] | None = None
    for method_key, method_config in study["methods"].items():
        canonical_method = CANONICAL_METHOD.get(method_key)
        if canonical_method is None:
            raise RuntimeError(f"unknown registered method key: {method_key}")
        receipt_path = receipt_dir / f"{dataset}__{method_key}__seed-{seed}.json"
        receipt = load_json(receipt_path)
        expected_keys = {
            f"{canonical_method}::{strength}"
            for strength in canonical_strengths(method_key, method_config)
        }
        candidates = receipt.get("candidates", [])
        if not isinstance(candidates, list) or len(candidates) != len(expected_keys):
            raise RuntimeError(f"candidate count mismatch: {receipt_path.name}")
        observed_keys: set[str] = set()
        for candidate in candidates:
            method = str(candidate.get("method", ""))
            strength = str(candidate.get("strength", ""))
            candidate_key = str(candidate.get("candidate_key", ""))
            if method != canonical_method or candidate_key != f"{method}::{strength}":
                raise RuntimeError(
                    f"candidate method/key/strength mismatch: {receipt_path.name}"
                )
            if candidate_key not in expected_keys or candidate_key in observed_keys:
                raise RuntimeError(f"unexpected candidate key: {candidate_key}")
            observed_keys.add(candidate_key)
            audit_path = Path(str(candidate.get("audit_npz", "")))
            if file_sha256(audit_path) != candidate.get("audit_npz_sha256"):
                raise RuntimeError(f"candidate audit hash mismatch: {candidate_key}")
            with np.load(audit_path, allow_pickle=False) as archive:
                arrays = {key: np.asarray(archive[key]) for key in archive.files}
            labels = (
                arrays["target_certification"],
                arrays["source_certification"],
                arrays["environment_certification"],
            )
            if reference is None:
                reference = labels
            elif not all(
                np.array_equal(left, right) for left, right in zip(reference, labels)
            ):
                raise RuntimeError(
                    f"candidate labels disagree for {dataset}/seed-{seed}"
                )
            legacy_key = (
                candidate_key.replace("R-LACE::", "RLACE::", 1)
                if candidate_key.startswith("R-LACE::")
                else candidate_key
            )
            loaded.append(
                {
                    "candidate": candidate_key,
                    "legacy_cap4_candidate_key": legacy_key,
                    "method": method,
                    "strength": strength,
                    "arrays": arrays,
                    "audit_npz_sha256": candidate["audit_npz_sha256"],
                    "receipt_certification_split_sha256": receipt["indices"]
                    ["certification"]["sha256"],
                }
            )
        if observed_keys != expected_keys:
            raise RuntimeError(f"candidate frontier mismatch: {receipt_path.name}")
    if reference is None:
        raise RuntimeError(f"no candidates loaded for {dataset}/seed-{seed}")
    return loaded


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    locked_hashes = verify_locked_dependencies()
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
    gamma_cap = float(study["gamma_cap"])
    if gamma_cap != EXPECTED_GAMMA_CAP:
        raise RuntimeError(
            f"registered gamma cap differs from {EXPECTED_GAMMA_CAP:g}: {gamma_cap:g}"
        )
    candidate_key_crosswalk = verify_candidate_key_crosswalk(study)

    rows: list[dict[str, Any]] = []
    profiles: list[dict[str, Any]] = []
    allocations: list[dict[str, Any]] = []
    candidate_envelopes: list[dict[str, Any]] = []
    for dataset in DATASETS:
        contract = study["locked_dataset_contracts"][dataset]
        target_threshold = float(contract["target_harm_threshold"])
        leakage_threshold = float(contract["balanced_leakage_threshold"])
        for seed in seeds:
            loaded = load_canonical_candidates(
                args.receipt_dir, study, dataset, seed
            )
            metadata, design_metadata = validate_shared_metadata(loaded)
            candidates = [
                {
                    "candidate": candidate["candidate"],
                    "method": candidate["method"],
                    "legacy_cap4_candidate_key": candidate[
                        "legacy_cap4_candidate_key"
                    ],
                    "reference": candidate_arrays(
                        candidate["arrays"], "certification"
                    ),
                    "design": candidate_arrays(candidate["arrays"], "external"),
                    "raw_arrays": candidate["arrays"],
                    "audit_npz_sha256": candidate["audit_npz_sha256"],
                    "receipt_certification_split_sha256": candidate[
                        "receipt_certification_split_sha256"
                    ],
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
                    raise RuntimeError(
                        "controlled shift left the declared ambiguity class"
                    )
                profiles.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        **shift.to_dict(),
                        "reference_probability_sha256": array_sha256(probabilities),
                        "design_indices_sha256": array_sha256(design_indices),
                        "evaluation_indices_sha256": array_sha256(evaluation_indices),
                        "evaluation_size": int(len(evaluation_indices)),
                        "membership_verified": membership_verified,
                    }
                )
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
                        allocations.append(
                            {
                                "dataset": dataset,
                                "seed": seed,
                                "requested_gamma": requested_gamma,
                                "total_budget": budget,
                                "allocation": allocation_name,
                                "pilot_candidate": pilot_candidate,
                                "cell_allocation": allocation,
                                "scores": scores,
                            }
                        )
                        rng = np.random.default_rng(
                            8_000_000_000
                            + 1_000_003 * seed
                            + 10_007 * int(round(100 * requested_gamma))
                            + 101 * budget
                            + sum(map(ord, dataset))
                        )
                        decisions, details = evaluate_configuration_cap(
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
                            gamma_cap=gamma_cap,
                        )
                        attach_stress_metrics(
                            decisions,
                            candidates,
                            probabilities,
                            leakage_threshold,
                        )
                        oracle_deployed = decisions["external_oracle"]["deployed"]
                        configuration = {
                            "dataset": dataset,
                            "seed": seed,
                            "requested_gamma": requested_gamma,
                            "total_budget": budget,
                            "allocation": allocation_name,
                        }
                        for detail in details:
                            candidate_envelopes.append({**configuration, **detail})
                        for rule, decision in decisions.items():
                            rows.append(
                                {
                                    **configuration,
                                    "rule": rule,
                                    "oracle_deployed": oracle_deployed,
                                    **decision,
                                }
                            )

    profiles.sort(key=lambda row: (row["dataset"], row["seed"], row["requested_gamma"]))
    allocations.sort(
        key=lambda row: (
            row["dataset"],
            row["seed"],
            row["requested_gamma"],
            row["total_budget"],
            row["allocation"],
        )
    )
    rows.sort(
        key=lambda row: (
            row["dataset"],
            row["seed"],
            row["requested_gamma"],
            row["total_budget"],
            row["allocation"],
            row["rule"],
        )
    )
    candidate_envelopes.sort(
        key=lambda row: (
            row["dataset"],
            row["seed"],
            row["requested_gamma"],
            row["total_budget"],
            row["allocation"],
            row["canonical_candidate_key"],
        )
    )
    if len(rows) != EXPECTED_ROW_COUNT:
        raise RuntimeError(
            f"decision-row count mismatch: {len(rows)} != {EXPECTED_ROW_COUNT}"
        )
    if len(candidate_envelopes) != EXPECTED_CANDIDATE_DETAIL_COUNT:
        raise RuntimeError(
            "candidate-envelope count mismatch: "
            f"{len(candidate_envelopes)} != {EXPECTED_CANDIDATE_DETAIL_COUNT}"
        )
    summaries = summarize(rows)
    primary_rows = [
        row
        for row in rows
        if row["requested_gamma"] == PRIMARY_GAMMA
        and row["total_budget"] == PRIMARY_BUDGET
        and row["allocation"] == PRIMARY_ALLOCATION
    ]
    inference = primary_inference(primary_rows)
    inference["common_limiting_contract_counts"] = dict(
        sorted(
            Counter(
                contract
                for row in primary_rows
                if row["rule"] == "vera_vector_envelope" and row["deployed"]
                for contract in row["common_limiting_contracts"]
            ).items()
        )
    )
    return {
        "schema_version": 2,
        "name": "VERA protocol-compliant cap-8 controlled-shift analysis",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_git_commit": git_commit(),
        "preregistration_sha256": sha256(args.prereg),
        "locked_cap4_dependency_sha256": locked_hashes,
        "candidate_key_crosswalk": candidate_key_crosswalk,
        "candidate_key_crosswalk_order_preserving": True,
        "radius_gamma_cap": gamma_cap,
        "analysis_tier": (
            "confirmatory primary plus preregistered secondary analyses and "
            "protocol-cap geometry"
        ),
        "fresh_seeds": list(seeds),
        "datasets": list(DATASETS),
        "gammas": list(GAMMAS),
        "budgets": list(BUDGETS),
        "allocations": ["targeted_floor_0.15", "uniform"],
        "rules": list(RULES),
        "profile_count": len(profiles),
        "allocation_count": len(allocations),
        "row_count": len(rows),
        "candidate_envelope_detail_count": len(candidate_envelopes),
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
        "candidate_envelopes": candidate_envelopes,
        "summaries": summaries,
        "claim_boundary": (
            "Confirmatory inference concerns the locked finite-reference controlled "
            "shift experiment. The cap extends registered geometry only; held-out "
            "attacker results remain stress evidence."
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
    print(
        json.dumps(
            {
                "output": str(args.output),
                "output_sha256": file_sha256(args.output),
                "row_count": report["row_count"],
                "candidate_envelope_detail_count": report[
                    "candidate_envelope_detail_count"
                ],
                "radius_gamma_cap": report["radius_gamma_cap"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
