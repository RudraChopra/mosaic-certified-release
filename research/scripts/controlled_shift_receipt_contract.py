"""Closed-set structural audit for VERA controlled-shift receipts."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np


SPLITS = ("certification", "external")
ATTACKERS = ("linear", "rbf", "forest", "mlp")
CANONICAL_METHOD = {
    "inlp": "INLP",
    "rlace": "R-LACE",
    "leace": "LEACE",
    "taco": "TaCo",
    "mance": "MANCE++",
}
BASE_ARRAYS = {
    f"{field}_{split}"
    for field in (
        "target_harm",
        "identity_target_error",
        "edited_target_error",
        "source",
        "environment",
        "target",
    )
    for split in SPLITS
}
ATTACKER_ARRAYS = {
    f"leakage_correct_{split}__{attacker}"
    for split in SPLITS
    for attacker in ATTACKERS
}
HELDOUT_ARRAYS = {
    f"heldout_leakage_correct_{split}__boosted_tree" for split in SPLITS
}
EXPECTED_ARRAYS = BASE_ARRAYS | ATTACKER_ARRAYS | HELDOUT_ARRAYS
BINARY_PREFIXES = (
    "identity_target_error_",
    "edited_target_error_",
    "leakage_correct_",
    "heldout_leakage_correct_",
)


@dataclass
class TreeScan:
    regular_files: dict[str, os.stat_result]
    directories: set[str]
    all_entries: set[str]
    errors: list[str]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def case_collisions(paths: Iterable[str]) -> list[list[str]]:
    folded: dict[str, list[str]] = {}
    for path in paths:
        folded.setdefault(path.casefold(), []).append(path)
    return [sorted(values) for values in folded.values() if len(values) > 1]


def symlink_components(path: Path) -> list[str]:
    absolute = path.expanduser().absolute()
    current = Path(absolute.anchor)
    links: list[str] = []
    for part in absolute.parts[1:]:
        current /= part
        try:
            if stat.S_ISLNK(current.lstat().st_mode):
                links.append(str(current))
        except OSError:
            break
    return links


def scan_tree(root: Path, label: str) -> TreeScan:
    regular: dict[str, os.stat_result] = {}
    directories: set[str] = set()
    entries: set[str] = set()
    errors: list[str] = []
    try:
        root_stat = root.lstat()
    except OSError as exc:
        return TreeScan({}, set(), set(), [f"{label} root is unavailable: {exc}"])
    if stat.S_ISLNK(root_stat.st_mode) or not stat.S_ISDIR(root_stat.st_mode):
        errors.append(f"{label} root is not a real directory: {root}")
        return TreeScan({}, set(), set(), errors)
    links = symlink_components(root)
    if links:
        errors.append(f"{label} root resolves through symlink components: {links}")

    def visit(directory: Path) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            errors.append(f"cannot scan {label} directory {directory}: {exc}")
            return
        for child in children:
            path = Path(child.path)
            relative = path.relative_to(root).as_posix()
            entries.add(relative)
            try:
                observed = child.stat(follow_symlinks=False)
            except OSError as exc:
                errors.append(f"cannot stat {label} entry {relative}: {exc}")
                continue
            mode = observed.st_mode
            if stat.S_ISLNK(mode):
                errors.append(f"{label} symlink is forbidden: {relative}")
            elif stat.S_ISDIR(mode):
                directories.add(relative)
                visit(path)
            elif stat.S_ISREG(mode):
                regular[relative] = observed
                if observed.st_nlink != 1:
                    errors.append(
                        f"{label} hard-linked file is forbidden: {relative} "
                        f"(nlink={observed.st_nlink})"
                    )
            else:
                errors.append(f"{label} special file is forbidden: {relative}")

    visit(root)
    collisions = case_collisions(entries)
    if collisions:
        errors.append(f"{label} case-colliding paths: {collisions}")
    return TreeScan(regular, directories, entries, errors)


def expected_strengths(method_key: str, config: dict[str, Any]) -> tuple[str, ...]:
    candidate = config.get("candidate_configuration", {})
    candidate = candidate if isinstance(candidate, dict) else {}
    if method_key == "inlp":
        return tuple(f"rank={int(value)}" for value in candidate.get("ranks", []))
    if method_key == "rlace":
        return tuple(f"rank={int(value)}" for value in candidate.get("ranks", []))
    if method_key == "leace":
        return (str(candidate.get("candidate", "")),)
    if method_key == "taco":
        return tuple(
            f"components_removed={int(value)}" for value in candidate.get("removals", [])
        )
    if method_key == "mance":
        epsilon = float(candidate.get("epsilon"))
        steps = int(candidate.get("steps"))
        return (f"epsilon={epsilon:g},steps={steps}",)
    raise ValueError(f"unknown registered method key: {method_key}")


def expected_keys(method_key: str, config: dict[str, Any]) -> tuple[str, ...]:
    method = CANONICAL_METHOD[method_key]
    return tuple(f"{method}::{strength}" for strength in expected_strengths(method_key, config))


def array_fingerprint(
    array: np.ndarray,
    *,
    domain: str,
    dataset: str,
    seed: int,
    split: str,
    field: str,
) -> str:
    header = json.dumps(
        {
            "domain": domain,
            "dataset": dataset,
            "seed": seed,
            "split": split,
            "field": field,
            "dtype": array.dtype.str,
            "shape": list(array.shape),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(header)
    digest.update(b"\0")
    digest.update(np.ascontiguousarray(array).tobytes())
    return digest.hexdigest()


def _relative_to(path: Path, root: Path) -> str | None:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return None


def audit_closed_contract(
    study: dict[str, Any],
    receipt_root: Path,
    prereg_sha256: str,
) -> dict[str, Any]:
    errors: list[str] = []
    freshness = study.get("freshness_guard", {})
    freshness = freshness if isinstance(freshness, dict) else {}
    expected_receipt_root = Path(str(freshness.get("fresh_receipt_dir", "")))
    audit_root = Path(str(freshness.get("fresh_audit_dir", "")))
    receipt_root = Path(receipt_root)
    if receipt_root.resolve(strict=False) != expected_receipt_root.resolve(strict=False):
        errors.append(
            f"receipt root differs from preregistration: {receipt_root} != {expected_receipt_root}"
        )
    receipt_scan = scan_tree(receipt_root, "receipt")
    audit_scan = scan_tree(audit_root, "audit-array")
    errors.extend(receipt_scan.errors)
    errors.extend(audit_scan.errors)

    datasets = study.get("datasets", {})
    datasets = datasets if isinstance(datasets, dict) else {}
    methods = study.get("methods", {})
    methods = methods if isinstance(methods, dict) else {}
    seeds = [int(value) for value in study.get("seeds", [])]
    unknown_methods = sorted(set(methods) - set(CANONICAL_METHOD))
    if unknown_methods:
        errors.append(f"unknown registered methods: {unknown_methods}")

    expected_receipts = {
        f"{dataset}__{method}__seed-{seed}.json"
        for dataset in datasets
        for method in methods
        for seed in seeds
    }
    observed_receipts = set(receipt_scan.regular_files)
    missing_receipts = sorted(expected_receipts - observed_receipts)
    unexpected_receipts = sorted(observed_receipts - expected_receipts)
    if missing_receipts:
        errors.append(f"missing receipt files: {missing_receipts}")
    if unexpected_receipts:
        errors.append(f"unexpected receipt files: {unexpected_receipts}")
    if receipt_scan.directories:
        errors.append(f"unexpected receipt directories: {sorted(receipt_scan.directories)}")

    all_expected_keys: set[str] = set()
    per_method_keys: dict[str, set[str]] = {}
    for method_key, config in methods.items():
        if method_key not in CANONICAL_METHOD or not isinstance(config, dict):
            continue
        try:
            keys = set(expected_keys(method_key, config))
        except (TypeError, ValueError) as exc:
            errors.append(f"cannot derive candidate keys for {method_key}: {exc}")
            continue
        if len(keys) != int(config.get("candidate_count", -1)):
            errors.append(f"registered candidate count disagrees with configuration: {method_key}")
        per_method_keys[method_key] = keys
        all_expected_keys.update(keys)

    candidates: list[dict[str, Any]] = []
    block_keys: dict[tuple[str, int], list[str]] = {}
    expected_npz_paths: list[str] = []
    resolved_npz_paths: list[str] = []
    inode_paths: dict[tuple[int, int], list[str]] = {}
    candidate_key_occurrences: dict[tuple[str, int, str], int] = {}

    for dataset in datasets:
        for method_key, method_config in methods.items():
            if method_key not in per_method_keys or not isinstance(method_config, dict):
                continue
            for seed in seeds:
                run_key = f"{dataset}__{method_key}__seed-{seed}"
                relative_receipt = f"{run_key}.json"
                if relative_receipt not in receipt_scan.regular_files:
                    continue
                receipt = load_json(receipt_root / relative_receipt)
                if not receipt:
                    errors.append(f"receipt is not a JSON object: {relative_receipt}")
                    continue
                if receipt.get("prereg_sha256") != prereg_sha256:
                    errors.append(f"preregistration hash mismatch: {relative_receipt}")
                records = receipt.get("candidates", [])
                if not isinstance(records, list):
                    errors.append(f"candidate collection is not a list: {relative_receipt}")
                    records = []
                if len(records) != int(method_config.get("candidate_count", -1)):
                    errors.append(f"candidate count mismatch: {relative_receipt}")
                observed_method_keys: list[str] = []
                for index, candidate in enumerate(records):
                    if not isinstance(candidate, dict):
                        errors.append(f"candidate is not an object: {relative_receipt}#{index}")
                        continue
                    method = str(candidate.get("method", ""))
                    strength = str(candidate.get("strength", ""))
                    candidate_key = str(candidate.get("candidate_key", ""))
                    expected_method = CANONICAL_METHOD[method_key]
                    if method != expected_method:
                        errors.append(
                            f"candidate method mismatch: {relative_receipt}#{index} "
                            f"{method!r} != {expected_method!r}"
                        )
                    if candidate_key != f"{method}::{strength}":
                        errors.append(
                            f"candidate method/key/strength mismatch: "
                            f"{relative_receipt}#{index}"
                        )
                    if candidate_key not in per_method_keys[method_key]:
                        errors.append(
                            f"unexpected candidate key: {relative_receipt}#{index} "
                            f"{candidate_key!r}"
                        )
                    observed_method_keys.append(candidate_key)
                    block_keys.setdefault((dataset, seed), []).append(candidate_key)
                    occurrence_key = (dataset, seed, candidate_key)
                    candidate_key_occurrences[occurrence_key] = (
                        candidate_key_occurrences.get(occurrence_key, 0) + 1
                    )

                    raw_npz = str(candidate.get("audit_npz", ""))
                    path = Path(raw_npz)
                    if not path.is_absolute() or ".." in path.parts:
                        errors.append(
                            f"candidate audit path is not canonical absolute: "
                            f"{relative_receipt}#{index}"
                        )
                    links = symlink_components(path)
                    if links:
                        errors.append(
                            f"candidate audit path uses symlink components: "
                            f"{relative_receipt}#{index}"
                        )
                    resolved = path.resolve(strict=False)
                    audit_resolved = audit_root.resolve(strict=False)
                    relative_npz = _relative_to(resolved, audit_resolved)
                    if relative_npz is None:
                        errors.append(
                            f"candidate audit path is outside registered root: "
                            f"{relative_receipt}#{index}"
                        )
                    else:
                        expected_npz_paths.append(relative_npz)
                        if Path(relative_npz).parent.as_posix() != run_key:
                            errors.append(
                                f"candidate audit path uses wrong run directory: "
                                f"{relative_receipt}#{index}"
                            )
                        if Path(relative_npz).suffix != ".npz":
                            errors.append(
                                f"candidate audit path is not NPZ: "
                                f"{relative_receipt}#{index}"
                            )
                    resolved_npz_paths.append(str(resolved))
                    if relative_npz in audit_scan.regular_files:
                        observed_stat = audit_scan.regular_files[relative_npz]
                        inode_paths.setdefault(
                            (observed_stat.st_dev, observed_stat.st_ino), []
                        ).append(relative_npz)
                    candidates.append(
                        {
                            "dataset": dataset,
                            "seed": seed,
                            "run_key": run_key,
                            "receipt": relative_receipt,
                            "receipt_data": receipt,
                            "candidate": candidate,
                            "path": path,
                            "relative_npz": relative_npz,
                        }
                    )
                if set(observed_method_keys) != per_method_keys[method_key] or len(
                    observed_method_keys
                ) != len(set(observed_method_keys)):
                    errors.append(f"candidate key set mismatch: {relative_receipt}")

    duplicate_candidate_keys = sorted(
        f"{dataset}/seed-{seed}/{key}"
        for (dataset, seed, key), count in candidate_key_occurrences.items()
        if count != 1
    )
    if duplicate_candidate_keys:
        errors.append(f"duplicate candidate keys: {duplicate_candidate_keys}")
    for dataset in datasets:
        for seed in seeds:
            observed = block_keys.get((dataset, seed), [])
            if set(observed) != all_expected_keys or len(observed) != len(all_expected_keys):
                errors.append(f"dataset-seed candidate frontier mismatch: {dataset}/seed-{seed}")

    expected_candidate_count = len(datasets) * len(seeds) * sum(
        int(config.get("candidate_count", 0))
        for config in methods.values()
        if isinstance(config, dict)
    )
    if len(candidates) != expected_candidate_count:
        errors.append(
            f"candidate cardinality mismatch: {len(candidates)} != {expected_candidate_count}"
        )
    duplicate_npz_paths = sorted(
        path for path in set(resolved_npz_paths) if resolved_npz_paths.count(path) > 1
    )
    if duplicate_npz_paths:
        errors.append(f"duplicate candidate NPZ paths: {duplicate_npz_paths}")
    duplicate_inodes = sorted(paths for paths in inode_paths.values() if len(paths) > 1)
    if duplicate_inodes:
        errors.append(f"multiple candidate paths share an inode: {duplicate_inodes}")

    expected_npz_set = set(expected_npz_paths)
    observed_npz_set = set(audit_scan.regular_files)
    missing_npz = sorted(expected_npz_set - observed_npz_set)
    unexpected_audit_files = sorted(observed_npz_set - expected_npz_set)
    if missing_npz:
        errors.append(f"missing registered NPZ files: {missing_npz}")
    if unexpected_audit_files:
        errors.append(f"unknown files under audit root: {unexpected_audit_files}")
    expected_audit_directories = {
        str(Path(path).parent) for path in expected_npz_set if str(Path(path).parent) != "."
    }
    unexpected_audit_directories = sorted(audit_scan.directories - expected_audit_directories)
    missing_audit_directories = sorted(expected_audit_directories - audit_scan.directories)
    if unexpected_audit_directories:
        errors.append(f"unknown directories under audit root: {unexpected_audit_directories}")
    if missing_audit_directories:
        errors.append(f"missing registered audit directories: {missing_audit_directories}")

    identity_hashes: dict[tuple[str, int, str], set[str]] = {}
    identity_contributors: dict[tuple[str, int, str], int] = {}
    metadata_hashes: dict[tuple[str, int, str, str], set[str]] = {}
    metadata_contributors: dict[tuple[str, int, str, str], int] = {}
    validated_archives = 0
    for item in candidates:
        path = item["path"]
        relative_npz = item["relative_npz"]
        candidate = item["candidate"]
        receipt = item["receipt_data"]
        label = f"{item['receipt']}::{candidate.get('candidate_key', '')}"
        if relative_npz not in audit_scan.regular_files:
            continue
        if sha256(path) != candidate.get("audit_npz_sha256"):
            errors.append(f"audit NPZ hash mismatch: {label}")
            continue
        archive_errors_before = len(errors)
        try:
            with zipfile.ZipFile(path) as zipped:
                members = zipped.namelist()
            expected_members = {f"{name}.npy" for name in EXPECTED_ARRAYS}
            if len(members) != len(set(members)) or set(members) != expected_members:
                errors.append(f"closed NPZ member contract mismatch: {label}")
                continue
            with np.load(path, allow_pickle=False) as archive:
                if set(archive.files) != EXPECTED_ARRAYS:
                    errors.append(f"closed array contract mismatch: {label}")
                    continue
                arrays: dict[str, np.ndarray] = {}
                archive_valid = True
                for name in sorted(EXPECTED_ARRAYS):
                    array = archive[name]
                    arrays[name] = array
                    if array.ndim != 1:
                        errors.append(f"array is not one-dimensional: {label}/{name}")
                        archive_valid = False
                        continue
                    if array.dtype.kind not in "biuf":
                        errors.append(f"array dtype is not real numeric/bool: {label}/{name}")
                        archive_valid = False
                        continue
                    if not np.isfinite(array).all():
                        errors.append(f"array contains nonfinite values: {label}/{name}")
                        archive_valid = False
                    split = next((value for value in SPLITS if value in name), None)
                    if split is None:
                        errors.append(f"array has no registered split: {label}/{name}")
                        archive_valid = False
                        continue
                    expected_n = int(receipt.get("indices", {}).get(split, {}).get("n", -1))
                    if len(array) != expected_n:
                        errors.append(f"split length mismatch: {label}/{name}")
                        archive_valid = False
                    if name.startswith(BINARY_PREFIXES) and not np.isin(array, (0, 1)).all():
                        errors.append(f"binary array leaves support: {label}/{name}")
                        archive_valid = False
                    if name.startswith("target_harm_") and not np.isin(array, (-1, 0, 1)).all():
                        errors.append(f"harm array leaves support: {label}/{name}")
                        archive_valid = False
                    if name.startswith("target_") and not name.startswith("target_harm_"):
                        if not np.array_equal(array, np.rint(array)):
                            errors.append(f"target metadata is non-integer: {label}/{name}")
                            archive_valid = False
                    if name.startswith("source_"):
                        allowed = receipt.get("source_classes", {}).get(split, [])
                        if not np.isin(array, allowed).all():
                            errors.append(
                                f"source metadata leaves declared support: {label}/{name}"
                            )
                            archive_valid = False
                    if name.startswith("environment_"):
                        allowed = receipt.get("environment_classes", {}).get(split, [])
                        if not np.isin(array, allowed).all():
                            errors.append(
                                f"environment metadata leaves declared support: "
                                f"{label}/{name}"
                            )
                            archive_valid = False

                if not archive_valid:
                    continue

                for split in SPLITS:
                    reconstructed = (
                        arrays[f"edited_target_error_{split}"]
                        - arrays[f"identity_target_error_{split}"]
                    )
                    if not np.array_equal(reconstructed, arrays[f"target_harm_{split}"]):
                        errors.append(f"paired harm reconstruction mismatch: {label}/{split}")
                    identity_key = (item["dataset"], item["seed"], split)
                    identity_hashes.setdefault(identity_key, set()).add(
                        array_fingerprint(
                            arrays[f"identity_target_error_{split}"],
                            domain="VERA shared identity comparator v1",
                            dataset=item["dataset"],
                            seed=item["seed"],
                            split=split,
                            field="identity_target_error",
                        )
                    )
                    identity_contributors[identity_key] = (
                        identity_contributors.get(identity_key, 0) + 1
                    )
                    for field in ("source", "environment", "target"):
                        metadata_key = (item["dataset"], item["seed"], split, field)
                        metadata_hashes.setdefault(metadata_key, set()).add(
                            array_fingerprint(
                                arrays[f"{field}_{split}"],
                                domain="VERA shared evaluation metadata v1",
                                dataset=item["dataset"],
                                seed=item["seed"],
                                split=split,
                                field=field,
                            )
                        )
                        metadata_contributors[metadata_key] = (
                            metadata_contributors.get(metadata_key, 0) + 1
                        )
        except (OSError, TypeError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            errors.append(f"audit NPZ is unreadable: {label}: {exc}")
        if len(errors) == archive_errors_before:
            validated_archives += 1

    expected_per_block = sum(
        int(config.get("candidate_count", 0))
        for config in methods.values()
        if isinstance(config, dict)
    )
    identity_mismatches = sorted(
        f"{dataset}/seed-{seed}/{split}"
        for (dataset, seed, split), hashes in identity_hashes.items()
        if len(hashes) != 1
        or identity_contributors.get((dataset, seed, split), 0) != expected_per_block
    )
    expected_identity_blocks = len(datasets) * len(seeds) * len(SPLITS)
    if len(identity_hashes) != expected_identity_blocks:
        errors.append(
            f"shared identity block count mismatch: {len(identity_hashes)} != "
            f"{expected_identity_blocks}"
        )
    if identity_mismatches:
        errors.append(f"shared identity comparator mismatch: {identity_mismatches}")

    metadata_mismatches = sorted(
        f"{dataset}/seed-{seed}/{split}/{field}"
        for (dataset, seed, split, field), hashes in metadata_hashes.items()
        if len(hashes) != 1
        or metadata_contributors.get((dataset, seed, split, field), 0) != expected_per_block
    )
    expected_metadata_blocks = expected_identity_blocks * 3
    if len(metadata_hashes) != expected_metadata_blocks:
        errors.append(
            f"shared metadata block count mismatch: {len(metadata_hashes)} != "
            f"{expected_metadata_blocks}"
        )
    if metadata_mismatches:
        errors.append(f"shared evaluation metadata mismatch: {metadata_mismatches}")

    return {
        "passed": not errors,
        "resolved_receipt_root": str(receipt_root.resolve(strict=False)),
        "resolved_audit_root": str(audit_root.resolve(strict=False)),
        "expected_receipt_files": sorted(expected_receipts),
        "observed_receipt_files": sorted(observed_receipts),
        "missing_receipt_count": len(missing_receipts),
        "unexpected_receipt_count": len(unexpected_receipts),
        "expected_candidate_count": expected_candidate_count,
        "observed_candidate_count": len(candidates),
        "expected_candidate_keys_per_dataset_seed": sorted(all_expected_keys),
        "duplicate_candidate_key_count": len(duplicate_candidate_keys),
        "expected_npz_files": sorted(expected_npz_set),
        "observed_npz_files": sorted(observed_npz_set),
        "missing_npz_count": len(missing_npz),
        "unexpected_audit_file_count": len(unexpected_audit_files),
        "unexpected_audit_directory_count": len(unexpected_audit_directories),
        "duplicate_npz_path_count": len(duplicate_npz_paths),
        "duplicate_npz_inode_count": len(duplicate_inodes),
        "validated_closed_array_archive_count": validated_archives,
        "expected_array_names": sorted(EXPECTED_ARRAYS),
        "shared_identity_block_split_count": len(identity_hashes),
        "shared_identity_mismatch_count": len(identity_mismatches),
        "shared_metadata_block_count": len(metadata_hashes),
        "shared_metadata_mismatch_count": len(metadata_mismatches),
        "errors": errors,
    }
