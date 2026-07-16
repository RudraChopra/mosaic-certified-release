"""First-read comparator for replay, protocol-cap, and locked-cap outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping


FLOAT_TOLERANCE = 1e-10
RADIUS_TOLERANCE = 1e-4
EXPECTED_PROFILE_COUNT = 768
EXPECTED_ALLOCATION_COUNT = 6_144
EXPECTED_ROW_COUNT = 55_296
EXPECTED_DETAIL_COUNT = 73_728
EXPECTED_SUMMARY_COUNT = 864
EXPECTED_CANONICAL_CANDIDATE_KEYS = (
    "INLP::rank=1",
    "INLP::rank=2",
    "INLP::rank=4",
    "INLP::rank=8",
    "LEACE::closed_form",
    "MANCE++::epsilon=0.05,steps=3",
    "R-LACE::rank=1",
    "R-LACE::rank=4",
    "TaCo::components_removed=1",
    "TaCo::components_removed=2",
    "TaCo::components_removed=3",
    "TaCo::components_removed=5",
)
ROW_KEY_FIELDS = (
    "dataset",
    "seed",
    "requested_gamma",
    "total_budget",
    "allocation",
    "rule",
)
CONFIG_KEY_FIELDS = ROW_KEY_FIELDS[:-1]
DETAIL_KEY_FIELDS = (*CONFIG_KEY_FIELDS, "canonical_candidate_key")
SUMMARY_KEY_FIELDS = (
    "dataset",
    "requested_gamma",
    "total_budget",
    "allocation",
    "rule",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"input is not a JSON object: {path.name}")
    return value


def canonical_candidate(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    return value.replace("RLACE::", "R-LACE::", 1) if value.startswith("RLACE::") else value


def canonical_method(value: Any) -> Any:
    return "R-LACE" if value == "RLACE" else value


def validate_crosswalk_mapping(
    crosswalk: Mapping[str, str], canonical_keys: Iterable[str]
) -> dict[str, str]:
    canonical = tuple(sorted(canonical_keys))
    if len(canonical) != 12 or len(canonical) != len(set(canonical)):
        raise RuntimeError("expected candidate frontier is not exactly 12 unique keys")
    normalized = dict(crosswalk)
    if set(normalized) != set(canonical):
        raise RuntimeError("candidate crosswalk has a missing or unknown canonical key")
    if any(not isinstance(value, str) or not value for value in normalized.values()):
        raise RuntimeError("candidate crosswalk contains an invalid legacy key")
    if len(set(normalized.values())) != len(normalized):
        raise RuntimeError("candidate crosswalk is not one-to-one")
    reverse = {legacy: key for key, legacy in normalized.items()}
    if [reverse[key] for key in sorted(reverse)] != list(canonical):
        raise RuntimeError("candidate crosswalk changes stable-key ordering")
    return dict(sorted(normalized.items()))


def expected_candidate_crosswalk() -> dict[str, str]:
    canonical = tuple(sorted(EXPECTED_CANONICAL_CANDIDATE_KEYS))
    proposed = {
        key: (
            key.replace("R-LACE::", "RLACE::", 1)
            if key.startswith("R-LACE::")
            else key
        )
        for key in canonical
    }
    return validate_crosswalk_mapping(proposed, canonical)


def candidate_crosswalk_sha256(crosswalk: Mapping[str, str]) -> str:
    payload = json.dumps(
        dict(sorted(crosswalk.items())),
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def logical_key(record: Mapping[str, Any], fields: Iterable[str]) -> tuple[Any, ...]:
    return tuple(record[field] for field in fields)


def unique_index(
    records: list[dict[str, Any]], fields: Iterable[str], expected_count: int, label: str
) -> dict[tuple[Any, ...], dict[str, Any]]:
    output: dict[tuple[Any, ...], dict[str, Any]] = {}
    for record in records:
        key = logical_key(record, fields)
        if key in output:
            raise RuntimeError(f"duplicate {label} key: {key}")
        output[key] = record
    if len(output) != expected_count:
        raise RuntimeError(f"{label} count mismatch: {len(output)} != {expected_count}")
    return output


def radius_path(path: str) -> bool:
    lowered = path.casefold()
    return any(token in lowered for token in ("radius", "radii", "intercept"))


@dataclass
class Differences:
    count: int = 0
    examples: list[dict[str, Any]] = field(default_factory=list)

    def add(self, path: str, left: Any, right: Any) -> None:
        self.count += 1
        if len(self.examples) < 20:
            self.examples.append({"path": path, "left": left, "right": right})


def compare_value(
    left: Any,
    right: Any,
    path: str,
    differences: Differences,
    *,
    expected_subset: bool = False,
) -> None:
    if isinstance(right, dict):
        if not isinstance(left, dict):
            differences.add(path, left, right)
            return
        if not expected_subset and set(left) != set(right):
            differences.add(f"{path}.__keys__", sorted(left), sorted(right))
        for key, value in right.items():
            if key not in left:
                differences.add(f"{path}.{key}", None, value)
            else:
                compare_value(
                    left[key],
                    value,
                    f"{path}.{key}",
                    differences,
                    expected_subset=expected_subset,
                )
        return
    if isinstance(right, list):
        if not isinstance(left, list) or len(left) != len(right):
            differences.add(path, left, right)
            return
        for index, value in enumerate(right):
            compare_value(
                left[index],
                value,
                f"{path}[{index}]",
                differences,
                expected_subset=expected_subset,
            )
        return
    if isinstance(right, bool) or right is None or isinstance(right, str):
        if left != right:
            differences.add(path, left, right)
        return
    if isinstance(right, (int, float)) and isinstance(left, (int, float)):
        tolerance = RADIUS_TOLERANCE if radius_path(path) else FLOAT_TOLERANCE
        scale = max(1.0, abs(float(left)), abs(float(right)))
        if abs(float(left) - float(right)) > tolerance * scale:
            differences.add(path, left, right)
        return
    if left != right:
        differences.add(path, left, right)


ROW_FIELDS = (
    "deployed",
    "safe",
    "violation",
    "evaluation_violation",
    "selected_candidate",
    "canonical_candidate_key",
    "legacy_cap4_candidate_key",
    "selected_method",
    "q_target",
    "q_leakage",
    "evaluation_target",
    "evaluation_leakage",
    "certified_common_radius",
    "target_environment_radii",
    "source_class_radii",
    "limiting_coordinates",
    "axis_limiting_coordinates",
    "common_limiting_contracts",
    "common_radius_right_censored",
    "fixed_profile_limiting_contracts",
    "heldout_leakage",
    "heldout_stress_violation",
    "registered_attacker_q",
    "oracle_deployed",
)


def normalize_row(record: Mapping[str, Any], *, legacy: bool = False) -> dict[str, Any]:
    selected = canonical_candidate(
        record.get(
            "canonical_candidate_key", record.get("selected_candidate", "")
        )
    )
    method = canonical_method(record.get("selected_method", ""))
    normalized = {field: record.get(field) for field in ROW_KEY_FIELDS}
    for field in ROW_FIELDS:
        if field == "selected_candidate" or field == "canonical_candidate_key":
            normalized[field] = selected
        elif field == "legacy_cap4_candidate_key":
            normalized[field] = canonical_candidate(
                record.get(field, record.get("selected_candidate", ""))
            )
        elif field == "selected_method":
            normalized[field] = method
        elif field == "axis_limiting_coordinates":
            normalized[field] = record.get(field, record.get("limiting_coordinates", []))
        elif field == "common_limiting_contracts":
            normalized[field] = record.get(field, [])
        elif field == "common_radius_right_censored":
            normalized[field] = record.get(field, False)
        else:
            normalized[field] = record.get(field)
    if legacy:
        for field in (
            "axis_limiting_coordinates",
            "common_limiting_contracts",
            "common_radius_right_censored",
        ):
            normalized.pop(field, None)
    return normalized


def normalize_profile(record: Mapping[str, Any]) -> dict[str, Any]:
    return dict(record)


def normalize_allocation(record: Mapping[str, Any]) -> dict[str, Any]:
    output = dict(record)
    output["pilot_candidate"] = canonical_candidate(output["pilot_candidate"])
    return output


def normalized_curve_parameters(
    detail: Mapping[str, Any], *, analyzer: bool
) -> dict[str, Any]:
    if analyzer:
        curves = detail["envelope"]["simultaneous_curve_parameters"]
    else:
        curves = detail["curve_parameters"]
    output: dict[str, Any] = {}
    for key in sorted(curves):
        curve = curves[key]
        if key.startswith("target::"):
            stats = detail["target_sufficient_statistics"][key]
            output[key] = {
                **stats,
                "positive_probability_upper": curve["positive_probability_upper"],
                "negative_probability_lower": curve["negative_probability_lower"],
                "threshold": curve["threshold"],
            }
        else:
            attacker = key.split("::", 1)[1]
            stats = detail["leakage_sufficient_statistics"][attacker]
            if analyzer:
                probabilities = {
                    str(source_class): curve[
                        f"class_{source_class}_probability_upper"
                    ]
                    for source_class in (0, 1)
                }
            else:
                probabilities = {
                    str(source_class): curve["classes"][str(source_class)][
                        "probability_upper"
                    ]
                    for source_class in (0, 1)
                }
            output[key] = {
                "sources": {
                    str(source_class): {
                        **stats[str(source_class)],
                        "probability_upper": probabilities[str(source_class)],
                    }
                    for source_class in (0, 1)
                },
                "threshold": curve["threshold"],
            }
    return output


DETAIL_SCALAR_FIELDS = (
    "point_target",
    "point_leakage",
    "point_feasible",
    "iid_eligible",
    "robust_point_eligible",
    "scalar_eligible",
    "fixed_eligible",
    "vector_eligible",
    "common_eligible",
    "q_safe",
    "evaluation_safe",
    "q_target",
    "q_leakage",
    "evaluation_target",
    "evaluation_leakage",
    "envelope_radius",
    "target_environment_radii",
    "source_class_radii",
    "limiting_coordinates",
    "axis_limiting_coordinates",
    "common_limiting_contracts",
    "common_radius_right_censored",
    "fixed_profile_limiting_contracts",
    "family_size",
    "local_error_budget",
    "target_threshold",
    "leakage_threshold",
    "gamma_cap",
    "requested_target_profile",
    "requested_source_profile",
    "requested_profile_in_envelope",
    "target_sufficient_statistics",
    "leakage_sufficient_statistics",
    "target_coordinate_axis_intercepts",
    "source_coordinate_axis_intercepts",
    "coupled_common_radius",
    "common_radius_right_censored",
    "certification_index_sha256",
    "sampled_source_sha256",
    "certification_source_sha256",
    "receipt_certification_split_sha256",
    "audit_npz_sha256",
)


def normalize_detail(record: Mapping[str, Any], *, analyzer: bool) -> dict[str, Any]:
    output = {field: record[field] for field in CONFIG_KEY_FIELDS}
    output["canonical_candidate_key"] = canonical_candidate(
        record["canonical_candidate_key"]
    )
    output["legacy_cap4_candidate_key"] = canonical_candidate(
        record["legacy_cap4_candidate_key"]
    )
    output["eraser_family"] = canonical_method(record["eraser_family"])
    for field in DETAIL_SCALAR_FIELDS:
        output[field] = record[field]
    output["curve_parameters"] = normalized_curve_parameters(
        record, analyzer=analyzer
    )
    output["common_radius_contract_margins"] = (
        record["common_radius_details"]["contract_margins"]
        if analyzer
        else record["common_radius_contract_margins"]
    )
    output["right_censored_coordinates"] = (
        record["envelope"]["right_censored_coordinates"]
        if analyzer
        else record["right_censored_coordinates"]
    )
    return output


def compare_indexed(
    left: dict[tuple[Any, ...], dict[str, Any]],
    right: dict[tuple[Any, ...], dict[str, Any]],
    differences: Differences,
    label: str,
) -> None:
    if set(left) != set(right):
        differences.add(f"{label}.__keys__", len(left), len(right))
        return
    for key in sorted(left):
        compare_value(left[key], right[key], f"{label}{key}", differences)


def summarize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = logical_key(row, SUMMARY_KEY_FIELDS)
        grouped.setdefault(key, []).append(row)
    output: list[dict[str, Any]] = []
    for key, values in sorted(grouped.items()):
        oracle_opportunities = sum(bool(row["oracle_deployed"]) for row in values)
        safe_on_opportunity = sum(
            bool(row["oracle_deployed"]) and bool(row["safe"]) for row in values
        )
        output.append(
            {
                "dataset": key[0],
                "requested_gamma": key[1],
                "total_budget": key[2],
                "allocation": key[3],
                "rule": key[4],
                "seed_count": len(values),
                "deployment_count": sum(bool(row["deployed"]) for row in values),
                "violation_count": sum(bool(row["violation"]) for row in values),
                "violation_rate": sum(bool(row["violation"]) for row in values)
                / len(values),
                "evaluation_violation_count": sum(
                    bool(row["evaluation_violation"]) for row in values
                ),
                "evaluation_violation_rate": sum(
                    bool(row["evaluation_violation"]) for row in values
                )
                / len(values),
                "oracle_opportunity_count": oracle_opportunities,
                "safe_retention": (
                    None
                    if oracle_opportunities == 0
                    else safe_on_opportunity / oracle_opportunities
                ),
            }
        )
    return output


def validate_candidate_crosswalk(
    replay_details: Mapping[tuple[Any, ...], Mapping[str, Any]],
    analyzer_details: Mapping[tuple[Any, ...], Mapping[str, Any]],
    analyzer: Mapping[str, Any],
    differences: Differences,
) -> dict[str, Any]:
    expected = expected_candidate_crosswalk()
    expected_keys = set(expected)
    replay_keys = {str(key[-1]) for key in replay_details}
    analyzer_keys = {str(key[-1]) for key in analyzer_details}
    if replay_keys != expected_keys:
        differences.add(
            "candidate_crosswalk.replay_frontier",
            sorted(replay_keys),
            sorted(expected_keys),
        )
    if analyzer_keys != expected_keys:
        differences.add(
            "candidate_crosswalk.analyzer_frontier",
            sorted(analyzer_keys),
            sorted(expected_keys),
        )
    observed = analyzer.get("candidate_key_crosswalk")
    if not isinstance(observed, dict) or observed != expected:
        differences.add("candidate_crosswalk.mapping", observed, expected)
    if analyzer.get("candidate_key_crosswalk_order_preserving") is not True:
        differences.add(
            "candidate_crosswalk.order_preserving",
            analyzer.get("candidate_key_crosswalk_order_preserving"),
            True,
        )
    for key in replay_keys | analyzer_keys:
        if key.startswith("RLACE::"):
            differences.add("candidate_crosswalk.legacy_cap8_token", key, None)
    return {
        "canonical_candidate_keys": sorted(expected),
        "legacy_candidate_keys": sorted(expected.values()),
        "canonical_to_legacy": expected,
        "crosswalk_sha256": candidate_crosswalk_sha256(expected),
        "one_to_one": len(set(expected.values())) == len(expected),
        "order_preserving": True,
    }


def compare_cap8(
    replay: Mapping[str, Any], analyzer: Mapping[str, Any]
) -> tuple[Differences, dict[str, Any]]:
    differences = Differences()
    if float(replay.get("gamma_cap", -1)) != 8.0 or float(
        analyzer.get("radius_gamma_cap", -1)
    ) != 8.0:
        differences.add("cap8.gamma_cap", replay.get("gamma_cap"), analyzer.get("radius_gamma_cap"))
    replay_profiles = unique_index(
        [normalize_profile(row) for row in replay["profiles"]],
        ("dataset", "seed", "requested_gamma"),
        EXPECTED_PROFILE_COUNT,
        "replay profile",
    )
    analyzer_profiles = unique_index(
        [normalize_profile(row) for row in analyzer["profiles"]],
        ("dataset", "seed", "requested_gamma"),
        EXPECTED_PROFILE_COUNT,
        "analyzer profile",
    )
    compare_indexed(replay_profiles, analyzer_profiles, differences, "profile")
    replay_allocations = unique_index(
        [normalize_allocation(row) for row in replay["allocation_records"]],
        CONFIG_KEY_FIELDS,
        EXPECTED_ALLOCATION_COUNT,
        "replay allocation",
    )
    analyzer_allocations = unique_index(
        [normalize_allocation(row) for row in analyzer["allocation_receipts"]],
        CONFIG_KEY_FIELDS,
        EXPECTED_ALLOCATION_COUNT,
        "analyzer allocation",
    )
    compare_indexed(
        replay_allocations, analyzer_allocations, differences, "allocation"
    )
    replay_rows = unique_index(
        [normalize_row(row) for row in replay["decision_rows"]],
        ROW_KEY_FIELDS,
        EXPECTED_ROW_COUNT,
        "replay row",
    )
    analyzer_rows = unique_index(
        [normalize_row(row) for row in analyzer["rows"]],
        ROW_KEY_FIELDS,
        EXPECTED_ROW_COUNT,
        "analyzer row",
    )
    compare_indexed(replay_rows, analyzer_rows, differences, "row")
    replay_details = unique_index(
        [normalize_detail(row, analyzer=False) for row in replay["candidate_envelope_details"]],
        DETAIL_KEY_FIELDS,
        EXPECTED_DETAIL_COUNT,
        "replay detail",
    )
    analyzer_details = unique_index(
        [normalize_detail(row, analyzer=True) for row in analyzer["candidate_envelopes"]],
        DETAIL_KEY_FIELDS,
        EXPECTED_DETAIL_COUNT,
        "analyzer detail",
    )
    compare_indexed(replay_details, analyzer_details, differences, "detail")
    crosswalk = validate_candidate_crosswalk(
        replay_details, analyzer_details, analyzer, differences
    )
    replay_summaries = unique_index(
        summarize_rows(replay["decision_rows"]),
        SUMMARY_KEY_FIELDS,
        EXPECTED_SUMMARY_COUNT,
        "replay reconstructed summary",
    )
    analyzer_summaries = unique_index(
        analyzer["summaries"],
        SUMMARY_KEY_FIELDS,
        EXPECTED_SUMMARY_COUNT,
        "analyzer summary",
    )
    compare_indexed(
        replay_summaries,
        analyzer_summaries,
        differences,
        "summary",
    )
    compare_value(
        replay["primary_inference"],
        analyzer["primary_inference"],
        "primary_inference",
        differences,
    )
    return differences, {
        "profiles": analyzer_profiles,
        "allocations": analyzer_allocations,
        "rows": analyzer_rows,
        "summaries": analyzer_summaries,
        "candidate_crosswalk": crosswalk,
    }


CAP4_CORE_FIELDS = (
    "deployed",
    "safe",
    "violation",
    "evaluation_violation",
    "selected_candidate",
    "selected_method",
    "q_target",
    "q_leakage",
    "evaluation_target",
    "evaluation_leakage",
    "fixed_profile_limiting_contracts",
    "heldout_leakage",
    "heldout_stress_violation",
    "registered_attacker_q",
    "oracle_deployed",
)


def compare_cap4(
    cap8_analyzer: Mapping[str, Any], cap4: Mapping[str, Any]
) -> tuple[Differences, dict[str, Any]]:
    disallowed = Differences()
    cap8_profiles = unique_index(
        [normalize_profile(row) for row in cap8_analyzer["profiles"]],
        ("dataset", "seed", "requested_gamma"),
        EXPECTED_PROFILE_COUNT,
        "cap8 profile",
    )
    cap4_profiles = unique_index(
        [normalize_profile(row) for row in cap4["profiles"]],
        ("dataset", "seed", "requested_gamma"),
        EXPECTED_PROFILE_COUNT,
        "cap4 profile",
    )
    compare_indexed(cap8_profiles, cap4_profiles, disallowed, "cap4.profile")
    cap8_allocations = unique_index(
        [normalize_allocation(row) for row in cap8_analyzer["allocation_receipts"]],
        CONFIG_KEY_FIELDS,
        EXPECTED_ALLOCATION_COUNT,
        "cap8 allocation",
    )
    cap4_allocations = unique_index(
        [normalize_allocation(row) for row in cap4["allocation_receipts"]],
        CONFIG_KEY_FIELDS,
        EXPECTED_ALLOCATION_COUNT,
        "cap4 allocation",
    )
    compare_indexed(cap8_allocations, cap4_allocations, disallowed, "cap4.allocation")
    cap8_rows = unique_index(
        [normalize_row(row) for row in cap8_analyzer["rows"]],
        ROW_KEY_FIELDS,
        EXPECTED_ROW_COUNT,
        "cap8 row",
    )
    cap4_rows = unique_index(
        [normalize_row(row, legacy=True) for row in cap4["rows"]],
        ROW_KEY_FIELDS,
        EXPECTED_ROW_COUNT,
        "cap4 row",
    )
    difference_counts = {
        "certified_common_radius": 0,
        "target_environment_intercepts": 0,
        "source_class_intercepts": 0,
        "axis_limiting_coordinates": 0,
    }
    geometry_difference_rows: set[tuple[Any, ...]] = set()
    candidate_difference_rows: set[tuple[Any, ...]] = set()
    decision_difference_rows: set[tuple[Any, ...]] = set()
    for key in sorted(cap8_rows):
        left = cap8_rows[key]
        right = cap4_rows[key]
        for field in CAP4_CORE_FIELDS:
            compare_value(
                left[field], right[field], f"cap4.row{key}.{field}", disallowed
            )
        if (
            abs(
                float(left["certified_common_radius"])
                - float(right["certified_common_radius"])
            )
            > RADIUS_TOLERANCE
        ):
            difference_counts["certified_common_radius"] += 1
            geometry_difference_rows.add(key)
        if left["target_environment_radii"] != right["target_environment_radii"]:
            difference_counts["target_environment_intercepts"] += 1
            geometry_difference_rows.add(key)
        if left["source_class_radii"] != right["source_class_radii"]:
            difference_counts["source_class_intercepts"] += 1
            geometry_difference_rows.add(key)
        if left["limiting_coordinates"] != right["limiting_coordinates"]:
            difference_counts["axis_limiting_coordinates"] += 1
            geometry_difference_rows.add(key)
        if left["selected_candidate"] != right["selected_candidate"]:
            candidate_difference_rows.add(key)
        if any(
            left[field] != right[field]
            for field in (
                "deployed",
                "safe",
                "violation",
                "evaluation_violation",
            )
        ):
            decision_difference_rows.add(key)
    cap8_summaries = unique_index(
        cap8_analyzer["summaries"],
        SUMMARY_KEY_FIELDS,
        EXPECTED_SUMMARY_COUNT,
        "cap8 summary",
    )
    cap4_summaries = unique_index(
        cap4["summaries"],
        SUMMARY_KEY_FIELDS,
        EXPECTED_SUMMARY_COUNT,
        "cap4 summary",
    )
    cap4_reconstructed = unique_index(
        summarize_rows(cap4["rows"]),
        SUMMARY_KEY_FIELDS,
        EXPECTED_SUMMARY_COUNT,
        "cap4 reconstructed summary",
    )
    compare_indexed(
        cap4_reconstructed,
        cap4_summaries,
        disallowed,
        "cap4.summary_reconstruction",
    )
    compare_indexed(
        cap8_summaries,
        cap4_summaries,
        disallowed,
        "cap4.summary_cap_independent",
    )
    cap8_primary = dict(cap8_analyzer["primary_inference"])
    cap4_primary = dict(cap4["primary_inference"])
    geometry_aggregate_fields = (
        "common_radius_distribution_on_vector_deployments",
        "limiting_coordinate_counts",
        "common_limiting_contract_counts",
    )
    geometry_aggregate_difference_count = sum(
        cap8_primary.get(key) != cap4_primary.get(key)
        for key in geometry_aggregate_fields
    )
    for key in geometry_aggregate_fields:
        cap8_primary.pop(key, None)
        cap4_primary.pop(key, None)
    compare_value(
        cap8_primary,
        cap4_primary,
        "cap4.primary_cap_independent",
        disallowed,
    )
    gate_paths = {
        "paired_reduction": ("paired_reduction", "passed"),
        "safety": ("safety", "passed"),
        "usefulness": ("usefulness", "passed"),
        "vector_advantage": ("vector_advantage", "passed"),
        "overall_confirmatory_success": ("overall_confirmatory_success",),
    }

    def nested(record: Mapping[str, Any], path: tuple[str, ...]) -> Any:
        value: Any = record
        for token in path:
            if not isinstance(value, Mapping):
                return None
            value = value.get(token)
        return value

    gate_differences = [
        name
        for name, path in gate_paths.items()
        if nested(cap8_analyzer["primary_inference"], path)
        != nested(cap4["primary_inference"], path)
    ]
    return disallowed, {
        "allowed_geometry_difference_counts": difference_counts,
        "cap_dependent_geometry_row_difference_count": len(
            geometry_difference_rows
        ),
        "cap_dependent_candidate_difference_count": len(
            candidate_difference_rows
        ),
        "cap_dependent_decision_difference_count": len(decision_difference_rows),
        "cap_dependent_aggregate_difference_count": int(
            geometry_aggregate_difference_count
        ),
        "primary_gate_differences": gate_differences,
        "primary_gate_differs": bool(gate_differences),
    }


def compare(args: argparse.Namespace) -> dict[str, Any]:
    replay = load_json(args.replay)
    cap8 = load_json(args.cap8)
    cap4 = load_json(args.cap4)
    cap8_differences, cap8_records = compare_cap8(replay, cap8)
    cap4_disallowed, cap4_report = compare_cap4(cap8, cap4)
    passed = cap8_differences.count == 0 and cap4_disallowed.count == 0
    return {
        "schema_version": 1,
        "name": "VERA sealed three-way first-read comparison",
        "passed": passed,
        "input_sha256": {
            "independent_cap8_replay": sha256(args.replay),
            "protocol_cap8_analyzer": sha256(args.cap8),
            "locked_cap4_analyzer": sha256(args.cap4),
        },
        "cap8_equality": {
            "passed": cap8_differences.count == 0,
            "mismatch_count": cap8_differences.count,
            "first_mismatches": cap8_differences.examples,
            "floating_tolerance": FLOAT_TOLERANCE,
            "radius_tolerance": RADIUS_TOLERANCE,
            "candidate_key_crosswalk": cap8_records["candidate_crosswalk"],
        },
        "cap4_semantic_difference": {
            "passed": cap4_disallowed.count == 0,
            "disallowed_mismatch_count": cap4_disallowed.count,
            "first_disallowed_mismatches": cap4_disallowed.examples,
            **cap4_report,
            "candidate_key_order_preserved": cap8_records[
                "candidate_crosswalk"
            ]["order_preserving"],
            "candidate_key_attributed_decision_difference_count": (
                0 if passed else None
            ),
            "cap_independent_mismatch_count": cap4_disallowed.count,
        },
        "scientific_first_read": (
            {
                "authoritative_cap8_primary_inference": cap8["primary_inference"],
                "locked_cap4_primary_inference": cap4["primary_inference"],
            }
            if passed
            else None
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--cap8", type=Path, required=True)
    parser.add_argument("--cap4", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = compare(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "cap8_mismatch_count": report["cap8_equality"]["mismatch_count"],
                "cap4_disallowed_mismatch_count": report[
                    "cap4_semantic_difference"
                ]["disallowed_mismatch_count"],
                "output": str(args.output),
                "output_sha256": sha256(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
