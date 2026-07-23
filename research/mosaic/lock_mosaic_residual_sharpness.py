#!/usr/bin/env python3
"""Lock the exact residual census after one disclosed design-case inspection."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from run_mosaic_local_dp_baseline import ROOT, acs_jobs, biasbios_jobs, sha256
from run_mosaic_residual_sharpness import LOCK, expected_protocol


CODE = (
    "research/mosaic/run_mosaic_residual_sharpness.py",
    "research/mosaic/PATH9_THEOREMS.md",
    "research/mosaic/mosaic_channel.py",
    "research/mosaic/mosaic_transform_exact.py",
    "research/mosaic/run_mosaic_local_dp_baseline.py",
)


def git_head() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=LOCK)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    if args.output.exists() or sidecar.exists():
        raise FileExistsError("refusing to overwrite an existing residual lock")
    jobs = biasbios_jobs() + acs_jobs()
    inputs = sorted(
        {
            ROOT / relative
            for job in jobs
            for relative in job["inputs"]
        }
    )
    payload = {
        "name": "MOSAIC residual-sharpness census preregistration v1",
        "status": "locked_before_residual_census",
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head_before_lock": git_head(),
        "protocol": expected_protocol(),
        "code_sha256": {relative: sha256(ROOT / relative) for relative in CODE},
        "input_sha256": {
            str(path.relative_to(ROOT)): sha256(path) for path in inputs
        },
        "stopping_rule": (
            "Report all 35 rows, all four decomposition modes, the disclosed "
            "design case, the remaining 34-job census, and both sampling and "
            "residual increments regardless of direction."
        ),
        "claim_boundary": (
            "The decomposition is exact for the registered bridge class. It "
            "shows which part of the certificate survives infinite reference "
            "data under that model; it does not estimate how often adversarial "
            "residual laws occur naturally."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = sha256(args.output)
    sidecar.write_text(f"{digest}  {args.output.name}\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
