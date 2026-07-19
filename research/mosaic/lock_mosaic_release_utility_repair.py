#!/usr/bin/env python3
"""Lock the diagnostic-anchored utility repair before it is executed."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from mosaic_release_utility_common_v2 import selected_jobs
from mosaic_real import sha256


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
DEFAULT_OUTPUT = ROOT / "prereg_mosaic_release_utility_repair_v1.json"
STRICT_DIR = REPOSITORY / "research/artifacts/mosaic_bridge_strict_v2_receipts_v1"
UTILITY_OUTPUT = REPOSITORY / "research/artifacts/mosaic_release_utility_v2.json"
SLICES = {"BiasBios-Clinical": ["0.40"], "Waterbirds": ["0.49"]}
CODE_FILES = (
    "research/mosaic/mosaic_release_utility_common.py",
    "research/mosaic/mosaic_release_utility_common_v2.py",
    "research/mosaic/run_mosaic_release_utility_v2.py",
    "research/mosaic/audit_mosaic_release_utility_v2.py",
    "research/mosaic/lock_mosaic_release_utility_repair.py",
    "research/mosaic/run_mosaic_bridge_frontier.py",
    "research/mosaic/mosaic_real.py",
    "research/scripts/run_official_eraser_frontier.py",
    "research/scripts/official_eraser_adapters.py",
    "research/tests/test_mosaic_release_utility_v2.py",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    if args.output.exists() or sidecar.exists():
        raise FileExistsError("refusing to overwrite an existing utility repair lock")
    if UTILITY_OUTPUT.exists():
        raise FileExistsError("utility repair output already exists")
    jobs = selected_jobs(STRICT_DIR, SLICES)
    payload = {
        "project": "MOSAIC diagnostic-anchored released-interface utility repair",
        "status": "locked_diagnostic_anchored_utility_repair_before_execution",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "slices": SLICES,
        "expected_deployed_release_count": len(jobs),
        "repair": {
            "trigger": "The v1 utility run stopped because current reference and bridge token counts differed from their locked receipts.",
            "observation": "For the investigated first selected release, the untouched diagnostic token counts matched exactly while the reference and bridge counts did not.",
            "change": "v2 requires the diagnostic count match, records every reference and bridge discrepancy, and computes no metric from those discrepant splits.",
            "classification": "post-outcome diagnostic-anchored measurement repair",
        },
        "claim_boundary": (
            "The v2 table measures diagnostic interface utility only. It neither revalidates "
            "the historical reference/bridge features nor changes the original MOSAIC result."
        ),
        "code_sha256": {relative: sha256(REPOSITORY / relative) for relative in CODE_FILES},
    }
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    args.output.write_text(data, encoding="utf-8")
    sidecar.write_text(hashlib.sha256(data.encode("utf-8")).hexdigest() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
