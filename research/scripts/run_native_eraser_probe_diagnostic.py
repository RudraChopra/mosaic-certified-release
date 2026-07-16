"""Run one fixed method-native-probe diagnostic for VERA."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from sklearn.linear_model import SGDClassifier
from sklearn.metrics import balanced_accuracy_score

from official_eraser_adapters import EditedCandidate, _train_taco_head
from run_official_eraser_frontier import (
    SPLIT_EXTERNAL,
    SPLIT_TRAIN,
    SPLIT_VALIDATION,
    dispatch_candidates,
    load_store,
    make_attackers,
    materialize,
    preprocess,
    random_cap,
    split_eraser_train_construction,
)


DATASETS = ("Waterbirds", "CivilComments-WILDS", "Bios", "GaitPDB")
METHODS = ("inlp", "rlace", "leace", "taco", "mance")
SEEDS = tuple(range(45, 61))
MANCE_REPO = Path("/Volumes/Backups/FARO/external/mance")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def balanced(source: np.ndarray, prediction: np.ndarray) -> float | None:
    if len(np.unique(source)) < 2:
        return None
    return float(balanced_accuracy_score(source, prediction))


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def prepare_data(
    prereg: dict[str, Any], dataset: str, seed: int
) -> dict[str, Any]:
    study = prereg["real_study"]
    dataset_record = study["datasets"][dataset]
    store_dir = Path(dataset_record["store_dir"])
    if sha256(store_dir / "manifest.json") != dataset_record["manifest_sha256"]:
        raise RuntimeError("dataset store manifest hash mismatch")
    store = load_store(store_dir)
    rng = np.random.default_rng(100_003 * seed + 2027)
    train_indices, construction_indices = split_eraser_train_construction(
        np.flatnonzero(store.split == SPLIT_TRAIN), store.y, store.s, store.g, rng
    )
    train_indices = random_cap(train_indices, int(study["max_train"]), rng)
    construction_indices = random_cap(
        construction_indices, int(study["max_construction"]), rng
    )
    certification_indices = random_cap(
        np.flatnonzero(store.split == SPLIT_VALIDATION),
        int(study["max_certification"]),
        rng,
    )
    external_indices = random_cap(
        np.flatnonzero(store.split == SPLIT_EXTERNAL),
        int(study["max_external"]),
        rng,
    )
    train = materialize(store, train_indices)
    construction = materialize(store, construction_indices)
    certification = materialize(store, certification_indices)
    external = materialize(store, external_indices)
    representations, preprocessing = preprocess(
        train[0],
        construction[0],
        certification[0],
        external[0],
        dimension=int(study["pca_dimension"]),
        seed=seed,
    )
    return {
        "representations": representations,
        "train": train,
        "construction": construction,
        "certification": certification,
        "external": external,
        "preprocessing": preprocessing,
        "index_sha256": {
            "train": hashlib.sha256(train_indices.tobytes()).hexdigest(),
            "construction": hashlib.sha256(construction_indices.tobytes()).hexdigest(),
            "certification": hashlib.sha256(certification_indices.tobytes()).hexdigest(),
            "external": hashlib.sha256(external_indices.tobytes()).hexdigest(),
        },
    }


def mance_with_true_diagnostic_labels(
    train: np.ndarray,
    construction: np.ndarray,
    deployment: np.ndarray,
    y_train: np.ndarray,
    y_construction: np.ndarray,
    y_deployment: np.ndarray,
    s_train: np.ndarray,
    s_construction: np.ndarray,
    s_deployment: np.ndarray,
    *,
    seed: int,
) -> tuple[list[EditedCandidate], list[dict[str, Any]]]:
    sys.path.insert(0, str(MANCE_REPO))
    from mance import MANCE  # type: ignore

    eraser = MANCE(
        variant="mance++",
        epsilon=0.05,
        n_steps=3,
        n_neighbors=8,
        scorer_hidden=128,
        scorer_steps=120,
        scorer_refit_every=3,
        eval_hidden=64,
        eval_steps=80,
        seed=seed,
        device="cpu",
        stop_at_floor=False,
        verbose=False,
    )
    result = eraser.fit_erase(
        train,
        s_train,
        construction,
        s_construction,
        deployment,
        s_deployment,
        control_train=y_train,
        control_val=y_construction,
        control_test=y_deployment,
    )
    candidate = EditedCandidate(
        method="MANCE++",
        strength="epsilon=0.05,steps=3",
        train=result.train.astype(np.float32),
        validation=result.val.astype(np.float32),
        external=result.test.astype(np.float32),
        provenance={"diagnostic_true_labels_only": True},
    )
    return [candidate], list(result.history)


def fresh_attacker_metrics(
    candidate: EditedCandidate,
    source_train: np.ndarray,
    source_certification: np.ndarray,
    source_external: np.ndarray,
    certification_n: int,
    seed: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, attacker in make_attackers(seed, candidate.train.shape[1]).items():
        attacker.fit(candidate.train, source_train)
        certification_prediction = attacker.predict(
            candidate.external[:certification_n]
        )
        external_prediction = attacker.predict(candidate.external[certification_n:])
        result[name] = {
            "certification_accuracy": float(
                np.mean(certification_prediction == source_certification)
            ),
            "certification_balanced_accuracy": balanced(
                source_certification, certification_prediction
            ),
            "external_accuracy": float(
                np.mean(external_prediction == source_external)
            ),
            "external_balanced_accuracy": balanced(
                source_external, external_prediction
            ),
        }
    return result


def inlp_native(
    candidate: EditedCandidate,
    source_train: np.ndarray,
    source_construction: np.ndarray,
    source_certification: np.ndarray,
    source_external: np.ndarray,
    certification_n: int,
    seed: int,
) -> dict[str, Any]:
    classifier = SGDClassifier(
        loss="log_loss",
        fit_intercept=True,
        max_iter=5000,
        tol=1e-4,
        n_iter_no_change=20,
        alpha=1e-4,
        n_jobs=8,
        random_state=seed,
    )
    classifier.fit(candidate.train, source_train)
    certification_prediction = classifier.predict(
        candidate.external[:certification_n]
    )
    external_prediction = classifier.predict(candidate.external[certification_n:])
    return {
        "status": "available",
        "type": "official_native_classifier_refit_post_edit",
        "construction_accuracy": float(
            classifier.score(candidate.validation, source_construction)
        ),
        "certification_accuracy": float(
            np.mean(certification_prediction == source_certification)
        ),
        "certification_balanced_accuracy": balanced(
            source_certification, certification_prediction
        ),
        "external_accuracy": float(
            np.mean(external_prediction == source_external)
        ),
        "external_balanced_accuracy": balanced(
            source_external, external_prediction
        ),
    }


def taco_native(
    candidates: list[EditedCandidate],
    train: np.ndarray,
    construction: np.ndarray,
    source_train: np.ndarray,
    source_construction: np.ndarray,
    source_certification: np.ndarray,
    source_external: np.ndarray,
    certification_n: int,
    seed: int,
) -> dict[str, dict[str, Any]]:
    head = _train_taco_head(
        train,
        source_train,
        construction,
        source_construction,
        seed=seed + 211,
        steps=250,
        device="cpu",
    )
    output: dict[str, dict[str, Any]] = {}
    with torch.no_grad():
        for candidate in candidates:
            certification_prediction = (
                head(
                    torch.from_numpy(
                        np.asarray(
                            candidate.external[:certification_n], dtype=np.float32
                        )
                    )
                )
                .argmax(1)
                .cpu()
                .numpy()
            )
            external_prediction = (
                head(
                    torch.from_numpy(
                        np.asarray(
                            candidate.external[certification_n:], dtype=np.float32
                        )
                    )
                )
                .argmax(1)
                .cpu()
                .numpy()
            )
            output[candidate.key] = {
                "status": "available",
                "type": "method_native_pre_edit_source_head_post_edit_evaluation",
                "certification_accuracy": float(
                    np.mean(certification_prediction == source_certification)
                ),
                "certification_balanced_accuracy": balanced(
                    source_certification, certification_prediction
                ),
                "external_accuracy": float(
                    np.mean(external_prediction == source_external)
                ),
                "external_balanced_accuracy": balanced(
                    source_external, external_prediction
                ),
            }
    return output


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, required=True)
    parser.add_argument("--hash-file", type=Path, required=True)
    parser.add_argument("--dataset", choices=DATASETS, required=True)
    parser.add_argument("--method", choices=METHODS, required=True)
    parser.add_argument("--seed", type=int, choices=SEEDS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def analyze(args: argparse.Namespace) -> dict[str, Any]:
    expected_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    if sha256(args.prereg) != expected_hash:
        raise RuntimeError("controlled-shift preregistration hash mismatch")
    prereg = load_json(args.prereg)
    if prereg.get("status") != "locked_before_claim_grade_runs":
        raise RuntimeError("controlled-shift preregistration is not locked")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    data = prepare_data(prereg, args.dataset, args.seed)
    train, construction, certification, external = data["representations"]
    y_train, s_train = data["train"][1:3]
    y_construction, s_construction = data["construction"][1:3]
    y_certification, s_certification = data["certification"][1:3]
    y_external, s_external = data["external"][1:3]
    deployment = np.concatenate([certification, external], axis=0)
    y_deployment = np.concatenate([y_certification, y_external])
    s_deployment = np.concatenate([s_certification, s_external])
    mance_history: list[dict[str, Any]] | None = None
    if args.method == "mance":
        candidates, mance_history = mance_with_true_diagnostic_labels(
            train,
            construction,
            deployment,
            y_train,
            y_construction,
            y_deployment,
            s_train,
            s_construction,
            s_deployment,
            seed=args.seed,
        )
    else:
        candidates = dispatch_candidates(
            args.method,
            train,
            construction,
            deployment,
            y_train,
            y_construction,
            y_deployment,
            s_train,
            s_construction,
            s_deployment,
            seed=args.seed,
            smoke=False,
        )
    taco_outputs = (
        taco_native(
            candidates,
            train,
            construction,
            s_train,
            s_construction,
            s_certification,
            s_external,
            len(certification),
            args.seed,
        )
        if args.method == "taco"
        else {}
    )
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        if args.method == "inlp":
            native = inlp_native(
                candidate,
                s_train,
                s_construction,
                s_certification,
                s_external,
                len(certification),
                args.seed,
            )
        elif args.method == "rlace":
            native = {
                "status": "available",
                "type": "official_upstream_training_score",
                "reported_upstream_score": candidate.provenance[
                    "reported_upstream_score"
                ],
                "external_comparability": False,
            }
        elif args.method == "leace":
            native = {
                "status": "NA",
                "reason": "the pinned closed-form eraser has no native classifier",
            }
        elif args.method == "taco":
            native = taco_outputs[candidate.key]
        else:
            assert mance_history is not None
            final_history = json_safe(mance_history[-1])
            native = {
                "status": "available",
                "type": "official_native_neural_probe_trajectory",
                "history": json_safe(mance_history),
                "external_accuracy": final_history.get("concept_acc"),
                "external_labels_used_for_diagnostic_only": True,
            }
        records.append(
            {
                "candidate_key": candidate.key,
                "method_native": native,
                "fresh_registered_attackers": fresh_attacker_metrics(
                    candidate,
                    s_train,
                    s_certification,
                    s_external,
                    len(certification),
                    args.seed,
                ),
            }
        )
    return {
        "schema_version": 1,
        "name": "VERA method-native probe diagnostic run",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": args.dataset,
        "method": args.method,
        "seed": args.seed,
        "preregistration_sha256": expected_hash,
        "index_sha256": data["index_sha256"],
        "preprocessing": data["preprocessing"],
        "candidate_count": len(records),
        "records": records,
        "independent_unit": "seed",
        "formal_guarantee": False,
        "cross_method_native_probe_equivalence_claimed": False,
        "can_change_primary_gate": False,
    }


def main() -> int:
    args = parse_args()
    if args.output.exists() or args.output.is_symlink():
        raise RuntimeError(f"diagnostic output already exists: {args.output}")
    report = analyze(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "completed",
                "candidate_count": report["candidate_count"],
                "output": str(args.output),
                "output_sha256": sha256(args.output),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
