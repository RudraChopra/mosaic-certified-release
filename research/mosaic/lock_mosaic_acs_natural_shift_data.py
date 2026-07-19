#!/usr/bin/env python3
"""Hash-lock every frozen input for the ACS natural-shift confirmation."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import numpy as np

from mosaic_real import sha256
from run_mosaic_acs_natural_shift import TARGET_STATES, TASKS


ROOT = Path(__file__).resolve().parent
DEFAULT_PREREG = ROOT / "prereg_mosaic_acs_natural_shift_v1.json"
DEFAULT_STORES = Path("/Volumes/Backups/FARO/artifacts/acs_natural_shift_stores")
DEFAULT_OUTPUT = ROOT / "prereg_mosaic_acs_natural_shift_data_v1.json"
ARRAYS = ("z.npy", "y.npy", "s.npy", "environment.npy", "split.npy", "g.npy")


def store_path(root: Path, task: str, state: str) -> Path:
    return root / f"acs_{task}_ca_{state.lower()}_natural_store"


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--stores", type=Path, default=DEFAULT_STORES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    if args.output.exists() or sidecar.exists():
        raise FileExistsError("refusing to overwrite the natural-shift data lock")
    prereg_sidecar = args.prereg.with_suffix(args.prereg.suffix + ".sha256")
    prereg_sha = sha256(args.prereg)
    if prereg_sidecar.read_text(encoding="utf-8").strip() != prereg_sha:
        raise ValueError("preregistration sidecar mismatch")
    stores: dict[str, Any] = {}
    raw_assets: dict[str, Any] = {}
    for task in TASKS:
        for state in TARGET_STATES:
            path = store_path(args.stores, task, state)
            manifest_path = path / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest["task"] != task or manifest["states"] != {
                "reference": "CA",
                "external": state,
            }:
                raise ValueError(f"store identity mismatch: {path}")
            arrays = {}
            row_count = None
            for name in ARRAYS:
                array_path = path / name
                values = np.load(array_path, mmap_mode="r")
                row_count = values.shape[0] if row_count is None else row_count
                if values.shape[0] != row_count:
                    raise ValueError(f"array row mismatch: {array_path}")
                arrays[name] = {
                    "bytes": array_path.stat().st_size,
                    "sha256": sha256(array_path),
                    "shape": list(values.shape),
                    "dtype": str(values.dtype),
                }
            key = f"{task}:CA->{state}"
            stores[key] = {
                "manifest_sha256": sha256(manifest_path),
                "manifest": manifest,
                "arrays": arrays,
            }
            for relative, receipt in manifest["raw_assets"].items():
                previous = raw_assets.get(relative)
                if previous is not None and previous != receipt:
                    raise ValueError(f"inconsistent raw hash for {relative}")
                raw_assets[relative] = receipt
    payload = {
        "project": "MOSAIC natural multi-environment ACS confirmation",
        "status": "frozen_before_outcome_execution",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "preregistration_sha256": prereg_sha,
        "store_count": len(stores),
        "raw_assets": raw_assets,
        "stores": stores,
        "claim_boundary": (
            "This lock authenticates the exact public raw assets and processed arrays "
            "used by the registered confirmation; it contains no model outcomes."
        ),
    }
    if len(stores) != len(TASKS) * len(TARGET_STATES):
        raise RuntimeError("natural-shift data lock is incomplete")
    atomic_write(args.output, payload)
    sidecar.write_text(sha256(args.output) + "\n", encoding="utf-8")
    print(json.dumps({"data_lock": str(args.output), "stores": len(stores)}, indent=2))


if __name__ == "__main__":
    main()
