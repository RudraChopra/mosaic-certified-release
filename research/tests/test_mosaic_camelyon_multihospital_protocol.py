from __future__ import annotations

import numpy as np
import pytest

from run_mosaic_camelyon_multihospital_confirmation import (
    recode_source,
    split_construction_reference,
    stratified_bridge_diagnostic_split,
    stratum_counts,
)


def test_recode_source_uses_registered_hospitals() -> None:
    centers = np.asarray([0, 1, 2, 3, 4], dtype=np.int8)
    assert recode_source(centers).tolist() == [0, -1, -1, 1, 1]


def test_balanced_folds_are_disjoint_and_reproducible() -> None:
    target = np.tile(np.repeat([0, 1], 40), 2)
    source = np.repeat([0, 1], 80)
    pool = np.arange(len(target), dtype=np.int64)
    first = split_construction_reference(
        pool,
        target,
        source,
        construction_cap=40,
        reference_cap=80,
        seed=4301,
    )
    second = split_construction_reference(
        pool,
        target,
        source,
        construction_cap=40,
        reference_cap=80,
        seed=4301,
    )
    construction, reference = first
    assert np.array_equal(construction, second[0])
    assert np.array_equal(reference, second[1])
    assert len(construction) == 40
    assert len(reference) == 80
    assert not set(construction).intersection(map(int, reference))
    assert stratum_counts(construction, target, source) == [[10, 10], [10, 10]]
    assert stratum_counts(reference, target, source) == [[20, 20], [20, 20]]


def test_balanced_folds_fail_closed_on_missing_rows() -> None:
    pool = np.arange(12, dtype=np.int64)
    target = np.asarray([0, 1] * 6, dtype=np.int8)
    source = np.zeros(12, dtype=np.int8)
    with pytest.raises(RuntimeError, match="stratum"):
        split_construction_reference(
            pool,
            target,
            source,
            construction_cap=4,
            reference_cap=4,
            seed=4301,
        )


def test_target_split_preserves_every_stratum() -> None:
    target = np.tile(np.repeat([0, 1], 12), 2)
    source = np.repeat([0, 1], 24)
    pool = np.arange(len(target), dtype=np.int64)
    bridge, diagnostic = stratified_bridge_diagnostic_split(
        pool,
        target,
        source,
        seed=4301,
    )
    assert not set(bridge).intersection(map(int, diagnostic))
    assert stratum_counts(bridge, target, source) == [[8, 8], [8, 8]]
    assert stratum_counts(diagnostic, target, source) == [[4, 4], [4, 4]]
