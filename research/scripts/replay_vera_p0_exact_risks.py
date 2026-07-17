"""Independent low-level replay of VERA P0 construction choices and Q risks.

This program intentionally does not import the P0 policy evaluator.  It is a
second result reader: it reconstructs the construction-selected edit, the
finite-reference deployment law, and all exact Q risks directly from hashed
receipts.  It is sealed before scientific P0 outcomes are inspected.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = ROOT / "prereg_vera_p0_confirmation_v4.json"
DEFAULT_HASH = ROOT / "prereg_vera_p0_confirmation_v4.sha256"
DEFAULT_RECEIPTS = Path(
    "/Volumes/Backups/FARO/artifacts/vera_p0_confirmation_v4_receipts"
)
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_p0_confirmation_v4_exact_replay.json"
DATASETS = ("Bios", "CivilComments-WILDS", "GaitPDB", "Waterbirds")
GAMMAS = (1.0, 1.1, 1.25, 1.5)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(values: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(values).view(np.uint8)).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def split_arrays(
    arrays: dict[str, np.ndarray], split: str, attackers: tuple[str, ...]
) -> dict[str, np.ndarray]:
    names = {
        "harm": f"target_harm_{split}",
        "source": f"source_{split}",
        "environment": f"environment_{split}",
        "target": f"target_{split}",
    }
    output = {key: np.asarray(arrays[value]) for key, value in names.items()}
    for attacker in attackers:
        output[f"attacker::{attacker}"] = np.asarray(
            arrays[f"leakage_correct_{split}__{attacker}"]
        )
    lengths = {len(value) for value in output.values()}
    if len(lengths) != 1 or not lengths or min(lengths) <= 0:
        raise ValueError(f"misaligned {split} arrays")
    return output


def balanced_accuracy_from_errors(errors: np.ndarray, target: np.ndarray) -> float:
    return float(
        np.mean([1.0 - errors[target == label].mean() for label in np.unique(target)])
    )


def select_edit(
    candidates: list[dict[str, Any]], attackers: tuple[str, ...]
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    records = []
    for candidate in candidates:
        arrays = candidate["arrays"]
        construction = split_arrays(arrays, "construction", attackers)
        errors = np.asarray(arrays["edited_target_error_construction"], dtype=float)
        records.append(
            (
                balanced_accuracy_from_errors(errors, construction["target"]),
                str(candidate["candidate"]),
                candidate,
                construction,
            )
        )
    _, _, candidate, construction = min(records, key=lambda item: (-item[0], item[1]))
    return candidate, construction


def choose_focus(
    construction: dict[str, np.ndarray],
    certification: dict[str, np.ndarray],
    *,
    target_threshold: float,
    leakage_threshold: float,
    gamma: float,
) -> tuple[int, int, int, float]:
    candidates: list[tuple[float, int, int, int]] = []
    for environment in sorted(map(int, np.unique(construction["environment"]))):
        for source in sorted(map(int, np.unique(construction["source"]))):
            for target in sorted(map(int, np.unique(construction["target"]))):
                mask = (
                    (construction["environment"] == environment)
                    & (construction["source"] == source)
                    & (construction["target"] == target)
                )
                cert_environment = certification["environment"] == environment
                cert_focus = (
                    cert_environment
                    & (certification["source"] == source)
                    & (certification["target"] == target)
                )
                if not np.any(mask) or not np.any(cert_focus):
                    continue
                p = float(cert_focus.sum() / cert_environment.sum())
                if p >= 1.0 or gamma * p > 1.0 + 1e-12:
                    continue
                target_surplus = float(construction["harm"][mask].mean()) - target_threshold
                attacker_surplus = max(
                    float(construction[key][mask].mean()) - leakage_threshold
                    for key in construction
                    if key.startswith("attacker::")
                )
                candidates.append((max(target_surplus, attacker_surplus), environment, source, target))
    if not candidates:
        raise RuntimeError("no feasible construction-selected focus cell")
    surplus, environment, source, target = min(
        candidates, key=lambda item: (-item[0], item[1], item[2], item[3])
    )
    return environment, source, target, surplus


def make_q(
    certification: dict[str, np.ndarray], focus: tuple[int, int, int], gamma: float
) -> np.ndarray:
    environment, source, target = focus
    env = certification["environment"]
    src = certification["source"]
    tgt = certification["target"]
    environment_mask = env == environment
    focus_mask = environment_mask & (src == source) & (tgt == target)
    p = float(focus_mask.sum() / environment_mask.sum())
    residual = (1.0 - gamma * p) / (1.0 - p)
    weights = np.ones(len(env), dtype=float)
    weights[environment_mask & ~focus_mask] = residual
    weights[focus_mask] = gamma
    if not np.isclose(weights.mean(), 1.0, atol=1e-10):
        raise RuntimeError("replayed density ratios fail normalization")
    return weights / len(weights)


def exact_risks(
    reference: dict[str, np.ndarray], q: np.ndarray, attackers: tuple[str, ...]
) -> dict[str, Any]:
    target_by_environment: dict[str, float] = {}
    for environment in sorted(map(int, np.unique(reference["environment"]))):
        mask = reference["environment"] == environment
        conditional = q[mask] / q[mask].sum()
        target_by_environment[str(environment)] = float(np.dot(conditional, reference["harm"][mask]))
    leakage: dict[str, float] = {}
    for attacker in attackers:
        recalls = []
        for source in (0, 1):
            mask = reference["source"] == source
            conditional = q[mask] / q[mask].sum()
            recalls.append(float(np.dot(conditional, reference[f"attacker::{attacker}"][mask])))
        leakage[attacker] = float(np.mean(recalls))
    return {
        "target_harm_by_environment": target_by_environment,
        "maximum_target_harm": max(target_by_environment.values()),
        "attacker_balanced_leakage": leakage,
        "maximum_attacker_leakage": max(leakage.values()),
    }


def load_frontier(
    receipt_dir: Path,
    prereg_hash: str,
    dataset: str,
    seed: int,
    methods: tuple[str, ...],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for method in methods:
        receipt_path = receipt_dir / f"{dataset}__{method}__seed-{seed}.json"
        receipt = load_json(receipt_path)
        if receipt.get("prereg_sha256") != prereg_hash or receipt.get("claim_grade") is not True:
            raise RuntimeError(f"unlocked or mismatched receipt: {receipt_path}")
        for candidate in receipt["candidates"]:
            audit_path = Path(candidate["audit_npz"])
            if sha256(audit_path) != candidate["audit_npz_sha256"]:
                raise RuntimeError(f"audit hash mismatch: {audit_path}")
            with np.load(audit_path, allow_pickle=False) as archive:
                arrays = {name: np.asarray(archive[name]) for name in archive.files}
            output.append({"candidate": candidate["candidate_key"], "arrays": arrays})
    return sorted(output, key=lambda candidate: str(candidate["candidate"]))


def replay(args: argparse.Namespace) -> dict[str, Any]:
    prereg = load_json(args.prereg)
    prereg_hash = sha256(args.prereg)
    expected = args.hash_file.read_text(encoding="utf-8").split()[0]
    if prereg_hash != expected or prereg.get("status") != "locked_before_claim_grade_runs":
        raise RuntimeError("P0 preregistration identity check failed")
    study = prereg["real_study"]
    attackers = tuple(str(value) for value in study["leakage_attackers"])
    methods = tuple(str(value) for value in study["methods"])
    rows: list[dict[str, Any]] = []
    for dataset in DATASETS:
        contract = study["locked_dataset_contracts"][dataset]
        for seed in map(int, study["seeds"]):
            frontier = load_frontier(args.receipt_dir, prereg_hash, dataset, seed, methods)
            if len(frontier) != int(study["candidate_count_total"]):
                raise RuntimeError(f"incomplete frontier: {dataset}/seed-{seed}")
            selected, construction = select_edit(frontier, attackers)
            certification = split_arrays(selected["arrays"], "certification", attackers)
            for gamma in GAMMAS:
                focus = choose_focus(
                    construction,
                    certification,
                    target_threshold=float(contract["target_harm_threshold"]),
                    leakage_threshold=float(contract["balanced_leakage_threshold"]),
                    gamma=gamma,
                )
                q = make_q(certification, focus[:3], gamma)
                density_ratio = q * len(q)
                candidate_risks = {
                    str(candidate["candidate"]): exact_risks(
                        split_arrays(candidate["arrays"], "certification", attackers),
                        q,
                        attackers,
                    )
                    for candidate in frontier
                }
                rows.append(
                    {
                        "dataset": dataset,
                        "seed": seed,
                        "requested_gamma": gamma,
                        "construction_selected_candidate": selected["candidate"],
                        "focus_environment": focus[0],
                        "focus_source": focus[1],
                        "focus_target": focus[2],
                        "construction_surplus": focus[3],
                        "q_probability_sha256": array_sha256(q),
                        "q_membership_verified": bool(
                            np.isclose(q.sum(), 1.0)
                            and np.all(q >= 0.0)
                            and density_ratio.max() <= gamma + 1e-10
                        ),
                        "candidate_exact_risks": candidate_risks,
                    }
                )
    rows.sort(key=lambda row: (row["dataset"], row["seed"], row["requested_gamma"]))
    return {
        "name": "VERA P0 independent exact-risk replay",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "preregistration_sha256": prereg_hash,
        "row_count": len(rows),
        "all_q_membership_verified": all(row["q_membership_verified"] for row in rows),
        "claim_boundary": (
            "This replay independently reconstructs construction choices and exact "
            "finite-reference Q risks. It does not replace the separately sealed "
            "certificate-policy analyzer."
        ),
        "rows": rows,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--receipt-dir", type=Path, default=DEFAULT_RECEIPTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite replay output: {args.output}")
    output = replay(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "sha256": sha256(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
