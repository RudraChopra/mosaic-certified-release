#!/usr/bin/env python3
"""Run MOSAIC's data-certified bridge on the official erasure frontier."""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from mosaic_bridge import BridgeMembershipCertificate, certify_bridge_membership
from mosaic_real import (
    SPLIT_EXTERNAL,
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    TokenTable,
    balanced_stratum_sample,
    build_token_table,
    evaluate_external_channel,
    fit_score_tokenizer,
    load_frozen_store,
    sha256,
)
from mosaic_transform_exact_optimizer import optimize_transform_exact_channel
from official_eraser_adapters import EditedCandidate
from run_mosaic_official_frontier_exact_confirmation import (
    FRONTIER_CANDIDATE_COUNT,
    METHODS,
    atomic_json_dump,
    identity_candidate,
    materialize,
)
from run_mosaic_real_pilot import DATASETS
from run_official_eraser_frontier import (
    dispatch_candidates,
    preprocess,
    random_cap,
    split_eraser_train_construction,
)


ROOT = Path(__file__).resolve().parent
REPOSITORY = ROOT.parents[1]
FINE_TOKEN_COUNT = 4
PRIMARY_RELEASED_TOKEN_COUNT = 2
SECONDARY_RELEASED_TOKEN_COUNT = 4
FAMILYWISE_DELTA = 0.05
PRIVACY_THRESHOLD = 0.35
UTILITY_THRESHOLDS = (0.30, 0.35, 0.40, 0.45, 0.49)
PRIMARY_UTILITY_THRESHOLD = 0.40
BRIDGE_FRACTION = 2.0 / 3.0


@dataclass(frozen=True)
class CandidateContext:
    candidate: EditedCandidate
    reference_table: TokenTable
    bridge_table: TokenTable
    bridge_certificate: BridgeMembershipCertificate
    diagnostic_tokens: np.ndarray
    y_diagnostic: np.ndarray
    s_diagnostic: np.ndarray
    tokenizer_thresholds: tuple[float, ...]


def threshold_key(value: float) -> str:
    return f"{float(value):.2f}"


def stratified_bridge_diagnostic_split(
    indices: np.ndarray,
    target: np.ndarray,
    source: np.ndarray,
    *,
    seed: int,
    bridge_fraction: float = BRIDGE_FRACTION,
) -> tuple[np.ndarray, np.ndarray]:
    """Split every represented source-label stratum before tokenization."""

    selected = np.asarray(indices, dtype=np.int64)
    if selected.ndim != 1 or selected.size == 0:
        raise ValueError("external indices must be a nonempty vector")
    if not 0.0 < bridge_fraction < 1.0:
        raise ValueError("bridge_fraction must lie in (0, 1)")
    rng = np.random.default_rng(seed)
    bridge: list[int] = []
    diagnostic: list[int] = []
    groups = sorted(
        {(int(target[index]), int(source[index])) for index in selected}
    )
    for label, current_source in groups:
        group = selected[
            (target[selected] == label) & (source[selected] == current_source)
        ].copy()
        rng.shuffle(group)
        if len(group) == 1:
            bridge.extend(group.tolist())
            continue
        bridge_count = int(np.floor(bridge_fraction * len(group)))
        bridge_count = min(max(1, bridge_count), len(group) - 1)
        bridge.extend(group[:bridge_count].tolist())
        diagnostic.extend(group[bridge_count:].tolist())
    if not bridge:
        raise ValueError("bridge split is empty")
    return (
        np.sort(np.asarray(bridge, dtype=np.int64)),
        np.sort(np.asarray(diagnostic, dtype=np.int64)),
    )


