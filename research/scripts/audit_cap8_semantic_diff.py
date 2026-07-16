"""Static outcome-blind audit of the authorized cap-8 analysis changes."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


LOCKED_ANALYZER_SHA256 = (
    "c4858136e189a4b9ecdbe55fd912c6cf83e6dce42a3320add581f18d596180ad"
)
CRITICAL_IMPORTED_NAMES = {
    "BUDGETS",
    "DATASETS",
    "FRESH_SEEDS",
    "GAMMAS",
    "PRIMARY_ALLOCATION",
    "PRIMARY_BUDGET",
    "PRIMARY_GAMMA",
    "array_sha256",
    "attach_stress_metrics",
    "primary_inference",
}
EXACT_ANALYZE_CALLS = (
    "allocation_scores",
    "allocate_integer_budget",
    "attach_stress_metrics",
    "default_rng",
    "design_controlled_shift_from_fold",
    "primary_inference",
    "q_metrics",
    "sampled_metrics",
    "summarize",
)
EXPECTED_RULES = {
    "always_deploy",
    "validation_point_selection",
    "iid_ltt",
    "robust_point_estimate",
    "generic_scalar_robust_certificate",
    "vera_fixed_profile",
    "vera_vector_envelope",
    "vera_common_radius",
    "external_oracle",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def function(tree: ast.Module, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one function named {name}, found {len(matches)}")
    return matches[0]


def call_name(call: ast.Call) -> str:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return ""


def calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Call) and call_name(child) == name
    ]


def dumps(values: Iterable[ast.AST]) -> list[str]:
    return sorted(ast.dump(value, include_attributes=False) for value in values)


def imported_from(tree: ast.Module, module: str) -> set[str]:
    output: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == module:
            output.update(alias.name for alias in node.names)
    return output


def import_aliases(tree: ast.Module, module: str) -> dict[str, str | None]:
    output: dict[str, str | None] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == module:
            output.update({alias.name: alias.asname for alias in node.names})
    return output


def assignment_value(tree: ast.Module, name: str) -> ast.AST:
    values: list[ast.AST] = []
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            if node.value is not None:
                values.append(node.value)
    if len(values) != 1:
        raise RuntimeError(f"expected one assignment to {name}, found {len(values)}")
    return values[0]


def normalized_evaluator_call(call: ast.Call, *, cap8: bool) -> str:
    clone = ast.parse(ast.unparse(call), mode="eval").body
    if not isinstance(clone, ast.Call):
        raise RuntimeError("evaluator expression is not a call")
    if cap8:
        if not isinstance(clone.func, ast.Name) or clone.func.id != "evaluate_configuration_cap":
            raise RuntimeError("cap-8 analyzer does not call its authorized evaluator")
        clone.func.id = "evaluate_configuration"
        gamma_keywords = [key for key in clone.keywords if key.arg == "gamma_cap"]
        if len(gamma_keywords) != 1 or not isinstance(gamma_keywords[0].value, ast.Name):
            raise RuntimeError("cap-8 evaluator does not receive the verified cap variable")
        if gamma_keywords[0].value.id != "gamma_cap":
            raise RuntimeError("cap-8 evaluator receives the wrong cap expression")
        clone.keywords = [key for key in clone.keywords if key.arg != "gamma_cap"]
    return ast.dump(clone, include_attributes=False)


def selection_rule_names(evaluator: ast.Module) -> set[str]:
    target = function(evaluator, "evaluate_configuration_cap")
    for node in ast.walk(target):
        if not isinstance(node, ast.Assign):
            continue
        if not any(
            isinstance(item, ast.Name) and item.id == "selections"
            for item in node.targets
        ):
            continue
        if not isinstance(node.value, ast.Dict):
            raise RuntimeError("selection rules are not a static dictionary")
        if not all(
            isinstance(key, ast.Constant) and isinstance(key.value, str)
            for key in node.value.keys
        ):
            raise RuntimeError("selection rules contain a dynamic key")
        return {str(key.value) for key in node.value.keys}
    raise RuntimeError("selection rule dictionary is missing")


def audit(locked_path: Path, cap8_path: Path, evaluator_path: Path) -> dict[str, Any]:
    failures: list[str] = []
    locked_hash = sha256(locked_path)
    if locked_hash != LOCKED_ANALYZER_SHA256:
        failures.append("locked analyzer hash changed")
    locked = parse(locked_path)
    cap8 = parse(cap8_path)
    evaluator = parse(evaluator_path)
    locked_analyze = function(locked, "analyze")
    cap8_analyze = function(cap8, "analyze")

    imported = imported_from(cap8, "analyze_controlled_shift_confirmatory")
    if imported != CRITICAL_IMPORTED_NAMES:
        failures.append("critical locked imports differ")
    if any(
        alias is not None
        for alias in import_aliases(
            cap8, "analyze_controlled_shift_confirmatory"
        ).values()
    ):
        failures.append("critical locked imports are aliased")
    local_functions = {
        node.name for node in cap8.body if isinstance(node, ast.FunctionDef)
    }
    if local_functions & CRITICAL_IMPORTED_NAMES:
        failures.append("cap-8 source shadows a locked scientific function")

    for name in EXACT_ANALYZE_CALLS:
        if dumps(calls(locked_analyze, name)) != dumps(calls(cap8_analyze, name)):
            failures.append(f"analyze call changed: {name}")

    locked_eval = calls(locked_analyze, "evaluate_configuration")
    cap8_eval = calls(cap8_analyze, "evaluate_configuration_cap")
    if len(locked_eval) != 1 or len(cap8_eval) != 1:
        failures.append("wrong evaluator call cardinality")
    else:
        try:
            if normalized_evaluator_call(
                locked_eval[0], cap8=False
            ) != normalized_evaluator_call(cap8_eval[0], cap8=True):
                failures.append("evaluator arguments changed outside gamma_cap")
        except RuntimeError as exc:
            failures.append(str(exc))

    try:
        gamma_literal = ast.literal_eval(assignment_value(cap8, "EXPECTED_GAMMA_CAP"))
        if float(gamma_literal) != 8.0:
            failures.append("expected gamma cap is not 8")
    except (RuntimeError, ValueError, TypeError):
        failures.append("expected gamma cap is not a single numeric literal")
    gamma_reads = [
        node
        for node in ast.walk(cap8_analyze)
        if isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Name)
        and node.value.id == "study"
        and isinstance(node.slice, ast.Constant)
        and node.slice.value == "gamma_cap"
    ]
    if len(gamma_reads) != 1:
        failures.append("gamma cap is not read exactly once from the verified study")

    if selection_rule_names(evaluator) != EXPECTED_RULES:
        failures.append("evaluator rule set changed")
    design_imports = imported_from(evaluator, "design_vera_controlled_shift_study")
    if design_imports != {
        "ATTACKERS",
        "candidate_certification_data",
        "choose",
        "point_metrics",
        "sample_streams",
    }:
        failures.append("evaluator does not reuse the locked sampling or tie-break functions")
    if any(
        alias is not None
        for alias in import_aliases(
            evaluator, "design_vera_controlled_shift_study"
        ).values()
    ):
        failures.append("locked sampling or tie-break imports are aliased")
    if (
        len(
            calls(
                function(evaluator, "evaluate_configuration_cap"),
                "certify_balanced_shift_envelope",
            )
        )
        != 1
    ):
        failures.append("cap-8 envelope call cardinality changed")

    return {
        "schema_version": 1,
        "name": "VERA cap-8 authorized semantic-difference audit",
        "passed": not failures,
        "failures": failures,
        "source_sha256": {
            "locked_cap4_analyzer": locked_hash,
            "protocol_cap8_analyzer": sha256(cap8_path),
            "cap8_evaluator": sha256(evaluator_path),
        },
        "locked_scientific_calls_equal": not any(
            value.startswith("analyze call changed") for value in failures
        ),
        "only_evaluator_argument_extension": (
            "evaluator arguments changed outside gamma_cap" not in failures
        ),
        "registered_cap_source_verified": not any(
            "gamma cap" in value for value in failures
        ),
        "rule_set_verified": "evaluator rule set changed" not in failures,
        "locked_tie_break_reused": (
            "evaluator does not reuse the locked sampling or tie-break functions"
            not in failures
        ),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--locked", type=Path, required=True)
    parser.add_argument("--cap8", type=Path, required=True)
    parser.add_argument("--evaluator", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit(args.locked, args.cap8, args.evaluator)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "failure_count": len(report["failures"]),
                "source_sha256": report["source_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
