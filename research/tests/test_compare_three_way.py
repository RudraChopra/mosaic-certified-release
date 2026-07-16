from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

import numpy as np


def find_repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "research" / "scripts").is_dir() and (parent / ".git").exists():
            return parent
    return Path("/Volumes/Backups/FARO/github_export/vera-edit-or-abstain")


ROOT = find_repo_root()
LOCAL = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "research" / "scripts"))
sys.path.insert(0, str(LOCAL))

import compare_three_way as comparator  # noqa: E402
from cap8_evaluator import evaluate_configuration_cap  # noqa: E402
from independent_replay import (  # noqa: E402
    ATTACKERS,
    evaluate_configuration,
)


def fixture() -> tuple[dict, dict, dict]:
    n = 800
    environment = np.asarray([0, 1] * (n // 2), dtype=np.int8)
    source = np.asarray(([0] * (n // 4) + [1] * (n // 4)) * 2, dtype=np.int8)
    target = np.zeros(n, dtype=np.int8)
    reference = {
        "target_harm": np.zeros(n, dtype=np.int8),
        "source": source,
        "environment": environment,
        "target": target,
    }
    for index, attacker in enumerate(ATTACKERS):
        reference[f"leakage::{attacker}"] = (
            (source == 0).astype(np.int8)
            if index == 0
            else np.zeros(n, dtype=np.int8)
        )
    cap_candidates = []
    replay_candidates = []
    for key in comparator.EXPECTED_CANONICAL_CANDIDATE_KEYS:
        method = key.split("::", 1)[0]
        legacy_key = key.replace("R-LACE::", "RLACE::", 1)
        cap_candidates.append(
            {
                "candidate": key,
                "legacy_cap4_candidate_key": legacy_key,
                "method": method,
                "reference": reference,
                "q_metrics": (0.0, 0.0),
                "evaluation_metrics": (0.0, 0.0),
                "audit_npz_sha256": "a" * 64,
                "receipt_certification_split_sha256": "b" * 64,
            }
        )
        replay_candidates.append(
            {
                "canonical_candidate_key": key,
                "legacy_cap4_candidate_key": legacy_key,
                "method": method,
                "certification": reference,
                "q_metrics": (0.0, 0.0),
                "evaluation_metrics": (0.0, 0.0),
                "audit_npz_sha256": "a" * 64,
                "receipt_certification_split_sha256": "b" * 64,
            }
        )
    metadata = {"source": source, "environment": environment, "target": target}
    target_profile = {"0": 1.1, "1": 1.1}
    source_profile = {"0": 1.1, "1": 1.1}
    allocation = {
        "target::0": 100,
        "target::1": 100,
        "source::0": 100,
        "source::1": 100,
    }
    shared = {
        "delta": 0.05,
        "target_threshold": 0.2,
        "leakage_threshold": 0.2,
    }
    cap_decisions, cap_details = evaluate_configuration_cap(
        cap_candidates,
        metadata,
        np.full(n, 1.0 / n),
        target_profile,
        source_profile,
        allocation,
        rng=np.random.default_rng(2027),
        gamma_cap=8.0,
        **shared,
    )
    replay_decisions, replay_details = evaluate_configuration(
        replay_candidates,
        metadata,
        target_profile,
        source_profile,
        allocation,
        np.random.default_rng(2027),
        **shared,
    )
    config = {
        "dataset": "Synthetic",
        "seed": 45,
        "requested_gamma": 1.1,
        "total_budget": 400,
        "allocation": "uniform",
    }

    def rows(decisions: dict) -> list[dict]:
        output = []
        oracle_deployed = decisions["external_oracle"]["deployed"]
        for rule, decision in decisions.items():
            output.append(
                {
                    **config,
                    "rule": rule,
                    "oracle_deployed": oracle_deployed,
                    "heldout_leakage": 0.0,
                    "heldout_stress_violation": False,
                    "registered_attacker_q": {},
                    **decision,
                }
            )
        return output

    profile = {"dataset": "Synthetic", "seed": 45, "requested_gamma": 1.1}
    allocation_record = {
        **config,
        "pilot_candidate": "INLP::rank=1",
        "counts": allocation,
    }
    primary = {
        "overall_confirmatory_success": True,
        "confirmatory_statistic": 0.0,
        "common_radius_distribution_on_vector_deployments": {"median": 8.0},
        "limiting_coordinate_counts": {"target::environment=0": 1},
    }
    replay = {
        "gamma_cap": 8.0,
        "profiles": [profile],
        "allocation_records": [allocation_record],
        "decision_rows": rows(replay_decisions),
        "candidate_envelope_details": [
            {**config, **detail} for detail in replay_details
        ],
        "primary_inference": copy.deepcopy(primary),
    }
    cap8 = {
        "radius_gamma_cap": 8.0,
        "profiles": [profile],
        "allocation_receipts": [allocation_record],
        "rows": rows(cap_decisions),
        "candidate_envelopes": [{**config, **detail} for detail in cap_details],
        "primary_inference": copy.deepcopy(primary),
        "candidate_key_crosswalk": comparator.expected_candidate_crosswalk(),
        "candidate_key_crosswalk_order_preserving": True,
    }
    cap8["summaries"] = comparator.summarize_rows(cap8["rows"])
    cap4 = copy.deepcopy(cap8)
    cap4["radius_gamma_cap"] = 4.0
    return tuple(
        json.loads(json.dumps(value, allow_nan=False))
        for value in (replay, cap8, cap4)
    )


def configure_small_fixture() -> None:
    comparator.EXPECTED_PROFILE_COUNT = 1
    comparator.EXPECTED_ALLOCATION_COUNT = 1
    comparator.EXPECTED_ROW_COUNT = 9
    comparator.EXPECTED_DETAIL_COUNT = 12
    comparator.EXPECTED_SUMMARY_COUNT = 9


def test_exact_agreement() -> None:
    configure_small_fixture()
    replay, cap8, cap4 = fixture()
    cap8_diff, _ = comparator.compare_cap8(replay, cap8)
    cap4_diff, report = comparator.compare_cap4(cap8, cap4)
    assert cap8_diff.count == 0, cap8_diff.examples
    assert cap4_diff.count == 0, cap4_diff.examples
    assert report["allowed_geometry_difference_counts"] == {
        "certified_common_radius": 0,
        "target_environment_intercepts": 0,
        "source_class_intercepts": 0,
        "axis_limiting_coordinates": 0,
    }
    assert not report["primary_gate_differs"]


def test_detects_cap8_tampering() -> None:
    configure_small_fixture()
    replay, cap8, _ = fixture()
    replay["candidate_envelope_details"][0]["target_sufficient_statistics"][
        "target::environment=0"
    ]["positive_count"] += 1
    differences, _ = comparator.compare_cap8(replay, cap8)
    assert differences.count > 0


def test_detects_aggregate_tampering() -> None:
    configure_small_fixture()
    replay, cap8, _ = fixture()
    cap8["summaries"][0]["deployment_count"] += 1
    differences, _ = comparator.compare_cap8(replay, cap8)
    assert differences.count > 0


def test_detects_cap4_core_tampering() -> None:
    configure_small_fixture()
    _, cap8, cap4 = fixture()
    cap4["rows"][0]["q_target"] = 0.5
    differences, _ = comparator.compare_cap4(cap8, cap4)
    assert differences.count > 0


def test_allows_only_cap4_geometry_changes() -> None:
    configure_small_fixture()
    _, cap8, cap4 = fixture()
    cap4["rows"][0]["certified_common_radius"] = 4.0
    cap4["rows"][0]["target_environment_radii"]["0"] = 4.0
    cap4["rows"][0]["source_class_radii"]["0"] = 4.0
    cap4["rows"][0]["limiting_coordinates"] = ["source::0"]
    differences, report = comparator.compare_cap4(cap8, cap4)
    assert differences.count == 0, differences.examples
    assert all(
        value == 1
        for value in report["allowed_geometry_difference_counts"].values()
    )


def test_legacy_rlace_crosswalk_is_order_preserving() -> None:
    canonical = sorted(comparator.EXPECTED_CANONICAL_CANDIDATE_KEYS)
    crosswalk = comparator.expected_candidate_crosswalk()
    reverse = {legacy: current for current, legacy in crosswalk.items()}
    assert canonical == [reverse[value] for value in sorted(reverse)]


def test_crosswalk_corruptions_fail() -> None:
    canonical = comparator.EXPECTED_CANONICAL_CANDIDATE_KEYS
    expected = comparator.expected_candidate_crosswalk()

    duplicate = dict(expected)
    duplicate["INLP::rank=2"] = duplicate["INLP::rank=1"]
    order_changing = dict(expected)
    order_changing["INLP::rank=1"], order_changing["INLP::rank=2"] = (
        order_changing["INLP::rank=2"],
        order_changing["INLP::rank=1"],
    )
    unknown = dict(expected)
    unknown.pop("INLP::rank=1")
    unknown["Unknown::candidate"] = "Unknown::candidate"
    for value in (duplicate, order_changing, unknown):
        try:
            comparator.validate_crosswalk_mapping(value, canonical)
        except RuntimeError:
            pass
        else:
            raise AssertionError("invalid crosswalk passed")


def test_cap8_rejects_wrong_crosswalk() -> None:
    configure_small_fixture()
    replay, cap8, _ = fixture()
    cap8["candidate_key_crosswalk"]["R-LACE::rank=1"] = "R-LACE::rank=1"
    differences, _ = comparator.compare_cap8(replay, cap8)
    assert differences.count > 0


def test_envelope_corruptions_fail() -> None:
    configure_small_fixture()
    base_replay, base_cap8, _ = fixture()

    def must_fail(mutator) -> None:
        replay = copy.deepcopy(base_replay)
        cap8 = copy.deepcopy(base_cap8)
        mutator(replay, cap8)
        try:
            differences, _ = comparator.compare_cap8(replay, cap8)
        except (KeyError, RuntimeError, TypeError, ValueError):
            return
        assert differences.count > 0, mutator.__name__

    def missing_detail(replay, _):
        replay["candidate_envelope_details"].pop()

    def duplicate_detail(replay, _):
        replay["candidate_envelope_details"].append(
            copy.deepcopy(replay["candidate_envelope_details"][0])
        )

    def negative_count(replay, _):
        stats = replay["candidate_envelope_details"][0][
            "target_sufficient_statistics"
        ]
        stats["target::environment=0"]["negative_count"] += 1

    def attacker_count(replay, _):
        stats = replay["candidate_envelope_details"][0][
            "leakage_sufficient_statistics"
        ]
        attacker = sorted(stats)[0]
        stats[attacker]["0"]["correct_count"] += 1

    def swapped_source_classes(replay, _):
        stats = replay["candidate_envelope_details"][0][
            "leakage_sufficient_statistics"
        ]
        attacker = next(
            key for key in sorted(stats) if stats[key]["0"] != stats[key]["1"]
        )
        stats[attacker]["0"], stats[attacker]["1"] = (
            stats[attacker]["1"],
            stats[attacker]["0"],
        )

    def wrong_alpha(replay, _):
        replay["candidate_envelope_details"][0]["local_error_budget"] *= 2

    def missing_selected_candidate(replay, _):
        deployed = next(row for row in replay["decision_rows"] if row["deployed"])
        deployed["selected_candidate"] = "Unknown::candidate"
        deployed["canonical_candidate_key"] = "Unknown::candidate"

    def inconsistent_vector(replay, _):
        detail = replay["candidate_envelope_details"][0]
        detail["vector_eligible"] = not detail["vector_eligible"]

    def wrong_common_limiter(replay, _):
        replay["candidate_envelope_details"][0]["common_limiting_contracts"] = [
            "not-a-contract"
        ]

    def intercept_as_common_radius(replay, _):
        detail = replay["candidate_envelope_details"][0]
        detail["coupled_common_radius"] = (
            detail["target_coordinate_axis_intercepts"]["0"] + 1.0
        )

    for mutator in (
        missing_detail,
        duplicate_detail,
        negative_count,
        attacker_count,
        swapped_source_classes,
        wrong_alpha,
        missing_selected_candidate,
        inconsistent_vector,
        wrong_common_limiter,
        intercept_as_common_radius,
    ):
        must_fail(mutator)


if __name__ == "__main__":
    test_exact_agreement()
    test_detects_cap8_tampering()
    test_detects_aggregate_tampering()
    test_detects_cap4_core_tampering()
    test_allows_only_cap4_geometry_changes()
    test_legacy_rlace_crosswalk_is_order_preserving()
    test_crosswalk_corruptions_fail()
    test_cap8_rejects_wrong_crosswalk()
    test_envelope_corruptions_fail()
    print("18 comparator and envelope checks passed")
