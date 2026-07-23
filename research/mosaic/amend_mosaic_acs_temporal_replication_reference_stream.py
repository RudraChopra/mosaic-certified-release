#!/usr/bin/env python3
"""Lock a transport-only amendment after the local reference inode failed."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from run_mosaic_acs_temporal_replication import (
    AMENDMENT,
    LOCK,
    OUTPUT,
    REFERENCE_URL,
    STATE_FIPS,
)


ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "research/mosaic/run_mosaic_acs_temporal_replication.py"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--future-raw-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sidecar = AMENDMENT.with_suffix(AMENDMENT.suffix + ".sha256")
    if AMENDMENT.exists() or sidecar.exists():
        raise FileExistsError("reference-stream amendment already exists")
    if OUTPUT.exists():
        raise FileExistsError("confirmation outcome already exists")
    if not LOCK.exists():
        raise FileNotFoundError(LOCK)
    present = [
        str(
            args.future_raw_root
            / "2022"
            / "1-Year"
            / f"psam_p{STATE_FIPS[state]}.csv"
        )
        for state in sorted(STATE_FIPS)
        if (
            args.future_raw_root
            / "2022"
            / "1-Year"
            / f"psam_p{STATE_FIPS[state]}.csv"
        ).exists()
    ]
    if present:
        raise ValueError(f"2022 confirmation assets are already present: {present}")
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    relative = RUNNER.relative_to(ROOT).as_posix()
    payload = {
        "name": "MOSAIC ACS temporal replication reference transport amendment v1",
        "status": "locked_before_2022_download_after_io_failure",
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head_before_amendment": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "original_lock_sha256": sha256(LOCK),
        "original_protocol": lock["protocol"],
        "failure": {
            "stage": "before_reference_header_and_before_any_2022_download",
            "exception": "TimeoutError: [Errno 60] Operation timed out",
            "failed_asset": "locked local 2018 California CSV inode",
        },
        "amendment": (
            "Change only reference-byte transport. Stream the official 2018 "
            "California Census PUMS archive in memory and require its "
            "uncompressed member to match the original locked byte count and "
            "SHA-256 before parsing."
        ),
        "unchanged": [
            "three hypotheses",
            "2018 frozen interfaces",
            "2022 confirmation population",
            "sampling rule",
            "familywise delta",
            "thresholds",
            "confirmation criterion",
            "stopping rule",
        ],
        "reference_url": REFERENCE_URL,
        "code_sha256": {relative: sha256(RUNNER)},
        "raw_2022_assets_absent_at_amendment": True,
    }
    AMENDMENT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = sha256(AMENDMENT)
    sidecar.write_text(f"{digest}  {AMENDMENT.name}\n", encoding="utf-8")
    print(json.dumps({"amendment": str(AMENDMENT), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
