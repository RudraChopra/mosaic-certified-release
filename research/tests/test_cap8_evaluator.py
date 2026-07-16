from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


SCRIPTS = Path(
    "/Volumes/Backups/FARO/github_export/vera-edit-or-abstain/research/scripts"
)
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from cap8_evaluator import evaluate_configuration_cap  # noqa: E402
from design_vera_controlled_shift_study import (  # noqa: E402
    ATTACKERS,
    evaluate_configuration,
)


def fixture() -> tuple[
    list[dict],
    dict[str, np.ndarray],
    np.ndarray,
    dict[str, float],
    dict[str, float],
    dict[str, int],
]:
    n = 400
    source = np.tile(np.asarray([0, 1], dtype=np.int8), n // 2)
    environment = np.repeat(np.asarray([0, 1], dtype=np.int8), n // 2)
    target = np.tile(np.asarray([0, 1, 1, 0], dtype=np.int8), n // 4)
    reference = {
        "target_harm": np.zeros(n, dtype=np.int8),
        "source": source,
        "environment": environment,
        "target": target,
    }
    for attacker in ATTACKERS:
        reference[f"leakage::{attacker}"] = np.zeros(n, dtype=np.int8)
    candidates = [
        {
            "candidate": "LEACE::closed_form",
            "method": "LEACE",
            "reference": reference,
            "q_metrics": (0.0, 0.0),
            "evaluation_metrics": (0.0, 0.0),
        }
    ]
    metadata = {
        "source": source,
        "environment": environment,
        "target": target,
    }
    probabilities = np.full(n, 1.0 / n)
    target_profile = {"0": 1.1, "1": 1.1}
    source_profile = {"0": 1.1, "1": 1.1}
    allocation = {
        "target::0": 200,
        "target::1": 200,
        "source::0": 200,
        "source::1": 200,
    }
    return (
        candidates,
        metadata,
        probabilities,
        target_profile,
        source_profile,
        allocation,
    )


def main() -> None:
    (
        candidates,
        metadata,
        probabilities,
        target_profile,
        source_profile,
        allocation,
    ) = fixture()
    shared = {
        "delta": 0.05,
        "target_threshold": 0.2,
        "leakage_threshold": 0.2,
    }
    locked = evaluate_configuration(
        candidates,
        metadata,
        probabilities,
        target_profile,
        source_profile,
        allocation,
        rng=np.random.default_rng(2027),
        **shared,
    )
    cap4, details4 = evaluate_configuration_cap(
        candidates,
        metadata,
        probabilities,
        target_profile,
        source_profile,
        allocation,
        rng=np.random.default_rng(2027),
        gamma_cap=4.0,
        **shared,
    )
    for rule, expected in locked.items():
        for key, value in expected.items():
            assert cap4[rule][key] == value, (rule, key, cap4[rule][key], value)
    assert len(details4) == 1
    assert details4[0]["envelope"]["gamma_cap"] == 4.0
    assert details4[0]["common_limiting_contracts"]
    assert details4[0]["axis_limiting_coordinates"]

    cap8, details8 = evaluate_configuration_cap(
        candidates,
        metadata,
        probabilities,
        target_profile,
        source_profile,
        allocation,
        rng=np.random.default_rng(2027),
        gamma_cap=8.0,
        **shared,
    )
    assert len(details8) == 1
    assert details8[0]["envelope"]["gamma_cap"] == 8.0
    assert details8[0]["envelope_radius"] >= details4[0]["envelope_radius"]
    assert details8[0]["common_limiting_contracts"]
    assert set(cap8) == set(cap4)
    print("PASS cap-4 executable equivalence")
    print("PASS cap-8 extension and common-radius diagnostics")


if __name__ == "__main__":
    main()
