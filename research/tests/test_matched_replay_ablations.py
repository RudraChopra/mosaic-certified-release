from __future__ import annotations

import copy

from analyze_matched_replay_ablations import (
    ALLOCATIONS,
    BUDGETS,
    DATASETS,
    GAMMAS,
    RULES,
    SEEDS,
    analyze,
)


def fixture() -> dict[str, object]:
    rows = []
    for dataset in DATASETS:
        for seed in SEEDS:
            for gamma in GAMMAS:
                for budget in BUDGETS:
                    for allocation in ALLOCATIONS:
                        for rule in RULES:
                            deployed = rule not in {
                                "vera_common_radius",
                            }
                            rows.append(
                                {
                                    "dataset": dataset,
                                    "seed": seed,
                                    "requested_gamma": gamma,
                                    "total_budget": budget,
                                    "allocation": allocation,
                                    "rule": rule,
                                    "deployed": deployed,
                                    "safe": True,
                                    "violation": False,
                                    "oracle_deployed": True,
                                    "certified_common_radius": 1.2,
                                    "limiting_coordinates": ["source::0"],
                                    "heldout_stress_violation": False,
                                    "registered_attacker_q": {
                                        "linear": 0.55,
                                        "rbf": 0.56,
                                        "forest": 0.57,
                                        "mlp": 0.58,
                                    },
                                }
                            )
    return {"counts": {"decision_rows": 55_296}, "decision_rows": rows}


def main() -> None:
    value = fixture()
    report = analyze(value)
    assert len(report["registered_ids"]) == 6
    assert report["registered_vs_heldout_attacker"]["heldout_safe_fraction"] == 1.0
    assert report["common_radius_vs_anisotropic_profile"][
        "vector_only_deployments"
    ] == 256
    print("PASS complete matched replay ablation fixture")
    corrupted = copy.deepcopy(value)
    corrupted["decision_rows"][0] = copy.deepcopy(corrupted["decision_rows"][1])
    try:
        analyze(corrupted)
    except RuntimeError:
        print("PASS rejects duplicate replay decision key")
    else:
        raise AssertionError("duplicate replay decision key passed")


if __name__ == "__main__":
    main()
