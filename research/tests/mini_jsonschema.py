"""Small fail-closed validator for the JSON Schema features used by VERA."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any, Mapping, Sequence


def same_json(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isfinite(float(left)) and math.isfinite(float(right)) and left == right
    return type(left) is type(right) and left == right


def json_type(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        )
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    raise ValueError(f"unsupported JSON type: {expected}")


class Validator:
    def __init__(self, root: Mapping[str, Any]):
        self.root = root

    def resolve(self, reference: str) -> Mapping[str, Any]:
        if not reference.startswith("#/"):
            raise ValueError(f"only local references are supported: {reference}")
        value: Any = self.root
        for token in reference[2:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            value = value[token]
        if not isinstance(value, dict):
            raise ValueError(f"reference is not a schema object: {reference}")
        return value

    def errors(
        self, value: Any, schema: Any | None = None, path: str = "$"
    ) -> list[str]:
        active = self.root if schema is None else schema
        if active is True:
            return []
        if active is False:
            return [f"{path}: false schema"]
        if not isinstance(active, dict):
            return [f"{path}: malformed schema"]
        errors: list[str] = []
        if "$ref" in active:
            errors.extend(self.errors(value, self.resolve(active["$ref"]), path))
            siblings = {key: item for key, item in active.items() if key != "$ref"}
            if siblings:
                errors.extend(self.errors(value, siblings, path))
            return errors
        if "const" in active and not same_json(value, active["const"]):
            errors.append(f"{path}: does not equal const")
        if "enum" in active and not any(same_json(value, item) for item in active["enum"]):
            errors.append(f"{path}: is not in enum")
        if "type" in active:
            expected = active["type"]
            choices = [expected] if isinstance(expected, str) else list(expected)
            if not any(json_type(value, choice) for choice in choices):
                errors.append(f"{path}: wrong type; expected {choices}")
                return errors
        for branch in active.get("allOf", []):
            errors.extend(self.errors(value, branch, path))
        if "anyOf" in active:
            outcomes = [self.errors(value, branch, path) for branch in active["anyOf"]]
            if all(outcome for outcome in outcomes):
                errors.append(f"{path}: no anyOf branch matched")
        if "oneOf" in active:
            matches = sum(
                not self.errors(value, branch, path) for branch in active["oneOf"]
            )
            if matches != 1:
                errors.append(f"{path}: expected one oneOf match, observed {matches}")
        if "not" in active and not self.errors(value, active["not"], path):
            errors.append(f"{path}: forbidden schema matched")
        if "if" in active:
            branch = "then" if not self.errors(value, active["if"], path) else "else"
            if branch in active:
                errors.extend(self.errors(value, active[branch], path))
        if isinstance(value, dict):
            required = active.get("required", [])
            for key in required:
                if key not in value:
                    errors.append(f"{path}: missing required property {key!r}")
            properties = active.get("properties", {})
            for key, item in value.items():
                child = f"{path}.{key}"
                if key in properties:
                    errors.extend(self.errors(item, properties[key], child))
                elif active.get("additionalProperties") is False:
                    errors.append(f"{child}: additional property is forbidden")
                elif isinstance(active.get("additionalProperties"), dict):
                    errors.extend(
                        self.errors(item, active["additionalProperties"], child)
                    )
            if len(value) < int(active.get("minProperties", 0)):
                errors.append(f"{path}: fewer than minProperties")
            if "maxProperties" in active and len(value) > int(active["maxProperties"]):
                errors.append(f"{path}: more than maxProperties")
        if isinstance(value, list):
            if len(value) < int(active.get("minItems", 0)):
                errors.append(f"{path}: fewer than minItems")
            if "maxItems" in active and len(value) > int(active["maxItems"]):
                errors.append(f"{path}: more than maxItems")
            if active.get("uniqueItems"):
                encoded = [
                    json.dumps(item, sort_keys=True, separators=(",", ":"))
                    for item in value
                ]
                if len(encoded) != len(set(encoded)):
                    errors.append(f"{path}: array items are not unique")
            prefix = active.get("prefixItems", [])
            for index, item_schema in enumerate(prefix[: len(value)]):
                errors.extend(self.errors(value[index], item_schema, f"{path}[{index}]"))
            if "items" in active:
                if active["items"] is False and len(value) > len(prefix):
                    errors.append(f"{path}: items after prefix are forbidden")
                elif isinstance(active["items"], dict):
                    for index in range(len(prefix), len(value)):
                        errors.extend(
                            self.errors(value[index], active["items"], f"{path}[{index}]")
                        )
            if "contains" in active:
                count = sum(
                    not self.errors(item, active["contains"], f"{path}[{index}]")
                    for index, item in enumerate(value)
                )
                minimum = int(active.get("minContains", 1))
                maximum = active.get("maxContains")
                if count < minimum:
                    errors.append(f"{path}: contains count {count} below {minimum}")
                if maximum is not None and count > int(maximum):
                    errors.append(f"{path}: contains count {count} above {maximum}")
        if isinstance(value, str):
            if len(value) < int(active.get("minLength", 0)):
                errors.append(f"{path}: string shorter than minLength")
            if "maxLength" in active and len(value) > int(active["maxLength"]):
                errors.append(f"{path}: string longer than maxLength")
            if "pattern" in active and re.search(active["pattern"], value) is None:
                errors.append(f"{path}: string does not match pattern")
            if active.get("format") == "date-time":
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    errors.append(f"{path}: invalid date-time")
        if (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
        ):
            if "minimum" in active and value < active["minimum"]:
                errors.append(f"{path}: below minimum")
            if "maximum" in active and value > active["maximum"]:
                errors.append(f"{path}: above maximum")
            if "exclusiveMinimum" in active and value <= active["exclusiveMinimum"]:
                errors.append(f"{path}: below exclusiveMinimum")
            if "exclusiveMaximum" in active and value >= active["exclusiveMaximum"]:
                errors.append(f"{path}: above exclusiveMaximum")
        return errors

    def check(self, value: Any) -> None:
        errors = self.errors(value)
        if errors:
            raise RuntimeError("\n".join(errors[:100]))


def validate(value: Any, schema: Mapping[str, Any]) -> list[str]:
    return Validator(schema).errors(value)
