#!/usr/bin/env python3
"""Run the locked five-seed CINIC-10 natural-origin confirmation."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
import torch
from concept_erasure import LeaceFitter
from sklearn.metrics import balanced_accuracy_score

from mosaic_bridge import certify_bridge_membership
from mosaic_real import (
    build_token_table,
    evaluate_external_channel,
    fit_score_tokenizer,
    load_frozen_store,
)
from mosaic_transform_exact_optimizer import optimize_transform_exact_channel


ROOT = Path(__file__).resolve().parents[2]
PREREG = ROOT / "research/mosaic/prereg_mosaic_cinic10_natural_v1.json"
STORE = Path("/Users/rudrachopra/.cache/cinic10_natural_origin_numpy_store")
OUTPUT = ROOT / "research/artifacts/mosaic_cinic10_natural_v1.json"
SEEDS = (4101, 4102, 4103, 4104, 4105)
PRIVACY_THRESHOLD = 0.35
UTILITY_THRESHOLDS = (0.30, 0.35, 0.40, 0.45)
PRIMARY_UTILITY_THRESHOLD = 0.40
FAMILY_FAILURE = 0.05
FINE_TOKEN_COUNT = 4


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_lock() -> dict[str, object]:
    sidecar = PREREG.with_suffix(PREREG.suffix + ".sha256")
    if sidecar.read_text(encoding="utf-8").strip() != sha256(PREREG):
        raise ValueError("CINIC preregistration sidecar mismatch")
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    if prereg["status"] != "locked_before_confirmatory_outcomes":
        raise ValueError("CINIC preregistration status mismatch")
    if sha256(STORE / "manifest.json") != prereg["store_manifest_sha256"]:
        raise ValueError("CINIC store manifest mismatch")
    for relative, expected in prereg["code_sha256"].items():
        if sha256(ROOT / relative) != expected:
            raise ValueError(f"locked code mismatch: {relative}")
    for path in (PREREG, sidecar):
        relative = path.relative_to(ROOT)
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative.as_posix()}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise ValueError(f"{relative} is not the committed lock")
    return prereg


def balanced_take(
    pool: np.ndarray,
    labels: np.ndarray,
    sources: np.ndarray,
    *,
    maximum_total: int,
    rng: np.random.Generator,
) -> np.ndarray:
    cells = [
        np.asarray(pool[(labels[pool] == label) & (sources[pool] == source)])
        for label in (0, 1)
        for source in (0, 1)
    ]
    per_cell = min(min(len(cell) for cell in cells), maximum_total // 4)
    selected = []
    for cell in cells:
        selected.append(rng.choice(cell, size=per_cell, replace=False))
    return np.sort(np.concatenate(selected).astype(np.int64))


def split_balanced(
    pool: np.ndarray,
    labels: np.ndarray,
    sources: np.ndarray,
    *,
    first_total: int,
    second_total: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    first = balanced_take(
        pool, labels, sources, maximum_total=first_total, rng=rng
    )
    remainder = np.setdiff1d(pool, first, assume_unique=False)
    second = balanced_take(
        remainder, labels, sources, maximum_total=second_total, rng=rng
    )
    return first, second


def leace_features(
    train: np.ndarray,
    sources: np.ndarray,
    arrays: tuple[np.ndarray, ...],
) -> tuple[np.ndarray, ...]:
    one_hot = np.eye(2, dtype=np.float32)[sources.astype(np.int64)]
    fitter = LeaceFitter.fit(
        torch.from_numpy(train.astype(np.float32, copy=False)),
        torch.from_numpy(one_hot),
        method="leace",
    )
    with torch.inference_mode():
        return tuple(
            fitter.eraser(
                torch.from_numpy(values.astype(np.float32, copy=False))
            )
            .cpu()
            .numpy()
            .astype(np.float32, copy=False)
            for values in arrays
        )


def expected_balanced_accuracy(
    tokens: np.ndarray,
    labels: np.ndarray,
    channel: np.ndarray,
    decoder: tuple[int, ...],
) -> float:
    values = []
    decoded = np.asarray(decoder, dtype=np.int64)
    for label in (0, 1):
        rows = tokens[labels == label]
        probability_correct = channel[rows][:, decoded == label].sum(axis=1)
        values.append(float(probability_correct.mean()))
    return float(np.mean(values))


def main() -> None:
    prereg = validate_lock()
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUTPUT}")
    store = load_frozen_store(STORE)
    train_pool = np.flatnonzero(store.split == 0)
    reference_pool = np.flatnonzero(store.split == 1)
    target_pool = np.flatnonzero(store.split == 2)
    per_table_delta = FAMILY_FAILURE / (len(SEEDS) * 2 * 2)
    rows = []
    for seed in SEEDS:
        rng = np.random.default_rng(seed)
        eraser_train, construction = split_balanced(
            train_pool,
            store.target,
            store.source,
            first_total=8000,
            second_total=4000,
            rng=rng,
        )
        reference = balanced_take(
            reference_pool,
            store.target,
            store.source,
            maximum_total=8000,
            rng=rng,
        )
        bridge, diagnostic = split_balanced(
            target_pool,
            store.target,
            store.source,
            first_total=8000,
            second_total=8000,
            rng=rng,
        )
        candidate_arrays = {
            "Identity::unedited": (
                store.features[construction],
                store.features[reference],
                store.features[bridge],
                store.features[diagnostic],
            )
        }
        candidate_arrays["LEACE::closed_form"] = leace_features(
            store.features[eraser_train],
            store.source[eraser_train],
            candidate_arrays["Identity::unedited"],
        )
        candidates = []
        for candidate, arrays in candidate_arrays.items():
            construction_x, reference_x, bridge_x, diagnostic_x = arrays
            tokenizer = fit_score_tokenizer(
                construction_x,
                store.target[construction],
                token_count=FINE_TOKEN_COUNT,
                seed=seed,
            )
            reference_tokens = tokenizer.encode(reference_x)
            bridge_tokens = tokenizer.encode(bridge_x)
            diagnostic_tokens = tokenizer.encode(diagnostic_x)
            reference_table = build_token_table(
                reference_tokens,
                store.target[reference],
                store.source[reference],
                token_count=FINE_TOKEN_COUNT,
                familywise_delta=per_table_delta,
            )
            bridge_table = build_token_table(
                bridge_tokens,
                store.target[bridge],
                store.source[bridge],
                token_count=FINE_TOKEN_COUNT,
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
                common_channels_by_label=bridge_certificate.transforms_by_label,
                contaminations=bridge_certificate.contaminations,
                privacy_advantage_thresholds=(
                    PRIVACY_THRESHOLD,
                    PRIVACY_THRESHOLD,
                ),
                released_token_count=2,
                maximum_worst_conditional_error=max(UTILITY_THRESHOLDS),
                solver_time_limit_seconds=300.0,
            )
            diagnostic_risk = evaluate_external_channel(
                diagnostic_tokens,
                store.target[diagnostic],
                store.source[diagnostic],
                solution.release_channel,
                solution.decoder,
            )
            source_bounds = [
                float(value.normalized_advantage)
                for value in solution.privacy_certificates
            ]
            decisions = {}
            for threshold in UTILITY_THRESHOLDS:
                deployed = bool(
                    max(source_bounds) <= PRIVACY_THRESHOLD + 1e-10
                    and solution.certified_worst_conditional_error
                    <= threshold + 1e-10
                )
                safe = bool(
                    diagnostic_risk.estimable
                    and diagnostic_risk.worst_privacy_advantage is not None
                    and diagnostic_risk.worst_conditional_error is not None
                    and diagnostic_risk.worst_privacy_advantage
                    <= PRIVACY_THRESHOLD + 1e-10
                    and diagnostic_risk.worst_conditional_error
                    <= threshold + 1e-10
                )
                decisions[f"{threshold:.2f}"] = {
                    "deployed": deployed,
                    "diagnostic_safe": safe,
                    "false_acceptance": bool(deployed and not safe),
                }
            construction_tokens = tokenizer.encode(construction_x)
            raw_decoder = tuple(
                int(
                    store.target[construction][
                        construction_tokens == token
                    ].mean()
                    >= 0.5
                )
                if np.any(construction_tokens == token)
                else 0
                for token in range(FINE_TOKEN_COUNT)
            )
            raw_predictions = np.asarray(raw_decoder)[diagnostic_tokens]
            candidates.append(
                {
                    "candidate": candidate,
                    "tokenizer_thresholds": list(tokenizer.thresholds),
                    "reference_stratum_counts": reference_table.counts.sum(
                        axis=2
                    ).tolist(),
                    "bridge_stratum_counts": bridge_table.counts.sum(
                        axis=2
                    ).tolist(),
                    "diagnostic_examples": int(len(diagnostic)),
                    "retained_masses": list(
                        bridge_certificate.retained_masses
                    ),
                    "certified_source_advantage_upper": source_bounds,
                    "certified_worst_conditional_error_upper": float(
                        solution.certified_worst_conditional_error
                    ),
                    "diagnostic_source_advantage": (
                        diagnostic_risk.worst_privacy_advantage
                    ),
                    "diagnostic_worst_conditional_error": (
                        diagnostic_risk.worst_conditional_error
                    ),
                    "released_expected_balanced_accuracy": (
                        expected_balanced_accuracy(
                            diagnostic_tokens,
                            store.target[diagnostic],
                            solution.release_channel,
                            solution.decoder,
                        )
                    ),
                    "unedited_token_balanced_accuracy": float(
                        balanced_accuracy_score(
                            store.target[diagnostic], raw_predictions
                        )
                    ),
                    "release_channel": solution.release_channel.tolist(),
                    "decoder": list(solution.decoder),
                    "threshold_decisions": decisions,
                }
            )
        primary_key = f"{PRIMARY_UTILITY_THRESHOLD:.2f}"
        eligible = [
            value
            for value in candidates
            if value["threshold_decisions"][primary_key]["deployed"]
        ]
        selected = (
            min(
                eligible,
                key=lambda value: (
                    value["certified_worst_conditional_error_upper"],
                    value["candidate"],
                ),
            )["candidate"]
            if eligible
            else None
        )
        rows.append(
            {"seed": seed, "selected_primary_candidate": selected, "candidates": candidates}
        )
    primary_rows = [
        candidate
        for row in rows
        for candidate in row["candidates"]
        if candidate["candidate"] == row["selected_primary_candidate"]
    ]
    primary_releases = len(primary_rows)
    false_acceptances = sum(
        value["threshold_decisions"][f"{PRIMARY_UTILITY_THRESHOLD:.2f}"][
            "false_acceptance"
        ]
        for value in primary_rows
    )
    payload = {
        "name": "MOSAIC CINIC-10 natural-origin confirmation v1",
        "preregistration_sha256": sha256(PREREG),
        "store_manifest_sha256": sha256(STORE / "manifest.json"),
        "protocol": prereg["protocol"],
        "rows": rows,
        "summary": {
            "primary_releases": primary_releases,
            "primary_false_acceptances": false_acceptances,
            "primary_release_rate": primary_releases / len(SEEDS),
            "pass": bool(primary_releases >= 3 and false_acceptances == 0),
        },
        "pass": bool(primary_releases >= 3 and false_acceptances == 0),
        "claim_boundary": (
            "The image-origin shift is natural and file-provenanced, while "
            "the frozen ResNet-18 encoder was pretrained on ImageNet. This "
            "tests release certification, not independent image recognition."
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload["summary"], indent=2))


if __name__ == "__main__":
    main()
