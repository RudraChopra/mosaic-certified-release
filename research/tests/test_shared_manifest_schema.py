from __future__ import annotations

import copy
import json
from pathlib import Path

from mini_jsonschema import Validator
from schema_fixture import build_fixture


SCHEMA = Path(
    "/Volumes/Backups/FARO/github_export/vera-edit-or-abstain/"
    "research/maintrack/SHARED_RESULT_MANIFEST_SCHEMA.json"
)


def main() -> None:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    fixture = build_fixture(schema)
    validator = Validator(schema)
    errors = validator.errors(fixture)
    if errors:
        raise AssertionError("synthetic fixture failed:\n" + "\n".join(errors[:80]))
    print("PASS complete synthetic V2 manifest")
    assert len(fixture["ablations"]) == 16
    assert fixture["candidate_key_correction"]["order_preserved"]
    assert fixture["gait_diagnostic"]["candidate_count"] == 768
    assert fixture["heldout_attacker_result"]["attacker"] == "boosted_tree"
    assert fixture["figure_candidate"]["determinism_verified"]
    print("PASS new candidate-key, ablation, Gait, held-out, and figure records")

    mutations = {}
    for key in (
        "candidate_key_correction",
        "ablations",
        "gait_diagnostic",
        "heldout_attacker_result",
        "figure_candidate",
    ):
        value = copy.deepcopy(fixture)
        del value[key]
        mutations[f"missing {key}"] = value
    value = copy.deepcopy(fixture)
    value["candidate_key_correction"]["selection_difference_count"] = 1
    mutations["candidate-key scientific difference"] = value
    value = copy.deepcopy(fixture)
    value["ablations"].pop()
    mutations["missing ablation"] = value
    value = copy.deepcopy(fixture)
    value["ablations"][13]["id"] = "not_the_native_probe_ablation"
    mutations["wrong ablation identity"] = value
    value = copy.deepcopy(fixture)
    value["ablations"][13]["status"] = "invalid"
    mutations["invalid ablation in complete analysis"] = value
    value = copy.deepcopy(fixture)
    value["gait_diagnostic"]["candidate_count"] = 767
    mutations["incomplete Gait candidate grid"] = value
    value = copy.deepcopy(fixture)
    value["heldout_attacker_result"]["formal_guarantee"] = True
    mutations["held-out promoted to guarantee"] = value
    value = copy.deepcopy(fixture)
    value["figure_candidate"]["determinism_verified"] = False
    mutations["nondeterministic figure candidate"] = value
    value = copy.deepcopy(fixture)
    del value["primary"]["efficacy"]["test"]["nonzero_denominator"]
    mutations["missing sign-test denominator"] = value
    value = copy.deepcopy(fixture)
    value["rule_results"][0]["per_dataset"][0]["decisions"] = 63
    mutations["wrong per-dataset denominator"] = value
    value = copy.deepcopy(fixture)
    value["safety_sensitivity"]["dataset_bound_component_alpha"] = 0.05
    mutations["wrong safety alpha"] = value
    value = copy.deepcopy(fixture)
    value["title_decision"].update(
        {
            "title_branch": "evidence_efficient",
            "literature_condition": False,
            "allocation_condition": True,
        }
    )
    mutations["strong title after literature collision"] = value
    value = copy.deepcopy(fixture)
    value["analysis_status"] = "invalid"
    mutations["invalid analysis with passing gates"] = value
    for label, mutation in mutations.items():
        if not validator.errors(mutation):
            raise AssertionError(f"{label} passed")
        print(f"PASS rejects {label}")

    failed = copy.deepcopy(fixture)
    failed["primary"]["efficacy"]["status"] = "fail"
    failed["primary"]["overall"] = {
        "status": "fail",
        "failed_gates": ["efficacy"],
    }
    failed["negative_results"].append(
        {
            "id": "primary_efficacy_failed",
            "scope": "primary",
            "statement": "synthetic failure",
            "manifest_paths": ["primary.efficacy"],
        }
    )
    if validator.errors(failed):
        raise AssertionError("legal disclosed primary failure did not validate")
    failed["negative_results"] = [
        row
        for row in failed["negative_results"]
        if row["id"] != "primary_efficacy_failed"
    ]
    if not validator.errors(failed):
        raise AssertionError("suppressed failed-gate negative result passed")
    print("PASS disclosed failure branch and mandatory negative-result rule")


if __name__ == "__main__":
    main()
