#!/usr/bin/env python3
"""Run the predetermined unlocked Qwen CivilComments architecture pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from mosaic_bridge import certify_bridge_membership
from mosaic_real import (
    SPLIT_EXTERNAL,
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    build_token_table,
    evaluate_external_channel,
    fit_score_tokenizer,
    load_frozen_store,
)
from mosaic_transform_exact_optimizer import optimize_transform_exact_channel
from run_mosaic_bridge_frontier import stratified_bridge_diagnostic_split


REPOSITORY = Path(__file__).resolve().parents[2]
DEFAULT_STORE_ROOT = Path("/Volumes/Backups/FARO/artifacts/civilcomments_qwen25_pilot")
DEFAULT_OUTPUT = REPOSITORY / "research" / "artifacts" / "mosaic_qwen_pilot_v1.json"
REPRESENTATIONS = ("layer14_mean", "layer28_mean", "layer28_last")
FINE_TOKEN_COUNTS = (4, 8)
FAMILYWISE_DELTA = 0.05
PRIVACY_THRESHOLD = 0.35
UTILITY_THRESHOLDS = (0.30, 0.35, 0.40, 0.45, 0.49)
PRIMARY_UTILITY_THRESHOLD = 0.40
PILOT_SEED = 2027


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def nonconstant(channel: np.ndarray) -> bool:
    return not np.allclose(channel, channel[0:1], atol=1e-8, rtol=0.0)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite {args.output}")
    candidate_count = len(REPRESENTATIONS) * len(FINE_TOKEN_COUNTS)
    per_table_delta = FAMILYWISE_DELTA / (2.0 * candidate_count)
    candidates: list[dict[str, object]] = []

    for representation in REPRESENTATIONS:
        store_path = args.store_root / representation
        store = load_frozen_store(store_path)
        train = np.flatnonzero(store.split == SPLIT_TRAIN)
        reference = np.flatnonzero(store.split == SPLIT_VALIDATION)
        external = np.flatnonzero(store.split == SPLIT_EXTERNAL)
        bridge, diagnostic = stratified_bridge_diagnostic_split(
            external,
            store.target,
            store.source,
            seed=PILOT_SEED,
        )
        for token_count in FINE_TOKEN_COUNTS:
            key = f"{representation}::K={token_count}"
            tokenizer = fit_score_tokenizer(
                store.features[train],
                store.target[train],
                token_count=token_count,
                seed=PILOT_SEED,
            )
            reference_tokens = tokenizer.encode(store.features[reference])
            bridge_tokens = tokenizer.encode(store.features[bridge])
            diagnostic_tokens = tokenizer.encode(store.features[diagnostic])
            reference_table = build_token_table(
                reference_tokens,
                store.target[reference],
                store.source[reference],
                token_count=token_count,
                familywise_delta=per_table_delta,
            )
            bridge_table = build_token_table(
                bridge_tokens,
                store.target[bridge],
                store.source[bridge],
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
                common_channels_by_label=bridge_certificate.transforms_by_label,
                contaminations=bridge_certificate.contaminations,
                privacy_advantage_thresholds=(PRIVACY_THRESHOLD, PRIVACY_THRESHOLD),
                released_token_count=2,
                solver_time_limit_seconds=300.0,
            )
            diagnostic_risk = evaluate_external_channel(
                diagnostic_tokens,
                store.target[diagnostic],
                store.source[diagnostic],
                solution.release_channel,
                solution.decoder,
            )
            source_upper = [
                float(value.normalized_advantage) for value in solution.privacy_certificates
            ]
            minimum_retained = float(min(bridge_certificate.retained_masses))
            is_nonconstant = nonconstant(solution.release_channel)
            error = float(solution.certified_worst_conditional_error)
            complete_strata = bool(
                np.all(reference_table.counts.sum(axis=2) > 0)
                and np.all(bridge_table.counts.sum(axis=2) > 0)
                and diagnostic_risk.estimable
            )
            go = bool(
                complete_strata
                and minimum_retained >= 0.50
                and is_nonconstant
                and error <= 0.49
                and max(source_upper) <= PRIVACY_THRESHOLD + 1e-10
            )
            candidates.append(
                {
                    "candidate": key,
                    "representation_manifest_sha256": sha256(store_path / "manifest.json"),
                    "token_count": token_count,
                    "tokenizer_thresholds": list(tokenizer.thresholds),
                    "reference_stratum_counts": reference_table.counts.sum(axis=2).tolist(),
                    "bridge_stratum_counts": bridge_table.counts.sum(axis=2).tolist(),
                    "diagnostic_stratum_counts": [
                        [
                            int(np.sum((store.target[diagnostic] == y) & (store.source[diagnostic] == s)))
                            for s in (0, 1)
                        ]
                        for y in (0, 1)
                    ],
                    "retained_masses": list(bridge_certificate.retained_masses),
                    "contaminations": list(bridge_certificate.contaminations),
                    "minimum_retained_mass": minimum_retained,
                    "release_channel": solution.release_channel.tolist(),
                    "decoder": list(solution.decoder),
                    "nonconstant_release": is_nonconstant,
                    "certified_source_advantage_upper": source_upper,
                    "certified_worst_conditional_error_upper": error,
                    "diagnostic_estimable": diagnostic_risk.estimable,
                    "diagnostic_source_advantage": diagnostic_risk.worst_privacy_advantage,
                    "diagnostic_worst_conditional_error": diagnostic_risk.worst_conditional_error,
                    "pilot_go": go,
                }
            )

    eligible = [candidate for candidate in candidates if candidate["pilot_go"]]
    selected = (
        min(
            eligible,
            key=lambda value: (
                float(value["certified_worst_conditional_error_upper"]),
                -float(value["minimum_retained_mass"]),
                str(value["candidate"]),
            ),
        )
        if eligible
        else None
    )
    report = {
        "name": "MOSAIC Qwen2.5 CivilComments unlocked pilot v1",
        "status": "complete_unlocked_pilot",
        "confirmatory_evidence": False,
        "protocol": {
            "candidate_count": candidate_count,
            "familywise_delta": FAMILYWISE_DELTA,
            "per_table_delta": per_table_delta,
            "privacy_threshold": PRIVACY_THRESHOLD,
            "utility_thresholds": list(UTILITY_THRESHOLDS),
            "primary_utility_threshold": PRIMARY_UTILITY_THRESHOLD,
            "pilot_partition": "integer dataset id modulo 4 equals 0",
            "confirmation_partition": "integer dataset id modulo 4 is nonzero",
        },
        "go_to_locked_confirmation": selected is not None,
        "selected_candidate": selected,
        "candidates": candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(args.output),
                "go_to_locked_confirmation": selected is not None,
                "selected_candidate": selected["candidate"] if selected else None,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
