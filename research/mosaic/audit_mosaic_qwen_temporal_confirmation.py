#!/usr/bin/env python3
"""Deterministically replay and compare the MOSAIC Qwen confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_STORE = Path(
    "/Volumes/Backups/FARO/artifacts/civilcomments_qwen25_temporal_confirmation"
)
DEFAULT_PREREG = (
    REPOSITORY / "research/mosaic/prereg_mosaic_qwen_temporal_confirmation_v1.json"
)
DEFAULT_RECEIPTS = REPOSITORY / "research/artifacts/mosaic_qwen_temporal_confirmation_v1"
DEFAULT_OUTPUT = REPOSITORY / "research/artifacts/mosaic_qwen_temporal_confirmation_audit_v1.json"
RUNNER = REPOSITORY / "research/mosaic/run_mosaic_qwen_temporal_confirmation.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--receipts", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    expected_names = sorted(path.name for path in args.receipts.glob("*.json"))
    if "summary.json" not in expected_names:
        raise RuntimeError("frozen confirmation summary is missing")

    with tempfile.TemporaryDirectory(prefix="mosaic-qwen-replay-") as temporary:
        replay = Path(temporary) / "receipts"
        environment = os.environ.copy()
        python_path = os.pathsep.join(
            (
                str(REPOSITORY / "research/mosaic"),
                str(REPOSITORY / "research/scripts"),
                environment.get("PYTHONPATH", ""),
            )
        )
        environment["PYTHONPATH"] = python_path
        subprocess.run(
            [
                sys.executable,
                str(RUNNER),
                "--store",
                str(args.store),
                "--prereg",
                str(args.prereg),
                "--output",
                str(replay),
            ],
            cwd=REPOSITORY,
            env=environment,
            check=True,
        )
        observed_names = sorted(path.name for path in replay.glob("*.json"))
        failures: list[str] = []
        if observed_names != expected_names:
            failures.append(
                f"receipt set differs: frozen={expected_names}, replay={observed_names}"
            )
        comparisons = {}
        for name in sorted(set(expected_names) & set(observed_names)):
            frozen_path = args.receipts / name
            replay_path = replay / name
            frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
            regenerated = json.loads(replay_path.read_text(encoding="utf-8"))
            exact = frozen == regenerated
            comparisons[name] = {
                "exact_semantic_match": exact,
                "frozen_sha256": sha256(frozen_path),
                "replay_sha256": sha256(replay_path),
            }
            if not exact:
                failures.append(f"semantic mismatch: {name}")

    report = {
        "name": "MOSAIC Qwen2.5 temporal confirmation deterministic replay v1",
        "passed": not failures,
        "preregistration_sha256": sha256(args.prereg),
        "runner_sha256": sha256(RUNNER),
        "receipt_files": len(expected_names),
        "comparisons": comparisons,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
