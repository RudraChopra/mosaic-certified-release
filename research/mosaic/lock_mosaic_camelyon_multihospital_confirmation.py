#!/usr/bin/env python3
"""Lock the Camelyon17 multi-hospital protocol before new outcome access."""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LOCK = (
    ROOT
    / "research/mosaic/"
    "prereg_mosaic_camelyon_multihospital_confirmation_v1.json"
)
OUTPUT = (
    ROOT
    / "research/artifacts/"
    "mosaic_camelyon_multihospital_confirmation_v1"
)
INHERITED_LOCK = ROOT / "research/mosaic/prereg_mosaic_real_exact_v1.json"
STORE_PATH = (
    "/Volumes/Backups/FARO/artifacts/"
    "camelyon17_resnet18_torch_center_numpy_store"
)
CODE = (
    "research/mosaic/mosaic_bridge.py",
    "research/mosaic/mosaic_channel.py",
    "research/mosaic/mosaic_envelope.py",
    "research/mosaic/mosaic_real.py",
    "research/mosaic/mosaic_transform_exact_optimizer.py",
    "research/mosaic/run_mosaic_camelyon_multihospital_confirmation.py",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    sidecar = LOCK.with_suffix(LOCK.suffix + ".sha256")
    if LOCK.exists() or sidecar.exists():
        raise FileExistsError("Camelyon multi-hospital lock already exists")
    if OUTPUT.exists():
        raise FileExistsError("Camelyon multi-hospital outcomes already exist")
    inherited = json.loads(INHERITED_LOCK.read_text(encoding="utf-8"))
    inherited_store = inherited["frozen_stores"]["Camelyon17-WILDS"]
    if inherited_store["path"] != STORE_PATH:
        raise RuntimeError("inherited Camelyon store path changed")
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    payload = {
        "name": "MOSAIC Camelyon17 multi-hospital confirmation lock v1",
        "status": "locked_before_multihospital_outcomes",
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head_before_lock": head,
        "design": (
            "registered follow-up to the known one-source external-hospital "
            "impossibility; no new multi-hospital outcomes were inspected"
        ),
        "claim_boundary": (
            "This confirmation uses official held-out Camelyon17 patients "
            "from hospitals represented in training. It tests supported "
            "multi-hospital patient shift, not transport to the unsupported "
            "official test hospital."
        ),
        "store": {
            "path": STORE_PATH,
            "manifest_sha256": inherited_store["manifest_sha256"],
            "inherited_preregistration": str(
                INHERITED_LOCK.relative_to(ROOT)
            ),
            "inherited_preregistration_sha256": sha256(INHERITED_LOCK),
        },
        "model": (
            "fixed torchvision ResNet-18 ImageNet-v1 penultimate features "
            "from the inherited frozen store"
        ),
        "target": "Camelyon17 tumor label",
        "source_definition": {
            "0": [0],
            "1": [3, 4],
            "excluded_hospitals": [1, 2],
        },
        "roles": {
            "construction_and_reference": (
                "disjoint balanced samples from official training rows in "
                "hospitals 0, 3, and 4"
            ),
            "bridge_and_diagnostic": (
                "registered two-thirds/one-third stratified split of official "
                "validation rows in hospitals 0, 3, and 4"
            ),
        },
        "balanced_fold_caps": {
            "construction": 6000,
            "reference": 18000,
        },
        "candidate": "ResNet18::penultimate::task-score::K=4",
        "fine_token_count": 4,
        "released_token_count": 2,
        "seeds": [4301, 4302, 4303, 4304, 4305],
        "privacy_advantage_threshold": 0.35,
        "utility_thresholds": [0.35, 0.40, 0.45, 0.49],
        "primary_utility_threshold": 0.40,
        "familywise_delta": 0.05,
        "family": "two token tables for each of five registered seeds",
        "operational_draws_per_primary_release": 100,
        "solver_time_limit_seconds": 300.0,
        "attacker_constraint_generation": True,
        "runtime_semantics": (
            "one persistent sampled release token per immutable image"
        ),
        "main_paper_inclusion_gate": {
            "minimum_primary_releases": 3,
            "maximum_heldout_primary_violations": 0,
            "maximum_operational_primary_violations": 0,
        },
        "code_sha256": {
            relative: sha256(ROOT / relative) for relative in CODE
        },
        "stopping_rule": (
            "Run all five seeds. Do not replace the frozen model, feature "
            "store, hospital grouping, roles, caps, seeds, alphabet, "
            "thresholds, confidence allocation, or diagnostic folds."
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
