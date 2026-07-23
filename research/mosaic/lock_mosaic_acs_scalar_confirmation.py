#!/usr/bin/env python3
"""Lock the scalar ACS confirmation before any 2023 asset is accessed."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from run_mosaic_acs_scalar_confirmation import (
    DISCOVERY,
    LOCK,
    OUTPUT,
    PANDEMIC_LOCK,
    STATE_FIPS,
    WITNESSES,
    expected_protocol,
    receipt_path,
)


ROOT = Path(__file__).resolve().parents[2]
CODE = (
    "research/mosaic/mosaic_real.py",
    "research/mosaic/run_mosaic_acs_pandemic_panel.py",
    "research/mosaic/run_mosaic_acs_temporal_replication.py",
    "research/mosaic/run_mosaic_acs_scalar_confirmation.py",
    "research/mosaic/run_mosaic_official_frontier_exact_confirmation.py",
    "research/scripts/official_eraser_adapters.py",
    "research/scripts/prepare_acs_natural_shift_stores.py",
    "research/scripts/run_official_eraser_frontier.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--future-raw-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sidecar = LOCK.with_suffix(LOCK.suffix + ".sha256")
    if LOCK.exists() or sidecar.exists():
        raise FileExistsError("scalar-confirmation lock already exists")
    if OUTPUT.exists():
        raise FileExistsError("scalar-confirmation outcome already exists")
    present = [
        str(
            args.future_raw_root
            / "2023"
            / "1-Year"
            / f"psam_p{STATE_FIPS[state]}.csv"
        )
        for state in sorted(STATE_FIPS)
        if (
            args.future_raw_root
            / "2023"
            / "1-Year"
            / f"psam_p{STATE_FIPS[state]}.csv"
        ).exists()
    ]
    if present:
        raise ValueError(f"2023 confirmation assets are already present: {present}")
    discovery = load(DISCOVERY)
    repeated = [
        {
            "target_state": row["target_state"],
            "task": row["task"],
            "seed": row["seed"],
            "candidate": row["candidate"],
            "worst_conditional_error_empirical": row["future_diagnostic"][
                "worst_conditional_error_empirical"
            ],
        }
        for row in discovery["rows"]
        if row["future_diagnostic"]["utility_contract_violation_empirical"]
    ]
    expected = [dict(row) for row in WITNESSES]
    observed_keys = {
        (row["target_state"], row["task"], row["seed"], row["candidate"])
        for row in repeated
    }
    expected_keys = {
        (row["target_state"], row["task"], row["seed"], row["candidate"])
        for row in expected
    }
    if observed_keys != expected_keys:
        raise ValueError("scalar witness family differs from 2022 persistence")
    inputs = {
        str(DISCOVERY.relative_to(ROOT)): sha256(DISCOVERY),
        str(PANDEMIC_LOCK.relative_to(ROOT)): sha256(PANDEMIC_LOCK),
        "research/mosaic/prereg_mosaic_acs_natural_shift_data_v1.json": sha256(
            ROOT / "research/mosaic/prereg_mosaic_acs_natural_shift_data_v1.json"
        ),
    }
    for witness in WITNESSES:
        path = receipt_path(witness)
        inputs[str(path.relative_to(ROOT))] = sha256(path)
    payload = {
        "name": "MOSAIC ACS fixed-functional natural failure confirmation lock v1",
        "status": "locked_before_2023_download",
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head_before_lock": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "claim_boundary": (
            "This is a prospective 2023 confirmation after 2021 discovery and "
            "2022 persistence, not a prospectively selected initial hypothesis. "
            "The scalar bound is fixed before 2023 access and applies only "
            "because each tested channel and utility functional is frozen."
        ),
        "protocol": expected_protocol(),
        "repeated_2022_rows": repeated,
        "code_sha256": {relative: sha256(ROOT / relative) for relative in CODE},
        "input_sha256": inputs,
        "reference_raw_asset": load(PANDEMIC_LOCK)["reference_raw_asset"],
        "raw_2023_assets_absent_at_lock": True,
        "stopping_rule": (
            "Report both frozen interfaces, all eight scalar stratum bounds, "
            "every reconstruction failure, and every confirmed or unconfirmed "
            "violation. No replacement interface or confidence method is allowed."
        ),
    }
    LOCK.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    digest = sha256(LOCK)
    sidecar.write_text(f"{digest}  {LOCK.name}\n", encoding="utf-8")
    print(json.dumps({"lock": str(LOCK), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
