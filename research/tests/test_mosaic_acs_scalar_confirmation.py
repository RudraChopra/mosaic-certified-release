from __future__ import annotations

import math

from run_mosaic_acs_scalar_confirmation import (
    CELL_DELTA,
    FAMILYWISE_DELTA,
    WITNESSES,
    expected_protocol,
    scalar_bounds,
)


def test_scalar_confirmation_family_and_error_allocation_are_fixed() -> None:
    assert len(WITNESSES) == 2
    assert {row["seed"] for row in WITNESSES} == {1401, 1402}
    assert CELL_DELTA == FAMILYWISE_DELTA / 8
    protocol = expected_protocol()
    assert protocol["confirmation_year"] == "2023"
    assert protocol["hypotheses"] == 2


def test_scalar_hoeffding_bounds_cover_fixed_loss_cells() -> None:
    import numpy as np

    channel = np.asarray([[0.9, 0.1], [0.2, 0.8]])
    rows = scalar_bounds(
        tokens=np.asarray([0, 1, 0, 1] * 1000),
        labels=np.asarray([0, 0, 1, 1] * 1000),
        sources=np.asarray([0, 1, 0, 1] * 1000),
        channel=channel,
        decoder=(0, 1),
    )
    assert len(rows) == 4
    for row in rows:
        assert row["hoeffding_lower"] <= row["empirical_expected_error"]
        assert row["empirical_expected_error"] <= row["hoeffding_upper"]
        assert math.isfinite(row["half_width"])
