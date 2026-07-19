#!/usr/bin/env python3
"""Lock the untouched-seed MOSAIC bridge confirmation before outcomes."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

import numpy as np
import scipy
import sklearn

from mosaic_real import sha256
from run_mosaic_bridge_frontier import expected_protocol
from run_mosaic_real_pilot import DATASETS


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_OUTPUT = ROOT / "prereg_mosaic_bridge_v1.json"
CONFIRMATION_SEEDS = tuple(range(1200, 1220))
CODE_PATHS = (
    "research/mosaic/BRIDGE_MEMBERSHIP_THEOREM.md",
    "research/mosaic/REPEATED_QUERY_THEOREM.md",
    "research/mosaic/audit_mosaic_bridge_frontier.py",
    "research/mosaic/build_mosaic_bridge_manifest.py",
    "research/mosaic/lock_mosaic_bridge_prereg.py",
    "research/mosaic/mosaic_bridge.py",
    "research/mosaic/mosaic_channel.py",
    "research/mosaic/mosaic_envelope.py",
    "research/mosaic/mosaic_real.py",
    "research/mosaic/mosaic_release.py",
    "research/mosaic/mosaic_transform_exact.py",
    "research/mosaic/mosaic_transform_exact_optimizer.py",
    "research/mosaic/run_mosaic_bridge_frontier.py",
    "research/mosaic/run_mosaic_official_frontier_exact_confirmation.py",
    "research/mosaic/run_mosaic_real_pilot.py",
    "research/mosaic/verify_mosaic_bridge.py",
    "research/scripts/official_eraser_adapters.py",
    "research/scripts/run_official_eraser_frontier.py",
    "research/tests/test_mosaic_bridge.py",
    "research/tests/test_mosaic_bridge_frontier.py",
    "research/tests/test_mosaic_bridge_manifest.py",
    "research/tests/test_mosaic_release.py",
)
OFFICIAL_REPOSITORIES = {
    "INLP": Path("/Volumes/Backups/FARO/external/nullspace_projection"),
    "LEACE": Path("/Volumes/Backups/FARO/external/concept-erasure"),
    "R-LACE": Path("/Volumes/Backups/FARO/external/rlace-icml"),
    "TaCo": Path("/Volumes/Backups/FARO/external/TaCo"),
    "MANCE++": Path("/Volumes/Backups/FARO/external/mance"),
}


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def git(*arguments: str, cwd: Path = REPOSITORY) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def committed_code_hashes() -> dict[str, str]:
    hashes: dict[str, str] = {}
    for relative in CODE_PATHS:
        path = REPOSITORY / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative}"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise RuntimeError(f"{relative} differs from committed HEAD")
        hashes[relative] = sha256(path)
    return hashes


def official_repository_receipts() -> dict[str, object]:
    receipts: dict[str, object] = {}
    for name, path in OFFICIAL_REPOSITORIES.items():
        status = git("status", "--porcelain", cwd=path)
        if status:
            raise RuntimeError(f"official repository is dirty: {name}")
        receipts[name] = {
            "path": str(path),
            "commit": git("rev-parse", "HEAD", cwd=path),
            "remote": git("remote", "get-url", "origin", cwd=path),
            "clean": True,
        }
    return receipts


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".sha256").exists():
        raise FileExistsError("refusing to overwrite a bridge preregistration")
    dataset_receipts = {}
    for name, config in DATASETS.items():
        path = Path(config["path"])
        dataset_receipts[name] = {
            "path": str(path),
            "modality": config["modality"],
            "target_mode": config["target_mode"],
            "manifest_sha256": sha256(path / "manifest.json"),
        }
    payload: dict[str, object] = {
        "project": "MOSAIC: Minimax-Optimized Source-Agnostic Invariant Channels",
        "phase": "data-certified structured-shift bridge confirmation",
        "status": "locked_before_confirmatory_outcomes",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "repository_head_at_lock": git("rev-parse", "HEAD"),
        "confirmation_seeds": list(CONFIRMATION_SEEDS),
        "datasets": dataset_receipts,
        "protocol": expected_protocol(),
        "frontier": {
            "candidate_count": 13,
            "official_methods": ["INLP", "LEACE", "R-LACE", "TaCo", "MANCE++"],
            "proxy_rows_permitted": False,
            "primary_selection": (
                "For each dataset and seed, choose the L=2 candidate with minimum "
                "bridge-certified worst source-label error among candidates satisfying "
                "source advantage <=0.35 and utility error <=0.40; break exact ties "
                "lexically and otherwise abstain."
            ),
            "l4_followup": (
                "Reoptimize L=4 only for the minimum-error L=2 candidate, without "
                "using diagnostic outcomes."
            ),
        },
        "data_protocol": {
            "maximum_eraser_train": 8000,
            "maximum_tokenizer_construction": 2000,
            "maximum_balanced_reference": 8000,
            "maximum_balanced_external": 12000,
            "external_split": (
                "Within each represented source-label stratum, deterministic seeded "
                "two-thirds bridge and one-third untouched diagnostic split."
            ),
            "tokenizer": (
                "Balanced logistic task score fit only on construction features and "
                "discretized at construction-score quartiles."
            ),
            "bridge": (
                "Joint reference and bridge multinomial L1 confidence regions; exact "
                "LP maximizes a source-blind common-transform retained mass per label."
            ),
        },
        "claim_boundary": (
            "This confirmation tests whether a labeled bridge sample from the natural "
            "external population can certify membership in MOSAIC's structured shift "
            "class and support a release on an untouched diagnostic split. The theorem "
            "applies when bridge and deployment observations are exchangeable draws from "
            "the same source-label conditional laws. Results do not imply clinical "
            "safety, protect unregistered side channels, or justify future drift after "
            "the bridge population changes."
        ),
        "decision_gates": {
            "required_files": 100,
            "required_candidate_rows": 1300,
            "required_global_optimization_replays": 1400,
            "maximum_optimization_errors": 0,
            "maximum_primary_false_acceptances": 0,
            "minimum_estimable_primary_deployments": 16,
            "minimum_biasbios_primary_deployments": 16,
            "minimum_biasbios_tau035_deployments": 14,
            "maximum_bridge_membership_violation": 3e-7,
            "require_l4_pointwise_no_worse": True,
            "require_camelyon_missing_support_abstention": True,
        },
        "pass_conditions": {
            "all_required": True,
            "complete_execution": (
                "All 100 dataset-seed jobs contain 13 official candidate rows and "
                "the independent audit replays every bridge and global optimum."
            ),
            "finite_sample_membership": (
                "Every stored bridge transform satisfies the robust confidence-region "
                "domination inequalities under independent recomputation."
            ),
            "stronger_utility": (
                "BiasBios deploys on at least 16/20 seeds at tau_U=0.40 and at least "
                "14/20 seeds at tau_U=0.35."
            ),
            "diagnostic_safety": (
                "There are zero contract violations among estimable primary selected "
                "releases on the untouched diagnostic splits."
            ),
            "interface_sensitivity": (
                "The globally optimized four-token objective is no worse than the "
                "two-token objective for every registered follow-up row."
            ),
            "missing_support": (
                "Camelyon jobs with an absent required bridge source-label stratum "
                "certify zero retained mass and abstain under the primary contract."
            ),
            "complete_reporting": (
                "Report all datasets, seeds, thresholds, abstentions, missing strata, "
                "bridge contaminations, diagnostic failures, and negative results."
            ),
        },
        "pilot_exclusion": {
            "excluded_real_seed_ranges": ["0-1199"],
            "use": (
                "Prior seeds selected the architecture and showed that BiasBios can "
                "support a finite-sample bridge. No excluded real row enters the "
                "confirmation estimates or intervals."
            ),
        },
        "stopping_rule": (
            "Run every registered dataset and seed. No outcome-based replacement, "
            "threshold change, candidate change, early stopping, or selective omission."
        ),
        "code_sha256": committed_code_hashes(),
        "official_repositories": official_repository_receipts(),
        "runtime_environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }
    serialized = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    atomic_write(args.output, serialized)
    digest = sha256(args.output)
    atomic_write(args.output.with_suffix(args.output.suffix + ".sha256"), digest + "\n")
    print(json.dumps({"path": str(args.output), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
