from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from run_official_eraser_frontier import (  # noqa: E402
    HELDOUT_ATTACKER_CONFIG,
    make_heldout_attacker,
    paired_target_error_arrays,
)


class HeldoutAttackerTests(unittest.TestCase):
    def test_configuration_marks_attacker_as_stress_only(self) -> None:
        self.assertEqual(HELDOUT_ATTACKER_CONFIG["name"], "boosted_tree")
        self.assertFalse(HELDOUT_ATTACKER_CONFIG["formal_guarantee"])
        self.assertIn("never used by certification", HELDOUT_ATTACKER_CONFIG["usage"])

    def test_attacker_is_deterministic_for_locked_seed(self) -> None:
        rng = np.random.default_rng(7)
        features = rng.normal(size=(160, 8))
        labels = (features[:, 0] + 0.5 * features[:, 1] > 0).astype(int)

        first = make_heldout_attacker(13).fit(features, labels).predict(features)
        second = make_heldout_attacker(13).fit(features, labels).predict(features)

        np.testing.assert_array_equal(first, second)

    def test_paired_harm_reconstructs_from_component_errors(self) -> None:
        target = np.asarray([0, 0, 1, 1])
        identity = np.asarray([0, 1, 1, 0])
        edited = np.asarray([1, 0, 1, 0])

        arrays = paired_target_error_arrays(identity, edited, target)

        np.testing.assert_array_equal(arrays["identity"], [0, 1, 0, 1])
        np.testing.assert_array_equal(arrays["edited"], [1, 0, 0, 1])
        np.testing.assert_array_equal(arrays["harm"], [1, -1, 0, 0])


if __name__ == "__main__":
    unittest.main()
