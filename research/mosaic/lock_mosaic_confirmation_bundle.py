#!/usr/bin/env python3
"""Seal the audited MOSAIC confirmation evidence into a hash manifest."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
OUTPUT = REPOSITORY / "research" / "artifacts" / "mosaic_confirmation_bundle_v1.json"
SIDECAR = OUTPUT.with_suffix(".sha256")
ARTIFACTS = (
    "research/artifacts/mosaic_synthetic_confirmation_v1.json",
    "research/artifacts/mosaic_synthetic_confirmation_audit_v1.json",
    "research/artifacts/mosaic_synthetic_theory_alignment_audit_v1.json",
    "research/artifacts/mosaic_synthetic_claim_summary_v1.json",
    "research/maintrack/mosaic_aaai2027/figures/figure2_mosaic_confirmation.pdf",
    "research/maintrack/mosaic_aaai2027/figures/figure2_mosaic_confirmation.png",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    confirmation = load_json(REPOSITORY / ARTIFACTS[0])
    replay = load_json(REPOSITORY / ARTIFACTS[1])
    alignment = load_json(REPOSITORY / ARTIFACTS[2])
    summary = load_json(REPOSITORY / ARTIFACTS[3])
    confirmation_hash = sha256(REPOSITORY / ARTIFACTS[0])
    if replay.get("pass") is not True or replay.get("report_sha256") != confirmation_hash:
        raise AssertionError("confirmation lacks a matching passing replay")
    if (
        alignment.get("pass") is not True
        or alignment.get("confirmation_sha256") != confirmation_hash
    ):
        raise AssertionError("confirmation lacks a matching passing alignment audit")
    if summary.get("confirmation_sha256") != confirmation_hash:
        raise AssertionError("paired summary does not cover the confirmation")
    if confirmation.get("pass_conditions", {}).get("all_pass") is not True:
        raise AssertionError("the locked confirmation gate did not pass")
    payload = {
        "name": "MOSAIC audited confirmation evidence bundle v1",
        "status": "sealed_post_outcome_evidence",
        "preregistration_sha256": confirmation["preregistration_sha256"],
        "artifacts_sha256": {
            relative: sha256(REPOSITORY / relative) for relative in ARTIFACTS
        },
        "audit_requirements": {
            "confirmation_gate_passed": True,
            "independent_replay_passed": True,
            "theory_alignment_passed": True,
            "paired_claim_summary_linked": True,
        },
        "scope": (
            "This post-outcome manifest freezes the complete synthetic evidence "
            "chain. It does not turn internal replay into independent human review "
            "or establish deployment-shift membership on a real domain."
        ),
    }
    atomic_write(OUTPUT, json.dumps(payload, indent=2, sort_keys=True) + "\n")
    manifest_hash = sha256(OUTPUT)
    atomic_write(SIDECAR, f"{manifest_hash}  {OUTPUT.name}\n")
    print(json.dumps({"manifest": str(OUTPUT), "sha256": manifest_hash}, indent=2))


if __name__ == "__main__":
    main()
