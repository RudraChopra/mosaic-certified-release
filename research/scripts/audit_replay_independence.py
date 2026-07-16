"""Static fail-closed independence audit for the isolated replay source."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


ALLOWED_IMPORT_ROOTS = {
    "__future__",
    "argparse",
    "collections",
    "hashlib",
    "json",
    "pathlib",
    "typing",
    "numpy",
    "scipy",
}
FORBIDDEN_SOURCE_NAMES = (
    "analyze_controlled_shift_confirmatory",
    "design_vera_controlled_shift_study",
    "vera_controlled_shift",
    "vera_robust_certificate",
    "build_vera_confirmatory_results",
    "build_vera_results_package",
)
FORBIDDEN_CALL_NAMES = {
    "__import__",
    "compile",
    "eval",
    "exec",
}
FORBIDDEN_ATTRIBUTE_ROOTS = {
    "ctypes",
    "importlib",
    "subprocess",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def attribute_root(node: ast.Attribute) -> str | None:
    value: ast.expr = node
    while isinstance(value, ast.Attribute):
        value = value.value
    return value.id if isinstance(value, ast.Name) else None


def audit_source(
    replay_source: Path,
    forbidden_sources: list[Path],
) -> dict[str, Any]:
    text = replay_source.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(replay_source))
    errors: list[str] = []
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                imports.append(alias.name)
                if root not in ALLOWED_IMPORT_ROOTS:
                    errors.append(f"forbidden import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                errors.append(f"relative import is forbidden at line {node.lineno}")
                continue
            module = str(node.module or "")
            imports.append(module)
            if module.split(".", 1)[0] not in ALLOWED_IMPORT_ROOTS:
                errors.append(f"forbidden import-from: {module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALL_NAMES:
                errors.append(
                    f"dynamic evaluation/import call is forbidden: "
                    f"{node.func.id} at line {node.lineno}"
                )
            elif isinstance(node.func, ast.Attribute):
                root = attribute_root(node.func)
                if root in FORBIDDEN_ATTRIBUTE_ROOTS:
                    errors.append(
                        f"forbidden dynamic/shell API: {root} at line {node.lineno}"
                    )
                if root == "os" and node.func.attr in {
                    "popen",
                    "spawnl",
                    "spawnle",
                    "spawnlp",
                    "spawnlpe",
                    "spawnv",
                    "spawnve",
                    "spawnvp",
                    "spawnvpe",
                    "system",
                }:
                    errors.append(f"forbidden shell API: os.{node.func.attr}")
    lowered = text.casefold()
    for name in FORBIDDEN_SOURCE_NAMES:
        if name.casefold() in lowered:
            errors.append(f"forbidden project-source reference: {name}")
    forbidden_hashes: dict[str, str] = {}
    for path in forbidden_sources:
        if not path.is_file():
            errors.append(f"forbidden source is missing from the audit set: {path.name}")
        else:
            forbidden_hashes[path.name] = sha256(path)
    return {
        "name": "VERA independent replay static source audit",
        "passed": not errors,
        "replay_source_name": replay_source.name,
        "replay_source_sha256": sha256(replay_source),
        "imports": sorted(set(imports)),
        "allowed_import_roots": sorted(ALLOWED_IMPORT_ROOTS),
        "forbidden_source_sha256": dict(sorted(forbidden_hashes.items())),
        "errors": errors,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replay-source", type=Path, required=True)
    parser.add_argument("--forbidden-source", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = audit_source(args.replay_source, args.forbidden_source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "error_count": len(report["errors"]),
                "output": str(args.output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
