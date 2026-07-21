#!/usr/bin/env python3
"""Audit the complete unlocked MOSAIC Qwen pilot and its stopping rule."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = REPOSITORY / "research/artifacts/mosaic_qwen_pilot_v1.json"
DEFAULT_STORE = Path("/Volumes/Backups/FARO/artifacts/civilcomments_qwen25_pilot")
DEFAULT_OUTPUT = REPOSITORY / "research/artifacts/mosaic_qwen_pilot_audit_v1.json"
EXPECTED_CANDIDATES = {
    f"{representation}::K={token_count}"
    for representation in ("layer14_mean", "layer28_mean", "layer28_last")
    for token_count in (4, 8)
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    report = json.loads(args.report.read_text(encoding="utf-8"))
    failures: list[str] = []
    candidates = report.get("candidates", [])
    observed = {str(value["candidate"]) for value in candidates}
    if observed != EXPECTED_CANDIDATES or len(candidates) != len(EXPECTED_CANDIDATES):
        failures.append("candidate family is incomplete or duplicated")
    recomputed_go = []
    representation_checks = {}

    for representation in ("layer14_mean", "layer28_mean", "layer28_last"):
        directory = args.store_root / representation
        manifest_path = directory / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ids = np.load(directory / "ids.npy")
        target = np.load(directory / "y.npy")
        source = np.load(directory / "s.npy")
        split = np.load(directory / "split.npy")
        overlap = int(np.sum(ids % 4 != 0))
        counts = {
            f"split={role},y={yy},s={ss}": int(
                np.sum((split == role) & (target == yy) & (source == ss))
            )
            for role in (0, 1, 2)
            for yy in (0, 1)
            for ss in (0, 1)
        }
        if overlap:
            failures.append(f"{representation} contains {overlap} confirmation IDs")
        if counts != manifest["group_counts"]:
            failures.append(f"{representation} manifest counts differ from arrays")
        representation_checks[representation] = {
            "manifest_sha256": sha256(manifest_path),
            "rows": len(ids),
            "confirmation_id_overlap": overlap,
            "all_registered_strata_nonempty": all(value > 0 for value in counts.values()),
        }

    for candidate in candidates:
        key = str(candidate["candidate"])
        representation = key.split("::", 1)[0]
        if (
            candidate["representation_manifest_sha256"]
            != representation_checks[representation]["manifest_sha256"]
        ):
            failures.append(f"{key} representation manifest hash differs")
        source_bounds = tuple(float(value) for value in candidate["certified_source_advantage_upper"])
        expected_go = bool(
            candidate["diagnostic_estimable"]
            and min(min(row) for row in candidate["reference_stratum_counts"]) > 0
            and min(min(row) for row in candidate["bridge_stratum_counts"]) > 0
            and float(candidate["minimum_retained_mass"]) >= 0.50
            and candidate["nonconstant_release"]
            and float(candidate["certified_worst_conditional_error_upper"]) <= 0.49
            and max(source_bounds) <= 0.35 + 1e-10
        )
        if bool(candidate["pilot_go"]) != expected_go:
            failures.append(f"{key} pilot-go field differs from the prewritten rule")
        if expected_go:
            recomputed_go.append(candidate)

    selected = (
        min(
            recomputed_go,
            key=lambda value: (
                float(value["certified_worst_conditional_error_upper"]),
                -float(value["minimum_retained_mass"]),
                str(value["candidate"]),
            ),
        )
        if recomputed_go
        else None
    )
    if bool(report["go_to_locked_confirmation"]) != (selected is not None):
        failures.append("top-level go/no-go differs from recomputation")
    if report["selected_candidate"] != selected:
        failures.append("selected candidate differs from the prewritten tie break")

    report_out = {
        "name": "MOSAIC Qwen2.5 unlocked pilot audit v1",
        "passed": not failures,
        "pilot_report_sha256": sha256(args.report),
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(recomputed_go),
        "go_to_locked_confirmation": selected is not None,
        "selected_candidate": selected["candidate"] if selected else None,
        "representation_checks": representation_checks,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report_out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report_out, indent=2, sort_keys=True))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
