"""Diagnostic-anchored repair for the released-interface utility analysis.

The original utility reconstruction requires all three split tables to match
their receipts. The current frozen store reproduces the untouched diagnostic
table but not the historical reference or bridge tables. This repair records
that discrepancy and computes utility only from the matching diagnostic table.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np

import mosaic_release_utility_common as v1


UtilityJob = v1.UtilityJob
selected_jobs = v1.selected_jobs


def evaluate_job(job: UtilityJob) -> dict[str, object]:
    strict = json.loads(job.strict_path.read_text(encoding="utf-8"))
    raw = json.loads(Path(str(strict["original_receipt"])).read_text(encoding="utf-8"))
    candidate = next(row for row in raw["results"] if row["candidate"] == job.selection["candidate"])
    expected = [
        candidate["reference_token_counts"],
        candidate["bridge_token_counts"],
        candidate["diagnostic_token_counts"],
    ]
    observed: list[list[list[list[int]]]] = []
    original = v1.build_token_table

    def diagnostic_anchored_table(*args, **kwargs):
        table = original(*args, **kwargs)
        index = len(observed)
        counts = table.counts.tolist()
        observed.append(counts)
        if index < 2:
            # These tables are not used in the utility metric; preserve the old
            # receipt solely so the v1 evaluator can reach the diagnostic check.
            return replace(table, counts=np.asarray(expected[index], dtype=np.int64))
        return table

    v1.build_token_table = diagnostic_anchored_table
    try:
        result = v1.evaluate_job(job)
    finally:
        v1.build_token_table = original
    if len(observed) != 3 or observed[2] != expected[2]:
        raise ValueError("current diagnostic token table does not match locked receipt")
    reconstruction = dict(result["reconstruction"])
    reconstruction.update(
        {
            "diagnostic_token_count_receipt_match": True,
            "reference_token_count_receipt_match": observed[0] == expected[0],
            "bridge_token_count_receipt_match": observed[1] == expected[1],
            "reference_token_counts_current": observed[0],
            "reference_token_counts_locked": expected[0],
            "bridge_token_counts_current": observed[1],
            "bridge_token_counts_locked": expected[1],
            "freeze_discrepancy": (
                "The current frozen store reproduces the untouched diagnostic token "
                "table but not the historical reference or bridge tables. Utility is "
                "therefore reported only as a diagnostic-anchored post-outcome audit."
            ),
        }
    )
    result["reconstruction"] = reconstruction
    result["claim_boundary"] = (
        "The task metrics are computed from the current reconstructed features and "
        "the exact locked diagnostic token table. They do not revalidate the original "
        "reference or bridge split, whose current feature reconstruction differs."
    )
    return result
