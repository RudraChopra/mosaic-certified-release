"""Independently replay and audit the locked balanced-leakage study."""

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
DEFAULT_PREREG = ROOT / "prereg_confirmatory_balanced.json"
DEFAULT_HASH = ROOT / "prereg_confirmatory_balanced.sha256"
DEFAULT_REPORT = ROOT / "artifacts" / "vera_exact_balanced_report.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "vera_exact_balanced_audit.json"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def upper_cp(successes: np.ndarray | int, trials: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    result = np.ones(values.shape, dtype=np.float64)
    interior = values < trials
    result[interior] = beta.ppf(
        1.0 - alpha, values[interior] + 1, trials - values[interior]
    )
    return result


def lower_cp(successes: np.ndarray | int, trials: int, alpha: float) -> np.ndarray:
    values = np.asarray(successes)
    result = np.zeros(values.shape, dtype=np.float64)
    interior = values > 0
    result[interior] = beta.ppf(
        alpha, values[interior], trials - values[interior] + 1
    )
    return result


def worst_case_paired(
    positive: np.ndarray, negative: np.ndarray, gamma: float
) -> np.ndarray:
    positive = np.minimum(positive, 1.0 - negative)
    zero = np.maximum(0.0, 1.0 - positive - negative)
    shifted_positive = np.minimum(1.0, gamma * positive)
    remaining = 1.0 - shifted_positive
    shifted_zero = np.minimum(remaining, gamma * zero)
    return shifted_positive - np.maximum(0.0, remaining - shifted_zero)


def target_pass_probability(
    trials: int,
    p_positive: float,
    p_negative: float,
    gamma: float,
    threshold: float,
    candidate_alpha: float,
) -> float:
    """Sum the registered trinomial law without calling the generator."""
    counts = np.arange(trials + 1)
    positive_bound = upper_cp(counts, trials, candidate_alpha / 2.0)
    negative_bound = lower_cp(counts, trials, candidate_alpha / 2.0)
    p_negative_given_not_positive = p_negative / (1.0 - p_positive)
    total = 0.0
    for positive_count in counts:
        remaining = trials - int(positive_count)
        low, high = 0, remaining + 1
        while low < high:
            negative_count = (low + high) // 2
            bound = worst_case_paired(
                np.asarray([positive_bound[positive_count]]),
                np.asarray([negative_bound[negative_count]]),
                gamma,
            )[0]
            if bound <= threshold:
                high = negative_count
            else:
                low = negative_count + 1
        if low > remaining:
            continue
        conditional_mass = float(
            binom.sf(low - 1, remaining, p_negative_given_not_positive)
        )
        total += float(binom.pmf(positive_count, trials, p_positive)) * conditional_mass
    return float(np.clip(total, 0.0, 1.0))


def balanced_pass_probability(
    trials_per_class: int,
    p_class_zero: float,
    p_class_one: float,
    gamma: float,
    threshold: float,
    candidate_alpha: float,
) -> float:
    counts = np.arange(trials_per_class + 1)
    class_bound = np.minimum(
        1.0,
        gamma * upper_cp(counts, trials_per_class, candidate_alpha / 2.0),
    )
    total = 0.0
    for class_zero_count, class_zero_mass in enumerate(
        binom.pmf(counts, trials_per_class, p_class_zero)
    ):
        remaining_bound = 2.0 * threshold - class_bound[class_zero_count]
        last_passing = int(np.searchsorted(class_bound, remaining_bound, side="right") - 1)
        if last_passing >= 0:
            total += float(class_zero_mass) * float(
                binom.cdf(last_passing, trials_per_class, p_class_one)
            )
    return float(np.clip(total, 0.0, 1.0))


