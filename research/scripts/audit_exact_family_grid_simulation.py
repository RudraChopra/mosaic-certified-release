"""Independently replay the locked VERA n-by-m-by-group coverage grid."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import beta


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PREREG = ROOT / "prereg_exact_family_grid.json"
DEFAULT_HASH = ROOT / "prereg_exact_family_grid.sha256"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_exact_family_grid_report.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_exact_family_grid_audit.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def binomial_upper(counts: np.ndarray | int, total: int, alpha: float) -> np.ndarray:
    counts_array = np.asarray(counts)
    result = np.ones(counts_array.shape, dtype=np.float64)
    interior = counts_array < total
    result[interior] = beta.ppf(
        1.0 - alpha,
        counts_array[interior] + 1,
        total - counts_array[interior],
    )
    return result


def binomial_lower(counts: np.ndarray | int, total: int, alpha: float) -> np.ndarray:
    counts_array = np.asarray(counts)
    result = np.zeros(counts_array.shape, dtype=np.float64)
    interior = counts_array > 0
    result[interior] = beta.ppf(
        alpha,
        counts_array[interior],
        total - counts_array[interior] + 1,
    )
    return result


def paired_worst_case(
    positive: np.ndarray, negative: np.ndarray, ratio_cap: float
) -> np.ndarray:
    feasible_positive = np.minimum(positive, 1.0 - negative)
    neutral = np.maximum(0.0, 1.0 - feasible_positive - negative)
    shifted_positive = np.minimum(1.0, ratio_cap * feasible_positive)
    unfilled = 1.0 - shifted_positive
    shifted_neutral = np.minimum(unfilled, ratio_cap * neutral)
    shifted_negative = np.maximum(0.0, unfilled - shifted_neutral)
    return shifted_positive - shifted_negative


def make_probabilities(
    config: dict[str, Any], candidate_count: int, group_count: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    offsets = (
        np.asarray([0.0])
        if group_count == 1
        else np.linspace(-0.005, 0.005, group_count)
    )
    target_base = np.asarray(
        config["candidate_target_positive_probabilities"][:candidate_count],
        dtype=np.float64,
    )
    target = target_base[:, None] + offsets[None, :]
    identity_index = int(config["identity_candidate_index"])
    if identity_index < candidate_count:
        target[identity_index] = 0.0
    target_negative = np.asarray(
        config["candidate_target_negative_probabilities"][:candidate_count],
        dtype=np.float64,
    )
    leakage = np.asarray(
        config["candidate_balanced_leakage_probabilities"][:candidate_count],
        dtype=np.float64,
    )[:, None, None]
    leakage = leakage + np.asarray(
        config["attacker_probability_offsets"], dtype=np.float64
    )[None, :, None]
    leakage = leakage + np.asarray(
        config["class_recall_offsets"], dtype=np.float64
    )[None, None, :]
    return target, target_negative, leakage


def replay_cell(
    payload: tuple[dict[str, Any], int, int, int, float, int]
) -> dict[str, Any]:
    config, n, candidate_count, group_count, delta, seed = payload
    random = np.random.default_rng(seed)
    repeats = int(config["replicates"])
    ratio_cap = float(config["gamma"])
    target_probability, target_negative_probability, leakage_probability = make_probabilities(
        config, candidate_count, group_count
    )
    group_trials = n // group_count
    class_trials = n // 2
    local_alpha = delta / candidate_count

    target_counts = np.empty(
        (repeats, candidate_count, group_count, 3), dtype=np.int64
    )
    for candidate in range(candidate_count):
        for group in range(group_count):
            positive_probability = float(target_probability[candidate, group])
            negative_probability = float(target_negative_probability[candidate])
            target_counts[:, candidate, group] = random.multinomial(
                group_trials,
                (
                    negative_probability,
                    1.0 - positive_probability - negative_probability,
                    positive_probability,
                ),
                size=repeats,
            )
    target_bound = paired_worst_case(
        binomial_upper(
            target_counts[..., 2], group_trials, local_alpha / 2.0
        ),
        binomial_lower(
            target_counts[..., 0], group_trials, local_alpha / 2.0
        ),
        ratio_cap,
    )

    leakage_counts = random.binomial(
        class_trials,
        leakage_probability,
        size=(repeats, candidate_count, int(config["attacker_count"]), 2),
    )
    class_bounds = np.minimum(
        1.0,
        ratio_cap
        * binomial_upper(leakage_counts, class_trials, local_alpha / 2.0),
    )
    candidate_passes = np.all(
        target_bound <= float(config["target_threshold"]), axis=2
    ) & np.all(
        np.mean(class_bounds, axis=3)
        <= float(config["leakage_threshold"]),
        axis=2,
    )
    deployed = np.any(candidate_passes, axis=1)
    chosen = np.argmax(candidate_passes, axis=1)

    target_truth = np.max(
        paired_worst_case(
            target_probability,
            np.broadcast_to(
                target_negative_probability[:, None], target_probability.shape
            ),
            ratio_cap,
        ),
        axis=1,
    )
    leakage_truth = np.max(
        np.mean(np.minimum(1.0, ratio_cap * leakage_probability), axis=2),
        axis=1,
    )
    unsafe = (target_truth > float(config["target_threshold"])) | (
        leakage_truth > float(config["leakage_threshold"])
    )
    false_acceptances = int(np.count_nonzero(deployed & unsafe[chosen]))
    abstentions = int(np.count_nonzero(~deployed))
    familywise_alpha = 0.05 / int(config["cell_count"])
    upper = float(binomial_upper(false_acceptances, repeats, familywise_alpha))
    return {
        "validation_size": n,
        "candidate_count": candidate_count,
        "environment_count": group_count,
        "delta": delta,
        "gamma": ratio_cap,
        "replicates": repeats,
        "n_per_environment": group_trials,
        "n_per_source_class": class_trials,
        "unsafe_candidate_count": int(np.count_nonzero(unsafe)),
        "false_acceptances": false_acceptances,
        "false_acceptance_rate": false_acceptances / repeats,
        "false_acceptance_cp95_upper_simultaneous": upper,
        "abstentions": abstentions,
        "abstention_rate": abstentions / repeats,
        "coverage_pass": upper <= delta,
    }


def same_value(observed: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(expected, (int, str)):
        return observed == expected
    return bool(np.isclose(float(observed), float(expected), rtol=1e-10, atol=1e-12))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    config = prereg["study"]
    prereg_hash = file_sha256(args.prereg)
    locked_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    cells = [
        (int(n), int(candidate_count), int(group_count), float(delta))
        for n in config["validation_sizes"]
        for candidate_count in config["candidate_counts"]
        for group_count in config["environment_counts"]
        for delta in config["delta_levels"]
    ]
    payloads = [
        (
            config,
            n,
            candidate_count,
            group_count,
            delta,
            int(config["seed"]) + 1009 * index,
        )
        for index, (n, candidate_count, group_count, delta) in enumerate(cells)
    ]
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        replayed = list(executor.map(replay_cell, payloads))

    failures: list[str] = []
    if prereg_hash != locked_hash:
        failures.append("preregistration hash does not match sidecar")
    if report.get("prereg_sha256") != prereg_hash:
        failures.append("report preregistration hash mismatch")
    if report.get("config") != config:
        failures.append("report configuration differs from preregistration")
    if report.get("claim_grade") is not True:
        failures.append("report is not marked claim-grade")
    report_commit = str(report.get("git_commit", ""))
    git_probe = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
    )
    repository_available = git_probe.returncode == 0
    source_commit_verified = False
    if repository_available:
        try:
            committed_prereg = subprocess.run(
                [
                    "git",
                    "show",
                    f"{report_commit}:research/prereg_exact_family_grid.json",
                ],
                cwd=REPOSITORY,
                check=True,
                capture_output=True,
            ).stdout
        except subprocess.CalledProcessError:
            committed_prereg = b""
        source_commit_verified = (
            hashlib.sha256(committed_prereg).hexdigest() == prereg_hash
        )
        if not source_commit_verified:
            failures.append("report commit does not contain the locked preregistration")
    reported_cells = report.get("cells", [])
    if not isinstance(reported_cells, list) or len(reported_cells) != len(replayed):
        failures.append("report has the wrong number of cells")
        reported_cells = []
    for index, (observed, expected) in enumerate(zip(reported_cells, replayed)):
        if not isinstance(observed, dict):
            failures.append(f"cell {index} is not an object")
            continue
        for key, expected_value in expected.items():
            if key not in observed or not same_value(observed[key], expected_value):
                failures.append(f"cell {index} field {key} does not match replay")

    coverage = all(cell["coverage_pass"] for cell in replayed)
    unsafe_present = all(cell["unsafe_candidate_count"] > 0 for cell in replayed)
    candidate_counts = sorted({cell["candidate_count"] for cell in replayed})
    group_counts = sorted({cell["environment_count"] for cell in replayed})
    if report.get("candidate_counts_tested") != candidate_counts:
        failures.append("reported candidate-count grid is inconsistent")
    if report.get("group_counts_tested") != group_counts:
        failures.append("reported group-count grid is inconsistent")
    if report.get("coverage_pass") is not coverage:
        failures.append("top-level coverage flag is inconsistent")
    if report.get("all_cells_have_unsafe_candidate") is not unsafe_present:
        failures.append("top-level unsafe-candidate flag is inconsistent")
    if report.get("all_cells_pass") is not (coverage and unsafe_present):
        failures.append("top-level all-cells flag is inconsistent")

    audit = {
        "passed": not failures and coverage and unsafe_present,
        "prereg_sha256": prereg_hash,
        "report_sha256": file_sha256(args.report),
        "report_git_commit": report_commit,
        "repository_available": repository_available,
        "source_commit_verified": source_commit_verified,
        "cells_replayed": len(replayed),
        "candidate_counts_tested": candidate_counts,
        "group_counts_tested": group_counts,
        "false_acceptances_replayed": sum(
            cell["false_acceptances"] for cell in replayed
        ),
        "coverage_pass": coverage,
        "all_cells_have_unsafe_candidate": unsafe_present,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
