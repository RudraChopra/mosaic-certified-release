"""Outcome-blind consistency audit for the three VERA scientific sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


CONTROLLED_MACROS = {
    "ControlledShiftAbstractResult",
    "ControlledPrimaryResult",
    "ControlledSafetyResult",
    "ControlledRetentionResult",
    "ControlledAllocationResult",
    "ControlledEvidenceResult",
    "ControlledGaitResult",
    "ControlledHeldoutResult",
    "ControlledNegativeResults",
    "ControlledMainResultTable",
    "ControlledMainResultFigure",
}
VENUES = ("AAAI-27", "ICLR-2027", "NeurIPS-2027")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def citation_keys(text: str) -> set[str]:
    output: set[str] = set()
    for match in re.finditer(r"\\cite\w*\{([^{}]+)\}", text):
        output.update(key.strip() for key in match.group(1).split(","))
    return output


def bibliography_keys(text: str) -> set[str]:
    return set(re.findall(r"@\w+\s*\{\s*([^,\s]+)\s*,", text))


def pair_present(text: str, numerator: int, denominator: int) -> bool:
    return bool(
        re.search(
            rf"\b{numerator}\s*(?:/|\s+of\s+){denominator}\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def require_tokens(
    text: str, tokens: list[tuple[str, str]], venue: str, failures: list[str]
) -> None:
    for label, token in tokens:
        if token not in text:
            failures.append(f"{venue}: missing {label}: {token}")


def audit_source(
    venue: str, path: Path, bibliography: set[str], final: bool
) -> dict[str, Any]:
    failures: list[str] = []
    text = path.read_text(encoding="utf-8")
    provided = set(
        re.findall(r"\\providecommand\{\\([A-Za-z]+)\}", text)
    ) & CONTROLLED_MACROS
    if provided != CONTROLLED_MACROS:
        failures.append(
            f"{venue}: controlled macro set differs: {sorted(provided)}"
        )
    for name in CONTROLLED_MACROS:
        occurrences = len(re.findall(rf"\\{re.escape(name)}\b", text))
        if occurrences < 2:
            failures.append(f"{venue}: controlled macro is not consumed: {name}")
    if final and re.search(r"\b(?:pending|in progress)\b", text, re.IGNORECASE):
        failures.append(f"{venue}: final source retains pending result text")

    require_tokens(
        text,
        [
            ("fresh seed range", "45--108"),
            ("method-run count", "1,280"),
            ("candidate-evaluation count", "3,072"),
            ("candidate count", "12"),
            ("primary evidence budget", "4,000"),
            ("minimum evidence floor", r"15\%"),
            ("Bios target threshold", "0.40"),
            ("Bios leakage threshold", "0.70"),
            ("CivilComments target threshold", "0.075"),
            ("CivilComments leakage threshold", "0.80"),
            ("Gait target threshold", "0.20"),
            ("Gait leakage threshold", "0.55"),
            ("Waterbirds target threshold", "0.10"),
            ("Waterbirds leakage threshold", "0.90"),
            ("primary gamma", "1.1"),
            ("secondary gamma 1.25", "1.25"),
            ("secondary gamma 1.5", "1.5"),
            ("budget 1000", "1000"),
            ("budget 2000", "2000"),
            ("budget 8000", "8000"),
            ("cap 8 disclosure", "cap 8"),
            ("cap 4 disclosure", "cap 4"),
            ("INLP", "INLP"),
            ("R-LACE", "R-LACE"),
            ("LEACE", "LEACE"),
            ("TaCo", "TaCo"),
            ("MANCE++", "MANCE++"),
            ("Camelyon17 boundary", "Camelyon17"),
            ("Learn Then Test", "Learn Then Test"),
            ("finite-reference scope", "finite-reference"),
            ("registered attacker scope", "registered"),
            ("AI disclosure", "OpenAI Codex"),
        ],
        venue,
        failures,
    )
    for value in (1000, 2000, 8000):
        if str(value) not in text:
            failures.append(f"{venue}: secondary budget absent: {value}")
    if "RLACE" in text:
        failures.append(f"{venue}: legacy RLACE token appears")
    if "200 official-method runs" in text:
        failures.append(f"{venue}: stale study count or seed block appears")
    if "We make four contributions" not in text:
        failures.append(f"{venue}: four-contribution declaration absent")
    for ordinal in ("First", "Second", "Third", "Fourth"):
        if not re.search(rf"\b{ordinal},", text):
            failures.append(f"{venue}: contribution ordinal absent: {ordinal}")
    for numerator, denominator in ((35, 128), (1, 128), (52, 102), (5, 32)):
        if not pair_present(text, numerator, denominator):
            failures.append(
                f"{venue}: historical pair absent: {numerator}/{denominator}"
            )
    observed_pairs = {
        (int(numerator), int(denominator))
        for numerator, denominator in re.findall(
            r"\b(\d+)\s*(?:/|\s+of\s+)(128|102|32)\b",
            text,
            flags=re.IGNORECASE,
        )
    }
    allowed_pairs = {(35, 128), (1, 128), (52, 102), (5, 32)}
    unexpected_pairs = sorted(observed_pairs - allowed_pairs)
    if unexpected_pairs:
        failures.append(
            f"{venue}: conflicting historical pair appears: {unexpected_pairs}"
        )
    if not (
        re.search(r"GaitPDB.{0,120}(?:failed|missed|did not reach)", text, re.DOTALL)
        or re.search(r"(?:failed|missed|did not reach).{0,120}GaitPDB", text, re.DOTALL)
    ):
        failures.append(f"{venue}: prior GaitPDB composite miss absent")
    if not re.search(
        r"support.{0,180}(?:not evidence|not clinical|does not claim)",
        text,
        re.IGNORECASE | re.DOTALL,
    ):
        failures.append(f"{venue}: support-boundary non-harm statement absent")
    if not (
        re.search(
            r"finite-family testing.{0,160}(?:follows|foundation|not claim|not VERA)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        or re.search(
            r"Learn Then Test.{0,120}(?:supplies|foundation)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
    ):
        failures.append(f"{venue}: inherited finite-family mechanism is unclear")
    if text.count("Learn Then Test") < 2:
        failures.append(
            f"{venue}: Learn Then Test must be positioned in both overview and related work"
        )
    if not re.search(r"independent.{0,80}cap-?8 replay", text, re.IGNORECASE | re.DOTALL):
        failures.append(f"{venue}: independent cap-8 replay disclosure absent")

    citations = citation_keys(text)
    missing_citations = sorted(citations - bibliography)
    if missing_citations:
        failures.append(f"{venue}: unresolved citations: {missing_citations}")
    if len(citations) < 40:
        failures.append(f"{venue}: fewer than 40 distinct citations: {len(citations)}")
    return {
        "venue": venue,
        "path": str(path),
        "sha256": sha256(path),
        "controlled_macros": sorted(provided),
        "distinct_citations": len(citations),
        "failures": failures,
    }


def audit(args: argparse.Namespace) -> dict[str, Any]:
    bibliography_text = args.bibliography.read_text(encoding="utf-8")
    bibliography = bibliography_keys(bibliography_text)
    sources = (args.aaai, args.iclr, args.neurips)
    reports = [
        audit_source(venue, path, bibliography, args.final)
        for venue, path in zip(VENUES, sources)
    ]
    failures = [failure for report in reports for failure in report["failures"]]
    theory_text = args.theory.read_text(encoding="utf-8")
    required_labels = {
        "lem:cvar-identity",
        "cor:exact-discrete",
        "thm:iut",
        "thm:shift-envelope",
        "cor:common-radius",
        "thm:sample-complexity-upper",
        "cor:evidence-allocation",
        "thm:additive-allocation",
        "thm:sample-complexity-lower",
        "thm:unsupported",
    }
    observed_labels = set(re.findall(r"\\label\{([^{}]+)\}", theory_text))
    if not required_labels <= observed_labels:
        failures.append(
            f"theory: missing labels: {sorted(required_labels - observed_labels)}"
        )
    return {
        "schema_version": 1,
        "name": "VERA three-venue scientific-source consistency audit",
        "mode": "final" if args.final else "pre-outcome",
        "passed": not failures,
        "failures": failures,
        "sources": reports,
        "bibliography_sha256": sha256(args.bibliography),
        "bibliography_entry_count": len(bibliography),
        "theory_sha256": sha256(args.theory),
        "theory_required_labels": sorted(required_labels),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aaai", type=Path, required=True)
    parser.add_argument("--iclr", type=Path, required=True)
    parser.add_argument("--neurips", type=Path, required=True)
    parser.add_argument("--bibliography", type=Path, required=True)
    parser.add_argument("--theory", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--final", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "failure_count": len(report["failures"]),
                "mode": report["mode"],
                "source_sha256": {
                    item["venue"]: item["sha256"] for item in report["sources"]
                },
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
