#!/usr/bin/env python3
"""Run the disclosed diagnostic-anchored MOSAIC utility repair."""

from __future__ import annotations

import argparse
import json
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from mosaic_real import sha256
from mosaic_release_utility_common_v2 import evaluate_job, selected_jobs
from run_mosaic_official_frontier_exact_confirmation import atomic_json_dump


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]


def validate_lock(path: Path) -> tuple[dict[str, object], str]:
    digest = sha256(path)
    if path.with_suffix(path.suffix + ".sha256").read_text(encoding="utf-8").strip() != digest:
        raise ValueError("utility repair lock sidecar mismatch")
    lock = json.loads(path.read_text(encoding="utf-8"))
    if lock.get("status") != "locked_diagnostic_anchored_utility_repair_before_execution":
        raise ValueError("utility repair is not correctly locked")
    relative = path.resolve().relative_to(REPOSITORY.resolve())
    if subprocess.run(
        ["git", "show", f"HEAD:{relative.as_posix()}"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
    ).stdout != path.read_bytes():
        raise ValueError("utility repair lock is not committed")
    for relative_name, expected in lock["code_sha256"].items():
        if sha256(REPOSITORY / relative_name) != expected:
            raise ValueError(f"locked utility repair code mismatch: {relative_name}")
    return lock, digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict-dir", required=True, type=Path)
    parser.add_argument("--lock", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    lock, lock_hash = validate_lock(args.lock)
    jobs = selected_jobs(args.strict_dir, lock["slices"])
    if len(jobs) != int(lock["expected_deployed_release_count"]):
        raise ValueError("selected release count differs from repair lock")
    results: list[dict[str, object] | None] = [None] * len(jobs)
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(evaluate_job, job): index for index, job in enumerate(jobs)}
        for future in as_completed(futures):
            index = futures[future]
            results[index] = future.result()
            print(f"evaluated {results[index]['dataset']} seed {results[index]['seed']}", flush=True)
    completed = [row for row in results if row is not None]
    atomic_json_dump(
        {
            "name": "MOSAIC diagnostic-anchored released-interface utility analysis v2",
            "utility_repair_lock_sha256": lock_hash,
            "slices": lock["slices"],
            "release_count": len(completed),
            "results": completed,
            "repair_disclosure": lock["repair"],
            "claim_boundary": lock["claim_boundary"],
        },
        args.output,
    )


if __name__ == "__main__":
    main()
