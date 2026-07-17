from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from replay_vera_p0_exact_risks import (  # noqa: E402
    choose_focus,
    exact_risks,
    make_q,
)


def test_independent_replay_reconstructs_a_normalized_supported_q_law() -> None:
    construction = {
        "harm": np.asarray([0, 0, 0, 1, 0, 0, 0, 0], dtype=np.int8),
        "source": np.asarray([0, 0, 1, 1, 0, 0, 1, 1], dtype=np.int8),
        "environment": np.asarray([0, 0, 0, 0, 1, 1, 1, 1], dtype=np.int8),
        "target": np.asarray([0, 1, 0, 1, 0, 1, 0, 1], dtype=np.int8),
        "attacker::linear": np.asarray([0, 0, 1, 1, 0, 0, 1, 1], dtype=np.int8),
    }
    focus = choose_focus(
        construction,
        construction,
        target_threshold=0.25,
        leakage_threshold=0.75,
        gamma=1.1,
    )
    q = make_q(construction, focus[:3], 1.1)
    risks = exact_risks(construction, q, ("linear",))

    assert np.isclose(q.sum(), 1.0)
    assert np.max(q * len(q)) <= 1.1 + 1e-12
    assert risks["maximum_target_harm"] >= 0.0
    assert "linear" in risks["attacker_balanced_leakage"]
