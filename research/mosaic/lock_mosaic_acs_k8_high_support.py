#!/usr/bin/env python3
"""Lock the post-review high-support K=8 ACS extension before execution."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from mosaic_real import sha256


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
STORE_ROOT = Path("/Volumes/Backups/FARO/artifacts/acs_natural_shift_stores")
OUTPUT = ROOT / "prereg_mosaic_acs_k8_high_support_v1.json"
RECEIPT_ROOT = REPOSITORY / "research/artifacts/mosaic_acs_k8_high_support_v1_receipts"
SUMMARY = REPOSITORY / "research/artifacts/mosaic_acs_k8_high_support_v1_summary.json"
JOBS = (
    ("employment", "FL", 1400, "acs_employment_ca_fl_natural_store"),
    ("employment", "IL", 1400, "acs_employment_ca_il_natural_store"),
    ("employment", "NY", 1400, "acs_employment_ca_ny_natural_store"),
)
CODE_PATHS = (
    "research/mosaic/lock_mosaic_acs_k8_high_support.py",
    "research/mosaic/run_mosaic_acs_k8_high_support.py",
    "research/mosaic/run_mosaic_acs_natural_shift.py",
    "research/mosaic/mosaic_bridge.py",
    "research/mosaic/mosaic_strict_certification.py",
    "research/mosaic/mosaic_transform_exact_optimizer.py",
    "research/mosaic/mosaic_real.py",
    "research/scripts/official_eraser_adapters.py",
    "research/scripts/run_official_eraser_frontier.py",
)


def atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    if args.output.exists() or sidecar.exists() or RECEIPT_ROOT.exists() or SUMMARY.exists():
        raise FileExistsError("K=8 high-support lock or outcome path already exists")
    jobs = []
    for task, state, seed, store_name in JOBS:
        manifest = STORE_ROOT / store_name / "manifest.json"
        if not manifest.is_file():
            raise FileNotFoundError(manifest)
        jobs.append({
            "task": task,
            "target_state": state,
            "seed": seed,
            "store": store_name,
            "manifest_sha256": sha256(manifest),
        })
    payload = {
        "project": "MOSAIC K=8 high-support ACS extension",
        "status": "locked_before_execution",
        "analysis_status": "post-review extension; separate from the original 60-job confirmation",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "repository_head_at_lock": __import__("subprocess").run(["git", "rev-parse", "HEAD"], cwd=REPOSITORY, check=True, capture_output=True, text=True).stdout.strip(),
        "jobs": jobs,
        "fine_token_count": 8,
        "released_token_count": 2,
        "source_advantage_threshold": 0.35,
        "utility_threshold": 0.40,
        "maximum_reference_rows": 64_000,
        "maximum_bridge_rows": 64_000,
        "maximum_diagnostic_rows": 24_000,
        "expected_rows_per_source_label": 16_000,
        "frontier": "identity plus twelve official candidate strengths",
        "complete_reporting": "Report every job and every candidate row regardless of outcome.",
        "claim_boundary": "This study tests whether higher certification support changes K=8 feasibility for the three locked employment transfers.",
        "code_sha256": {relative: sha256(REPOSITORY / relative) for relative in CODE_PATHS},
    }
    atomic_write(args.output, payload)
    sidecar.write_text(sha256(args.output) + "\n", encoding="utf-8")
    print(json.dumps({"lock": str(args.output), "jobs": len(jobs)}, indent=2))


if __name__ == "__main__":
    main()
