#!/usr/bin/env python3
"""Execute the locked high-support K=8 ACS extension."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile

import run_mosaic_acs_natural_shift as runner
from lock_mosaic_acs_k8_high_support import CODE_PATHS, JOBS, OUTPUT, RECEIPT_ROOT, STORE_ROOT, SUMMARY
from mosaic_real import sha256


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]


def atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=OUTPUT)
    parser.add_argument("--receipt-root", type=Path, default=RECEIPT_ROOT)
    parser.add_argument("--summary", type=Path, default=SUMMARY)
    args = parser.parse_args()
    if args.receipt_root.exists() or args.summary.exists():
        raise FileExistsError("K=8 high-support outcome path already exists")
    sidecar = args.lock.with_suffix(args.lock.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").strip() != sha256(args.lock):
        raise AssertionError("K=8 high-support lock sidecar mismatch")
    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    for relative, expected in lock["code_sha256"].items():
        if sha256(REPOSITORY / relative) != expected:
            raise AssertionError(f"locked code changed: {relative}")
    if [(row["task"], row["target_state"], row["seed"], row["store"]) for row in lock["jobs"]] != list(JOBS):
        raise AssertionError("locked job list changed")

    runner.FINE_TOKEN_COUNTS = (int(lock["fine_token_count"]),)
    runner.MAXIMUM_REFERENCE_ROWS = int(lock["maximum_reference_rows"])
    runner.MAXIMUM_BRIDGE_ROWS = int(lock["maximum_bridge_rows"])
    runner.MAXIMUM_DIAGNOSTIC_ROWS = int(lock["maximum_diagnostic_rows"])
    args.receipt_root.mkdir(parents=True, exist_ok=False)
    outputs = []
    for job in lock["jobs"]:
        store = STORE_ROOT / str(job["store"])
        manifest = store / "manifest.json"
        if sha256(manifest) != str(job["manifest_sha256"]):
            raise AssertionError(f"store changed: {store}")
        payload = runner.run_job(
            task=str(job["task"]), target_state=str(job["target_state"]), seed=int(job["seed"]), store_path=store
        )
        if payload["sample_counts"]["reference"] != int(lock["maximum_reference_rows"]) or payload["sample_counts"]["bridge"] != int(lock["maximum_bridge_rows"]):
            raise AssertionError("high-support sampling cap was not attained")
        result = payload["alphabets"][str(lock["fine_token_count"])]
        path = args.receipt_root / f"ACS-employment-CA-{job['target_state']}__seed{job['seed']}.json"
        payload["high_support_lock_sha256"] = sha256(args.lock)
        payload["analysis_status"] = "post-review pre-outcome K=8 high-support extension"
        atomic_write(path, payload)
        outputs.append({
            "task": job["task"],
            "target_state": job["target_state"],
            "seed": job["seed"],
            "receipt": str(path.relative_to(REPOSITORY)),
            "receipt_sha256": sha256(path),
            "mosaic_primary": result["primary_selection"]["mosaic"],
            "direct_primary": result["primary_selection"]["direct"],
        })
    summary = {
        "name": "MOSAIC K=8 high-support ACS extension v1",
        "status": "complete",
        "analysis_status": "post-review pre-outcome extension",
        "lock": str(args.lock.relative_to(REPOSITORY)),
        "lock_sha256": sha256(args.lock),
        "jobs": outputs,
        "mosaic_primary_deployments": sum(row["mosaic_primary"]["decision"] == "deploy" for row in outputs),
        "direct_primary_deployments": sum(row["direct_primary"]["decision"] == "deploy" for row in outputs),
        "claim_boundary": lock["claim_boundary"],
    }
    atomic_write(args.summary, summary)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
