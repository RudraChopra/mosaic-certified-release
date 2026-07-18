from __future__ import annotations

from run_mosaic_synthetic_pilot import witness_scenario
from run_mosaic_transform_exact_pilot import METHODS, aggregate, run_refinement_replicate


def test_refinement_replicate_is_complete_and_replayable() -> None:
    scenario = witness_scenario(
        privacy_threshold=0.35,
        utility_threshold=0.45,
        contamination=0.10,
    )
    results = run_refinement_replicate((91827, 250, scenario, 0.05))
    assert tuple(result.method for result in results) == METHODS
    assert all(result.seed == 91827 for result in results)
    assert all(len(result.release_channel) == 3 for result in results)
    assert all(len(result.empirical_table) == 2 for result in results)
    assert results[1].certified_worst_conditional_error <= (
        results[0].certified_worst_conditional_error + 2e-7
    )
    cells = aggregate(results)
    assert len(cells) == 2
    assert all(cell["replicates"] == 1 for cell in cells)
