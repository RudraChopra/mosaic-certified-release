from __future__ import annotations

import numpy as np

from run_mosaic_bridge_frontier import (
    select_candidate,
    stratified_bridge_diagnostic_split,
    threshold_key,
)


def test_stratified_bridge_split_preserves_every_supported_group() -> None:
    target = np.tile(np.repeat([0, 1], 12), 2)
    source = np.repeat([0, 1], 24)
    indices = np.arange(len(target))
    bridge, diagnostic = stratified_bridge_diagnostic_split(
        indices, target, source, seed=17
    )
    assert not set(bridge).intersection(diagnostic)
    assert set(bridge).union(diagnostic) == set(indices)
    for label in (0, 1):
        for current_source in (0, 1):
            assert np.any((target[bridge] == label) & (source[bridge] == current_source))
            assert np.any(
                (target[diagnostic] == label) & (source[diagnostic] == current_source)
            )


def release(error: float, deployed: bool) -> dict[str, object]:
    return {
        "certified_worst_conditional_error": error,
        "released_token_count": 2,
        "certified_privacy_advantages": [0.1, 0.1],
        "diagnostic_estimable": True,
        "diagnostic_worst_privacy_advantage": 0.1,
        "diagnostic_worst_conditional_error": 0.2,
        "threshold_decisions": {
            threshold_key(0.40): {
                "deployed": deployed,
                "diagnostic_safe": True,
                "false_acceptance": False,
            }
        },
    }


def test_bridge_selection_uses_certified_error_and_lexical_tie_break() -> None:
    rows = [
        {
            "candidate": "B",
            "method": "M",
            "strength": "b",
            "bridge_membership": {"contaminations": [0.2, 0.2]},
            "release_l2": release(0.3, True),
        },
        {
            "candidate": "A",
            "method": "M",
            "strength": "a",
            "bridge_membership": {"contaminations": [0.1, 0.1]},
            "release_l2": release(0.3, True),
        },
    ]
    selected = select_candidate(
        rows, release_key="release_l2", utility_threshold=0.40
    )
    assert selected["decision"] == "deploy"
    assert selected["candidate"] == "A"


def test_bridge_selection_abstains_when_contract_is_infeasible() -> None:
    rows = [
        {
            "candidate": "A",
            "method": "M",
            "strength": "a",
            "bridge_membership": {"contaminations": [0.1, 0.1]},
            "release_l2": release(0.5, False),
        }
    ]
    selected = select_candidate(
        rows, release_key="release_l2", utility_threshold=0.40
    )
    assert selected["decision"] == "abstain"
    assert selected["candidate"] is None
