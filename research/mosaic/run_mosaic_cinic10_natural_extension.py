#!/usr/bin/env python3
"""Run the locked 40-seed CINIC-10 natural-origin power extension."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import run_mosaic_cinic10_natural_confirmation as legacy


ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research/mosaic/prereg_mosaic_cinic10_natural_v2.json"
OUTPUT = ROOT / "research/artifacts/mosaic_cinic10_natural_v2.json"
SEEDS = (4101, 4102, 4103, 4104, 4105, *range(4201, 4236))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_lock() -> dict[str, object]:
    sidecar = PREREG.with_suffix(PREREG.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").strip() != sha256(PREREG):
        raise ValueError("CINIC extension preregistration sidecar mismatch")
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if prereg["status"] != "locked_before_extension_outcomes":
        raise ValueError("CINIC extension preregistration status mismatch")
    if sha256(legacy.STORE / "manifest.json") != prereg["store_manifest_sha256"]:
        raise ValueError("CINIC store manifest mismatch")
    for relative, expected in prereg["code_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f"locked code mismatch: {relative}")
    for path in (PREREG, sidecar):
        relative = path.relative_to(ROOT)
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative.as_posix()}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise ValueError(f"{relative} is not the committed lock")
    return prereg


def main() -> None:
    legacy.PREREG = PREREG
    legacy.OUTPUT = OUTPUT
    legacy.SEEDS = SEEDS
    legacy.validate_lock = validate_lock
    legacy.main()


if __name__ == "__main__":
    main()
