"""Run the closed-set VERA controlled-shift receipt contract audit."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from controlled_shift_receipt_contract import audit_closed_contract, sha256


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--hash-file", type=Path, required=True)
    parser.add_argument("--receipt-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def build_report(args: argparse.Namespace) -> dict[str, Any]:
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    observed_hash = sha256(args.prereg)
    if observed_hash != expected_hash:
        raise RuntimeError("controlled-shift preregistration hash mismatch")
    prereg = load_json(args.prereg)
    if prereg.get("status") != "locked_before_claim_grade_runs":
        raise RuntimeError("controlled-shift preregistration is not locked")
    contract = audit_closed_contract(
        prereg["real_study"], args.receipt_dir, observed_hash
    )
    return {
        "schema_version": 1,
        "name": "VERA strict controlled-shift receipt audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preregistration_sha256": observed_hash,
        **contract,
    }


def main() -> int:
    args = parse_args()
    report = build_report(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    summary = {
        "passed": report["passed"],
        "expected_receipt_count": len(report["expected_receipt_files"]),
        "observed_receipt_count": len(report["observed_receipt_files"]),
        "validated_array_count": report["validated_closed_array_archive_count"],
        "error_count": len(report["errors"]),
        "output": str(args.output),
        "output_sha256": sha256(args.output),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
