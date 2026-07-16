"""Build the independent controlled-shift follow-up preregistration."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PARENT = ROOT / "prereg_controlled_shift.json"
DEFAULT_RESULT = ROOT / "maintrack" / "CONTROLLED_SHIFT_RESULT_SUMMARY.json"
DEFAULT_OUTPUT = ROOT / "prereg_controlled_shift_followup.json"
FOLLOWUP_RECEIPT_DIR = Path(
    "/Volumes/Backups/FARO/artifacts/vera_controlled_shift_followup_receipts"
)
FOLLOWUP_AUDIT_DIR = Path(
    "/Volumes/Backups/FARO/artifacts/vera_controlled_shift_followup_audit_arrays"
)
SUPPORTED_DATASETS = (
    "Bios",
    "CivilComments-WILDS",
    "GaitPDB",
    "Waterbirds",
)
CALIBRATION_SEEDS = list(range(45, 109))
FOLLOWUP_SEEDS = list(range(109, 173))
PRIMARY_GAMMA = 1.1
PRIMARY_BUDGET = 8000
SENSITIVITY_BUDGETS = [1000, 2000, 4000]
TARGETED_FLOOR_FRACTION = 0.15


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("ascii")
    return hashlib.sha256(payload).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object in {path}")
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


def verify_followup_outcomes_absent() -> None:
    for directory in (FOLLOWUP_RECEIPT_DIR, FOLLOWUP_AUDIT_DIR):
        if directory.exists() and any(directory.iterdir()):
            raise RuntimeError(f"follow-up outcome directory is not empty: {directory}")


def validate_inputs(parent: dict[str, Any], result: dict[str, Any]) -> None:
    require(
        parent.get("status") == "locked_before_claim_grade_runs",
        "parent controlled-shift preregistration is not locked",
    )
    study = parent.get("real_study", {})
    require(isinstance(study, dict), "parent preregistration has no real_study")
    require(
        [int(seed) for seed in study.get("seeds", [])] == CALIBRATION_SEEDS,
        "parent seed block is not the completed controlled-shift block",
    )
    require(
        not (set(CALIBRATION_SEEDS) & set(FOLLOWUP_SEEDS)),
        "follow-up seed block overlaps the calibration block",
    )
    require(
        result.get("analysis_status") == "complete_primary_mixed",
        "controlled-shift result summary is not the sealed mixed primary result",
    )
    require(
        result.get("overall_confirmatory_success") is False,
        "follow-up lock expects the first controlled-shift primary to have failed",
    )
    require(
        result.get("failed_primary_gates") == ["usefulness"],
        "follow-up lock expects usefulness to be the only failed primary gate",
    )
    targeted_8000 = [
        row
        for row in result.get("budget_sensitivity_gamma_1_1", [])
        if row.get("allocation") == "targeted_floor_0.15"
        and int(row.get("budget", -1)) == PRIMARY_BUDGET
    ]
    require(len(targeted_8000) == 1, "missing targeted 8,000-budget sensitivity")
    vector = targeted_8000[0].get("vector", {})
    require(
        vector.get("safe") == 49 and vector.get("oracle") == 187,
        "targeted 8,000-budget calibration retention differs from the sealed summary",
    )
    require(
        vector.get("viol") == 0,
        "targeted 8,000-budget calibration safety differs from the sealed summary",
    )


def build_payload(
    parent: dict[str, Any],
    result: dict[str, Any],
    *,
    parent_path: Path,
    result_path: Path,
) -> dict[str, Any]:
    validate_inputs(parent, result)
    parent_study = parent["real_study"]
    study = copy.deepcopy(parent_study)
    study["analysis_tiers"] = {
        "primary": (
            "independent post-failure controlled supported-shift follow-up on "
            "seeds 109-172"
        ),
        "secondary": (
            "Gamma, evidence-budget, allocation, attacker, and candidate-family "
            "sensitivity analyses on the same follow-up seed clusters"
        ),
        "calibration_boundary": (
            "seeds 45-108 chose the follow-up budget and remain a reported failed "
            "primary study, not pooled evidence"
        ),
    }
    study["datasets"] = {
        name: copy.deepcopy(parent_study["datasets"][name])
        for name in SUPPORTED_DATASETS
    }
    study["seeds"] = FOLLOWUP_SEEDS
    study["locked_dataset_contracts"] = {
        name: copy.deepcopy(parent_study["locked_dataset_contracts"][name])
        for name in SUPPORTED_DATASETS
    }
    study["deployment_gamma"] = PRIMARY_GAMMA
    study["evidence_allocation"] = {
        **copy.deepcopy(parent_study["evidence_allocation"]),
        "primary_total_contract_observation_budget": PRIMARY_BUDGET,
        "primary_rule": "targeted_floor_0.15",
        "minimum_fraction_per_registered_cell": TARGETED_FLOOR_FRACTION,
        "sensitivity_budgets": SENSITIVITY_BUDGETS,
        "post_failure_rationale": (
            "The completed controlled-shift study failed only the usefulness lower "
            "bound at budget 4,000. Its prespecified 8,000-budget sensitivity showed "
            "higher descriptive safe retention with zero measured VERA violations. "
            "This lock tests that larger budget on new seeds only."
        ),
    }
    study["primary_endpoints"] = copy.deepcopy(parent_study["primary_endpoints"])
    study["primary_endpoints"]["safety"]["rotation_index"] = "(seed - 109) modulo 4"
    study["primary_endpoints"]["usefulness"]["success"] = (
        "lower confidence bound >= 0.20 on the independent follow-up seed block"
    )
    study["freshness_guard"] = {
        "fresh_receipt_dir": str(FOLLOWUP_RECEIPT_DIR),
        "fresh_audit_dir": str(FOLLOWUP_AUDIT_DIR),
        "required_order": [
            "commit this follow-up protocol and its SHA-256 sidecar",
            "push the protocol commits before running seed 109",
            "execute the official-method matrix only into the follow-up folders",
            "seal independent replay and protocol analyzer outputs before reading",
        ],
    }
    study["post_failure_reporting"] = {
        "original_primary_result_remains_failed": True,
        "pooling_with_original_seed_block_for_primary_claim": False,
        "successful_followup_wording": (
            "independent follow-up passed after increasing the locked evidence "
            "budget; the first controlled-shift primary remains a mixed result"
        ),
        "failed_followup_wording": (
            "independent follow-up failed; no secondary or exploratory result may "
            "replace it"
        ),
    }
    study["controlled_shift_protocol"] = copy.deepcopy(
        parent_study["controlled_shift_protocol"]
    )
    study["controlled_shift_protocol"]["primary_requested_gamma"] = PRIMARY_GAMMA

    calibration = {
        "result_path": str(result_path.relative_to(REPOSITORY)),
        "result_sha256": sha256(result_path),
        "result_canonical_sha256": canonical_sha256(result),
        "failed_primary_gates": result["failed_primary_gates"],
        "targeted_8000_vector_safe": 49,
        "targeted_8000_oracle_safe": 187,
        "targeted_8000_vector_violations": 0,
        "may_not_be_pooled_with_followup": True,
    }

    return {
        "schema_version": 1,
        "project": "VERA",
        "status": "locked_before_claim_grade_runs",
        "phase": "independent controlled supported-shift follow-up",
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "scientific_thesis": parent["scientific_thesis"],
        "primary_claim": (
            "At the prospectively locked 8,000-observation evidence budget, VERA's "
            "vector envelope reduces shifted-contract violations relative to "
            "validation point selection while retaining at least 20% of "
            "oracle-safe opportunities on an independent seed block."
        ),
        "parent_preregistration": {
            "path": str(parent_path.relative_to(REPOSITORY)),
            "sha256": sha256(parent_path),
        },
        "calibration_result": calibration,
        "protocol_generator_git_commit": git_commit(),
        "data_policy": {
            "calibration_seeds": CALIBRATION_SEEDS,
            "followup_seeds": FOLLOWUP_SEEDS,
            "seed_blocks_disjoint": True,
            "all_followup_outcomes_reported": True,
            "external_outcomes_may_not_change_locked_choices": True,
        },
        "non_rescue_boundary": (
            "This follow-up is not a retroactive pass for the failed controlled-shift "
            "primary. It creates a new, independent primary test with a disclosed "
            "post-failure budget choice."
        ),
        "human_only_gates_not_satisfied_by_this_lock": [
            "independent mathematical proof reconstruction",
            "external cold novelty and methods reviews",
            "authorship and AI-disclosure confirmations",
            "official venue submission",
        ],
        "real_study": study,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent", type=Path, default=DEFAULT_PARENT)
    parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--skip-freshness-check", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite preregistration: {args.output}")
    if not args.skip_freshness_check:
        verify_followup_outcomes_absent()
    parent = load_json(args.parent)
    result = load_json(args.result)
    payload = build_payload(
        parent,
        result,
        parent_path=args.parent,
        result_path=args.result,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    hash_path = args.output.with_suffix(".sha256")
    digest = sha256(args.output)
    hash_path.write_text(f"{digest}  {args.output.name}\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": digest,
                "hash_file": str(hash_path),
                "followup_seed_count": len(FOLLOWUP_SEEDS),
                "primary_gamma": PRIMARY_GAMMA,
                "primary_budget": PRIMARY_BUDGET,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
