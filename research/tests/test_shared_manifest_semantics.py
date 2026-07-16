from __future__ import annotations

import copy
import json
from pathlib import Path

from schema_fixture import build_fixture
from validate_shared_manifest_semantics import validate_semantics


SCHEMA = Path(
    "/Volumes/Backups/FARO/github_export/vera-edit-or-abstain/"
    "research/maintrack/SHARED_RESULT_MANIFEST_SCHEMA.json"
)


def main() -> None:
    fixture = build_fixture(json.loads(SCHEMA.read_text(encoding="utf-8")))
    report = validate_semantics(fixture)
    if not report["passed"]:
        raise AssertionError("semantic fixture failed:\n" + "\n".join(report["errors"]))
    print("PASS complete semantic fixture")
    mutations = []
    value = copy.deepcopy(fixture)
    value["primary"]["efficacy"]["test"]["nonzero_denominator"] += 1
    mutations.append(("wrong sign-test denominator", value))
    value = copy.deepcopy(fixture)
    value["primary"]["sentinel_safety"]["test"]["upper_bound"] = 0.0
    mutations.append(("wrong exact safety bound", value))
    value = copy.deepcopy(fixture)
    value["primary"]["safe_retention"]["effect"]["retention"]["estimate"] = 0.9
    mutations.append(("wrong retention fraction", value))
    value = copy.deepcopy(fixture)
    value["primary"]["vector_common_advantage"]["test"][
        "zero_denominator_cases"
    ]["zero_opportunity"] = 1
    mutations.append(("overlapping ratio cases", value))
    value = copy.deepcopy(fixture)
    value["safety_sensitivity"]["vector_violation_cooccurrence"][0][1] = 1
    mutations.append(("asymmetric co-occurrence", value))
    value = copy.deepcopy(fixture)
    value["safety_sensitivity"]["vector_violating_dataset_count_by_seed"][0] -= 1
    mutations.append(("incomplete violation multiplicity", value))
    value = copy.deepcopy(fixture)
    value["threshold_stress"]["readiness"]["always_deploy_max_registered_rate"] = 0.5
    mutations.append(("wrong threshold-stress maximum", value))
    value = copy.deepcopy(fixture)
    value["negative_results"] = [
        row
        for row in value["negative_results"]
        if row["id"] != "three_rule_threshold_stress_failed"
    ]
    mutations.append(("suppressed stress failure", value))
    value = copy.deepcopy(fixture)
    value["candidate_key_correction"]["gate_difference_count"] = 1
    mutations.append(("candidate-key gate difference", value))
    value = copy.deepcopy(fixture)
    value["heldout_attacker_result"].update(
        {
            "portfolio_safe_deployments": 10,
            "heldout_violation_count": 3,
            "heldout_safe_fraction": 0.9,
        }
    )
    mutations.append(("wrong held-out fraction", value))
    value = copy.deepcopy(fixture)
    value["figure_candidate"]["selected_by_vector"] = False
    mutations.append(("wrong figure selection branch", value))
    value = copy.deepcopy(fixture)
    value["title_decision"]["title_branch"] = "evidence_efficient"
    mutations.append(("illegal strong title", value))
    for label, mutation in mutations:
        if validate_semantics(mutation)["passed"]:
            raise AssertionError(f"{label} passed")
        print(f"PASS rejects {label}")


if __name__ == "__main__":
    main()