def registered_probabilities(
    config: dict[str, Any]
) -> tuple[np.ndarray, np.ndarray]:
    target = np.asarray(
        config["candidate_target_positive_probabilities"], dtype=np.float64
    )[:, None] + np.asarray(
        config["environment_target_positive_offsets"], dtype=np.float64
    )[None, :]
    leakage = np.asarray(
        config["candidate_balanced_leakage_probabilities"], dtype=np.float64
    )[:, None, None]
    leakage = leakage + np.asarray(
        config["attacker_probability_offsets"], dtype=np.float64
    )[None, :, None]
    leakage = leakage + np.asarray(
        config["class_recall_offsets"], dtype=np.float64
    )[None, None, :]
    return target, leakage


def exact_abstention(
    config: dict[str, Any], n: int, delta: float, gamma: float
) -> float:
    target, leakage = registered_probabilities(config)
    candidate_count, environment_count = target.shape
    attacker_count = leakage.shape[1]
    environment_trials = n // environment_count
    class_trials = n // 2
    candidate_alpha = delta / candidate_count
    no_candidate_passes = 1.0
    for candidate in range(candidate_count):
        pass_probability = 1.0
        for environment in range(environment_count):
            pass_probability *= target_pass_probability(
                environment_trials,
                float(target[candidate, environment]),
                float(config["target_negative_probability"]),
                gamma,
                float(config["target_threshold"]),
                candidate_alpha,
            )
        for attacker in range(attacker_count):
            pass_probability *= balanced_pass_probability(
                class_trials,
                float(leakage[candidate, attacker, 0]),
                float(leakage[candidate, attacker, 1]),
                gamma,
                float(config["leakage_threshold"]),
                candidate_alpha,
            )
        no_candidate_passes *= 1.0 - pass_probability
    return float(np.clip(no_candidate_passes, 0.0, 1.0))


