from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np

from controlled_shift_receipt_contract import (
    EXPECTED_ARRAYS,
    audit_closed_contract,
    case_collisions,
    sha256,
)


PREREG_HASH = "a" * 64


def arrays() -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    for name in EXPECTED_ARRAYS:
        if name.startswith("source_"):
            result[name] = np.asarray([0, 1, 0], dtype=np.int8)
        elif name.startswith("environment_"):
            result[name] = np.asarray([0, 1, 1], dtype=np.int8)
        elif name.startswith("leakage_correct_") or name.startswith(
            "heldout_leakage_correct_"
        ):
            result[name] = np.ones(3, dtype=np.int8)
        else:
            result[name] = np.zeros(3, dtype=np.int8)
    return result


def write_receipt(path: Path, candidates: list[dict[str, str]]) -> None:
    payload = {
        "prereg_sha256": PREREG_HASH,
        "indices": {
            "certification": {"n": 3, "sha256": "b" * 64},
            "external": {"n": 3, "sha256": "c" * 64},
        },
        "source_classes": {"certification": [0, 1], "external": [0, 1]},
        "environment_classes": {"certification": [0, 1], "external": [0, 1]},
        "candidates": candidates,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def read_receipt(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def update_receipt(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def mutate_archive(path: Path, mutation) -> None:
    with np.load(path, allow_pickle=False) as archive:
        payload = {name: archive[name].copy() for name in archive.files}
    mutation(payload)
    np.savez(path, **payload)


def build_fixture(root: Path) -> tuple[dict, Path, Path]:
    receipts = root / "receipts"
    audit = root / "arrays"
    receipts.mkdir()
    audit.mkdir()
    methods = {
        "rlace": {
            "candidate_count": 2,
            "candidate_configuration": {"ranks": [1, 4]},
        },
        "leace": {
            "candidate_count": 1,
            "candidate_configuration": {"candidate": "closed_form"},
        },
    }
    study = {
        "datasets": {"Toy": {"manifest_sha256": "d" * 64}},
        "methods": methods,
        "seeds": [45],
        "freshness_guard": {
            "fresh_receipt_dir": str(receipts),
            "fresh_audit_dir": str(audit),
        },
    }
    candidate_specs = {
        "rlace": [("R-LACE", "rank=1"), ("R-LACE", "rank=4")],
        "leace": [("LEACE", "closed_form")],
    }
    for method, specs in candidate_specs.items():
        run_key = f"Toy__{method}__seed-45"
        run_dir = audit / run_key
        run_dir.mkdir()
        candidates = []
        for index, (candidate_method, strength) in enumerate(specs):
            archive = run_dir / f"candidate-{index:02d}.npz"
            np.savez(archive, **arrays())
            candidates.append(
                {
                    "method": candidate_method,
                    "strength": strength,
                    "candidate_key": f"{candidate_method}::{strength}",
                    "audit_npz": str(archive),
                    "audit_npz_sha256": sha256(archive),
                }
            )
        write_receipt(receipts / f"{run_key}.json", candidates)
    return study, receipts, audit


def run_case(name: str, mutation, expected: str) -> None:
    with tempfile.TemporaryDirectory(prefix="vera-contract-", dir="/private/tmp") as temporary:
        root = Path(temporary)
        study, receipts, audit = build_fixture(root)
        baseline = audit_closed_contract(study, receipts, PREREG_HASH)
        assert baseline["passed"], baseline["errors"]
        mutation(root, receipts, audit)
        report = audit_closed_contract(study, receipts, PREREG_HASH)
        assert not report["passed"], name
        assert any(expected in error for error in report["errors"]), (name, report["errors"])
    print(f"PASS {name}")


def main() -> None:
    run_case(
        "extra receipt",
        lambda root, receipts, audit: (receipts / "extra.json").write_text("{}"),
        "unexpected receipt files",
    )

    def unexpected_name(root, receipts, audit):
        path = receipts / "Toy__leace__seed-45.json"
        path.rename(receipts / "Toy__leace__seed-45-wrong.json")

    run_case("unexpected basename", unexpected_name, "unexpected receipt files")

    def receipt_symlink(root, receipts, audit):
        path = receipts / "Toy__leace__seed-45.json"
        outside = root / "outside-receipt.json"
        shutil.copy2(path, outside)
        path.unlink()
        path.symlink_to(outside)

    run_case("receipt symlink", receipt_symlink, "receipt symlink is forbidden")

    assert case_collisions(["Toy__LEACE__seed-45.json", "Toy__leace__seed-45.json"])
    print("PASS case-colliding receipt names")

    def outside_npz(root, receipts, audit):
        receipt_path = receipts / "Toy__leace__seed-45.json"
        payload = read_receipt(receipt_path)
        original = Path(payload["candidates"][0]["audit_npz"])
        outside = root / "outside.npz"
        shutil.copy2(original, outside)
        payload["candidates"][0]["audit_npz"] = str(outside)
        payload["candidates"][0]["audit_npz_sha256"] = sha256(outside)
        update_receipt(receipt_path, payload)

    run_case("outside-root NPZ", outside_npz, "outside registered root")

    def npz_symlink(root, receipts, audit):
        receipt_path = receipts / "Toy__leace__seed-45.json"
        payload = read_receipt(receipt_path)
        path = Path(payload["candidates"][0]["audit_npz"])
        outside = root / "outside.npz"
        shutil.copy2(path, outside)
        path.unlink()
        path.symlink_to(outside)

    run_case("NPZ symlink", npz_symlink, "audit-array symlink is forbidden")

    def duplicate_key(root, receipts, audit):
        path = receipts / "Toy__rlace__seed-45.json"
        payload = read_receipt(path)
        payload["candidates"][1]["candidate_key"] = payload["candidates"][0]["candidate_key"]
        update_receipt(path, payload)

    run_case("duplicate candidate key", duplicate_key, "duplicate candidate keys")

    def duplicate_npz(root, receipts, audit):
        path = receipts / "Toy__rlace__seed-45.json"
        payload = read_receipt(path)
        payload["candidates"][1]["audit_npz"] = payload["candidates"][0]["audit_npz"]
        payload["candidates"][1]["audit_npz_sha256"] = payload["candidates"][0]["audit_npz_sha256"]
        update_receipt(path, payload)

    run_case("duplicate NPZ path", duplicate_npz, "duplicate candidate NPZ paths")

    def strength_mismatch(root, receipts, audit):
        path = receipts / "Toy__rlace__seed-45.json"
        payload = read_receipt(path)
        payload["candidates"][0]["strength"] = "rank=8"
        update_receipt(path, payload)

    run_case("method-key-strength mismatch", strength_mismatch, "method/key/strength mismatch")

    def extra_member(root, receipts, audit):
        path = receipts / "Toy__leace__seed-45.json"
        payload = read_receipt(path)
        archive = Path(payload["candidates"][0]["audit_npz"])
        mutate_archive(archive, lambda values: values.update({"extra": np.zeros(3, dtype=np.int8)}))
        payload["candidates"][0]["audit_npz_sha256"] = sha256(archive)
        update_receipt(path, payload)

    run_case("extra NPZ member", extra_member, "closed NPZ member contract mismatch")

    def string_array(root, receipts, audit):
        path = receipts / "Toy__leace__seed-45.json"
        payload = read_receipt(path)
        archive = Path(payload["candidates"][0]["audit_npz"])

        def change(values):
            values["target_certification"] = np.asarray(["x", "x", "x"])

        mutate_archive(archive, change)
        payload["candidates"][0]["audit_npz_sha256"] = sha256(archive)
        update_receipt(path, payload)

    run_case("string array", string_array, "array dtype is not real numeric/bool")

    def object_array(root, receipts, audit):
        path = receipts / "Toy__leace__seed-45.json"
        payload = read_receipt(path)
        archive = Path(payload["candidates"][0]["audit_npz"])

        def change(values):
            values["target_certification"] = np.asarray([object(), object(), object()])

        mutate_archive(archive, change)
        payload["candidates"][0]["audit_npz_sha256"] = sha256(archive)
        update_receipt(path, payload)

    run_case("object array", object_array, "audit NPZ is unreadable")

    run_case(
        "unknown controlled-root file",
        lambda root, receipts, audit: (audit / "unknown.txt").write_text("x"),
        "unknown files under audit root",
    )

    def metadata_mismatch(root, receipts, audit):
        path = receipts / "Toy__leace__seed-45.json"
        payload = read_receipt(path)
        archive = Path(payload["candidates"][0]["audit_npz"])

        def change(values):
            values["source_certification"][0] = 1

        mutate_archive(archive, change)
        payload["candidates"][0]["audit_npz_sha256"] = sha256(archive)
        update_receipt(path, payload)

    run_case("metadata disagreement", metadata_mismatch, "shared evaluation metadata mismatch")

    def multiclass_target_metadata(root, receipts, audit):
        target_values = {
            "target_certification": np.asarray([0, 2, 4], dtype=np.int16),
            "target_external": np.asarray([1, 3, 5], dtype=np.int16),
        }
        for path in sorted(receipts.glob("*.json")):
            payload = read_receipt(path)
            for candidate in payload["candidates"]:
                archive = Path(candidate["audit_npz"])

                def change(values, *, target_values=target_values):
                    values.update(target_values)

                mutate_archive(archive, change)
                candidate["audit_npz_sha256"] = sha256(archive)
            update_receipt(path, payload)
        report = audit_closed_contract(build_fixture_last_study(root), receipts, PREREG_HASH)
        assert report["passed"], report["errors"]

    def build_fixture_last_study(root):
        return {
            "datasets": {"Toy": {"manifest_sha256": "d" * 64}},
            "methods": {
                "rlace": {
                    "candidate_count": 2,
                    "candidate_configuration": {"ranks": [1, 4]},
                },
                "leace": {
                    "candidate_count": 1,
                    "candidate_configuration": {"candidate": "closed_form"},
                },
            },
            "seeds": [45],
            "freshness_guard": {
                "fresh_receipt_dir": str(root / "receipts"),
                "fresh_audit_dir": str(root / "arrays"),
            },
        }

    with tempfile.TemporaryDirectory(prefix="vera-contract-", dir="/private/tmp") as temporary:
        root = Path(temporary)
        build_fixture(root)
        multiclass_target_metadata(root, root / "receipts", root / "arrays")
    print("PASS multiclass target metadata")

    def fractional_target(root, receipts, audit):
        path = receipts / "Toy__leace__seed-45.json"
        payload = read_receipt(path)
        archive = Path(payload["candidates"][0]["audit_npz"])

        def change(values):
            values["target_certification"] = np.asarray([0.0, 0.5, 1.0])

        mutate_archive(archive, change)
        payload["candidates"][0]["audit_npz_sha256"] = sha256(archive)
        update_receipt(path, payload)

    run_case("fractional target metadata", fractional_target, "target metadata is non-integer")

    def rlace_token(root, receipts, audit):
        path = receipts / "Toy__rlace__seed-45.json"
        payload = read_receipt(path)
        payload["candidates"][0]["method"] = "RLACE"
        payload["candidates"][0]["candidate_key"] = "RLACE::rank=1"
        update_receipt(path, payload)

    run_case("RLACE candidate token", rlace_token, "candidate method mismatch")

    def identity_substitution(root, receipts, audit):
        path = receipts / "Toy__leace__seed-45.json"
        payload = read_receipt(path)
        archive = Path(payload["candidates"][0]["audit_npz"])

        def change(values):
            values["identity_target_error_certification"][0] = 1
            values["edited_target_error_certification"][0] = 1

        mutate_archive(archive, change)
        payload["candidates"][0]["audit_npz_sha256"] = sha256(archive)
        update_receipt(path, payload)

    run_case(
        "shared identity substitution with valid harm",
        identity_substitution,
        "shared identity comparator mismatch",
    )

    def hardlink(root, receipts, audit):
        path = receipts / "Toy__rlace__seed-45.json"
        payload = read_receipt(path)
        first = Path(payload["candidates"][0]["audit_npz"])
        second = Path(payload["candidates"][1]["audit_npz"])
        second.unlink()
        os.link(first, second)
        payload["candidates"][1]["audit_npz_sha256"] = sha256(second)
        update_receipt(path, payload)

    run_case("hard-linked NPZ", hardlink, "hard-linked file is forbidden")

    def special_file(root, receipts, audit):
        os.mkfifo(audit / "unexpected.pipe")

    run_case("special file", special_file, "special file is forbidden")


if __name__ == "__main__":
    main()
