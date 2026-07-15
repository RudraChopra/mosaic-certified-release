from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_controlled_shift_confirmatory import (  # noqa: E402
    DATASETS,
    FRESH_SEEDS,
    holm,
    primary_inference,
)


class ControlledShiftConfirmatoryTests(unittest.TestCase):
    def test_holm_adjustment_is_monotone(self) -> None:
        adjusted = holm({"a": 0.001, "b": 0.02, "c": 0.5})
        self.assertLessEqual(adjusted["a"], adjusted["b"])
        self.assertLessEqual(adjusted["b"], adjusted["c"])

    def test_synthetic_confirmatory_success_uses_seed_clusters(self) -> None:
        rows = []
        for seed in FRESH_SEEDS:
            for dataset_index, dataset in enumerate(DATASETS):
                point_violation = seed < 77 and dataset_index == 0
                vector_safe = dataset_index < 2
                common_safe = dataset_index == 0
                shared = {
                    "seed": seed,
                    "dataset": dataset,
                    "certified_common_radius": 1.05,
                    "limiting_coordinates": ["source::0"],
                    "heldout_stress_violation": False,
                }
                rows.extend(
                    [
                        {
                            **shared,
                            "rule": "external_oracle",
                            "deployed": True,
                            "safe": True,
                            "violation": False,
                        },
                        {
                            **shared,
                            "rule": "validation_point_selection",
                            "deployed": True,
                            "safe": not point_violation,
                            "violation": point_violation,
                        },
                        {
                            **shared,
                            "rule": "vera_vector_envelope",
                            "deployed": vector_safe,
                            "safe": vector_safe,
                            "violation": False,
                        },
                        {
                            **shared,
                            "rule": "vera_common_radius",
                            "deployed": common_safe,
                            "safe": common_safe,
                            "violation": False,
                        },
                    ]
                )

        inference = primary_inference(rows)

        self.assertTrue(inference["paired_reduction"]["passed"])
        self.assertTrue(inference["safety"]["passed"])
        self.assertTrue(inference["usefulness"]["passed"])
        self.assertTrue(inference["vector_advantage"]["passed"])
        self.assertTrue(inference["overall_confirmatory_success"])


if __name__ == "__main__":
    unittest.main()