def serialize_bridge(certificate: BridgeMembershipCertificate) -> dict[str, object]:
    return {
        "method": certificate.method,
        "retained_masses": list(certificate.retained_masses),
        "contaminations": list(certificate.contaminations),
        "labels": [
            {
                "transform": label.transform.tolist(),
                "retained_mass": label.retained_mass,
                "contamination": label.contamination,
                "optimal_retained_mass_upper": label.optimal_retained_mass_upper,
                "reference_l1_radii": list(label.reference_l1_radii),
                "bridge_l1_radii": list(label.bridge_l1_radii),
                "bridge_coordinate_lowers": [
                    list(row) for row in label.bridge_coordinate_lowers
                ],
                "minimum_membership_slack": label.minimum_membership_slack,
                "transform_trace": label.transform_trace,
                "solver_status": label.solver_status,
                "solver_iterations": label.solver_iterations,
            }
            for label in certificate.labels
        ],
    }


def prepare_candidate(
    candidate: EditedCandidate,
    *,
    y_construction: np.ndarray,
    y_reference: np.ndarray,
    s_reference: np.ndarray,
    y_bridge: np.ndarray,
    s_bridge: np.ndarray,
    y_diagnostic: np.ndarray,
    s_diagnostic: np.ndarray,
    reference_count: int,
    bridge_count: int,
    seed: int,
    familywise_delta: float,
) -> CandidateContext:
    reference = candidate.external[:reference_count]
    bridge_end = reference_count + bridge_count
    bridge = candidate.external[reference_count:bridge_end]
    diagnostic = candidate.external[bridge_end:]
    tokenizer = fit_score_tokenizer(
        candidate.validation,
        y_construction,
        token_count=FINE_TOKEN_COUNT,
        seed=seed,
    )
    reference_tokens = tokenizer.encode(reference)
    bridge_tokens = tokenizer.encode(bridge)
    diagnostic_tokens = (
        tokenizer.encode(diagnostic)
        if len(diagnostic)
        else np.asarray([], dtype=np.int16)
    )
    per_table_delta = familywise_delta / (2.0 * FRONTIER_CANDIDATE_COUNT)
    reference_table = build_token_table(
        reference_tokens,
        y_reference,
        s_reference,
        token_count=FINE_TOKEN_COUNT,
        familywise_delta=per_table_delta,
    )
    bridge_table = build_token_table(
        bridge_tokens,
        y_bridge,
        s_bridge,
        token_count=FINE_TOKEN_COUNT,
        familywise_delta=per_table_delta,
    )
    bridge_certificate = certify_bridge_membership(
        reference_table.probabilities,
        reference_l1_radii=reference_table.l1_radii,
        bridge_empirical_distributions=bridge_table.probabilities,
        bridge_l1_radii=bridge_table.l1_radii,
    )
    return CandidateContext(
        candidate=candidate,
        reference_table=reference_table,
        bridge_table=bridge_table,
        bridge_certificate=bridge_certificate,
        diagnostic_tokens=diagnostic_tokens,
        y_diagnostic=np.asarray(y_diagnostic, dtype=np.int64),
        s_diagnostic=np.asarray(s_diagnostic, dtype=np.int64),
        tokenizer_thresholds=tokenizer.thresholds,
    )


