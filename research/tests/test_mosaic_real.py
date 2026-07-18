from __future__ import annotations

import numpy as np

from mosaic_real import (
    balanced_stratum_sample,
    build_token_table,
    evaluate_external_channel,
    minimum_contamination_fraction,
    optimize_deterministic_invariant_channel,
    ordered_smoothing_library,
    random_cap_sample,
)
from run_mosaic_official_frontier_pilot import (
    identity_candidate,
    select_certified_result,
)


def test_balanced_stratum_sample_is_equal_and_deterministic() -> None:
    target = np.repeat([0, 0, 1, 1], [20, 30, 25, 35])
    source = np.repeat([0, 1, 0, 1], [20, 30, 25, 35])
    indices = np.arange(len(target))
    first = balanced_stratum_sample(indices, target, source, maximum_total=40, seed=7)
    second = balanced_stratum_sample(indices, target, source, maximum_total=40, seed=7)
    assert np.array_equal(first, second)
    assert len(first) == 40
    assert {
        (label, group): int(np.sum((target[first] == label) & (source[first] == group)))
        for label in (0, 1)
        for group in (0, 1)
    } == {(0, 0): 10, (0, 1): 10, (1, 0): 10, (1, 1): 10}


def test_random_cap_sample_uses_all_rows_or_exact_cap() -> None:
    indices = np.arange(30)
    assert np.array_equal(
        random_cap_sample(indices, maximum_total=40, seed=3), indices
    )
    first = random_cap_sample(indices, maximum_total=10, seed=3)
    second = random_cap_sample(indices, maximum_total=10, seed=3)
    assert len(first) == 10
    assert np.array_equal(first, second)


def test_token_table_allocates_one_simultaneous_event() -> None:
    tokens = np.tile(np.arange(4), 10)
    target = np.repeat([0, 0, 1, 1], 10)
    source = np.repeat([0, 1, 0, 1], 10)
    table = build_token_table(
        tokens, target, source, token_count=4, familywise_delta=0.05
    )
    assert table.counts.shape == (2, 2, 4)
    assert np.all(table.counts.sum(axis=2) == 10)
    assert np.allclose(table.probabilities.sum(axis=2), 1.0)
    assert np.all((table.l1_radii > 0.0) & (table.l1_radii <= 2.0))


def test_minimum_contamination_recovers_known_identity_mixture() -> None:
    reference = np.asarray([[0.8, 0.2], [0.3, 0.7]])
    eta = 0.2
    residual = np.asarray([[0.0, 1.0], [1.0, 0.0]])
    external = (1.0 - eta) * reference + eta * residual
    observed = minimum_contamination_fraction(reference, external, [np.eye(2)])
    assert abs(observed - eta) < 1e-10


def test_external_risk_is_exact_for_binary_identity_release() -> None:
    tokens = np.asarray([0, 0, 1, 1, 0, 1, 0, 1])
    target = np.asarray([0, 0, 0, 0, 1, 1, 1, 1])
    source = np.asarray([0, 0, 1, 1, 0, 0, 1, 1])
    risk = evaluate_external_channel(
        tokens, target, source, np.eye(2), decoder=(0, 1)
    )
    assert risk.estimable
    assert risk.worst_privacy_advantage == 1.0
    assert risk.worst_conditional_error == 1.0


def test_smoothing_library_is_row_stochastic() -> None:
    identity, smoothing = ordered_smoothing_library(4, smoothing=0.1)
    assert np.allclose(identity, np.eye(4))
    assert np.all(smoothing >= 0.0)
    assert np.allclose(smoothing.sum(axis=1), 1.0)


def test_deterministic_optimizer_exhausts_small_family() -> None:
    probabilities = np.asarray(
        [
            [[0.9, 0.1], [0.8, 0.2]],
            [[0.1, 0.9], [0.2, 0.8]],
        ]
    )
    counts = (probabilities * 100).astype(np.int64)
    table = build_token_table(
        np.repeat(np.arange(2), 20),
        np.repeat([0, 0, 1, 1], 10),
        np.repeat([0, 1, 0, 1], 10),
        token_count=2,
        familywise_delta=0.05,
    )
    # Replace the arbitrary test histogram with a compact exact-radius table.
    table = type(table)(
        probabilities=probabilities,
        counts=counts,
        l1_radii=np.zeros((2, 2)),
        labels=(0, 1),
        sources=(0, 1),
        token_count=2,
        familywise_delta=0.05,
    )
    solution = optimize_deterministic_invariant_channel(
        table,
        common_channels_by_label=((np.eye(2),), (np.eye(2),)),
        contaminations=(0.0, 0.0),
        privacy_advantage_thresholds=(0.2, 0.2),
        released_token_count=2,
    )
    assert solution is not None
    assert solution.evaluated_channel_decoder_pairs == 16
    assert solution.certified_worst_conditional_error <= 0.2 + 1e-12


def test_identity_candidate_preserves_every_frontier_array() -> None:
    train = np.arange(12, dtype=np.float32).reshape(4, 3)
    construction = np.arange(6, dtype=np.float32).reshape(2, 3)
    deployment = np.arange(15, dtype=np.float32).reshape(5, 3)
    candidate = identity_candidate(train, construction, deployment)
    assert candidate.key == "Identity::unedited"
    assert np.array_equal(candidate.train, train)
    assert np.array_equal(candidate.validation, construction)
    assert np.array_equal(candidate.external, deployment)
    assert not np.shares_memory(candidate.external, deployment)


def test_select_certified_result_uses_error_then_stable_key() -> None:
    base = {
        "method": "Method",
        "strength": "one",
        "certified_privacy_advantages": [0.1, 0.2],
        "external_estimable": True,
        "external_worst_privacy_advantage": 0.1,
        "external_worst_conditional_error": 0.2,
        "external_safe": True,
        "false_acceptance": False,
    }
    results = [
        {**base, "candidate": "B", "deployed": True, "certified_worst_conditional_error": 0.3},
        {**base, "candidate": "A", "deployed": True, "certified_worst_conditional_error": 0.3},
        {**base, "candidate": "C", "deployed": False, "certified_worst_conditional_error": 0.1},
    ]
    selected = select_certified_result(results)
    assert selected["decision"] == "deploy"
    assert selected["candidate"] == "A"


def test_select_certified_result_abstains_without_eligible_candidate() -> None:
    selected = select_certified_result(
        [{"candidate": "A", "deployed": False, "optimization_error": "infeasible"}]
    )
    assert selected["decision"] == "abstain"
    assert selected["candidate"] is None
