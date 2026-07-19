#!/usr/bin/env python3
"""Lock the pre-inspection numerical-safety amendment for the bridge study."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from mosaic_real import sha256


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_OUTPUT = ROOT / "prereg_mosaic_bridge_strict_amendment_v1.json"
STRICT_FILES = (
    "research/mosaic/mosaic_strict_certification.py",
    "research/mosaic/replay_mosaic_bridge_strict.py",
    "research/mosaic/audit_mosaic_bridge_strict.py",
    "research/mosaic/lock_mosaic_bridge_strict_amendment.py",
    "research/tests/test_mosaic_strict_certification.py",
    "research/tests/test_mosaic_bridge_strict_replay.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--prereg",
        type=Path,
        default=ROOT / "prereg_mosaic_bridge_v1.json",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--written-receipt-count", required=True, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists() or args.output.with_suffix(args.output.suffix + ".sha256").exists():
        raise FileExistsError("refusing to overwrite an existing amendment lock")
    if not 0 <= args.written_receipt_count < 100:
        raise ValueError("written receipt count must describe an incomplete matrix")
    prereg_hash = sha256(args.prereg)
    sidecar = args.prereg.with_suffix(args.prereg.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").strip() != prereg_hash:
        raise ValueError("original preregistration sidecar mismatch")
    code_hashes = {
        relative: sha256(REPOSITORY / relative) for relative in STRICT_FILES
    }
    payload = {
        "project": "MOSAIC data-certified bridge strict numerical amendment",
        "status": "locked_before_complete_matrix_and_before_outcome_inspection",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "original_preregistration": str(args.prereg.relative_to(REPOSITORY)),
        "original_preregistration_sha256": prereg_hash,
        "repository_head_before_amendment": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "trigger": (
            "An adversarial proof audit identified that accepting small negative "
            "solver residuals made the software guarantee tolerance-qualified."
        ),
        "timing_disclosure": {
            "written_original_receipts": args.written_receipt_count,
            "expected_original_receipts": 100,
            "receipt_contents_inspected": False,
            "information_seen": (
                "filenames, file count, process status, and timestamps only; no "
                "candidate, bridge, certificate, decision, or diagnostic outcomes"
            ),
        },
        "superseding_policy": {
            "scope": (
                "Every bridge, L=2 release, L=4 follow-up, threshold decision, "
                "selection, and aggregate claim is recomputed from all 100 stored "
                "token-table receipts."
            ),
            "bridge_feasibility_guard": 1e-9,
            "release_optimization_guard": 1e-6,
            "reported_value_guard": 1e-9,
            "decision_tolerance": 0.0,
            "bridge_acceptance": "independently recomputed minimum slack must be >= 0",
            "contract_acceptance": (
                "outward-rounded source and utility bounds must be <= the original "
                "registered thresholds with no additive tolerance"
            ),
            "stopping_rule": (
                "Replay all 100 original receipts regardless of strict outcomes; "
                "report all abstentions, failures, and decision changes."
            ),
        },
        "required_outputs": {
            "strict_receipts": 100,
            "candidate_rows": 1300,
            "global_optimizations": 1400,
            "minimum_membership_slack": 0.0,
            "maximum_decision_tolerance": 0.0,
        },
        "claim_rule": (
            "The paper may use only strict-replay decisions and strict aggregate "
            "rates for the bridge confirmation. Original receipts remain preserved "
            "as inputs and cannot be silently substituted."
        ),
        "code_sha256": code_hashes,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.write_text(data, encoding="utf-8")
    digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
    args.output.with_suffix(args.output.suffix + ".sha256").write_text(
        digest + "\n", encoding="utf-8"
    )
    print(digest)


if __name__ == "__main__":
    main()
