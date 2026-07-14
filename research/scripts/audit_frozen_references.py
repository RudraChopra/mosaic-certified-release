"""Audit internal consistency of the frozen, previously verified references."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "reference_manifest.json"
DEFAULT_REPORT = ROOT / "artifacts" / "reference_verification_report.json"
DEFAULT_BIB = ROOT / "maintrack" / "references_verified.bib"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--bib", type=Path, default=DEFAULT_BIB)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = load_json(args.manifest)
    report = load_json(args.report)
    references = manifest.get("references", [])
    if not isinstance(references, list):
        raise RuntimeError("manifest references are not a list")
    manifest_keys = [str(record.get("key", "")) for record in references]
    report_records = report.get("records", [])
    report_keys = [
        str(record.get("key", ""))
        for record in report_records
        if isinstance(record, dict)
    ]
    bib_text = args.bib.read_text(encoding="utf-8")
    bib_keys = re.findall(r"@\w+\{([^,]+),", bib_text)
    required_categories = set(map(str, manifest.get("required_categories", [])))
    categories = {
        str(record.get("category", ""))
        for record in references
        if isinstance(record, dict)
    }
    minimum = int(manifest.get("minimum_verified_references", 40))
    failures: list[str] = []
    if report.get("passed") is not True or report.get("failures") != []:
        failures.append("online verification report did not pass cleanly")
    if len(manifest_keys) < minimum:
        failures.append("manifest is below its minimum reference count")
    if len(set(manifest_keys)) != len(manifest_keys):
        failures.append("manifest contains duplicate or empty keys")
    if set(manifest_keys) != set(report_keys):
        failures.append("manifest and verification-report keys differ")
    if set(manifest_keys) != set(bib_keys):
        failures.append("manifest and bibliography keys differ")
    if not required_categories.issubset(categories):
        failures.append("manifest is missing a required literature category")
    if int(report.get("verified_reference_count", -1)) != len(manifest_keys):
        failures.append("verification report count is inconsistent")
    output = {
        "passed": not failures,
        "reference_count": len(manifest_keys),
        "required_categories": sorted(required_categories),
        "failures": failures,
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
