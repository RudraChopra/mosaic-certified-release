from __future__ import annotations

import pytest

from build_mosaic_bridge_manifest import exact_interval, one_sided_upper
from run_mosaic_bridge_frontier import expected_protocol


def test_zero_failures_among_twenty_has_exact_one_sided_upper_bound() -> None:
    expected = 1.0 - 0.05 ** (1.0 / 20.0)
    assert one_sided_upper(0, 20) == pytest.approx(expected)


def test_exact_interval_handles_boundaries_and_empty_sample() -> None:
    assert exact_interval(0, 0) is None
    zero = exact_interval(0, 20)
    all_success = exact_interval(20, 20)
    assert zero is not None and zero[0] == 0.0 and 0.0 < zero[1] < 0.2
    assert all_success is not None and 0.8 < all_success[0] < 1.0
    assert all_success[1] == 1.0


def test_bridge_protocol_registers_stronger_thresholds_and_l4() -> None:
    protocol = expected_protocol()
    assert protocol["primary_utility_threshold"] == 0.40
    assert protocol["utility_thresholds"] == [0.30, 0.35, 0.40, 0.45, 0.49]
    assert protocol["secondary_released_token_count"] == 4
    assert protocol["per_candidate_table_delta"] * 26 == pytest.approx(0.05)
