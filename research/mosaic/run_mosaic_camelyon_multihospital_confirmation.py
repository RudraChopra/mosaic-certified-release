#!/usr/bin/env python3
"""Run the locked Camelyon17 multi-hospital release confirmation."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import numpy as np

from mosaic_bridge import certify_bridge_membership
from mosaic_real import (
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    build_token_table,
    evaluate_external_channel,
    fit_score_tokenizer,
)
from mosaic_transform_exact_optimizer import optimize_transform_exact_channel
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE = Path(
    "/Volumes/Backups/FARO/artifacts/"
    "camelyon17_resnet18_torch_center_numpy_store"
)
DEFAULT_PREREG = (
    ROOT
    / "research/mosaic/"
    "prereg_mosaic_camelyon_multihospital_confirmation_v1.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "research/artifacts/"
    "mosaic_camelyon_multihospital_confirmation_v1"
)
SOURCE_ZERO_CENTERS = frozenset({0})
SOURCE_ONE_CENTERS = frozenset({3, 4})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} is not a JSON object")
    return payload


def validate_lock(path: Path) -> dict[str, Any]:
    sidecar = path.with_suffix(path.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").split()[0] != sha256(path):
        raise ValueError("Camelyon lock sidecar mismatch")
    prereg = load_json(path)
    if prereg.get("status") != "locked_before_multihospital_outcomes":
        raise RuntimeError("Camelyon preregistration is not locked")
    for relative, expected in prereg["code_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise RuntimeError(f"locked source mismatch: {relative}")
    for local in (path, sidecar):
        relative = local.relative_to(ROOT)
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative.as_posix()}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed != local.read_bytes():
            raise RuntimeError(f"{relative} is not the committed lock")
    return prereg


def load_store(
    path: Path,
    expected_manifest_sha256: str,
) -> tuple[dict[str, Any], np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    manifest_path = path / "manifest.json"
    if sha256(manifest_path) != expected_manifest_sha256:
        raise RuntimeError("Camelyon store manifest differs from the lock")
    manifest = load_json(manifest_path)
    arrays = manifest["arrays"]
    features = np.load(path / arrays["z"], mmap_mode="r")
    target = np.asarray(np.load(path / arrays["y"], mmap_mode="r"), dtype=np.int8)
    split = np.asarray(
        np.load(path / arrays["split"], mmap_mode="r"),
        dtype=np.int8,
    )
    centers = np.asarray(
        np.load(path / arrays["g"], mmap_mode="r"),
        dtype=np.int8,
    )
    expected = int(manifest["n_examples"])
    if not all(
        len(values) == expected
        for values in (features, target, split, centers)
    ):
        raise RuntimeError("Camelyon arrays do not match the manifest")
    if set(np.unique(target)) != {0, 1}:
        raise RuntimeError("Camelyon target is not binary")
    return manifest, features, target, split, centers


def recode_source(centers: np.ndarray) -> np.ndarray:
    source = np.full(len(centers), -1, dtype=np.int8)
    source[np.isin(centers, tuple(SOURCE_ZERO_CENTERS))] = 0
    source[np.isin(centers, tuple(SOURCE_ONE_CENTERS))] = 1
    return source


def split_construction_reference(
    pool: np.ndarray,
    target: np.ndarray,
    source: np.ndarray,
    *,
    construction_cap: int,
    reference_cap: int,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Draw disjoint balanced source-label folds from official training rows."""

    if construction_cap % 4 or reference_cap % 4:
        raise ValueError("fold caps must be divisible by four strata")
    rng = np.random.default_rng(seed)
    construction: list[np.ndarray] = []
    reference: list[np.ndarray] = []
    construction_per = construction_cap // 4
    reference_per = reference_cap // 4
    for label in (0, 1):
        for group in (0, 1):
            cell = np.asarray(
                pool[
                    (target[pool] == label)
                    & (source[pool] == group)
                ],
                dtype=np.int64,
            )
            required = construction_per + reference_per
            if len(cell) < required:
                raise RuntimeError(
                    f"Camelyon training stratum y={label},s={group} "
                    f"has {len(cell)} rows; {required} are required"
                )
            chosen = rng.choice(cell, size=required, replace=False)
            construction.append(chosen[:construction_per])
            reference.append(chosen[construction_per:])
    return (
        np.sort(np.concatenate(construction)),
        np.sort(np.concatenate(reference)),
    )


