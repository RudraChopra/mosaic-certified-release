"""Compare the sealed P0 policy analysis with its independent exact-risk replay."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PRIMARY = ROOT / "artifacts" / "vera_p0_confirmation_v4.json"
DEFAULT_REPLAY = ROOT / "artifacts" / "vera_p0_confirmation_v4_exact_replay.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_p0_confirmation_v4_reader_agreement.json"
TOLERANCE = 1e-12


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def key(row: dict[str, Any]) -> tuple[str, int, float]:
    return (str(row["dataset"]), int(row["seed"]), float(row["requested_gamma"]))


def close(left: Any, right: Any) -> bool:
    return isinstance(left, (float, int)) and isinstance(right, (float, int)) and abs(float(left) - float(right)) <= TOLERANCE


def compare(primary: dict[str, Any], replay: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if primary.get("preregistration_sha256") != replay.get("preregistration_sha256"):
        findings.append({"kind": "preregistration_hash_mismatch"})

    profiles = {key(row): row for row in primary.get("profiles", [])}
    replay_rows = {key(row): row for row in replay.get("rows", [])}
    if len(profiles) != len(primary.get("profiles", [])):
        findings.append({"kind": "duplicate_primary_profile_key"})
    if len(replay_rows) != len(replay.get("rows", [])):
        findings.append({"kind": "duplicate_replay_key"})
    for setting in sorted(set(profiles) | set(replay_rows)):
        profile = profiles.get(setting)
        independent = replay_rows.get(setting)
        if profile is None or independent is None:
            findings.append({"kind": "missing_profile", "setting": setting})
            continue
        focus = profile.get("focus", {})
        fields = {
            "selected_construction_candidate": (
                profile.get("selected_construction_candidate"),
                independent.get("construction_selected_candidate"),
            ),
            "focus_environment": (focus.get("environment"), independent.get("focus_environment")),
            "focus_source": (focus.get("source"), independent.get("focus_source")),
            "focus_target": (focus.get("target"), independent.get("focus_target")),
            "reference_probability_sha256": (
                profile.get("reference_probability_sha256"),
                independent.get("q_probability_sha256"),
            ),
            "membership_verified": (
                profile.get("membership_verified"),
                independent.get("q_membership_verified"),
            ),
        }
        for field, (left, right) in fields.items():
            if left != right:
                findings.append(
                    {"kind": "profile_mismatch", "setting": setting, "field": field, "primary": left, "replay": right}
                )

    seen_details: set[tuple[str, int, float, int, str]] = set()
    for detail in primary.get("candidate_details", []):
        setting = key(detail)
        detail_key = (*setting, int(detail["total_budget"]), str(detail["candidate"]))
        if detail_key in seen_details:
            findings.append({"kind": "duplicate_candidate_detail", "detail": detail_key})
            continue
        seen_details.add(detail_key)
        independent = replay_rows.get(setting)
        if independent is None:
            findings.append({"kind": "detail_missing_replay_profile", "detail": detail_key})
            continue
        risks = independent.get("candidate_exact_risks", {}).get(str(detail["candidate"]))
        if not isinstance(risks, dict):
            findings.append({"kind": "replay_candidate_missing", "detail": detail_key})
            continue
        comparisons = {
            "q_target": (detail.get("q_target"), risks.get("maximum_target_harm")),
            "q_leakage": (detail.get("q_leakage"), risks.get("maximum_attacker_leakage")),
        }
        for attacker, value in detail.get("registered_attacker_q", {}).items():
            comparisons[f"registered_attacker_q::{attacker}"] = (
                value,
                risks.get("attacker_balanced_leakage", {}).get(attacker),
            )
        for field, (left, right) in comparisons.items():
            if not close(left, right):
                findings.append(
                    {"kind": "exact_risk_mismatch", "detail": detail_key, "field": field, "primary": left, "replay": right}
                )
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary", type=Path, default=DEFAULT_PRIMARY)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError(f"refusing to overwrite agreement audit: {args.output}")
    primary = load_json(args.primary)
    replay = load_json(args.replay)
    findings = compare(primary, replay)
    output = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "primary_path": str(args.primary),
        "replay_path": str(args.replay),
        "passed": not findings,
        "profile_count": len(primary.get("profiles", [])),
        "candidate_detail_count": len(primary.get("candidate_details", [])),
        "findings": findings,
        "scope": "mechanical agreement between independently sealed result readers; it does not establish external-law membership",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if findings:
        raise SystemExit(f"reader-agreement audit failed with {len(findings)} finding(s)")


if __name__ == "__main__":
    main()
