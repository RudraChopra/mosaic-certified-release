"""Build the prospective controlled-shift preregistration from frozen design evidence."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_official_eraser_frontier import HELDOUT_ATTACKER_CONFIG


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PARENT = ROOT / "prereg_independent_stress_replication.json"
DEFAULT_DESIGN = ROOT / "artifacts" / "vera_controlled_shift_design.json"
DEFAULT_POWER = ROOT / "artifacts" / "vera_controlled_shift_power.json"
DEFAULT_OUTPUT = ROOT / "prereg_controlled_shift.json"
FRESH_RECEIPT_DIR = Path(
    "/Volumes/Backups/FARO/artifacts/vera_controlled_shift_receipts"
)
FRESH_AUDIT_DIR = Path(
    "/Volumes/Backups/FARO/artifacts/vera_controlled_shift_audit_arrays"
)
SUPPORTED_DATASETS = (
    "Bios",
    "CivilComments-WILDS",
    "GaitPDB",
    "Waterbirds",
)
DESIGN_SEEDS = list(range(13, 45))
FRESH_SEEDS = list(range(45, 109))
PRIMARY_GAMMA = 1.1
SECONDARY_GAMMAS = [1.25, 1.5]
PRIMARY_BUDGET = 4000
SENSITIVITY_BUDGETS = [1000, 2000, 8000]
TARGETED_FLOOR_FRACTION = 0.15


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected an object in {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def git_commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def verify_fresh_outcomes_absent() -> None:
    for directory in (FRESH_RECEIPT_DIR, FRESH_AUDIT_DIR):
        if directory.exists() and any(directory.iterdir()):
            raise RuntimeError(f"fresh outcome directory is not empty: {directory}")
    for seed in FRESH_SEEDS:
        patterns = (f"*seed-{seed}.json", f"*seed-{seed}__*.json")
        for pattern in patterns:
            if any((ROOT / "artifacts").glob(f"*receipts/{pattern}")):
                raise RuntimeError(
                    f"fresh seed {seed} already appears in a repository receipt"
                )


def validate_design_and_power(
    design: dict[str, Any], power: dict[str, Any], design_path: Path
) -> None:
    require(design.get("analysis_tier", "").startswith("exploratory"),
            "design report is not labeled exploratory")
    require(design.get("design_seeds") == DESIGN_SEEDS,
            "design seed block differs from the locked plan")
    require(design.get("future_seed_block") == FRESH_SEEDS,
            "design report future seed block differs from the power plan")
    require(all(bool(row.get("membership_verified")) for row in design["profiles"]),
            "a designed deployment law leaves its declared ambiguity class")
    require(not ({int(row["seed"]) for row in design["rows"]} & set(FRESH_SEEDS)),
            "fresh seeds appear in the exploratory design report")
    primary = design.get("recommended_primary") or {}
    require(primary.get("requested_gamma") == PRIMARY_GAMMA,
            "design recommendation has the wrong primary Gamma")
    require(primary.get("total_budget") == PRIMARY_BUDGET,
            "design recommendation has the wrong evidence budget")
    require(primary.get("allocation") == "targeted_floor_0.15",
            "design recommendation has the wrong allocation")
    require(power.get("design_report_sha256") == sha256(design_path),
            "power report does not hash the current design report")
    require(power.get("fresh_seed_block") == FRESH_SEEDS,
            "power report has the wrong fresh seed block")
    require(power.get("planned_seed_count") == len(FRESH_SEEDS),
            "power report has the wrong planned seed count")
    require(bool(power.get("fresh_block_disjoint_from_design")),
            "power report does not verify seed disjointness")
    require(
        power.get("safety_endpoint", {}).get("planned_zero_event_cp95_upper", 1.0)
        < 0.05,
        "planned sample size cannot establish the locked zero-event safety bound",
    )


def build_payload(
    parent: dict[str, Any],
    design: dict[str, Any],
    power: dict[str, Any],
    *,
    parent_path: Path,
    design_path: Path,
    power_path: Path,
) -> dict[str, Any]:
    parent_study = parent["real_study"]
    study = copy.deepcopy(parent_study)
    study["analysis_tiers"] = {
        "primary": (
            "prospective controlled supported shift experiment on seeds 45-108"
        ),
        "secondary": (
            "Gamma, evidence-budget, allocation, attacker, and candidate-family "
            "sensitivity analyses on the same seed clusters"
        ),
        "support_boundary": (
            "the prior Camelyon17 unsupported-hospital experiment remains separate"
        ),
    }
    study["datasets"] = {
        name: copy.deepcopy(parent_study["datasets"][name])
        for name in SUPPORTED_DATASETS
    }
    study["seeds"] = FRESH_SEEDS
    study["locked_dataset_contracts"] = {
        name: {
            "target_harm_threshold": parent_study["locked_dataset_contracts"][name][
                "target_harm_threshold"
            ],
            "balanced_leakage_threshold": parent_study[
                "locked_dataset_contracts"
            ][name]["balanced_leakage_threshold"],
            "source": (
                "frozen before the controlled-shift study; no fresh outcome may "
                "change this threshold"
            ),
        }
        for name in SUPPORTED_DATASETS
    }
    study["heldout_attacker"] = copy.deepcopy(HELDOUT_ATTACKER_CONFIG)
    study["paired_harm_component_arrays_required"] = True
    study["candidate_count_total"] = sum(
        int(method["candidate_count"]) for method in study["methods"].values()
    )
    require(study["candidate_count_total"] == 12,
            "the official eraser frontier no longer contains 12 candidates")
    study["deployment_gamma"] = PRIMARY_GAMMA
    study["deployment_rules"] = [
        "always_deploy",
        "validation_point_selection",
        "iid_ltt",
        "robust_point_estimate",
        "generic_scalar_robust_certificate",
        "vera_fixed_profile",
        "vera_vector_envelope",
        "vera_common_radius",
        "external_oracle",
    ]
    study["controlled_shift_protocol"] = {
        "scientific_object": (
            "the finite empirical reference law induced by each seed's untouched "
            "official validation audit atoms"
        ),
        "shift_design_fold": (
            "a deterministic sample of at most 1000 official external-fold atoms; "
            "metadata choose the shifted cell and outcomes may determine only the "
            "prospective evidence allocation"
        ),
        "focus_cell_rule": (
            "choose the lexicographically tie-broken rarest supported "
            "environment-source-target cell having the prespecified minimum design "
            "count and capable of realizing the requested Gamma"
        ),
        "weight_rule": (
            "within the focus environment assign the focus cell density ratio Gamma, "
            "give all nonfocus atoms the unique nonnegative residual weight preserving "
            "total mass, and leave every other environment unchanged"
        ),
        "support_rule": (
            "the deployment law may reweight only atoms present in the reference; "
            "missing registered environments or source classes force abstention"
        ),
        "primary_requested_gamma": PRIMARY_GAMMA,
        "secondary_requested_gammas": SECONDARY_GAMMAS,
        "profile": (
            "use the exact induced vector of environment-conditional and "
            "source-conditional density-ratio caps, not the global Gamma alone"
        ),
        "membership_receipt": (
            "store every profile, probability-vector hash, focus cell, exact global "
            "cap, and a machine-checked membership indicator"
        ),
        "certification_stream": (
            "independent with-replacement draws from the finite reference law using "
            "the locked per-cell evidence allocation"
        ),
        "final_evaluation_stream": (
            "50000 independent with-replacement draws from the exact shifted finite "
            "law; its draw indices and outcomes are unavailable to weight choice, "
            "candidate selection, and certification"
        ),
        "evaluation_stream_size_per_dataset_seed_profile": 50000,
        "claim_boundary": (
            "this is a controlled finite-reference replay with mathematically known "
            "shift membership; resampled atoms are not described as new patients, "
            "comments, images, or recordings"
        ),
    }
    study["evidence_allocation"] = {
        "primary_total_contract_observation_budget": PRIMARY_BUDGET,
        "primary_rule": "targeted_floor_0.15",
        "minimum_fraction_per_registered_cell": TARGETED_FLOOR_FRACTION,
        "score_rule": (
            "on the shift-design fold, select the candidate with the largest minimum "
            "normalized contract margin; allocate the remaining integer budget in "
            "proportion to squared Gamma-over-margin scores with deterministic "
            "largest-remainder rounding"
        ),
        "uniform_ablation": True,
        "sensitivity_budgets": SENSITIVITY_BUDGETS,
        "allocation_may_not_read": [
            "certification stream outcomes",
            "final evaluation stream outcomes",
        ],
    }
    study["primary_endpoints"] = {
        "paired_reduction": {
            "unit": "seed cluster across all four supported datasets",
            "contrast": (
                "validation point-selection violation count minus VERA vector-envelope "
                "violation count within each seed"
            ),
            "test": "two-sided exact sign test on non-tied seed differences",
            "success": "positive effect and p < 0.05",
        },
        "safety": {
            "unit": "one prespecified rotating dataset decision per seed",
            "rotation": ["Bios", "CivilComments-WILDS", "GaitPDB", "Waterbirds"],
            "rotation_index": "(seed - 45) modulo 4",
            "event": (
                "VERA vector-envelope deploys an edit whose exact shifted-law target "
                "or registered-portfolio leakage contract exceeds its threshold"
            ),
            "interval": "one-sided exact 95% Clopper-Pearson upper bound",
            "success": "upper bound <= 0.05",
        },
        "usefulness": {
            "unit": "seed cluster",
            "estimand": (
                "safe VERA vector-envelope deployments divided by exact shifted-law "
                "oracle-safe opportunities across supported datasets"
            ),
            "interval": (
                "95% percentile bootstrap over whole seed clusters with 20000 "
                "replicates and random seed 2027071601"
            ),
            "success": "lower confidence bound >= 0.20",
        },
        "vector_advantage": {
            "unit": "seed cluster",
            "estimand": (
                "vector-envelope safe retention divided by common-radius safe retention"
            ),
            "success": (
                "point ratio >= 2.0 with its seed-cluster bootstrap interval reported"
            ),
        },
    }
    study["primary_multiplicity"] = (
        "The overall confirmatory claim is made only if every primary endpoint gate "
        "passes. This is an intersection-union decision, so no alpha split is applied "
        "across the gates. Every within-rule candidate and contract correction remains "
        "as specified by the certificate."
    )
    study["secondary_endpoints"] = {
        "per_dataset_paired_effects": (
            "two-sided exact sign tests with Holm correction over four datasets"
        ),
        "effect_sizes": [
            "absolute and relative violation reduction",
            "exact violation-rate confidence intervals",
            "safe-retention and deployment-rate cluster-bootstrap intervals",
            "common-radius distribution",
            "vector-versus-common retention difference and ratio",
            "cross-dataset heterogeneity",
        ],
        "diagnostics": [
            "limiting contract and dimension",
            "per-contract bound-to-threshold margin",
            "per-cell evidence requirement",
            "held-out boosted-tree attacker stress",
        ],
    }
    study["registered_ablations"] = [
        "paired target harm versus edited-only target error",
        "balanced leakage versus ordinary source accuracy",
        "single registered attacker versus the full registered portfolio",
        "IID versus Gamma-greater-than-one certification",
        "generic scalar pooled certificate versus vector contracts",
        "common radius versus anisotropic profile",
        "uniform versus prospective evidence allocation",
        "full 12-candidate frontier versus one lowest-strength candidate per eraser",
        "one target environment versus all registered target environments",
        "1000, 2000, 4000, and 8000 observation budgets",
        "exact discrete bounds versus generic bounded-loss bounds",
        "registered portfolio versus held-out boosted-tree stress attacker",
        "support-aware abstention versus the prior Camelyon17 unsupported case",
    ]
    study["exclusions_and_missingness"] = {
        "performance_based_exclusions": "none",
        "allowed_exclusion": (
            "only a mechanically corrupt or unverifiable receipt, reported by seed, "
            "dataset, and method with no replacement"
        ),
        "missing_run_policy": (
            "the matrix is incomplete until restored; missing runs may not be counted "
            "as abstentions, safe decisions, or violations"
        ),
        "unsupported_cell_policy": "force abstention and report non-identifiability",
        "no_replacement": [
            "seed",
            "dataset",
            "candidate",
            "attacker",
            "threshold",
            "Gamma",
        ],
    }
    study["heldout_attacker_analysis"] = {
        "formal_guarantee": False,
        "selection_use": "prohibited",
        "reported_outputs": [
            "portfolio-safe edits remaining safe under boosted-tree stress",
            "registered attacker most predictive of held-out failure",
            "registered-attacker complementarity and redundancy",
        ],
    }
    study["freshness_guard"] = {
        "fresh_receipt_dir": str(FRESH_RECEIPT_DIR),
        "fresh_audit_dir": str(FRESH_AUDIT_DIR),
        "required_order": [
            "commit this protocol JSON by itself",
            "compute and commit its SHA-256 sidecar separately",
            "push both commits",
            "only then execute or inspect seeds 45-108",
        ],
    }

    return {
        "schema_version": 1,
        "project": "VERA",
        "status": "locked_before_claim_grade_runs",
        "phase": "prospective controlled supported-shift confirmation",
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_thesis": (
            "VERA certifies whether a representation edit can be deployed under a "
            "declared, supported reweighting shift while jointly controlling "
            "incremental target harm and recovery by a registered attacker portfolio."
        ),
        "primary_claim": (
            "Under supported deployment laws with known Gamma > 1 membership, the "
            "VERA vector envelope reduces contract-violating deployments relative to "
            "validation point selection while retaining a nontrivial fraction of "
            "certifiably safe opportunities."
        ),
        "parent_preregistration": {
            "path": str(parent_path.relative_to(REPOSITORY)),
            "sha256": sha256(parent_path),
        },
        "design_evidence": {
            "path": str(design_path.relative_to(REPOSITORY)),
            "sha256": sha256(design_path),
            "source_git_commit": design["source_git_commit"],
            "analysis_tier": "exploratory design only",
            "seeds": DESIGN_SEEDS,
        },
        "power_evidence": {
            "path": str(power_path.relative_to(REPOSITORY)),
            "sha256": sha256(power_path),
            "source_git_commit": power["source_git_commit"],
            "planned_seed_count": len(FRESH_SEEDS),
        },
        "protocol_generator_git_commit": git_commit(),
        "data_policy": {
            "design_seeds": DESIGN_SEEDS,
            "confirmatory_seeds": FRESH_SEEDS,
            "seed_blocks_disjoint": True,
            "all_confirmatory_outcomes_reported": True,
            "external_outcomes_may_not_change_locked_choices": True,
        },
        "claim_boundary": (
            "The central shift result certifies a finite registered candidate and "
            "attacker family under supported bounded reweighting of a finite empirical "
            "reference law. It is not universal erasure, structural causal transport, "
            "or evidence that arbitrary real deployments belong to the ambiguity class."
        ),
        "separate_support_boundary_evidence": {
            "dataset": "Camelyon17-WILDS",
            "role": (
                "prior unsupported-hospital study demonstrating forced abstention and "
                "the non-identifiability boundary; excluded from central supported-shift "
                "confirmatory endpoints"
            ),
        },
        "human_only_gates_not_satisfied_by_this_lock": [
            "independent mathematical proof reconstruction",
            "external cold novelty and methods reviews",
            "authorship and AI-disclosure confirmations",
            "OpenReview account, email, and deadline confirmations",
            "actual venue submission",
        ],
        "real_study": study,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=DEFAULT_PARENT)
    parser.add_argument("--design", type=Path, default=DEFAULT_DESIGN)
    parser.add_argument("--power", type=Path, default=DEFAULT_POWER)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite preregistration: {args.output}")
    verify_fresh_outcomes_absent()
    parent = load_json(args.parent)
    design = load_json(args.design)
    power = load_json(args.power)
    validate_design_and_power(design, power, args.design)
    payload = build_payload(
        parent,
        design,
        power,
        parent_path=args.parent,
        design_path=args.design,
        power_path=args.power,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output),
        "fresh_seed_count": len(FRESH_SEEDS),
        "primary_gamma": PRIMARY_GAMMA,
        "primary_budget": PRIMARY_BUDGET,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
