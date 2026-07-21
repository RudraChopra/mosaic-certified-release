#!/usr/bin/env python3
"""Diagnose whether CivilComments abstention is structural or representation-dependent."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = (
    REPOSITORY
    / "research"
    / "artifacts"
    / "mosaic_civilcomments_abstention_diagnosis_v1.json"
)
RECEIPT_ROOTS = (
    REPOSITORY / "research" / "artifacts" / "mosaic_bridge_strict_v2_receipts_v1",
    REPOSITORY
    / "research"
    / "artifacts"
    / "mosaic_bridge_corrected_confirmation_strict_v2_v1",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def is_nonconstant(channel: list[list[float]]) -> bool:
    first = channel[0]
    return any(
        any(abs(float(left) - float(right)) > 1e-8 for left, right in zip(row, first))
        for row in channel[1:]
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")

    jobs: list[dict[str, object]] = []
    for root in RECEIPT_ROOTS:
        for path in sorted(root.glob("CivilComments-WILDS__seed*.json")):
            receipt = json.loads(path.read_text(encoding="utf-8"))
            retained: list[float] = []
            errors: list[float] = []
            missing: list[object] = []
            nonconstant = False
            estimable = True
            for candidate in receipt["results"]:
                retained.extend(candidate["bridge_membership"]["retained_masses"])
                release = candidate["release_l2"]
                errors.append(float(release["certified_worst_conditional_error_upper"]))
                diagnostic = release["diagnostic"]
                estimable = estimable and bool(diagnostic["estimable"])
                missing.extend(diagnostic["missing_strata"])
                nonconstant = nonconstant or is_nonconstant(release["release_channel"])
            jobs.append(
                {
                    "receipt": str(path.relative_to(REPOSITORY)),
                    "receipt_sha256": sha256(path),
                    "minimum_retained_mass": min(retained),
                    "maximum_retained_mass": max(retained),
                    "minimum_certified_error": min(errors),
                    "all_diagnostics_estimable": estimable,
                    "missing_strata": missing,
                    "any_nonconstant_release": nonconstant,
                    "primary_decision": receipt["primary_selection"]["decision"],
                }
            )

    summary = {
        "jobs": len(jobs),
        "jobs_with_missing_strata": sum(bool(job["missing_strata"]) for job in jobs),
        "jobs_with_nonconstant_release": sum(
            bool(job["any_nonconstant_release"]) for job in jobs
        ),
        "primary_deployments": sum(job["primary_decision"] == "deploy" for job in jobs),
        "all_diagnostics_estimable": all(
            bool(job["all_diagnostics_estimable"]) for job in jobs
        ),
        "minimum_retained_mass": min(float(job["minimum_retained_mass"]) for job in jobs),
        "maximum_retained_mass": max(float(job["maximum_retained_mass"]) for job in jobs),
        "minimum_certified_error": min(
            float(job["minimum_certified_error"]) for job in jobs
        ),
    }
    support_failure = summary["jobs_with_missing_strata"] > 0
    representation_failure = (
        not support_failure
        and summary["jobs_with_nonconstant_release"] == 0
        and summary["minimum_certified_error"] >= 0.5
    )
    report = {
        "name": "MOSAIC CivilComments abstention diagnosis v1",
        "question": (
            "Did the registered CivilComments jobs abstain because a required "
            "source-label stratum was missing, or because no nonconstant interface "
            "satisfied the joint privacy-utility contract?"
        ),
        "diagnosis": (
            "joint_privacy_utility_feasibility_not_missing_support"
            if representation_failure
            else "missing_support_or_inconclusive"
        ),
        "qwen_pilot_warranted": representation_failure,
        "summary": summary,
        "jobs": jobs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"output": str(args.output), **summary}, indent=2))
    if not representation_failure:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
