from __future__ import annotations

import json
import tempfile
from pathlib import Path

from analyze_native_probe_diagnostic import (
    CANDIDATE_COUNTS,
    DATASETS,
    METHODS,
    SEEDS,
    analyze,
    expected_name,
)


def native(method: str) -> dict[str, object]:
    if method in {"inlp", "taco"}:
        return {
            "status": "available",
            "external_balanced_accuracy": 0.60,
        }
    if method == "mance":
        return {"status": "available", "external_accuracy": 0.60}
    if method == "leace":
        return {"status": "NA"}
    return {"status": "available", "reported_upstream_score": 0.60}


def main() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        for dataset in DATASETS:
            for method in METHODS:
                for seed in SEEDS:
                    records = [
                        {
                            "candidate_key": f"{method}::{index}",
                            "method_native": native(method),
                            "fresh_registered_attackers": {
                                "linear": {
                                    "external_accuracy": 0.70,
                                    "external_balanced_accuracy": 0.70,
                                }
                            },
                        }
                        for index in range(CANDIDATE_COUNTS[method])
                    ]
                    value = {
                        "dataset": dataset,
                        "method": method,
                        "seed": seed,
                        "formal_guarantee": False,
                        "cross_method_native_probe_equivalence_claimed": False,
                        "records": records,
                    }
                    (root / expected_name(dataset, method, seed)).write_text(
                        json.dumps(value), encoding="utf-8"
                    )
        report = analyze(root)
        assert report["receipt_count"] == 320
        assert report["candidate_row_count"] == 768
        assert len(report["seed_cluster_summaries"]) == 20
        print("PASS complete native-probe diagnostic fixture")
        missing = root / expected_name("Waterbirds", "inlp", 45)
        missing.unlink()
        try:
            analyze(root)
        except RuntimeError:
            print("PASS rejects incomplete native-probe receipt set")
        else:
            raise AssertionError("incomplete native-probe receipt set passed")


if __name__ == "__main__":
    main()