def replay_cell(
    payload: tuple[dict[str, Any], int, float, float, int]
) -> dict[str, Any]:
    config, n, delta, gamma, seed = payload
    rng = np.random.default_rng(seed)
    replicates = int(config["replicates"])
    target, leakage = registered_probabilities(config)
    candidate_count, environment_count = target.shape
    attacker_count = leakage.shape[1]
    environment_trials = n // environment_count
    class_trials = n // 2
    candidate_alpha = delta / candidate_count
    p_negative = float(config["target_negative_probability"])

    target_counts = np.empty(
        (replicates, candidate_count, environment_count, 3), dtype=np.int64
    )
    for candidate in range(candidate_count):
        for environment in range(environment_count):
            p_positive = float(target[candidate, environment])
            target_counts[:, candidate, environment] = rng.multinomial(
                environment_trials,
                [p_negative, 1.0 - p_positive - p_negative, p_positive],
                size=replicates,
            )
    target_bound = worst_case_paired(
        upper_cp(
            target_counts[:, :, :, 2],
            environment_trials,
            candidate_alpha / 2.0,
        ),
        lower_cp(
            target_counts[:, :, :, 0],
            environment_trials,
            candidate_alpha / 2.0,
        ),
        gamma,
    )

    leakage_counts = rng.binomial(
        class_trials,
        leakage,
        size=(replicates, candidate_count, attacker_count, 2),
    )
    class_bounds = np.minimum(
        1.0,
        gamma
        * upper_cp(
            leakage_counts, class_trials, candidate_alpha / 2.0
        ),
    )
    accepted = np.all(
        target_bound <= float(config["target_threshold"]), axis=2
    ) & np.all(
        np.mean(class_bounds, axis=3)
        <= float(config["leakage_threshold"]),
        axis=2,
    )
    deployed = np.any(accepted, axis=1)
    selected = np.argmax(accepted, axis=1)

    true_target = np.max(
        worst_case_paired(target, np.full_like(target, p_negative), gamma), axis=1
    )
    true_leakage = np.max(
        np.mean(np.minimum(1.0, gamma * leakage), axis=2), axis=1
    )
    unsafe = (true_target > float(config["target_threshold"])) | (
        true_leakage > float(config["leakage_threshold"])
    )
    false_acceptances = int(np.count_nonzero(deployed & unsafe[selected]))
    abstentions = int(np.count_nonzero(~deployed))

    cell_count = (
        len(config["validation_sizes"])
        * len(config["delta_levels"])
        * len(config["gamma_levels"])
    )
    simultaneous_alpha = 0.05 / cell_count
    false_upper = float(
        upper_cp(false_acceptances, replicates, simultaneous_alpha / 2.0)
    )
    predicted = exact_abstention(config, n, delta, gamma)
    lower = float(
        binom.ppf(simultaneous_alpha / 2.0, replicates, predicted) / replicates
    )
    upper = float(
        binom.ppf(1.0 - simultaneous_alpha / 2.0, replicates, predicted)
        / replicates
    )
    observed = abstentions / replicates
    return {
        "n": n,
        "n_per_environment": environment_trials,
        "n_per_source_class": class_trials,
        "delta": delta,
        "gamma": gamma,
        "replicates": replicates,
        "unsafe_candidate_count": int(np.count_nonzero(unsafe)),
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
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
    report = json.loads(args.report.read_text(encoding="utf-8"))
    prereg_hash = file_sha256(args.prereg)
    locked_hash = args.hash_file.read_text(encoding="utf-8").split()[0]
    git_probe = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=False,
        capture_output=True,
        text=True,
    )
    repository_available = git_probe.returncode == 0
    head = git_probe.stdout.strip() if repository_available else None
    report_commit = str(report.get("git_commit", ""))
    config = prereg["exact_synthetic_study"]
    cells = [
        (int(n), float(delta), float(gamma))
        for n in config["validation_sizes"]
        for delta in config["delta_levels"]
        for gamma in config["gamma_levels"]
    ]
    payloads = [
        (config, n, delta, gamma, int(config["seed"]) + 1009 * index)
        for index, (n, delta, gamma) in enumerate(cells)
    ]
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        replayed = list(executor.map(replay_cell, payloads))

    failures: list[str] = []
    if prereg_hash != locked_hash:
        failures.append("preregistration hash does not match its sidecar")
    if report.get("prereg_sha256") != prereg_hash:
        failures.append("report preregistration hash mismatch")
    if report.get("config") != config:
        failures.append("report configuration differs from preregistration")
    if report.get("claim_grade") is not True:
        failures.append("report is not marked claim-grade")
    source_commit_verified = False
    if repository_available:
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", report_commit, str(head)],
            cwd=REPOSITORY,
            check=False,
        ).returncode == 0
        try:
            committed_prereg = subprocess.run(
                [
                    "git",
                    "show",
                    f"{report_commit}:research/prereg_confirmatory_balanced.json",
                ],
                cwd=REPOSITORY,
                check=True,
                capture_output=True,
            ).stdout
        except subprocess.CalledProcessError:
            committed_prereg = b""
        source_commit_verified = (
            ancestor
            and hashlib.sha256(committed_prereg).hexdigest() == prereg_hash
        )
        if not ancestor:
            failures.append("report commit is not an ancestor of current HEAD")
        if hashlib.sha256(committed_prereg).hexdigest() != prereg_hash:
            failures.append("report commit does not contain the locked preregistration")

    reported_cells = report.get("cells")
    if not isinstance(reported_cells, list) or len(reported_cells) != len(replayed):
        failures.append("report has the wrong number of cells")
        reported_cells = []
    for index, (reported, expected) in enumerate(zip(reported_cells, replayed)):
        for key, expected_value in expected.items():
            if key not in reported or not values_match(reported[key], expected_value):
                failures.append(
                    f"cell {index} field {key} does not match independent replay"
                )

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
        "repository_available": repository_available,
        "source_commit_verified": source_commit_verified,
        "report_git_commit": report_commit,
        "report_sha256": file_sha256(args.report),
        "cells_replayed": len(replayed),
        "false_acceptances_replayed": sum(
            cell["false_acceptances"] for cell in replayed
        ),
        "coverage_pass": coverage,
        "overlay_pass": overlay,
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
