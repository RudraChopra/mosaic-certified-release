#!/usr/bin/env python3
"""Independently audit the locked K=8 high-support ACS extension."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from mosaic_real import sha256


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
LOCK = ROOT / "prereg_mosaic_acs_k8_high_support_v3.json"
SUMMARY = REPOSITORY / "research/artifacts/mosaic_acs_k8_high_support_v3_summary.json"
RECEIPTS = REPOSITORY / "research/artifacts/mosaic_acs_k8_high_support_v3_receipts"
DEFAULT_OUTPUT = REPOSITORY / "research/artifacts/mosaic_acs_k8_high_support_v3_audit.json"
EXPECTED_METHODS = {"Identity", "INLP", "LEACE", "R-LACE", "TaCo", "MANCE++"}


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    parser.add_argument("--receipts", type=Path, default=RECEIPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    sidecar = args.lock.with_suffix(args.lock.suffix + ".sha256")
    checks = {
        "lock_sidecar": sidecar.read_text(encoding="utf-8").strip() == sha256(args.lock),
        "summary_complete": summary.get("status") == "complete",
        "summary_lock": summary.get("lock_sha256") == sha256(args.lock),
        "three_locked_jobs": len(summary.get("jobs", [])) == 3 == len(lock.get("jobs", [])),
    }
    selected_rows = []
    all_rows = safe_mosaic = operational_violations = diagnostics = 0
    for job in summary["jobs"]:
        receipt = REPOSITORY / str(job["receipt"])
        payload = json.loads(receipt.read_text(encoding="utf-8"))
        result = payload["alphabets"][str(lock["fine_token_count"])]
        rows = result["rows"]
        all_rows += len(rows)
        methods = {str(row["method"]) for row in rows}
        state = str(job["target_state"])
        checks[f"{state}_receipt_sha256"] = sha256(receipt) == job["receipt_sha256"]
        checks[f"{state}_candidate_count"] = len(rows) == 13
        checks[f"{state}_official_coverage"] = methods == EXPECTED_METHODS
        checks[f"{state}_reference_cap"] = payload["sample_counts"]["reference"] == lock["maximum_reference_rows"]
        checks[f"{state}_bridge_cap"] = payload["sample_counts"]["bridge"] == lock["maximum_bridge_rows"]
        selection = result["primary_selection"]["mosaic"]
        if selection["decision"] == "deploy":
            diagnostics += 1
            safe_mosaic += int(bool(selection["diagnostic_safe"]) and not bool(selection["false_acceptance"]))
            operational_violations += int(selection["operational_replay"]["primary_contract_violations"])
        selected_rows.append(
            {
                "target_state": state,
                "mosaic_decision": selection["decision"],
                "candidate": selection.get("candidate"),
                "diagnostic_safe": selection.get("diagnostic_safe"),
                "operational_violations": selection.get("operational_replay", {}).get("primary_contract_violations"),
            }
        )
    checks["all_39_candidate_rows"] = all_rows == 39
    checks["two_mosaic_deployments"] = int(summary["mosaic_primary_deployments"]) == 2
    checks["two_safe_diagnostics"] = safe_mosaic == diagnostics == 2
    checks["zero_operational_violations"] = operational_violations == 0
    result = {
        "name": "MOSAIC K=8 high-support ACS extension v3 audit",
        "pass": all(checks.values()),
        "checks": checks,
        "lock": str(args.lock.relative_to(REPOSITORY)),
        "lock_sha256": sha256(args.lock),
        "summary": str(args.summary.relative_to(REPOSITORY)),
        "summary_sha256": sha256(args.summary),
        "selected_rows": selected_rows,
        "claim_boundary": lock["claim_boundary"],
    }
    atomic_write(args.output, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