def evaluate_solution(
    context: CandidateContext,
    *,
    released_token_count: int,
    privacy_threshold: float,
    utility_thresholds: tuple[float, ...],
) -> dict[str, object]:
    certificate = context.bridge_certificate
    solution = optimize_transform_exact_channel(
        context.reference_table.probabilities,
        l1_radii=context.reference_table.l1_radii,
        common_channels_by_label=certificate.transforms_by_label,
        contaminations=certificate.contaminations,
        privacy_advantage_thresholds=(privacy_threshold, privacy_threshold),
        released_token_count=released_token_count,
        solver_time_limit_seconds=300.0,
    )
    privacy = [
        value.normalized_advantage for value in solution.privacy_certificates
    ]
    diagnostic = evaluate_external_channel(
        context.diagnostic_tokens,
        context.y_diagnostic,
        context.s_diagnostic,
        solution.release_channel,
        solution.decoder,
    )
    decisions: dict[str, object] = {}
    for threshold in utility_thresholds:
        deployed = bool(
            max(privacy) <= privacy_threshold + 1e-10
            and solution.certified_worst_conditional_error <= threshold + 1e-10
        )
        diagnostic_safe = bool(
            diagnostic.estimable
            and diagnostic.worst_privacy_advantage is not None
            and diagnostic.worst_conditional_error is not None
            and diagnostic.worst_privacy_advantage <= privacy_threshold + 1e-10
            and diagnostic.worst_conditional_error <= threshold + 1e-10
        )
        decisions[threshold_key(threshold)] = {
            "deployed": deployed,
            "diagnostic_safe": diagnostic_safe,
            "false_acceptance": bool(
                deployed and diagnostic.estimable and not diagnostic_safe
            ),
        }
    return {
        "certificate_method": solution.method,
        "released_token_count": released_token_count,
        "certified_worst_conditional_error": (
            solution.certified_worst_conditional_error
        ),
        "certified_privacy_advantages": privacy,
        "release_channel": solution.release_channel.tolist(),
        "decoder": list(solution.decoder),
        "solver_objective": solution.solver_objective,
        "solver_status": solution.solver_status,
        "solver_mip_gap": solution.solver_mip_gap,
        "solver_dual_bound": solution.solver_dual_bound,
        "max_constraint_violation": solution.max_constraint_violation,
        "solved_decoder_assignments": solution.solved_decoder_assignments,
        "diagnostic_estimable": diagnostic.estimable,
        "diagnostic_worst_privacy_advantage": (
            diagnostic.worst_privacy_advantage
        ),
        "diagnostic_worst_conditional_error": (
            diagnostic.worst_conditional_error
        ),
        "missing_diagnostic_strata": [
            list(value) for value in diagnostic.missing_strata
        ],
        "threshold_decisions": decisions,
    }


def base_result(context: CandidateContext) -> dict[str, object]:
    diagnostic_table = build_token_table(
        context.diagnostic_tokens,
        context.y_diagnostic,
        context.s_diagnostic,
        token_count=FINE_TOKEN_COUNT,
        familywise_delta=0.5,
    )
    return {
        "candidate": context.candidate.key,
        "method": context.candidate.method,
        "strength": context.candidate.strength,
        "provenance": context.candidate.provenance,
        "tokenizer_thresholds": list(context.tokenizer_thresholds),
        "reference_token_counts": context.reference_table.counts.tolist(),
        "reference_stratum_counts": (
            context.reference_table.counts.sum(axis=2).tolist()
        ),
        "reference_l1_radii": context.reference_table.l1_radii.tolist(),
        "bridge_token_counts": context.bridge_table.counts.tolist(),
        "bridge_stratum_counts": context.bridge_table.counts.sum(axis=2).tolist(),
        "bridge_l1_radii": context.bridge_table.l1_radii.tolist(),
        "diagnostic_token_counts": diagnostic_table.counts.tolist(),
        "diagnostic_stratum_counts": diagnostic_table.counts.sum(axis=2).tolist(),
        "bridge_membership": serialize_bridge(context.bridge_certificate),
    }


