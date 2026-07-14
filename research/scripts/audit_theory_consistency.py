"""Audit numerical and source-level consistency of VERA's theory contract.

This catches formula and implementation mismatches. It is not a formal proof
checker and does not establish novelty; those remain manuscript and review
obligations.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np

from vera_robust_certificate import (
    certify_discrete_group_shift_envelope,
    certify_discrete_shift_radius,
    empirical_reweighting_risk,
)


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
PREREG = ROOT / "prereg_real.json"
PREREG_HASH = ROOT / "prereg_real.sha256"
ENVELOPE_PREREG = ROOT / "prereg_shift_envelope_extension.json"
ENVELOPE_PREREG_HASH = ROOT / "prereg_shift_envelope_extension.sha256"
THEORY = ROOT / "maintrack" / "appendix_shift_robust_theory.tex"
OUTPUT = ROOT / "artifacts" / "vera_theory_consistency_audit.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def empirical_cvar_dual(values: np.ndarray, gamma: float) -> float:
    candidates = np.unique(values)
    candidates = np.r_[values.min(), candidates, values.max()]
    objectives = [
        float(eta + gamma * np.maximum(values - eta, 0.0).mean())
        for eta in candidates
    ]
    return min(objectives)


def paired_formula(positive: float, negative: float, gamma: float) -> float:
    if gamma * positive >= 1.0:
        return 1.0
    if gamma * (1.0 - negative) >= 1.0:
        return gamma * positive
    return gamma * positive - (1.0 - gamma * (1.0 - negative))


def check_cvar_duality(rng: np.random.Generator) -> tuple[bool, float, int]:
    maximum_error = 0.0
    checks = 0
    for n in (3, 5, 11, 50):
        for gamma in (1.0, 1.1, 1.25, 2.0, 8.0):
            for _ in range(25):
                values = rng.uniform(-1.0, 1.0, size=n)
                primal = empirical_reweighting_risk(values, gamma)
                dual = empirical_cvar_dual(values, gamma)
                maximum_error = max(maximum_error, abs(primal - dual))
                checks += 1
    return maximum_error <= 1e-12, maximum_error, checks


def check_paired_formula() -> tuple[bool, float, int]:
    maximum_error = 0.0
    checks = 0
    n = 20
    for positive_count in range(n + 1):
        for negative_count in range(n - positive_count + 1):
            values = np.asarray(
                [1] * positive_count
                + [0] * (n - positive_count - negative_count)
                + [-1] * negative_count,
                dtype=float,
            )
            for gamma in (1.0, 1.01, 1.25, 2.0, 5.0, 20.0):
                expected = paired_formula(
                    positive_count / n, negative_count / n, gamma
                )
                observed = empirical_reweighting_risk(values, gamma)
                maximum_error = max(maximum_error, abs(expected - observed))
                checks += 1
    return maximum_error <= 1e-12, maximum_error, checks


def bounded_random_weights(
    rng: np.random.Generator, n: int, gamma: float
) -> np.ndarray:
    # Convex combinations of feasible extreme points remain feasible.
    first = np.ones(n)
    second = np.zeros(n)
    order = rng.permutation(n)
    remaining = float(n)
    for index in order:
        weight = min(gamma, remaining)
        second[index] = weight
        remaining -= weight
        if remaining <= 1e-12:
            break
    mixing = rng.uniform()
    weights = mixing * first + (1.0 - mixing) * second
    return weights / weights.mean()


def check_group_mixture(rng: np.random.Generator) -> tuple[bool, float, int]:
    maximum_violation = 0.0
    checks = 0
    for gamma in (1.0, 1.25, 2.0, 4.0):
        for _ in range(250):
            groups = [rng.uniform(-1.0, 1.0, size=20) for _ in range(4)]
            robust = [empirical_reweighting_risk(values, gamma) for values in groups]
            mixture = rng.dirichlet(np.ones(len(groups)))
            shifted_means = []
            for values in groups:
                weights = bounded_random_weights(rng, len(values), gamma)
                shifted_means.append(float(np.mean(weights * values)))
            violation = float(np.dot(mixture, shifted_means) - max(robust))
            maximum_violation = max(maximum_violation, violation)
            checks += 1
    return maximum_violation <= 1e-12, maximum_violation, checks


def check_hierarchical_shift(rng: np.random.Generator) -> tuple[bool, float, int]:
    """Check target marginals and leakage conditionals on one shift profile."""

    maximum_violation = 0.0
    checks = 0
    for gamma in (1.0, 1.25, 2.0, 4.0):
        for _ in range(150):
            target_values = [rng.uniform(-1.0, 1.0, size=24) for _ in range(3)]
            leakage_values = [
                [rng.binomial(1, rng.uniform(0.2, 0.7), size=18) for _ in range(2)]
                for _ in range(3)
            ]
            environment_weights = rng.dirichlet(np.ones(3))
            shifted_target = []
            robust_target = []
            for environment in range(3):
                target_weights = bounded_random_weights(
                    rng, len(target_values[environment]), gamma
                )
                shifted_target.append(
                    float(np.mean(target_weights * target_values[environment]))
                )
                robust_target.append(
                    empirical_reweighting_risk(target_values[environment], gamma)
                )
                for source in range(2):
                    values = leakage_values[environment][source]
                    conditional_weights = bounded_random_weights(rng, len(values), gamma)
                    shifted = float(np.mean(conditional_weights * values))
                    robust = empirical_reweighting_risk(values, gamma)
                    maximum_violation = max(maximum_violation, shifted - robust)
                    checks += 1
            mixture_target = float(np.dot(environment_weights, shifted_target))
            maximum_violation = max(
                maximum_violation, mixture_target - max(robust_target)
            )
            checks += 1
    return maximum_violation <= 1e-12, maximum_violation, checks


def check_radius_contracts(rng: np.random.Generator) -> tuple[bool, int, list[str]]:
    failures: list[str] = []
    checks = 0
    for index in range(100):
        n = 500
        samples = {
            "harm": rng.choice((-1, 0, 1), size=n, p=(0.03, 0.94, 0.03)),
            "leakage": rng.binomial(1, 0.35, size=n),
        }
        thresholds = {"harm": 0.15, "leakage": 0.75}
        result = certify_discrete_shift_radius(
            samples,
            delta=0.05,
            supports={"harm": (-1, 0, 1), "leakage": (0, 1)},
            thresholds=thresholds,
            family_size=24,
            gamma_cap=8.0,
        )
        if result.certified_radius > 0.0:
            for certificate in result.certificates_at_radius:
                if certificate.upper_confidence_bound > thresholds[certificate.key] + 1e-12:
                    failures.append(f"trial {index}: radius certificate violates {certificate.key}")
        elif result.decision != "ABSTAIN":
            failures.append(f"trial {index}: zero radius did not abstain")
        checks += 1
    return not failures, checks, failures


def check_group_shift_envelope(
    rng: np.random.Generator,
) -> tuple[bool, float, int, list[str]]:
    failures: list[str] = []
    maximum_error = 0.0
    checks = 0
    for index in range(100):
        grouped_samples: dict[str, dict[str, np.ndarray]] = {}
        grouped_supports: dict[str, dict[str, tuple[int, ...]]] = {}
        grouped_thresholds: dict[str, dict[str, float]] = {}
        for group in ("0", "1", "2"):
            grouped_samples[group] = {
                f"target::{group}": rng.choice(
                    (-1, 0, 1), size=500, p=(0.03, 0.94, 0.03)
                ),
                f"leakage::{group}": rng.binomial(1, 0.35, size=500),
            }
            grouped_supports[group] = {
                f"target::{group}": (-1, 0, 1),
                f"leakage::{group}": (0, 1),
            }
            grouped_thresholds[group] = {
                f"target::{group}": 0.15,
                f"leakage::{group}": 0.75,
            }
        family_size = 36
        envelope = certify_discrete_group_shift_envelope(
            grouped_samples,
            delta=0.05,
            grouped_supports=grouped_supports,
            grouped_thresholds=grouped_thresholds,
            family_size=family_size,
            gamma_cap=8.0,
        )
        flat_samples = {
            key: values for values_by_group in grouped_samples.values()
            for key, values in values_by_group.items()
        }
        flat_supports = {
            key: support for supports_by_group in grouped_supports.values()
            for key, support in supports_by_group.items()
        }
        flat_thresholds = {
            key: threshold for thresholds_by_group in grouped_thresholds.values()
            for key, threshold in thresholds_by_group.items()
        }
        joint = certify_discrete_shift_radius(
            flat_samples,
            delta=0.05,
            supports=flat_supports,
            thresholds=flat_thresholds,
            family_size=family_size,
            gamma_cap=8.0,
        )
        error = abs(envelope.observed_common_radius - joint.certified_radius)
        maximum_error = max(maximum_error, error)
        if error > 1e-4:
            failures.append(f"trial {index}: group-envelope minimum differs from joint radius")
        unsupported = certify_discrete_group_shift_envelope(
            grouped_samples,
            delta=0.05,
            grouped_supports=grouped_supports,
            grouped_thresholds=grouped_thresholds,
            family_size=family_size,
            registered_groups=["0", "1", "2", "unseen"],
            gamma_cap=8.0,
        )
        if unsupported.group_radii["unseen"] != 0.0 or unsupported.decision != "ABSTAIN":
            failures.append(f"trial {index}: unsupported group did not force radius zero")
        checks += 2
    return not failures, maximum_error, checks, failures


def main() -> int:
    rng = np.random.default_rng(20270713)
    failures: list[str] = []
    prereg_hash = sha256(PREREG)
    locked_hash = PREREG_HASH.read_text(encoding="utf-8").split()[0]
    envelope_prereg_hash = sha256(ENVELOPE_PREREG)
    envelope_locked_hash = ENVELOPE_PREREG_HASH.read_text(encoding="utf-8").split()[0]
    theory_text = THEORY.read_text(encoding="utf-8")
    required_source_fragments = (
        "\\label{lem:cvar-identity}",
        "\\label{thm:robust-paired}",
        "\\label{cor:exact-discrete}",
        "\\label{cor:mixture}",
        "\\label{cor:shift-envelope}",
        "\\label{thm:shift-radius}",
        "\\label{thm:unsupported}",
        "Q_g\\in\\mathcal{Q}_{\\Gamma}(P_g)",
        "Q_{g,s}\\in\\mathcal Q_{\\gamma_g}(P_{g,s})",
        "Source-class weights are not claimed",
        "\\widetilde p_+=\\min\\{U_+,1-L_-\\}",
    )
    source_contract_ok = all(fragment in theory_text for fragment in required_source_fragments)
    if prereg_hash != locked_hash:
        failures.append("preregistration hash mismatch")
    if envelope_prereg_hash != envelope_locked_hash:
        failures.append("shift-envelope extension preregistration hash mismatch")
    if not source_contract_ok:
        failures.append("theory source is missing a required statement")

    cvar_ok, cvar_error, cvar_checks = check_cvar_duality(rng)
    paired_ok, paired_error, paired_checks = check_paired_formula()
    mixture_ok, mixture_violation, mixture_checks = check_group_mixture(rng)
    hierarchy_ok, hierarchy_violation, hierarchy_checks = check_hierarchical_shift(rng)
    radius_ok, radius_checks, radius_failures = check_radius_contracts(rng)
    envelope_ok, envelope_error, envelope_checks, envelope_failures = (
        check_group_shift_envelope(rng)
    )
    if not cvar_ok:
        failures.append("empirical CVaR dual does not match the reweighting program")
    if not paired_ok:
        failures.append("paired closed form does not match the reweighting program")
    if not mixture_ok:
        failures.append("a sampled within-group shift exceeded the robust mixture bound")
    if not hierarchy_ok:
        failures.append("a hierarchical target/leakage shift exceeded its robust bound")
    failures.extend(radius_failures)
    failures.extend(envelope_failures)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    report = {
        "name": "VERA theory implementation consistency audit",
        "passed": not failures and radius_ok and envelope_ok and hierarchy_ok,
        "formal_proof_verified": False,
        "novelty_verified": False,
        "git_commit": head,
        "prereg_sha256": prereg_hash,
        "shift_envelope_prereg_sha256": envelope_prereg_hash,
        "theory_sha256": sha256(THEORY),
        "source_contract_ok": source_contract_ok,
        "cvar_duality": {
            "passed": cvar_ok,
            "checks": cvar_checks,
            "maximum_absolute_error": cvar_error,
        },
        "paired_closed_form": {
            "passed": paired_ok,
            "checks": paired_checks,
            "maximum_absolute_error": paired_error,
        },
        "group_mixture": {
            "passed": mixture_ok,
            "checks": mixture_checks,
            "maximum_observed_violation": mixture_violation,
        },
        "hierarchical_shift": {
            "passed": hierarchy_ok,
            "checks": hierarchy_checks,
            "maximum_observed_violation": hierarchy_violation,
        },
        "radius_contracts": {
            "passed": radius_ok,
            "checks": radius_checks,
        },
        "group_shift_envelope": {
            "passed": envelope_ok,
            "checks": envelope_checks,
            "maximum_common_radius_error": envelope_error,
        },
        "failures": failures,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
