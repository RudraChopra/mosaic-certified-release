from __future__ import annotations

from summarize_mosaic_off_event_accounting import aggregate, certificate_rows, summarize_cells


def test_event_accounting_separates_on_and_off_event_false_acceptances() -> None:
    rows = summarize_cells(
        {
            "cells": [
                {
                    "scenario": "s",
                    "method": "m",
                    "sample_size_per_stratum": 8,
                    "replicates": 10,
                    "confidence_event_count": 9,
                    "false_acceptances": 3,
                    "failures_on_confidence_event": 1,
                }
            ]
        },
        report_name="fixture",
    )
    assert rows[0]["confidence_event_failures"] == 1
    assert rows[0]["false_acceptances_off_event"] == 2
    summary = aggregate(rows)
    assert summary["false_acceptances_on_event"] == 1
    assert summary["false_acceptances_off_event"] == 2


def test_event_accounting_rejects_inconsistent_counts() -> None:
    report = {
        "cells": [
            {
                "scenario": "s",
                "method": "m",
                "sample_size_per_stratum": 8,
                "replicates": 10,
                "confidence_event_count": 11,
                "false_acceptances": 0,
                "failures_on_confidence_event": 0,
            }
        ]
    }
    try:
        summarize_cells(report, report_name="fixture")
    except ValueError as error:
        assert "confidence-event" in str(error)
    else:
        raise AssertionError("inconsistent counts must fail")


def test_formal_certificate_filter_excludes_noncertifying_comparators() -> None:
    rows = [
        {"study": "synthetic_confirmation", "method": "mosaic"},
        {"study": "synthetic_confirmation", "method": "plugin_continuum"},
    ]
    assert certificate_rows(rows) == [rows[0]]
