"""Generate a complete synthetic VERA manifest without scientific outcomes."""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Mapping

from mini_jsonschema import Validator


MISSING = object()


class FixtureBuilder:
    def __init__(self, root: Mapping[str, Any]):
        self.root = root
        self.validator = Validator(root)

    def resolve(self, reference: str) -> Mapping[str, Any]:
        return self.validator.resolve(reference)

    def scalar(self, schema: Mapping[str, Any]) -> Any:
        expected = schema.get("type")
        choices = [expected] if isinstance(expected, str) else list(expected or [])
        preferred = choices[0] if choices else None
        if preferred == "null":
            return None
        if preferred == "boolean":
            return False
        if preferred == "integer":
            lower = int(schema.get("minimum", 0))
            if "exclusiveMinimum" in schema:
                lower = max(lower, math_floor(schema["exclusiveMinimum"]) + 1)
            return lower
        if preferred == "number":
            lower = float(schema.get("minimum", 0.0))
            if "exclusiveMinimum" in schema:
                lower = max(lower, float(schema["exclusiveMinimum"]) + 0.5)
            if "maximum" in schema:
                lower = min(lower, float(schema["maximum"]))
            return lower
        if preferred == "string" or "pattern" in schema or "minLength" in schema:
            if schema.get("format") == "date-time":
                return "2026-07-16T00:00:00Z"
            pattern = str(schema.get("pattern", ""))
            if pattern == "^[0-9a-f]{64}$":
                return "a" * 64
            return "x" * max(1, int(schema.get("minLength", 1)))
        return MISSING

    def build(self, schema: Any, current: Any = MISSING) -> Any:
        if schema is True:
            return None if current is MISSING else current
        if schema is False:
            raise ValueError("cannot build a false schema")
        if "$ref" in schema:
            value = self.build(self.resolve(schema["$ref"]), current)
            siblings = {key: item for key, item in schema.items() if key != "$ref"}
            return self.build(siblings, value) if siblings else value
        if "const" in schema:
            return copy.deepcopy(schema["const"])
        if "enum" in schema and (
            current is MISSING
            or not any(current == item and type(current) is type(item) for item in schema["enum"])
        ):
            current = copy.deepcopy(schema["enum"][0])
        if "oneOf" in schema:
            current = self.build(schema["oneOf"][-1], current)
        elif "anyOf" in schema:
            current = self.build(schema["anyOf"][0], current)
        expected = schema.get("type")
        choices = [expected] if isinstance(expected, str) else list(expected or [])
        if "object" in choices or "properties" in schema or "required" in schema:
            if not isinstance(current, dict):
                current = {}
            properties = schema.get("properties", {})
            keys = list(dict.fromkeys([*schema.get("required", []), *current]))
            for key in keys:
                if key in properties or key in schema.get("required", []):
                    current[key] = self.build(
                        properties.get(key, {}), current.get(key, MISSING)
                    )
        elif "array" in choices or any(
            key in schema for key in ("items", "prefixItems", "minItems", "contains")
        ):
            if not isinstance(current, list):
                current = []
            prefix = schema.get("prefixItems", [])
            for index, item_schema in enumerate(prefix):
                if index < len(current):
                    current[index] = self.build(item_schema, current[index])
                else:
                    current.append(self.build(item_schema))
            minimum = max(int(schema.get("minItems", 0)), len(prefix))
            item_schema = schema.get("items", {})
            while len(current) < minimum:
                current.append(self.build(item_schema))
            if schema.get("uniqueItems") and isinstance(item_schema, dict):
                for index in range(len(prefix), len(current)):
                    if isinstance(current[index], int):
                        current[index] += index - len(prefix)
            if "contains" in schema and int(schema.get("minContains", 1)) > 0:
                if not any(
                    not self.validator.errors(item, schema["contains"])
                    for item in current
                ):
                    candidate = (
                        copy.deepcopy(current[0])
                        if current and item_schema == {}
                        else self.build(item_schema)
                    )
                    candidate = self.build(schema["contains"], candidate)
                    encoded = [json.dumps(item, sort_keys=True) for item in current]
                    duplicate = next(
                        (
                            index
                            for index, item in enumerate(encoded)
                            if encoded.count(item) > 1
                        ),
                        None,
                    )
                    maximum = schema.get("maxItems")
                    if duplicate is not None:
                        current[duplicate] = candidate
                    elif maximum is None or len(current) < int(maximum):
                        current.append(candidate)
                    else:
                        current[0] = candidate
        elif current is MISSING:
            scalar = self.scalar(schema)
            current = None if scalar is MISSING else scalar
        for branch in schema.get("allOf", []):
            current = self.build(branch, current)
        if "if" in schema:
            branch = "then" if not self.validator.errors(current, schema["if"]) else "else"
            if branch in schema:
                current = self.build(schema[branch], current)
        return current


