from __future__ import annotations

import numpy as np
import pytest

from mosaic_channel import population_balanced_attacker_accuracy
from mosaic_release import (
    PersistentReleaseMechanism,
    independent_repetition_channel,
)


def example_channel() -> np.ndarray:
    return np.asarray([[0.8, 0.2], [0.35, 0.65]], dtype=np.float64)


def test_persistent_release_returns_one_draw_on_every_access() -> None:
    mechanism = PersistentReleaseMechanism(
        example_channel(), rng=np.random.default_rng(2027)
    )
    first = mechanism.release("patient-17", 0)
    assert [mechanism.release("patient-17", 0) for _ in range(100)] == [first] * 100
    assert len(mechanism.state) == 1


def test_persistent_release_rejects_identifier_rebinding() -> None:
    mechanism = PersistentReleaseMechanism(
        example_channel(), rng=np.random.default_rng(9)
    )
    mechanism.release("same-item", 0)
    with pytest.raises(ValueError, match="different fine token"):
        mechanism.release("same-item", 1)


def test_unique_item_releases_follow_registered_channel() -> None:
    mechanism = PersistentReleaseMechanism(
        example_channel(), rng=np.random.default_rng(51)
    )
    draws = np.asarray(
        [mechanism.release(f"item-{index}", 1) for index in range(20_000)]
    )
    empirical = np.bincount(draws, minlength=2) / len(draws)
    assert np.allclose(empirical, example_channel()[1], atol=0.012)


def test_product_channel_matches_manual_two_query_probabilities() -> None:
    channel = example_channel()
    repeated = independent_repetition_channel(channel, 2)
    expected = np.asarray(
        [
            [row[0] * row[0], row[0] * row[1], row[1] * row[0], row[1] * row[1]]
            for row in channel
        ]
    )
    assert np.allclose(repeated, expected, atol=1e-14)
    assert np.allclose(repeated.sum(axis=1), 1.0)


def test_fresh_repetition_can_only_increase_worst_case_row_leakage() -> None:
    fine_laws = np.eye(2)
    accuracies = [
        population_balanced_attacker_accuracy(
            fine_laws, independent_repetition_channel(example_channel(), count)
        )
        for count in range(1, 7)
    ]
    assert np.all(np.diff(accuracies) >= -1e-12)
    assert accuracies[-1] > accuracies[0] + 0.15


def test_identical_rows_remain_noninformative_under_repetition() -> None:
    channel = np.asarray([[0.3, 0.7], [0.3, 0.7]])
    fine_laws = np.eye(2)
    for count in range(1, 8):
        repeated = independent_repetition_channel(channel, count)
        assert population_balanced_attacker_accuracy(fine_laws, repeated) == pytest.approx(
            0.5
        )


@pytest.mark.parametrize("query_count", [0, -1, 1.5])
def test_invalid_query_counts_are_rejected(query_count) -> None:
    with pytest.raises(ValueError):
        independent_repetition_channel(example_channel(), query_count)
