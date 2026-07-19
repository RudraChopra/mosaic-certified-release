from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from mosaic_strict_certification import certify_bridge_membership_strict
from replay_mosaic_bridge_strict import select_candidate, threshold_key


def test_strict_selection_uses_zero_decision_tolerance() -> None:
    threshold = 0.40
    rows = [
        {
            "candidate": "at_boundary",
            "method": "identity",
            "strength": 0.0,
            "bridge_membership": {"contaminations": [0.1, 0.1]},
            "release_l2": {
                "certified_worst_conditional_error_upper": np.nextafter(
                    threshold, np.inf
                ),
                "certified_source_advantage_upper": [0.2, 0.2],
                "released_token_count": 2,
                "diagnostic": {
                    "estimable": True,
                    "worst_privacy_advantage": 0.2,
                    "worst_conditional_error": 0.3,
                },
                "threshold_decisions": {
                    threshold_key(threshold): {
                        "deployed": False,
                        "diagnostic_safe": True,
                        "false_acceptance": False,
                    }
                },
            },
        }
    ]
    selection = select_candidate(
        rows, release_key="release_l2", utility_threshold=threshold
    )
    assert selection["decision"] == "abstain"


def test_strict_bridge_serialization_remains_json_safe() -> None:
    reference = np.asarray(
        [
            [[0.5, 0.3, 0.1, 0.1], [0.1, 0.2, 0.3, 0.4]],
            [[0.1, 0.2, 0.3, 0.4], [0.4, 0.3, 0.2, 0.1]],
        ]
    )
    certificate = certify_bridge_membership_strict(
        reference,
        reference_l1_radii=np.full((2, 2), 0.01),
        bridge_empirical_distributions=reference,
        bridge_l1_radii=np.full((2, 2), 0.01),
    )
    payload = {
        "retained": list(certificate.retained_masses),
        "transforms": [label.transform.tolist() for label in certificate.labels],
    }
    assert json.loads(json.dumps(payload))["retained"] == payload["retained"]
