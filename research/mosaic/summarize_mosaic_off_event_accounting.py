#!/usr/bin/env python3
"""Report how every observed false acceptance relates to the confidence event.

The synthetic studies know their generating population, so they can record the
simultaneous confidence event for each replicate.  Real benchmark diagnostics
do not reveal that event and are deliberately reported as observational only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


FORMAL_CERTIFICATE_METHODS = {
    "synthetic_confirmation": {
        "deterministic_mosaic",
        "finite_ltt",
        "heldout_fixed_channel",
        "mosaic",
    },
    "transform_exact_confirmation": {"capacity_transfer", "transform_exact"},
}


def load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def summarize_cells(report: dict[str, Any], *, report_name: str) -> list[dict[str, Any]]:
    cells = report.get("cells")
    if not isinstance(cells, list) or not cells:
        raise ValueError(f"{report_name} has no nonempty cell list")
    rows: list[dict[str, Any]] = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise ValueError(f"{report_name} has a malformed cell")
        required = (
            "scenario",
            "method",
            "replicates",
            "confidence_event_count",
            "false_acceptances",
            "failures_on_confidence_event",
        )
        if any(key not in cell for key in required):
            raise ValueError(f"{report_name} cell lacks event accounting")
        replicates = int(cell["replicates"])
        event_count = int(cell["confidence_event_count"])
        false_acceptances = int(cell["false_acceptances"])
        on_event = int(cell["failures_on_confidence_event"])
        if not (0 <= event_count <= replicates):
            raise ValueError(f"{report_name} has an invalid confidence-event count")
        if not (0 <= on_event <= false_acceptances <= replicates):
            raise ValueError(f"{report_name} has inconsistent failure accounting")
        rows.append(
            {
                "study": report_name,
                "scenario": str(cell["scenario"]),
                "method": str(cell["method"]),
                "sample_size_per_stratum": int(cell["sample_size_per_stratum"]),
                "replicates": replicates,
                "confidence_event_count": event_count,
                "confidence_event_failures": replicates - event_count,
                "false_acceptances": false_acceptances,
                "false_acceptances_on_event": on_event,
                "false_acceptances_off_event": false_acceptances - on_event,
            }
        )
    return rows


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "cells": len(rows),
        "replicates": sum(int(row["replicates"]) for row in rows),
        "confidence_event_failures": sum(
            int(row["confidence_event_failures"]) for row in rows
        ),
        "false_acceptances": sum(int(row["false_acceptances"]) for row in rows),
        "false_acceptances_on_event": sum(
            int(row["false_acceptances_on_event"]) for row in rows
        ),
        "false_acceptances_off_event": sum(
            int(row["false_acceptances_off_event"]) for row in rows
        ),
    }


def certificate_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row["method"] in FORMAL_CERTIFICATE_METHODS[str(row["study"])]
    ]


def atomic_dump(payload: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", dir=output.parent, delete=False) as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(output)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthetic", required=True, type=Path)
    parser.add_argument("--transform-exact", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")

    synthetic = summarize_cells(load(args.synthetic), report_name="synthetic_confirmation")
    exact = summarize_cells(
        load(args.transform_exact), report_name="transform_exact_confirmation"
    )
    rows = synthetic + exact
    certificates = certificate_rows(rows)
    payload = {
        "name": "MOSAIC synthetic confidence-event and off-event accounting",
        "rows": rows,
        "by_study": {
            "synthetic_confirmation": aggregate(synthetic),
            "transform_exact_confirmation": aggregate(exact),
            "all_methods": aggregate(rows),
            "formal_certificate_methods": aggregate(certificates),
        },
        "real_study_scope": (
            "The real benchmark diagnostic folds reveal neither the population law nor "
            "the simultaneous confidence event. Their observed violations are therefore "
            "not partitioned into on-event and off-event counts. They remain descriptive "
            "diagnostics rather than empirical coverage estimates."
        ),
        "interpretation": (
            "A false acceptance on the confidence event would contradict the stated "
            "certificate. A false acceptance off that event is counted in the observed "
            "false-acceptance total but is not a failure of the conditional theorem."
        ),
        "method_scope": (
            "The formal-certificate aggregate includes only rules with a stated "
            "simultaneous-event guarantee. Plug-in and always-deploy comparators are "
            "retained in the row-level report, but cannot have on-event accounting."
        ),
    }
    atomic_dump(payload, args.output)
    print(json.dumps(payload["by_study"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
