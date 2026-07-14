"""Independently replay and audit the preregistered exact-discrete study."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
from scipy.stats import beta, binom


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
DEFAULT_PREREG = ROOT / "prereg_real.json"
DEFAULT_HASH = ROOT / "prereg_real.sha256"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_exact_synthetic_report.json"
DEFAULT_AUDIT = ROOT / "artifacts" / "vera_exact_synthetic_audit.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cp_upper(successes: np.ndarray | int, n: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    result = np.ones(values.shape, dtype=np.float64)
    mask = values < n
    result[mask] = beta.ppf(1.0 - alpha, values[mask] + 1, n - values[mask])
    return result


def cp_lower(successes: np.ndarray | int, n: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    result = np.zeros(values.shape, dtype=np.float64)
    mask = values > 0
    result[mask] = beta.ppf(alpha, values[mask], n - values[mask] + 1)
    return result


def robust_paired(positive: np.ndarray, negative: np.ndarray, gamma: float) -> np.ndarray:
    bounded_positive = np.minimum(positive, 1.0 - negative)
    zero = np.maximum(0.0, 1.0 - bounded_positive - negative)
    shifted_positive = np.minimum(1.0, gamma * bounded_positive)
    remainder = 1.0 - shifted_positive
    shifted_zero = np.minimum(remainder, gamma * zero)
    return shifted_positive - np.maximum(0.0, remainder - shifted_zero)


def exact_target_probability(
    n: int,
    p_positive: float,
    p_negative: float,
    gamma: float,
    threshold: float,
    alpha: float,
) -> float:
    positive_counts = np.arange(n + 1)
    positive_bounds = cp_upper(positive_counts, n, alpha / 2.0)
    negative_bounds = cp_lower(np.arange(n + 1), n, alpha / 2.0)
    conditional_negative = p_negative / max(1e-15, 1.0 - p_positive)
    probability = 0.0
    for positive_count, positive_probability in enumerate(
        binom.pmf(positive_counts, n, p_positive)
    ):
        remaining = n - positive_count
        low, high = 0, remaining + 1
        while low < high:
            negative_count = (low + high) // 2
            value = robust_paired(
                np.asarray([positive_bounds[positive_count]]),
                np.asarray([negative_bounds[negative_count]]),
                gamma,
            )[0]
            if value <= threshold:
                high = negative_count
            else:
                low = negative_count + 1
        first_passing = low
        if first_passing <= remaining:
            probability += float(positive_probability) * float(
                binom.sf(first_passing - 1, remaining, conditional_negative)
            )
    return float(np.clip(probability, 0.0, 1.0))


def exact_leakage_probability(
    n: int,
    probability: float,
    gamma: float,
    threshold: float,
    alpha: float,
) -> float:
    counts = np.arange(n + 1)
    passing = np.flatnonzero(gamma * cp_upper(counts, n, alpha) <= threshold)
    if passing.size == 0:
        return 0.0
    return float(binom.cdf(int(passing[-1]), n, probability))


def exact_abstention(config: dict[str, Any], n: int, delta: float) -> float:
    positives = np.asarray(config["target_positive_probabilities"], dtype=float)
    negatives = np.asarray(config["target_negative_probabilities"], dtype=float)
    leakage = np.asarray(config["leakage_probabilities"], dtype=float)
    offsets = np.asarray(config["attacker_probability_offsets"], dtype=float)
    gamma = float(config["gamma"])
    target_threshold = float(config["target_threshold"])
    leakage_threshold = float(config["leakage_threshold"])
    alpha = delta / (len(positives) * (1 + len(offsets)))
    no_candidate_passes = 1.0
    for p_positive, p_negative, p_leakage in zip(positives, negatives, leakage):
        target = exact_target_probability(
            n, p_positive, p_negative, gamma, target_threshold, alpha
        )
        attackers = 1.0
        for offset in offsets:
            attackers *= exact_leakage_probability(
                n,
                float(np.clip(p_leakage + offset, 0.0, 1.0)),
                gamma,
                leakage_threshold,
                alpha,
            )
        no_candidate_passes *= 1.0 - target * attackers
    return float(no_candidate_passes)


def replay_cell(payload: tuple[dict[str, Any], int, float, int]) -> dict[str, Any]:
    config, n, delta, seed = payload
    rng = np.random.default_rng(seed)
    replicates = int(config["replicates"])
    positives = np.asarray(config["target_positive_probabilities"], dtype=float)
    negatives = np.asarray(config["target_negative_probabilities"], dtype=float)
    leakage = np.asarray(config["leakage_probabilities"], dtype=float)
    offsets = np.asarray(config["attacker_probability_offsets"], dtype=float)
    gamma = float(config["gamma"])
    target_threshold = float(config["target_threshold"])
    leakage_threshold = float(config["leakage_threshold"])
    candidate_count = len(positives)
    attacker_count = len(offsets)
    alpha = delta / (candidate_count * (1 + attacker_count))

    target_counts = np.empty((replicates, candidate_count, 3), dtype=np.int64)
    for candidate in range(candidate_count):
        target_counts[:, candidate] = rng.multinomial(
            n,
            [
                negatives[candidate],
                1.0 - positives[candidate] - negatives[candidate],
                positives[candidate],
            ],
            size=replicates,
        )
    target_ucb = robust_paired(
        cp_upper(target_counts[:, :, 2], n, alpha / 2.0),
        cp_lower(target_counts[:, :, 0], n, alpha / 2.0),
        gamma,
    )
    attacker_probabilities = np.clip(leakage[:, None] + offsets[None, :], 0.0, 1.0)
    attacker_counts = rng.binomial(
        n,
        attacker_probabilities,
        size=(replicates, candidate_count, attacker_count),
    )
    attacker_ucb = gamma * cp_upper(attacker_counts, n, alpha)
    accepted = (target_ucb <= target_threshold) & np.all(
        attacker_ucb <= leakage_threshold, axis=2
    )
    deployed = np.any(accepted, axis=1)
    selected = candidate_count - 1 - np.argmax(accepted[:, ::-1], axis=1)
    true_target = robust_paired(positives, negatives, gamma)
    true_leakage = np.max(gamma * attacker_probabilities, axis=1)
    unsafe = (true_target > target_threshold) | (true_leakage > leakage_threshold)
    false_acceptances = int(np.count_nonzero(deployed & unsafe[selected]))
    abstentions = int(np.count_nonzero(~deployed))

    cell_count = len(config["validation_sizes"]) * len(config["delta_levels"])
    simultaneous_alpha = 0.05 / cell_count
    false_upper = float(cp_upper(false_acceptances, replicates, simultaneous_alpha / 2.0))
    predicted = exact_abstention(config, n, delta)
    lower = float(binom.ppf(simultaneous_alpha / 2.0, replicates, predicted) / replicates)
    upper = float(
        binom.ppf(1.0 - simultaneous_alpha / 2.0, replicates, predicted) / replicates
    )
    observed = abstentions / replicates
    return {
        "n": n,
        "delta": delta,
        "replicates": replicates,
        "false_acceptances": false_acceptances,
        "abstentions": abstentions,
        "false_acceptance_rate": false_acceptances / replicates,
        "false_acceptance_cp95_upper_simultaneous": false_upper,
        "observed_abstention": observed,
        "predicted_abstention": predicted,
        "prediction_band_lower": lower,
        "prediction_band_upper": upper,
        "coverage_pass": false_upper <= delta,
        "overlay_pass": lower <= observed <= upper,
    }


def values_match(observed: Any, expected: Any) -> bool:
    if isinstance(expected, bool) or isinstance(expected, (int, str)):
        return observed == expected
    return bool(np.isclose(float(observed), float(expected), rtol=1e-10, atol=1e-12))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument("--hash-file", type=Path, default=DEFAULT_HASH)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--output", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    prereg_hash = file_sha256(args.prereg)
    locked_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    report_commit = str(report.get("git_commit", ""))
    config = prereg["exact_synthetic_study"]
    pairs = [
        (int(n), float(delta))
        for n in config["validation_sizes"]
        for delta in config["delta_levels"]
    ]
    payloads = [
        (config, n, delta, int(config["seed"]) + 1009 * index)
        for index, (n, delta) in enumerate(pairs)
    ]
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        replayed = list(executor.map(replay_cell, payloads))

    failures: list[str] = []
    if prereg_hash != locked_hash:
        failures.append("preregistration hash does not match its lock")
    if report.get("prereg_sha256") != prereg_hash:
        failures.append("report preregistration hash mismatch")
    report_is_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", report_commit, head],
        cwd=REPOSITORY,
        check=False,
    ).returncode == 0
    if not report_is_ancestor:
        failures.append("report commit is not an ancestor of current HEAD")
    try:
        committed_prereg = subprocess.run(
            ["git", "show", f"{report_commit}:research/prereg_real.json"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
        ).stdout
    except subprocess.CalledProcessError:
        committed_prereg = b""
    if hashlib.sha256(committed_prereg).hexdigest() != prereg_hash:
        failures.append("report commit does not contain the locked preregistration")
    if report.get("claim_grade") is not True:
        failures.append("report is not claim-grade")
    if report.get("config") != config:
        failures.append("report configuration differs from preregistration")
    reported_cells = report.get("cells")
    if not isinstance(reported_cells, list) or len(reported_cells) != len(replayed):
        failures.append("report has the wrong cell count")
        reported_cells = []
    for index, (reported, expected) in enumerate(zip(reported_cells, replayed)):
        for key, expected_value in expected.items():
            if key not in reported or not values_match(reported[key], expected_value):
                failures.append(f"cell {index} field {key} does not match independent replay")
    coverage = all(cell["coverage_pass"] for cell in replayed)
    overlay = all(cell["overlay_pass"] for cell in replayed)
    if report.get("coverage_pass") is not coverage:
        failures.append("top-level coverage flag is inconsistent")
    if report.get("overlay_pass") is not overlay:
        failures.append("top-level overlay flag is inconsistent")
    if report.get("all_cells_pass") is not (coverage and overlay):
        failures.append("top-level all-cells flag is inconsistent")

    audit = {
        "passed": not failures and coverage and overlay,
        "prereg_sha256": prereg_hash,
        "git_commit": head,
        "report_git_commit": report_commit,
        "report_sha256": file_sha256(args.report),
        "cells_replayed": len(replayed),
        "coverage_pass": coverage,
        "overlay_pass": overlay,
        "failures": failures,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0 if audit["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
