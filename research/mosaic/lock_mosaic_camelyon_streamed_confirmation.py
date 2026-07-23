#!/usr/bin/env python3
"""Lock the streamed Camelyon17 confirmation before feature outcomes."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from prepare_camelyon_streamed_confirmation_store import (
    load_metadata,
    selected_rows,
    sha256,
    sha256_array,
)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_METADATA = Path(
    "/Users/rudrachopra/Documents/Science Fair/research/artifacts/"
    "camelyon17_wilds_metadata 2.csv"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research/mosaic/"
    "prereg_mosaic_camelyon_streamed_confirmation_v1.json"
)
CODE_FILES = (
    "research/mosaic/mosaic_bridge.py",
    "research/mosaic/mosaic_channel.py",
    "research/mosaic/mosaic_envelope.py",
    "research/mosaic/mosaic_real.py",
    "research/mosaic/mosaic_transform_exact_optimizer.py",
    "research/mosaic/run_mosaic_bridge_frontier.py",
    "research/mosaic/run_mosaic_camelyon_multihospital_confirmation.py",
    "research/mosaic/prepare_camelyon_streamed_confirmation_store.py",
    "research/mosaic/run_mosaic_camelyon_streamed_confirmation.py",
)
REVISION = "d784d5344ba6c967f83f9f3d9b2f1e2a4d6eb78f"
PARQUET_FILES = (
    *(
        f"data/train-{index:05d}-of-00014.parquet"
        for index in range(14)
    ),
    *(
        f"data/validation-{index:05d}-of-00003.parquet"
        for index in range(3)
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to replace {args.output}")
    frame = load_metadata(args.metadata)
    selected = selected_rows(
        frame,
        train_per_stratum=7000,
        validation_per_stratum=2800,
        seed=20270727,
    )
    ids = selected["image_id"].to_numpy()
    payload = {
        "name": "MOSAIC Camelyon17 streamed multi-hospital lock v1",
        "status": "locked_before_streamed_model_and_outcomes",
        "locked_at_utc": datetime.now(timezone.utc).isoformat(),
        "repository_head_before_lock": subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "design": (
            "Outcome-blind data-access amendment to the previously locked "
            "multi-hospital confirmation after its APFS source volume failed "
            "read-only verification. Method, sources, thresholds, seeds, and "
            "diagnostic rule are unchanged."
        ),
        "metadata": {
            "bytes": args.metadata.stat().st_size,
            "sha256": sha256(args.metadata),
            "rows": len(frame),
        },
        "remote_dataset": {
            "repository": "wltjr1007/Camelyon17-WILDS",
            "revision": REVISION,
            "parquet_files": list(PARQUET_FILES),
            "provenance_check": (
                "Every selected image ID, label, center, patient, node, and "
                "coordinate must match the local official WILDS metadata."
            ),
        },
        "streamed_store": {
            "selection_seed": 20270727,
            "train_rows_per_stratum": 7000,
            "validation_rows_per_stratum": 2800,
            "selected_rows": len(selected),
            "selected_image_ids_sha256": sha256_array(ids),
            "model": "torchvision ResNet18 ImageNet-1K V1 penultimate",
            "preprocessing": "official torchvision weights transform",
        },
        "store": {
            "manifest_sha256": "bound_to_preregistration_sha256",
        },
        "balanced_fold_caps": {
            "construction": 6000,
            "reference": 18000,
        },
        "familywise_delta": 0.05,
        "privacy_advantage_threshold": 0.35,
        "utility_thresholds": [0.35, 0.40, 0.45, 0.49],
        "primary_utility_threshold": 0.40,
        "fine_token_count": 4,
        "released_token_count": 2,
        "seeds": [4301, 4302, 4303, 4304, 4305],
        "operational_draws_per_primary_release": 100,
        "solver_time_limit_seconds": 300.0,
        "attacker_constraint_generation": True,
        "main_paper_inclusion_gate": {
            "minimum_primary_releases": 3,
            "maximum_heldout_primary_violations": 0,
            "maximum_operational_primary_violations": 0,
        },
        "claim_boundary": (
            "This confirmation uses held-out Camelyon17 patches from hospitals "
            "represented in training. It tests supported multi-hospital "
            "patient shift, not transport to the unsupported center-2 test "
            "hospital."
        ),
        "code_sha256": {
            relative: sha256(ROOT / relative) for relative in CODE_FILES
        },
    }
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    sidecar.write_text(
        f"{sha256(args.output)}  {args.output.name}\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "sha256": sha256(args.output),
                "selected_rows": len(selected),
                "selected_image_ids_sha256": sha256_array(ids),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
