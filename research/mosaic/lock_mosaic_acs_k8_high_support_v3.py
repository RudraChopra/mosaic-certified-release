#!/usr/bin/env python3
"""Lock the fully preflighted high-support K=8 ACS extension before execution."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile

from mosaic_real import sha256


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
STORE_ROOT = Path("/Volumes/Backups/FARO/artifacts/acs_natural_shift_stores")
OUTPUT = ROOT / "prereg_mosaic_acs_k8_high_support_v3.json"
RECEIPT_ROOT = REPOSITORY / "research/artifacts/mosaic_acs_k8_high_support_v3_receipts"
SUMMARY = REPOSITORY / "research/artifacts/mosaic_acs_k8_high_support_v3_summary.json"
SPECIFICATION = ROOT / "MOSAIC_K8_HIGH_SUPPORT_V3_SPEC.md"
JOBS = (
    ("employment", "FL", 1400, "acs_employment_ca_fl_natural_store"),
    ("employment", "IL", 1400, "acs_employment_ca_il_natural_store"),
    ("employment", "NY", 1400, "acs_employment_ca_ny_natural_store"),
)
CODE_PATHS = (
    "research/mosaic/lock_mosaic_acs_k8_high_support_v3.py",
    "research/mosaic/run_mosaic_acs_k8_high_support_v3.py",
    "research/mosaic/run_mosaic_acs_natural_shift.py",
    "research/mosaic/mosaic_bridge.py",
    "research/mosaic/mosaic_strict_certification.py",
    "research/mosaic/mosaic_transform_exact_optimizer.py",
    "research/mosaic/mosaic_real.py",
    "research/scripts/official_eraser_adapters.py",
    "research/scripts/run_official_eraser_frontier.py",
)


def atomic_write(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def runtime_preflight() -> dict[str, object]:
    """Import every official adapter before protocol lock or execution."""

    from official_eraser_adapters import (
        INLP_REPO,
        LEACE_REPO,
        MANCE_REPO,
        RLACE_REPO,
        TACO_REPO,
    )

    for path in (INLP_REPO, LEACE_REPO, RLACE_REPO, TACO_REPO, MANCE_REPO):
        if not path.is_dir():
            raise FileNotFoundError(path)
        if str(path) not in sys.path:
            sys.path.insert(0, str(path))
    from concept_erasure import LeaceFitter  # type: ignore
    import rlace  # type: ignore
    from TaCo.concept_removal import crop_concepts  # type: ignore
    from mance import MANCE  # type: ignore
    from src import debias  # type: ignore

    packages = ("numpy", "scipy", "scikit-learn", "torch", "tqdm")
    return {
        "interpreter": sys.executable,
        "python": sys.version.split()[0],
        "packages": {name: importlib.metadata.version(name) for name in packages},
        "official_imports": {
            "INLP": str(Path(debias.__file__).resolve()),
            "LEACE": LeaceFitter.__module__,
            "R-LACE": str(Path(rlace.__file__).resolve()),
            "TaCo": crop_concepts.__module__,
            "MANCE++": MANCE.__module__,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    sidecar = args.output.with_suffix(args.output.suffix + ".sha256")
    if args.output.exists() or sidecar.exists() or RECEIPT_ROOT.exists() or SUMMARY.exists():
        raise FileExistsError("K=8 high-support v3 lock or outcome path already exists")
    preflight = runtime_preflight()
    if not SPECIFICATION.is_file():
        raise FileNotFoundError(SPECIFICATION)
    jobs = []
    for task, state, seed, store_name in JOBS:
        manifest = STORE_ROOT / store_name / "manifest.json"
        if not manifest.is_file():
            raise FileNotFoundError(manifest)
        jobs.append(
            {
                "task": task,
                "target_state": state,
                "seed": seed,
                "store": store_name,
                "manifest_sha256": sha256(manifest),
            }
        )
    payload = {
        "project": "MOSAIC K=8 high-support ACS extension v3",
        "status": "locked_before_execution",
        "analysis_status": "post-review extension; v1 and v2 stopped before a candidate frontier outcome",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "repository_head_at_lock": __import__("subprocess").run(
            ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, check=True,
            capture_output=True, text=True,
        ).stdout.strip(),
        "specification": str(SPECIFICATION.relative_to(REPOSITORY)),
        "specification_sha256": sha256(SPECIFICATION),
        "runtime_preflight": preflight,
        "jobs": jobs,
        "fine_token_count": 8,
        "released_token_count": 2,
        "source_advantage_threshold": 0.35,
        "utility_threshold": 0.40,
        "maximum_reference_rows": 64_000,
        "maximum_bridge_rows": 64_000,
        "maximum_diagnostic_rows": 24_000,
        "expected_rows_per_source_label": 16_000,
        "frontier": "identity plus twelve official candidate strengths",
        "complete_reporting": "Report every job and every candidate row regardless of outcome.",
        "claim_boundary": "This study tests whether higher certification support changes K=8 feasibility for the three locked employment transfers.",
        "code_sha256": {relative: sha256(REPOSITORY / relative) for relative in CODE_PATHS},
    }
    atomic_write(args.output, payload)
    sidecar.write_text(sha256(args.output) + "\n", encoding="utf-8")
    print(json.dumps({"lock": str(args.output), "jobs": len(jobs)}, indent=2))


if __name__ == "__main__":
    main()
