from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "mosaic"
sys.path.insert(0, str(SCRIPTS))

from run_mosaic_synthetic_pilot import (  # noqa: E402
    Selection,
    direct_one_sided_confidence_event,
    witness_scenario,
)


def _selection() -> Selection:
    return Selection(
        channel=np.asarray(
            [[1.0, 0.0], [1.0, 0.0], [0.0, 1.0]], dtype=np.float64
        ),
        decoder=(0, 1),
        criterion=0.0,
    )


def test_direct_event_holds_at_the_population_table() -> None:
    scenario = witness_scenario(
        privacy_threshold=0.35,
        utility_threshold=0.45,
        contamination=0.10,
    )
    assert direct_one_sided_confidence_event(
        scenario.population,
        scenario,
        _selection(),
        privacy_radius=0.0,
        utility_radius=0.0,
    )


def test_direct_event_detects_an_underestimated_selected_loss() -> None:
    scenario = witness_scenario(
        privacy_threshold=0.35,
        utility_threshold=0.45,
        contamination=0.10,
    )
    empirical = scenario.population.copy()
    empirical[0, 0, 0] += empirical[0, 0, 2]
    empirical[0, 0, 2] = 0.0
    assert not direct_one_sided_confidence_event(
        empirical,
        scenario,
        _selection(),
        privacy_radius=0.0,
        utility_radius=0.0,
    )
