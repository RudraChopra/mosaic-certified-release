#!/usr/bin/env python3
"""Lock the exact-rational audit before bridge outcomes are inspected."""

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
DEFAULT_OUTPUT = ROOT / "prereg_mosaic_bridge_rational_audit_v1.json"
CODE_FILES = (
    "research/mosaic/mosaic_rational_certificate.py",
    "research/mosaic/audit_mosaic_bridge_rational.py",
    "research/mosaic/lock_mosaic_bridge_rational_audit.py",
    "research/tests/test_mosaic_rational_certificate.py",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--strict-amendment",
        type=Path,
        default=ROOT / "prereg_mosaic_bridge_strict_amendment_v1.json",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--written-receipt-count", required=True, type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    if args.output.exists() or sidecar.exists():
        raise FileExistsError("refusing to overwrite an existing rational audit lock")
    if not 0 <= args.written_receipt_count < 100:
        raise ValueError("written receipt count must describe an incomplete matrix")
    strict_hash = sha256(args.strict_amendment)
    strict_sidecar = args.strict_amendment.with_suffix(
        args.strict_amendment.suffix + ".sha256"
    )
    if strict_sidecar.read_text(encoding="utf-8").strip() != strict_hash:
        raise ValueError("strict amendment sidecar mismatch")
    payload = {
        "project": "MOSAIC exact-rational serialized-certificate audit",
        "status": "locked_before_complete_matrix_and_before_outcome_inspection",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "strict_amendment_sha256": strict_hash,
        "repository_head_before_lock": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "timing_disclosure": {
            "written_original_receipts": args.written_receipt_count,
            "expected_original_receipts": 100,
            "receipt_contents_inspected": False,
            "information_seen": "filenames, counts, timestamps, and process status only",
        },
        "arithmetic_contract": {
            "serialized_numbers": "interpreted as exact decimal rationals",
            "stochastic_rows": "renormalized exactly over the rationals",
            "multinomial_radii": "inflated outward by exactly 1e-12",
            "l1_support": "greedy simplex transport evaluated with Fraction arithmetic",
            "bridge_gate": "every exact rational membership slack is nonnegative",
            "risk_gate": (
                "every stored outward source and utility bound is at least its "
                "exact rational recomputation"
            ),
            "scope": "all 1,300 bridges and all 1,400 serialized release certificates",
        },
        "code_sha256": {
            relative: sha256(REPOSITORY / relative) for relative in CODE_FILES
        },
    }
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.write_text(data, encoding="utf-8")
    digest = hashlib.sha256(data.encode("utf-8")).hexdigest()
    sidecar.write_text(digest + "\n", encoding="utf-8")
    print(digest)


if __name__ == "__main__":
    main()