def math_floor(value: float) -> int:
    integer = int(value)
    return integer if integer <= value else integer - 1


def build_fixture(schema: Mapping[str, Any]) -> dict[str, Any]:
    value = FixtureBuilder(schema).build(schema)
    if not isinstance(value, dict):
        raise RuntimeError("manifest fixture is not an object")
    rule_order = (
        "always_deploy",
        "validation_point_selection",
        "iid_ltt",
        "robust_point_estimate",
        "generic_scalar_robust_certificate",
        "vera_fixed_profile",
        "vera_vector_envelope",
        "vera_common_radius",
        "external_oracle",
    )
    value["rule_results"].sort(key=lambda row: rule_order.index(row["rule"]))
    dataset_order = ("Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB")
    for rule in value["rule_results"]:
        rule["per_dataset"].sort(
            key=lambda row: dataset_order.index(row["dataset"])
        )
    safe = value["primary"]["safe_retention"]
    safe["status"] = "pass"
    safe["effect"].update(
        {
            "safe_opportunities": 100,
            "retained_opportunities": 50,
            "retention": {"numerator": 50, "denominator": 100, "estimate": 0.5},
        }
    )
    safe["interval"].update({"lower": 0.30, "upper": 0.70})
    safe_sensitivity = safe["zero_opportunity_sensitivity"]
    safe_sensitivity.update(
        {
            "positive_opportunity_resamples": 20_000,
            "zero_opportunity_resamples": 0,
            "supports_registered_threshold": True,
        }
    )
    safe_sensitivity["completed_statistic_interval"].update(
        {"lower": 0.30, "upper": 0.70}
    )
    safe_sensitivity["division_free_margin_interval"].update(
        {"lower": 1.0, "upper": 40.0}
    )
    advantage = value["primary"]["vector_common_advantage"]
    advantage["status"] = "pass"
    advantage["effect"].update(
        {
            "vector_retention": {
                "numerator": 50,
                "denominator": 100,
                "estimate": 0.5,
            },
            "common_retention": {
                "numerator": 20,
                "denominator": 100,
                "estimate": 0.2,
            },
            "ratio": 2.5,
            "ratio_status": "finite",
        }
    )
    advantage["effect"]["registered_ratio_interval"].update(
        {"lower": 2.1, "upper": 3.0}
    )
    advantage["effect"]["zero_denominator_sensitivity_interval"].update(
        {"lower": 2.1, "upper": 3.0}
    )
    advantage["effect"]["division_free_interval"].update(
        {"lower": 0.01, "upper": 0.20}
    )
    advantage["interval"].update({"lower": 2.1, "upper": 3.0})
    cases = advantage["test"]["zero_denominator_cases"]
    cases["positive_opportunity_positive_common"] = 20_000
    value["gait_diagnostic"]["limiting_contract_counts"] = {"target_harm": 0}
    value["title_decision"].update(
        {
            "title_branch": "support_aware",
            "literature_condition": False,
            "allocation_condition": False,
        }
    )
    value["negative_results"] = [
        record
        for record in value["negative_results"]
        if record["id"]
        not in {"x", "safe_retention_zero_opportunity_sensitivity_disagrees"}
    ]
    efficacy = value["primary"]["efficacy"]
    efficacy["effect"].update(
        {
            "point_violations": 20,
            "vector_violations": 0,
            "paired_difference_estimate": 20 / 256,
        }
    )
    efficacy["test"].update(
        {
            "positive_seed_differences": 10,
            "negative_seed_differences": 0,
            "ties": 54,
            "nonzero_denominator": 10,
            "p_value": 0.001,
        }
    )
    sentinel = value["primary"]["sentinel_safety"]
    sentinel["test"]["upper_bound"] = 0.045729702330762456
    sentinel["interval"].update({"lower": 0.0, "upper": 0.045729702330762456})
    value["safety_sensitivity"]["vector_violating_dataset_count_by_seed"] = [
        64,
        0,
        0,
        0,
        0,
    ]
    value["heldout_attacker_result"]["heldout_safe_fraction"] = None
    value["figure_candidate"]["selected_by_vector"] = True
    for contrast in value["allocation"]["pairwise_contrasts"]:
        contrast.update(
            {
                "positive_seed_differences": 0,
                "negative_seed_differences": 0,
                "ties": 64,
                "nonzero_denominator": 0,
            }
        )

    def normalize_intervals(item: Any) -> None:
        if isinstance(item, dict):
            if {"numerator", "denominator", "estimate"} <= set(item):
                denominator = int(item["denominator"])
                item["estimate"] = (
                    None if denominator == 0 else item["numerator"] / denominator
                )
            if {"level", "lower", "upper", "method", "independent_unit"} <= set(item):
                item["level"] = 0.95
            for child in item.values():
                normalize_intervals(child)
        elif isinstance(item, list):
            for child in item:
                normalize_intervals(child)

    normalize_intervals(value)
    return value
