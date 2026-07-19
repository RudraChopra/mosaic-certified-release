#!/usr/bin/env python3
"""Execute every locked ACS natural-shift job with resumable subprocesses."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from mosaic_real import sha256


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_PREREG = ROOT / "prereg_mosaic_acs_natural_shift_v1.json"
DEFAULT_DATA_LOCK = ROOT / "prereg_mosaic_acs_natural_shift_data_v1.json"
DEFAULT_STORES = Path("/Volumes/Backups/FARO/artifacts/acs_natural_shift_stores")
DEFAULT_OUTPUT = REPOSITORY / "research/artifacts/mosaic_acs_natural_shift_v1_receipts"


def store_path(root: Path, task: str, state: str) -> Path:
    return root / f"acs_{task}_ca_{state.lower()}_natural_store"


def receipt_path(root: Path, task: str, state: str, seed: int) -> Path:
    return root / f"ACS-{task}-CA-{state}__seed{seed}.json"


def validate_data_lock(path: Path, *, prereg_sha: str, stores: Path) -> str:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    digest = sha256(path)
    if sidecar.read_text(encoding="utf-8").strip() != digest:
        raise ValueError("data-lock sidecar mismatch")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("status") != "frozen_before_outcome_execution":
        raise ValueError("data lock is not frozen")
    if payload.get("preregistration_sha256") != prereg_sha:
        raise ValueError("data lock references the wrong preregistration")
    for key, receipt in payload["stores"].items():
        task, transition = key.split(":", 1)
        state = transition.split("->", 1)[1]
        store = store_path(stores, task, state)
        if sha256(store / "manifest.json") != receipt["manifest_sha256"]:
            raise ValueError(f"store manifest differs from data lock: {key}")
        for name, array_receipt in receipt["arrays"].items():
            if sha256(store / name) != array_receipt["sha256"]:
                raise ValueError(f"store array differs from data lock: {key}:{name}")
    return digest


def run_one(
    job: dict[str, object], *, prereg: Path, stores: Path, output: Path
) -> dict[str, object]:
    task = str(job["task"])
    state = str(job["target_state"])
    seed = int(job["seed"])
    destination = receipt_path(output, task, state, seed)
    log = destination.with_suffix(".log")
    if destination.is_file():
        return {"task": task, "target_state": state, "seed": seed, "status": "existing"}
    environment = dict(os.environ)
    environment.update(
        {
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "VECLIB_MAXIMUM_THREADS": "1",
            "NUMEXPR_NUM_THREADS": "1",
            "PYTHONPATH": os.pathsep.join(
                (str(REPOSITORY / "research/mosaic"), str(REPOSITORY / "research/scripts"))
            ),
        }
    )
    command = [
        sys.executable,
        str(ROOT / "run_mosaic_acs_natural_shift.py"),
        "--task",
        task,
        "--target-state",
        state,
        "--seed",
        str(seed),
        "--store",
        str(store_path(stores, task, state)),
        "--output",
        str(destination),
        "--prereg",
        str(prereg),
    ]
    completed = subprocess.run(
        command,
        cwd=REPOSITORY,
        env=environment,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    log.write_text(completed.stdout, encoding="utf-8")
    return {
        "task": task,
        "target_state": state,
        "seed": seed,
        "status": "complete" if completed.returncode == 0 else "failed",
        "returncode": completed.returncode,
        "receipt": str(destination),
        "log": str(log),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--data-lock", type=Path, default=DEFAULT_DATA_LOCK)
    parser.add_argument("--stores", type=Path, default=DEFAULT_STORES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.workers < 1:
        raise ValueError("workers must be positive")
    sidecar = args.prereg.with_suffix(args.prereg.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").strip() != sha256(args.prereg):
        raise ValueError("preregistration sidecar mismatch")
    prereg_sha = sha256(args.prereg)
    prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
    data_lock_sha = validate_data_lock(
        args.data_lock, prereg_sha=prereg_sha, stores=args.stores
    )
    jobs = list(prereg["jobs"])
    args.output.mkdir(parents=True, exist_ok=True)
    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        pending = {
            executor.submit(
                run_one,
                job,
                prereg=args.prereg,
                stores=args.stores,
                output=args.output,
            ): job
            for job in jobs
        }
        for future in as_completed(pending):
            result = future.result()
            results.append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    statuses = {status: sum(row["status"] == status for row in results) for status in {row["status"] for row in results}}
    report = {
        "preregistration_sha256": prereg_sha,
        "data_lock_sha256": data_lock_sha,
        "jobs": len(jobs),
        "workers": args.workers,
        "statuses": statuses,
        "results": sorted(results, key=lambda row: (row["task"], row["target_state"], row["seed"])),
    }
    manifest = args.output / "batch_execution_manifest.json"
    manifest.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if statuses.get("failed", 0):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
