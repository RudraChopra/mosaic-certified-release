"""Fail-closed audit of human-confirmed ISEF eligibility and student ownership."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "private" / "isef_compliance_registry.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_isef_readiness_audit.json"
LEDGER = ROOT / "isef" / "AI_ASSISTANCE_LEDGER.md"
COMPLIANCE = ROOT / "isef" / "ISEF_2027_COMPLIANCE_GATE.md"

BOOLEAN_GATES = (
    "contra_costa_school_attendance_confirmed",
    "adult_sponsor_engaged",
    "local_src_contacted",
    "local_src_written_eligibility_guidance_received",
    "public_preexisting_data_exemption_confirmed_by_src",
    "work_already_performed_disclosed_to_src",
    "required_2027_forms_identified",
    "required_approvals_complete_without_backdating",
    "student_support_disclosure_complete",
    "ai_assistance_ledger_reviewed_with_sponsor",
    "student_independently_reran_core_pipeline",
    "student_independently_verified_theory",
    "student_can_defend_code_and_statistics",
    "student_authored_research_plan_without_generative_ai",
    "student_authored_abstract_without_generative_ai",
    "student_authored_poster_without_generative_ai",
    "student_built_and_verified_citations_without_generative_ai",
)


def load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-fail", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    registry = load_json(args.registry)
    gate_status = {key: registry.get(key) is True for key in BOOLEAN_GATES}
    start_text = registry.get("official_project_start_date")
    start_valid = False
    if isinstance(start_text, str):
        try:
            start = date.fromisoformat(start_text)
            start_valid = date(2026, 1, 1) <= start <= date(2027, 5, 31)
        except ValueError:
            start_valid = False
    src_reference_present = bool(
        str(registry.get("src_determination_reference") or "").strip()
    )
    grade_level = registry.get("student_grade_level")
    grade_valid = isinstance(grade_level, int) and 7 <= grade_level <= 12
    technical = {
        "compliance_gate_present": COMPLIANCE.is_file(),
        "ai_assistance_ledger_present": LEDGER.is_file(),
        "official_start_date_in_2027_window": start_valid,
        "src_determination_reference_present": src_reference_present,
        "student_grade_level_eligible_for_cccsef": grade_valid,
    }
    failures = [key for key, value in {**technical, **gate_status}.items() if not value]
    report = {
        "name": "VERA ISEF 2027 readiness audit",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "passed": not failures,
        "registry_present": bool(registry),
        "technical": technical,
        "human_and_student_gates": gate_status,
        "failures": failures,
        "warning": (
            "This automated audit cannot determine independent student work or "
            "fair eligibility; it only checks recorded human confirmations."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] or args.no_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