def stratified_bridge_diagnostic_split(
    indices: np.ndarray,
    target: np.ndarray,
    source: np.ndarray,
    *,
    seed: int,
    bridge_fraction: float = 2.0 / 3.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Split every represented source-label stratum before tokenization."""

    selected = np.asarray(indices, dtype=np.int64)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("target indices must be a nonempty vector")
    if not 0.0 < bridge_fraction < 1.0:
        raise ValueError("bridge_fraction must lie in (0, 1)")
    rng = np.random.default_rng(seed)
    bridge: list[int] = []
    diagnostic: list[int] = []
    groups = sorted(
        {(int(target[index]), int(source[index])) for index in selected}
    )
    for label, group_value in groups:
        cell = selected[
            (target[selected] == label) & (source[selected] == group_value)
        ].copy()
        rng.shuffle(cell)
        if len(cell) == 1:
            bridge.extend(cell.tolist())
            continue
        bridge_count = int(np.floor(bridge_fraction * len(cell)))
        bridge_count = min(max(1, bridge_count), len(cell) - 1)
        bridge.extend(cell[:bridge_count].tolist())
        diagnostic.extend(cell[bridge_count:].tolist())
    if not bridge or not diagnostic:
        raise ValueError("bridge or diagnostic split is empty")
    return (
        np.sort(np.asarray(bridge, dtype=np.int64)),
        np.sort(np.asarray(diagnostic, dtype=np.int64)),
    )


def nonconstant(channel: np.ndarray) -> bool:
    return not np.allclose(channel, channel[0:1], atol=1e-8, rtol=0.0)


def training_decoder(
    tokens: np.ndarray,
    target: np.ndarray,
    token_count: int,
) -> tuple[int, ...]:
    decoder = []
    for token in range(token_count):
        labels = target[tokens == token]
        decoder.append(int(labels.mean() >= 0.5) if len(labels) else 0)
    return tuple(decoder)


def sampled_release_tokens(
    fine_tokens: np.ndarray,
    channel: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    cumulative = np.cumsum(
        channel[np.asarray(fine_tokens, dtype=np.int64)],
        axis=1,
    )
    cumulative[:, -1] = 1.0
    uniforms = rng.random(len(fine_tokens))
    return np.sum(uniforms[:, None] > cumulative, axis=1).astype(np.int16)


def expected_balanced_accuracy(
    tokens: np.ndarray,
    labels: np.ndarray,
    channel: np.ndarray,
    decoder: tuple[int, ...],
) -> float:
    decoder_array = np.asarray(decoder)
    scores = []
    for label in (0, 1):
        current = tokens[labels == label]
        reward = (decoder_array == label).astype(np.float64)
        scores.append(float(np.mean(channel[current] @ reward)))
    return float(np.mean(scores))


def stratum_counts(
    indices: np.ndarray,
    target: np.ndarray,
    source: np.ndarray,
) -> list[list[int]]:
    return [
        [
            int(
                np.sum(
                    (target[indices] == label)
                    & (source[indices] == group)
                )
            )
            for group in (0, 1)
        ]
        for label in (0, 1)
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    prereg = validate_lock(args.prereg)
    manifest_path = args.store / "manifest.json"
    manifest, features, target, split, centers = load_store(
        args.store,
        str(prereg["store"]["manifest_sha256"]),
    )
    source = recode_source(centers)
    eligible = source >= 0
    training_pool = np.flatnonzero(
        eligible & (split == SPLIT_TRAIN)
    ).astype(np.int64)
    target_pool = np.flatnonzero(
        eligible & (split == SPLIT_VALIDATION)
    ).astype(np.int64)
    seeds = tuple(int(value) for value in prereg["seeds"])
    thresholds = tuple(float(value) for value in prereg["utility_thresholds"])
    primary_threshold = float(prereg["primary_utility_threshold"])
    privacy_threshold = float(prereg["privacy_advantage_threshold"])
    token_count = int(prereg["fine_token_count"])
    per_table_delta = float(prereg["familywise_delta"]) / (2.0 * len(seeds))
    operational_draws = int(
        prereg["operational_draws_per_primary_release"]
    )
    fold_caps = prereg["balanced_fold_caps"]
    args.output.mkdir(parents=True)
    receipts: list[dict[str, Any]] = []

    for seed in seeds:
        receipt: dict[str, Any] = {
            "seed": seed,
            "status": "started",
            "preregistration_sha256": sha256(args.prereg),
            "store_manifest_sha256": sha256(manifest_path),
            "candidate": "ResNet18::penultimate::task-score::K=4",
        }
        try:
            construction, reference = split_construction_reference(
                training_pool,
                target,
                source,
                construction_cap=int(fold_caps["construction"]),
                reference_cap=int(fold_caps["reference"]),
                seed=seed,
            )
            bridge, diagnostic = stratified_bridge_diagnostic_split(
                target_pool,
                target,
                source,
                seed=seed,
            )
            tokenizer = fit_score_tokenizer(
                np.asarray(features[construction]),
                target[construction],
                token_count=token_count,
                seed=seed,
            )
            construction_tokens = tokenizer.encode(
                np.asarray(features[construction])
            )
            reference_tokens = tokenizer.encode(
                np.asarray(features[reference])
            )
            bridge_tokens = tokenizer.encode(np.asarray(features[bridge]))
            diagnostic_tokens = tokenizer.encode(
                np.asarray(features[diagnostic])
            )
            reference_table = build_token_table(
                reference_tokens,
                target[reference],
                source[reference],
                token_count=token_count,
                familywise_delta=per_table_delta,
            )
            bridge_table = build_token_table(
                bridge_tokens,
                target[bridge],
                source[bridge],
                token_count=token_count,
                familywise_delta=per_table_delta,
            )
            bridge_certificate = certify_bridge_membership(
                reference_table.probabilities,
                reference_l1_radii=reference_table.l1_radii,
                bridge_empirical_distributions=bridge_table.probabilities,
                bridge_l1_radii=bridge_table.l1_radii,
            )
            solution = optimize_transform_exact_channel(
                reference_table.probabilities,
                l1_radii=reference_table.l1_radii,
                common_channels_by_label=(
                    bridge_certificate.transforms_by_label
                ),
                contaminations=bridge_certificate.contaminations,
                privacy_advantage_thresholds=(
                    privacy_threshold,
                    privacy_threshold,
                ),
                released_token_count=int(prereg["released_token_count"]),
                solver_time_limit_seconds=float(
                    prereg["solver_time_limit_seconds"]
                ),
                attacker_constraint_generation=bool(
                    prereg["attacker_constraint_generation"]
                ),
            )
            diagnostic_risk = evaluate_external_channel(
                diagnostic_tokens,
                target[diagnostic],
                source[diagnostic],
                solution.release_channel,
                solution.decoder,
            )
            raw_decoder = training_decoder(
                construction_tokens,
                target[construction],
                token_count,
            )
            raw_risk = evaluate_external_channel(
                diagnostic_tokens,
                target[diagnostic],
                source[diagnostic],
                np.eye(token_count),
                raw_decoder,
            )
            source_bounds = tuple(
                float(value.normalized_advantage)
                for value in solution.privacy_certificates
            )
            certified_error = float(
                solution.certified_worst_conditional_error
            )
            is_nonconstant = nonconstant(solution.release_channel)
            complete_support = bool(
                np.all(reference_table.counts.sum(axis=2) > 0)
                and np.all(bridge_table.counts.sum(axis=2) > 0)
                and diagnostic_risk.estimable
            )
            threshold_decisions = {
                f"{threshold:.2f}": bool(
                    complete_support
                    and is_nonconstant
                    and max(source_bounds)
                    <= privacy_threshold + 1e-10
                    and certified_error <= threshold + 1e-10
                )
                for threshold in thresholds
            }
            primary_release = threshold_decisions[
                f"{primary_threshold:.2f}"
            ]
            heldout_violation = bool(
                primary_release
                and (
                    diagnostic_risk.worst_privacy_advantage is None
                    or diagnostic_risk.worst_conditional_error is None
                    or diagnostic_risk.worst_privacy_advantage
                    > privacy_threshold
                    or diagnostic_risk.worst_conditional_error
                    > primary_threshold
                )
            )
            operational = []
            if primary_release:
                identity = np.eye(solution.released_token_count)
                for draw in range(operational_draws):
                    rng = np.random.default_rng(seed * 100_000 + draw)
                    released_tokens = sampled_release_tokens(
                        diagnostic_tokens,
                        solution.release_channel,
                        rng,
                    )
                    risk = evaluate_external_channel(
                        released_tokens,
                        target[diagnostic],
                        source[diagnostic],
                        identity,
                        solution.decoder,
                    )
                    operational.append(
                        {
                            "draw": draw,
                            "source_advantage": (
                                risk.worst_privacy_advantage
                            ),
                            "worst_conditional_error": (
                                risk.worst_conditional_error
                            ),
                            "violation": bool(
                                risk.worst_privacy_advantage is None
                                or risk.worst_conditional_error is None
                                or risk.worst_privacy_advantage
                                > privacy_threshold
                                or risk.worst_conditional_error
                                > primary_threshold
                            ),
                        }
                    )
            receipt.update(
                {
                    "status": "complete",
                    "source_definition": {
                        "0": sorted(SOURCE_ZERO_CENTERS),
                        "1": sorted(SOURCE_ONE_CENTERS),
                    },
                    "construction_stratum_counts": stratum_counts(
                        construction,
                        target,
                        source,
                    ),
                    "reference_stratum_counts": (
                        reference_table.counts.sum(axis=2).tolist()
                    ),
                    "bridge_stratum_counts": (
                        bridge_table.counts.sum(axis=2).tolist()
                    ),
                    "diagnostic_stratum_counts": stratum_counts(
                        diagnostic,
                        target,
                        source,
                    ),
                    "tokenizer_thresholds": list(tokenizer.thresholds),
                    "retained_masses": list(
                        bridge_certificate.retained_masses
                    ),
                    "contaminations": list(
                        bridge_certificate.contaminations
                    ),
                    "release_channel": solution.release_channel.tolist(),
                    "decoder": list(solution.decoder),
                    "nonconstant_release": is_nonconstant,
                    "certified_source_advantage_upper": list(source_bounds),
                    "certified_worst_conditional_error_upper": (
                        certified_error
                    ),
                    "threshold_decisions": threshold_decisions,
                    "primary_release": primary_release,
                    "heldout_source_advantage": (
                        diagnostic_risk.worst_privacy_advantage
                    ),
                    "heldout_worst_conditional_error": (
                        diagnostic_risk.worst_conditional_error
                    ),
                    "heldout_primary_violation": heldout_violation,
                    "raw_fine_token_decoder": list(raw_decoder),
                    "raw_fine_token_source_advantage": (
                        raw_risk.worst_privacy_advantage
                    ),
                    "raw_fine_token_worst_conditional_error": (
                        raw_risk.worst_conditional_error
                    ),
                    "released_expected_balanced_accuracy": (
                        expected_balanced_accuracy(
                            diagnostic_tokens,
                            target[diagnostic],
                            solution.release_channel,
                            solution.decoder,
                        )
                    ),
                    "operational_replays": operational,
                    "operational_violation_count": int(
                        sum(
                            bool(value["violation"])
                            for value in operational
                        )
                    ),
                    "solver_status": solution.solver_status,
                    "solver_mip_gap": solution.solver_mip_gap,
                    "solver_max_constraint_violation": (
                        solution.max_constraint_violation
                    ),
                }
            )
        except Exception as error:
            receipt.update(
                {
                    "status": "error",
                    "error_type": type(error).__name__,
                    "error": str(error),
                }
            )
        (args.output / f"seed-{seed}.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        receipts.append(receipt)

    complete = [row for row in receipts if row["status"] == "complete"]
    primary = [row for row in complete if row.get("primary_release")]
    heldout_violations = sum(
        bool(row["heldout_primary_violation"]) for row in primary
    )
    operational_trials = sum(
        len(row["operational_replays"]) for row in primary
    )
    operational_violations = sum(
        int(row["operational_violation_count"]) for row in primary
    )
    minimum_releases = int(
        prereg["main_paper_inclusion_gate"]["minimum_primary_releases"]
    )
    inclusion_gate = bool(
        len(complete) == len(seeds)
        and len(primary) >= minimum_releases
        and heldout_violations == 0
        and operational_violations == 0
    )
    summary = {
        "name": "MOSAIC Camelyon17 multi-hospital confirmation v1",
        "status": (
            "complete"
            if len(complete) == len(seeds)
            else "complete_with_errors"
        ),
        "preregistration_sha256": sha256(args.prereg),
        "store_manifest_sha256": sha256(manifest_path),
        "store_name": manifest["name"],
        "registered_seed_count": len(seeds),
        "completed_seed_count": len(complete),
        "primary_release_count": len(primary),
        "primary_heldout_violation_count": heldout_violations,
        "operational_replay_count": operational_trials,
        "operational_violation_count": operational_violations,
        "main_paper_inclusion_gate_passed": inclusion_gate,
        "utility_threshold_release_counts": {
            f"{threshold:.2f}": int(
                sum(
                    bool(
                        row["threshold_decisions"][f"{threshold:.2f}"]
                    )
                    for row in complete
                )
            )
            for threshold in thresholds
        },
        "receipts": [
            {
                "path": f"seed-{row['seed']}.json",
                "sha256": sha256(args.output / f"seed-{row['seed']}.json"),
                "status": row["status"],
            }
            for row in receipts
        ],
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
