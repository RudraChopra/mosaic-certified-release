"""Execute the fixed 320-run method-native-probe diagnostic matrix."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


DATASETS = ("Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB")
METHODS = ("inlp", "rlace", "leace", "taco", "mance")
SEEDS = tuple(range(45, 61))
EXPECTED = len(DATASETS) * len(METHODS) * len(SEEDS)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def key(dataset: str, method: str, seed: int) -> str:
    return f"{dataset}__{method}__seed-{seed}"


def valid_existing(path: Path, dataset: str, method: str, seed: int) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return (
        isinstance(value, dict)
        and value.get("dataset") == dataset
        and value.get("method") == method
        and value.get("seed") == seed
        and value.get("formal_guarantee") is False
        and value.get("cross_method_native_probe_equivalence_claimed") is False
    )


def execute(
    command: list[str], *, cwd: Path, log_path: Path
) -> tuple[int, str]:
    environment = dict(os.environ)
    environment.update(
        {
            "PYTHONHASHSEED": "0",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        }
    )
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        capture_output=True,
        check=False,
    )
    log_path.write_bytes(result.stdout + b"\n--- stderr ---\n" + result.stderr)
    return result.returncode, sha256(log_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--hash-file", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=2)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.workers < 1 or args.workers > 2:
        raise ValueError("native diagnostic workers must be between one and two")
    repo = args.repo.resolve()
    script = repo / "research" / "scripts" / "run_native_eraser_probe_diagnostic.py"
    output_dir = args.output_dir.resolve()
    receipt_dir = output_dir / "receipts"
    log_dir = output_dir / "logs"
    receipt_dir.mkdir(parents=True, exist_ok=True)
    log_dir.mkdir(parents=True, exist_ok=True)
    jobs: list[tuple[str, str, int, Path, Path, list[str]]] = []
    skipped: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for method in METHODS:
            for seed in SEEDS:
                run_key = key(dataset, method, seed)
                output = receipt_dir / f"{run_key}.json"
                log = log_dir / f"{run_key}.log"
                if valid_existing(output, dataset, method, seed):
                    skipped.append(
                        {"key": run_key, "output_sha256": sha256(output)}
                    )
                    continue
                if output.exists() or output.is_symlink():
                    raise RuntimeError(f"invalid existing diagnostic receipt: {output}")
                command = [
                    str(args.python),
                    str(script),
                    "--prereg",
                    str(args.prereg),
                    "--hash-file",
                    str(args.hash_file),
                    "--dataset",
                    dataset,
                    "--method",
                    method,
                    "--seed",
                    str(seed),
                    "--output",
                    str(output),
                ]
                jobs.append((dataset, method, seed, output, log, command))
    completed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    future_map: dict[Future[tuple[int, str]], tuple[str, str, int, Path, Path]] = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        for dataset, method, seed, output, log, command in jobs:
            future = executor.submit(execute, command, cwd=repo, log_path=log)
            future_map[future] = (dataset, method, seed, output, log)
        for index, future in enumerate(as_completed(future_map), start=1):
            dataset, method, seed, output, log = future_map[future]
            returncode, log_hash = future.result()
            run_key = key(dataset, method, seed)
            if returncode == 0 and valid_existing(output, dataset, method, seed):
                completed.append(
                    {
                        "key": run_key,
                        "output_sha256": sha256(output),
                        "log_sha256": log_hash,
                    }
                )
                print(
                    f"[{len(skipped) + index}/{EXPECTED}] {run_key}: completed",
                    flush=True,
                )
            else:
                failures.append(
                    {
                        "key": run_key,
                        "returncode": returncode,
                        "log": str(log),
                        "log_sha256": log_hash,
                    }
                )
                print(
                    f"[{len(skipped) + index}/{EXPECTED}] {run_key}: failed",
                    flush=True,
                )
    expected_names = {
        f"{key(dataset, method, seed)}.json"
        for dataset in DATASETS
        for method in METHODS
        for seed in SEEDS
    }
    observed = [path for path in receipt_dir.iterdir() if path.is_file()]
    observed_names = {path.name for path in observed}
    exact_file_set = observed_names == expected_names
    report = {
        "schema_version": 1,
        "name": "VERA native-probe diagnostic matrix execution",
        "expected": EXPECTED,
        "valid": len(observed) if not failures and exact_file_set else None,
        "skipped_valid": len(skipped),
        "completed_this_run": len(completed),
        "failures": failures,
        "exact_file_set": exact_file_set,
        "passed": not failures and exact_file_set,
        "receipt_manifest_sha256": hashlib.sha256(
            "\n".join(
                f"{path.name} {sha256(path)}" for path in sorted(observed)
            ).encode("utf-8")
        ).hexdigest(),
    }
    report_path = output_dir / "execution_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "expected": EXPECTED,
                "observed": len(observed),
                "failure_count": len(failures),
                "report": str(report_path),
                "report_sha256": sha256(report_path),
            },
            sort_keys=True,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
