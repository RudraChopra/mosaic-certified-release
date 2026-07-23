#!/usr/bin/env python3
"""Independently audit the locked ACS 2023 scalar confirmation artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "research/artifacts/mosaic_acs_scalar_confirmation_v1.json"
LOCK = ROOT / "research/mosaic/prereg_mosaic_acs_scalar_confirmation_v1.json"
AMENDMENT = ROOT / (
    "research/mosaic/"
    "prereg_mosaic_acs_scalar_confirmation_transport_v1.json"
)
OUTPUT = (
    ROOT
    / "research/artifacts/mosaic_acs_scalar_confirmation_audit_v1.json"
)
THRESHOLD = 0.40
FAMILYWISE_DELTA = 0.05
WITNESSES = (
    ("FL", "public_coverage", 1401, "TaCo::components_removed=1"),
    ("FL", "public_coverage", 1402, "R-LACE::rank=4"),
)
CELL_DELTA = FAMILYWISE_DELTA / (len(WITNESSES) * 4)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def close(left: float, right: float, tolerance: float = 2e-12) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=tolerance)


def audit(report_path: Path) -> dict[str, Any]:
    report = load(report_path)
    lock = load(LOCK)
    amendment = load(AMENDMENT)
    failures: list[str] = []
    checks = 0

    def require(condition: bool, message: str) -> None:
        nonlocal checks
        checks += 1
        if not condition:
            failures.append(message)

    require(report["lock_sha256"] == sha256(LOCK), "report lock hash differs")
    require(
        amendment["original_lock_sha256"] == sha256(LOCK),
        "transport amendment points to another lock",
    )
    require(
        amendment["failure"]["rows_read"] == 0
        and amendment["failure"]["outcomes_read"] is False,
        "transport amendment was not header-only",
    )
    require(
        lock["protocol"]["cell_delta"] == CELL_DELTA,
        "locked cell allocation differs",
    )
    require(
        lock["protocol"]["utility_threshold"] == THRESHOLD,
        "locked utility threshold differs",
    )
    expected_witnesses = [
        {
            "target_state": state,
            "task": task,
            "seed": seed,
            "candidate": candidate,
        }
        for state, task, seed, candidate in WITNESSES
    ]
    require(
        lock["protocol"]["witnesses"] == expected_witnesses,
        "locked witnesses differ",
    )
    require(len(report["rows"]) == len(WITNESSES), "report row count differs")

    confirmed = 0
    empirical = 0
    paired_abstentions = 0
    headline = None
    observed_witnesses = []
    for row in report["rows"]:
        observed_witnesses.append(
            {
                key: row[key]
                for key in ("target_state", "task", "seed", "candidate")
            }
        )
        require(row["direct_decision_2018"] == "deploy", "direct did not deploy")
        require(row["mosaic_decision_2018"] == "abstain", "MOSAIC did not abstain")
        require(
            row["reference_reconstruction_match"] is True,
            "reference reconstruction differs",
        )
        paired_abstentions += row["mosaic_decision_2018"] == "abstain"
        stratum_empirical = []
        stratum_lower = []
        total_rows = 0
        for cell in row["strata"]:
            n = int(cell["rows"])
            total_rows += n
            half_width = math.sqrt(math.log(1.0 / CELL_DELTA) / (2.0 * n))
            expected_lower = max(
                0.0, float(cell["empirical_expected_error"]) - half_width
            )
            expected_upper = min(
                1.0, float(cell["empirical_expected_error"]) + half_width
            )
            require(close(cell["half_width"], half_width), "half-width differs")
            require(
                close(cell["hoeffding_lower"], expected_lower),
                "Hoeffding lower bound differs",
            )
            require(
                close(cell["hoeffding_upper"], expected_upper),
                "Hoeffding upper bound differs",
            )
            stratum_empirical.append(float(cell["empirical_expected_error"]))
            stratum_lower.append(float(cell["hoeffding_lower"]))
        worst_empirical = max(stratum_empirical)
        worst_lower = max(stratum_lower)
        require(
            total_rows == row["confirmation_rows"],
            "confirmation row total differs",
        )
        require(
            close(row["worst_conditional_error_empirical"], worst_empirical),
            "reported worst empirical error differs",
        )
        require(
            close(
                row["worst_conditional_error_familywise_lower"],
                worst_lower,
            ),
            "reported worst lower bound differs",
        )
        empirical_flag = worst_empirical > THRESHOLD
        confirmed_flag = worst_lower > THRESHOLD
        require(
            row["utility_contract_violation_empirical"] == empirical_flag,
            "empirical violation flag differs",
        )
        require(
            row["utility_contract_violation_confirmed"] == confirmed_flag,
            "confirmed violation flag differs",
        )
        empirical += empirical_flag
        confirmed += confirmed_flag
        if confirmed_flag:
            headline = {
                "target_state": row["target_state"],
                "task": row["task"],
                "seed": row["seed"],
                "candidate": row["candidate"],
                "direct_2018": "deploy",
                "mosaic_2018": "abstain",
                "future_year": 2023,
                "worst_error_empirical": worst_empirical,
                "familywise_lower": worst_lower,
                "utility_threshold": THRESHOLD,
            }

    require(observed_witnesses == expected_witnesses, "report witnesses differ")
    expected_summary = {
        "registered_interfaces": len(WITNESSES),
        "empirical_2023_utility_violations": empirical,
        "familywise_confirmed_2023_utility_violations": confirmed,
        "paired_mosaic_2018_abstentions": paired_abstentions,
    }
    require(report["summary"] == expected_summary, "summary differs")
    require(empirical == 2, "both repeated failures did not persist empirically")
    require(confirmed >= 1, "no natural failure is familywise confirmed")
    require(headline is not None, "confirmed headline witness is absent")

    return {
        "name": "MOSAIC ACS 2023 scalar confirmation independent audit v1",
        "pass": not failures,
        "checks": checks,
        "failures": failures,
        "report_sha256": sha256(report_path),
        "lock_sha256": sha256(LOCK),
        "transport_amendment_sha256": sha256(AMENDMENT),
        "familywise_delta": FAMILYWISE_DELTA,
        "headline_witness": headline,
        "summary": expected_summary,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    payload = audit(args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
