#!/usr/bin/env python3
"""Run the locked Camelyon confirmation against the streamed feature store."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

import run_mosaic_camelyon_multihospital_confirmation as base


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE = ROOT / "research/data/camelyon17_streamed_confirmation"
DEFAULT_PREREG = (
    ROOT
    / "research/mosaic/"
    "prereg_mosaic_camelyon_streamed_confirmation_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research/artifacts/"
    "mosaic_camelyon_streamed_confirmation_v1"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def validate_lock(path: Path) -> dict[str, Any]:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").split()[0] != sha256(path):
        raise ValueError("Camelyon streamed lock sidecar mismatch")
    prereg = load_json(path)
    if prereg.get("status") != "locked_before_streamed_model_and_outcomes":
        raise RuntimeError("Camelyon streamed preregistration is not locked")
    for relative, expected in prereg["code_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"locked source mismatch: {relative}")
    for local in (path, sidecar):
        relative = local.relative_to(ROOT)
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative.as_posix()}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed != local.read_bytes():
            raise RuntimeError(f"{relative} is not the committed lock")
    return prereg


def load_store(
    path: Path,
    expected_manifest_sha256: str,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    del expected_manifest_sha256
    manifest_path = path / "manifest.json"
    manifest = load_json(manifest_path)
    prereg_sha = sha256(DEFAULT_PREREG)
    if manifest.get("preregistration_sha256") != prereg_sha:
        raise RuntimeError("streamed store belongs to another lock")
    prereg = load_json(DEFAULT_PREREG)
    if (
        manifest.get("selected_image_ids_sha256")
        != prereg["streamed_store"]["selected_image_ids_sha256"]
    ):
        raise RuntimeError("streamed Camelyon selection differs from the lock")
    arrays = manifest["arrays"]
    features = np.load(path / arrays["z"], mmap_mode="r")
    target = np.asarray(
        np.load(path / arrays["y"], mmap_mode="r"), dtype=np.int8
    )
    split = np.asarray(
        np.load(path / arrays["split"], mmap_mode="r"), dtype=np.int8
    )
    centers = np.asarray(
        np.load(path / arrays["g"], mmap_mode="r"), dtype=np.int8
    )
    expected = int(manifest["n_examples"])
    if not all(
        len(values) == expected
        for values in (features, target, split, centers)
    ):
        raise RuntimeError("streamed Camelyon arrays do not match")
    return manifest, features, target, split, centers


def main() -> None:
    base.DEFAULT_STORE = DEFAULT_STORE
    base.DEFAULT_PREREG = DEFAULT_PREREG
    base.DEFAULT_OUTPUT = DEFAULT_OUTPUT
    base.validate_lock = validate_lock
    base.load_store = load_store
    base.main()


if __name__ == "__main__":
    main()
