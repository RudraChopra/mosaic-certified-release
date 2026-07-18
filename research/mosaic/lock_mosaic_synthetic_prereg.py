#!/usr/bin/env python3
"""Materialize and hash-lock the MOSAIC synthetic preregistration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
TEMPLATE = ROOT / "prereg_mosaic_synthetic_v1.template.json"
OUTPUT = ROOT / "prereg_mosaic_synthetic_v1.json"
SIDECAR = ROOT / "prereg_mosaic_synthetic_v1.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_text(text: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=output.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(output)


def main() -> None:
    with TEMPLATE.open("r", encoding="utf-8") as handle:
        config = json.load(handle)
    code_paths = tuple(config.pop("code_paths"))
    pilot_paths = tuple(config.pop("pilot_artifact_paths"))
    config["code_sha256"] = {
        path: sha256(REPOSITORY / path) for path in code_paths
    }
    config["pilot_artifact_sha256"] = {
        path: sha256(REPOSITORY / path) for path in pilot_paths
    }
    serialized = json.dumps(config, indent=2, sort_keys=True) + "\n"
    atomic_text(serialized, OUTPUT)
    digest = sha256(OUTPUT)
    relative = OUTPUT.relative_to(REPOSITORY)
    atomic_text(f"{digest}  {relative}\n", SIDECAR)
    print(json.dumps({"preregistration": str(relative), "sha256": digest}, indent=2))


if __name__ == "__main__":
    main()