def select_candidate(
    results: list[dict[str, object]],
    *,
    release_key: str,
    utility_threshold: float,
) -> dict[str, object]:
    key = threshold_key(utility_threshold)
    eligible = [
        result
        for result in results
        if isinstance(result.get(release_key), dict)
        and result[release_key]["threshold_decisions"][key]["deployed"] is True
    ]
    if not eligible:
        return {
            "decision": "abstain",
            "candidate": None,
            "release_key": release_key,
            "utility_threshold": utility_threshold,
            "reason": "no candidate satisfied the bridge-certified contract",
        }
    selected = min(
        eligible,
        key=lambda result: (
            float(result[release_key]["certified_worst_conditional_error"]),
            str(result["candidate"]),
        ),
    )
    release = selected[release_key]
    decision = release["threshold_decisions"][key]
    return {
        "decision": "deploy",
        "candidate": selected["candidate"],
        "method": selected["method"],
        "strength": selected["strength"],
        "release_key": release_key,
        "released_token_count": release["released_token_count"],
        "utility_threshold": utility_threshold,
        "certified_worst_conditional_error": release[
            "certified_worst_conditional_error"
        ],
        "certified_privacy_advantages": release[
            "certified_privacy_advantages"
        ],
        "bridge_contaminations": selected["bridge_membership"][
            "contaminations"
        ],
        "diagnostic_estimable": release["diagnostic_estimable"],
        "diagnostic_worst_privacy_advantage": release[
            "diagnostic_worst_privacy_advantage"
        ],
        "diagnostic_worst_conditional_error": release[
            "diagnostic_worst_conditional_error"
        ],
        "diagnostic_safe": decision["diagnostic_safe"],
        "false_acceptance": decision["false_acceptance"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=tuple(DATASETS), required=True)
    parser.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--confirmation-prereg", type=Path)
    return parser.parse_args()


def expected_protocol() -> dict[str, object]:
    return {
        "fine_token_count": FINE_TOKEN_COUNT,
        "primary_released_token_count": PRIMARY_RELEASED_TOKEN_COUNT,
        "secondary_released_token_count": SECONDARY_RELEASED_TOKEN_COUNT,
        "frontier_candidate_count": FRONTIER_CANDIDATE_COUNT,
        "familywise_delta": FAMILYWISE_DELTA,
        "per_candidate_table_delta": FAMILYWISE_DELTA
        / (2.0 * FRONTIER_CANDIDATE_COUNT),
        "privacy_advantage_threshold": PRIVACY_THRESHOLD,
        "utility_thresholds": list(UTILITY_THRESHOLDS),
        "primary_utility_threshold": PRIMARY_UTILITY_THRESHOLD,
        "bridge_fraction": BRIDGE_FRACTION,
        "l4_policy": "reoptimize the minimum-error L2 candidate on the same covered table",
    }


def validate_confirmation_prereg(
    prereg_path: Path,
    *,
    dataset: str,
    seed: int,
    methods: list[str],
    smoke: bool,
) -> tuple[dict[str, object], str]:
    if smoke or tuple(methods) != METHODS:
        raise ValueError("confirmation requires the complete non-smoke frontier")
    prereg_sha = sha256(prereg_path)
    sidecar = prereg_path.with_suffix(prereg_path.suffix + ".sha256")
    if not sidecar.exists() or sidecar.read_text(encoding="utf-8").strip() != prereg_sha:
        raise ValueError("confirmation preregistration sidecar does not match")
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    if prereg.get("status") != "locked_before_confirmatory_outcomes":
        raise ValueError("confirmation preregistration is not locked")
    if dataset not in prereg.get("datasets", {}):
        raise ValueError("dataset is outside the locked confirmation")
    if seed not in prereg.get("confirmation_seeds", []):
        raise ValueError("seed is outside the locked confirmation")
    relative_runner = str(Path(__file__).resolve().relative_to(REPOSITORY))
    if prereg.get("code_sha256", {}).get(relative_runner) != sha256(Path(__file__)):
        raise ValueError("confirmation runner does not match its locked code hash")
    if prereg.get("protocol") != expected_protocol():
        raise ValueError("runner constants differ from the locked protocol")
    try:
        relative_prereg = prereg_path.resolve().relative_to(REPOSITORY.resolve())
        relative_sidecar = sidecar.resolve().relative_to(REPOSITORY.resolve())
    except ValueError as error:
        raise ValueError("confirmation preregistration must be inside the repository") from error
    for relative, path in (
        (relative_prereg, prereg_path),
        (relative_sidecar, sidecar),
    ):
        committed = subprocess.run(
            ["git", "show", f"HEAD:{relative.as_posix()}"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
        ).stdout
        if committed != path.read_bytes():
            raise ValueError(f"{relative} is not the committed lock")
    for relative, expected_hash in prereg.get("code_sha256", {}).items():
        if sha256(REPOSITORY / relative) != expected_hash:
            raise ValueError(f"locked code hash mismatch: {relative}")
    dataset_receipt = prereg["datasets"][dataset]
    if sha256(Path(dataset_receipt["path"]) / "manifest.json") != dataset_receipt[
        "manifest_sha256"
    ]:
        raise ValueError("frozen dataset manifest hash mismatch")
    for name, receipt in prereg.get("official_repositories", {}).items():
        path = Path(receipt["path"])
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        tracked_status = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            cwd=path,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        if head != receipt["commit"] or tracked_status:
            raise ValueError(f"official repository mismatch: {name}")
    return prereg, prereg_sha


def main() -> None:
    args = parse_args()
    prereg = None
    prereg_sha = None
    if args.confirmation_prereg is not None:
        prereg, prereg_sha = validate_confirmation_prereg(
            args.confirmation_prereg,
            dataset=args.dataset,
            seed=args.seed,
            methods=args.methods,
            smoke=args.smoke,
        )
        if args.output is None:
            raise ValueError("confirmation requires an explicit output path")
        if args.output.exists():
            raise FileExistsError(
                f"refusing to overwrite confirmation output: {args.output}"
            )

    config = DATASETS[args.dataset]
    store = load_frozen_store(
        Path(config["path"]), target_mode=str(config["target_mode"])
    )
    y = store.target
    s = store.source
    rng = np.random.default_rng(100_003 * args.seed + 2027)
    train_indices, construction_indices = split_eraser_train_construction(
        np.flatnonzero(store.split == SPLIT_TRAIN), y, s, s, rng
    )
    train_indices = random_cap(train_indices, 8000, rng)
    construction_indices = random_cap(construction_indices, 2000, rng)
    reference_indices = balanced_stratum_sample(
        np.flatnonzero(store.split == SPLIT_VALIDATION),
        y,
        s,
        maximum_total=8000,
        seed=args.seed * 100 + 2,
    )
    try:
        external_indices = balanced_stratum_sample(
            np.flatnonzero(store.split == SPLIT_EXTERNAL),
            y,
            s,
            maximum_total=12000,
            seed=args.seed * 100 + 3,
        )
    except ValueError:
        external_indices = np.flatnonzero(store.split == SPLIT_EXTERNAL).astype(
            np.int64
        )
        external_indices = random_cap(external_indices, 12000, rng)
    bridge_indices, diagnostic_indices = stratified_bridge_diagnostic_split(
        external_indices,
        y,
        s,
        seed=args.seed * 100 + 4,
    )

    train = materialize(store.features, train_indices)
    construction = materialize(store.features, construction_indices)
    reference = materialize(store.features, reference_indices)
    external_order = np.concatenate((bridge_indices, diagnostic_indices))
    external = materialize(store.features, external_order)
    (train, construction, reference, external), preprocessing = preprocess(
        train,
        construction,
        reference,
        external,
        dimension=128,
        seed=args.seed,
    )
    deployment = np.concatenate((reference, external), axis=0)
    y_deployment = np.concatenate((y[reference_indices], y[external_order]))
    s_deployment = np.concatenate((s[reference_indices], s[external_order]))

    candidates = [identity_candidate(train, construction, deployment)]
    for method in args.methods:
        print(f"running {args.dataset} {method}", flush=True)
        candidates.extend(
            dispatch_candidates(
                method,
                train,
                construction,
                deployment,
                y[train_indices],
                y[construction_indices],
                y_deployment,
                s[train_indices],
                s[construction_indices],
                s_deployment,
                seed=args.seed,
                smoke=args.smoke,
            )
        )

    contexts: list[CandidateContext] = []
    results: list[dict[str, object]] = []
    for candidate in candidates:
        try:
            context = prepare_candidate(
                candidate,
                y_construction=y[construction_indices],
                y_reference=y[reference_indices],
                s_reference=s[reference_indices],
                y_bridge=y[bridge_indices],
                s_bridge=s[bridge_indices],
                y_diagnostic=y[diagnostic_indices],
                s_diagnostic=s[diagnostic_indices],
                reference_count=len(reference_indices),
                bridge_count=len(bridge_indices),
                seed=args.seed,
                familywise_delta=FAMILYWISE_DELTA,
            )
            result = base_result(context)
            result["release_l2"] = evaluate_solution(
                context,
                released_token_count=PRIMARY_RELEASED_TOKEN_COUNT,
                privacy_threshold=PRIVACY_THRESHOLD,
                utility_thresholds=UTILITY_THRESHOLDS,
            )
            contexts.append(context)
            results.append(result)
        except (RuntimeError, ValueError) as error:
            results.append(
                {
                    "candidate": candidate.key,
                    "method": candidate.method,
                    "strength": candidate.strength,
                    "provenance": candidate.provenance,
                    "optimization_error": str(error),
                }
            )

    successful = [
        (result, context)
        for result, context in zip(
            [value for value in results if "optimization_error" not in value],
            contexts,
            strict=True,
        )
        if isinstance(result.get("release_l2"), dict)
    ]
    if successful:
        l4_result, l4_context = min(
            successful,
            key=lambda pair: (
                float(pair[0]["release_l2"]["certified_worst_conditional_error"]),
                str(pair[0]["candidate"]),
            ),
        )
        try:
            l4_result["release_l4"] = evaluate_solution(
                l4_context,
                released_token_count=SECONDARY_RELEASED_TOKEN_COUNT,
                privacy_threshold=PRIVACY_THRESHOLD,
                utility_thresholds=UTILITY_THRESHOLDS,
            )
        except (RuntimeError, ValueError) as error:
            l4_result["release_l4_error"] = str(error)

    selections = {
        threshold_key(threshold): select_candidate(
            results,
            release_key="release_l2",
            utility_threshold=threshold,
        )
        for threshold in UTILITY_THRESHOLDS
    }
    l4_rows = [value for value in results if isinstance(value.get("release_l4"), dict)]
    l4_comparison = None
    if l4_rows:
        row = l4_rows[0]
        l4_comparison = {
            "candidate": row["candidate"],
            "l2_certified_error": row["release_l2"][
                "certified_worst_conditional_error"
            ],
            "l4_certified_error": row["release_l4"][
                "certified_worst_conditional_error"
            ],
            "l2_diagnostic_error": row["release_l2"][
                "diagnostic_worst_conditional_error"
            ],
            "l4_diagnostic_error": row["release_l4"][
                "diagnostic_worst_conditional_error"
            ],
        }

    payload: dict[str, object] = {
        "project": "MOSAIC data-certified bridge frontier",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "seed": args.seed,
        "smoke": args.smoke,
        "prereg_sha256": prereg_sha,
        "protocol": expected_protocol(),
        "store_manifest_sha256": sha256(Path(config["path"]) / "manifest.json"),
        "preprocessing": preprocessing,
        "sample_counts": {
            "train": len(train_indices),
            "construction": len(construction_indices),
            "reference": len(reference_indices),
            "bridge": len(bridge_indices),
            "diagnostic": len(diagnostic_indices),
        },
        "bridge_stratum_counts": build_token_table(
            np.zeros(len(bridge_indices), dtype=np.int16),
            y[bridge_indices],
            s[bridge_indices],
            token_count=FINE_TOKEN_COUNT,
            familywise_delta=0.5,
        ).counts.sum(axis=2).tolist(),
        "diagnostic_stratum_counts": build_token_table(
            np.zeros(len(diagnostic_indices), dtype=np.int16),
            y[diagnostic_indices],
            s[diagnostic_indices],
            token_count=FINE_TOKEN_COUNT,
            familywise_delta=0.5,
        ).counts.sum(axis=2).tolist(),
        "results": results,
        "selection_by_utility_threshold": selections,
        "primary_selection": selections[threshold_key(PRIMARY_UTILITY_THRESHOLD)],
        "l4_interface_comparison": l4_comparison,
    }
    if prereg is not None:
        payload["claim_boundary"] = prereg["claim_boundary"]
    if args.output is None:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        atomic_json_dump(payload, args.output)
        print(args.output)


if __name__ == "__main__":
    main()
