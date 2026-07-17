"""Replayable P0 certification primitives for VERA's final confirmation study."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from vera_controlled_shift import (
    allocate_integer_budget,
    conditional_density_ratio_profile,
)
from vera_robust_certificate import (
    balanced_profile_in_envelope,
    certify_balanced_iut_profile,
    certify_balanced_shift_envelope,
    empirical_reweighting_risk,
)


RULES = (
    "always_deploy",
    "validation_point_selection",
    "iid_ltt",
    "vera_vector_envelope",
    "exact_shift_oracle",
)


@dataclass(frozen=True)
class P0Shift:
    requested_gamma: float
    focus_environment: int
    focus_source: int
    focus_target: int
    focus_probability_within_environment: float
    nonfocus_weight: float
    global_density_ratio_cap: float
    target_profile: Mapping[str, float]
    source_profile: Mapping[str, float]

    def to_dict(self) -> dict[str, object]:
        return {
            "requested_gamma": self.requested_gamma,
            "focus_environment": self.focus_environment,
            "focus_source": self.focus_source,
            "focus_target": self.focus_target,
            "focus_probability_within_environment": self.focus_probability_within_environment,
            "nonfocus_weight": self.nonfocus_weight,
            "global_density_ratio_cap": self.global_density_ratio_cap,
            "target_profile": dict(self.target_profile),
            "source_profile": dict(self.source_profile),
        }


def candidate_arrays(
    arrays: Mapping[str, np.ndarray], split: str, attackers: Sequence[str]
) -> dict[str, np.ndarray]:
    """Normalize one audit split and fail closed on a missing registered array."""

    required = {
        "target_harm": f"target_harm_{split}",
        "source": f"source_{split}",
        "environment": f"environment_{split}",
        "target": f"target_{split}",
    }
    output: dict[str, np.ndarray] = {}
    for key, array_key in required.items():
        if array_key not in arrays:
            raise KeyError(f"missing required audit array: {array_key}")
        output[key] = np.asarray(arrays[array_key])
    for attacker in attackers:
        array_key = f"leakage_correct_{split}__{attacker}"
        if array_key not in arrays:
            raise KeyError(f"missing registered-attacker audit array: {array_key}")
        output[f"leakage::{attacker}"] = np.asarray(arrays[array_key])
    lengths = {len(values) for values in output.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) == 0:
        raise ValueError(f"{split} audit arrays are not aligned and nonempty")
    return output


def validate_shared_metadata(
    candidates: Sequence[Mapping[str, Any]], attackers: Sequence[str]
) -> dict[str, dict[str, np.ndarray]]:
    """Check candidate-independent labels for all three retained partitions."""

    if not candidates:
        raise ValueError("candidate set must not be empty")
    output = {
        split: candidate_arrays(candidates[0]["raw_arrays"], split, attackers)
        for split in ("construction", "certification", "external")
    }
    for candidate in candidates[1:]:
        for split, reference in output.items():
            observed = candidate_arrays(candidate["raw_arrays"], split, attackers)
            for key in ("source", "environment", "target"):
                if not np.array_equal(reference[key], observed[key]):
                    raise ValueError(f"candidate {split} metadata mismatch: {key}")
    return output


def target_balanced_accuracy(candidate: Mapping[str, np.ndarray]) -> float:
    errors = np.asarray(candidate["edited_target_error"], dtype=float)
    target = np.asarray(candidate["target"], dtype=int)
    if len(errors) != len(target) or not len(target):
        raise ValueError("construction target errors and labels must align")
    return float(
        np.mean(
            [1.0 - float(errors[target == label].mean()) for label in np.unique(target)]
        )
    )


def construction_candidate_view(
    arrays: Mapping[str, np.ndarray], attackers: Sequence[str]
) -> dict[str, np.ndarray]:
    base = candidate_arrays(arrays, "construction", attackers)
    error_key = "edited_target_error_construction"
    if error_key not in arrays:
        raise KeyError(f"missing required audit array: {error_key}")
    base["edited_target_error"] = np.asarray(arrays[error_key])
    if len(base["edited_target_error"]) != len(base["target"]):
        raise ValueError("construction target-error array is misaligned")
    return base


def _feasible_focus(
    metadata: Mapping[str, np.ndarray], cell: tuple[int, int, int], gamma: float
) -> bool:
    environment, source, target = cell
    environment_mask = metadata["environment"] == environment
    focus_mask = (
        environment_mask
        & (metadata["source"] == source)
        & (metadata["target"] == target)
    )
    count = int(focus_mask.sum())
    total = int(environment_mask.sum())
    if count == 0 or total == 0 or count == total:
        return False
    return gamma * (count / total) <= 1.0 + 1e-12


def choose_construction_design(
    candidates: Sequence[Mapping[str, Any]],
    certification_metadata: Mapping[str, np.ndarray],
    attackers: Sequence[str],
    *,
    target_threshold: float,
    leakage_threshold: float,
    requested_gamma: float,
) -> tuple[str, dict[str, float | int]]:
    """Apply the version-2 construction-only edit and stress-cell rule exactly."""

    scored: list[tuple[float, str, Mapping[str, Any], dict[str, np.ndarray]]] = []
    for candidate in candidates:
        construction = construction_candidate_view(candidate["raw_arrays"], attackers)
        scored.append(
            (
                target_balanced_accuracy(construction),
                str(candidate["candidate"]),
                candidate,
                construction,
            )
        )
    # Highest balanced target accuracy; stable lexical key resolves exact ties.
    _, selected_key, _, selected = min(scored, key=lambda row: (-row[0], row[1]))

    cells: list[tuple[float, int, int, int, int]] = []
    for environment in sorted(map(int, np.unique(selected["environment"]))):
        for source in sorted(map(int, np.unique(selected["source"]))):
            for target in sorted(map(int, np.unique(selected["target"]))):
                mask = (
                    (selected["environment"] == environment)
                    & (selected["source"] == source)
                    & (selected["target"] == target)
                )
                if not np.any(mask) or not _feasible_focus(
                    certification_metadata,
                    (environment, source, target),
                    requested_gamma,
                ):
                    continue
                target_surplus = float(selected["target_harm"][mask].mean()) - target_threshold
                leakage_surplus = max(
                    float(selected[f"leakage::{attacker}"][mask].mean())
                    - leakage_threshold
                    for attacker in attackers
                )
                cells.append(
                    (
                        max(target_surplus, leakage_surplus),
                        environment,
                        source,
                        target,
                        int(mask.sum()),
                    )
                )
    if not cells:
        raise RuntimeError("no construction-supported cell realizes the declared shift")
    surplus, environment, source, target, count = min(
        cells, key=lambda row: (-row[0], row[1], row[2], row[3])
    )
    return selected_key, {
        "environment": environment,
        "source": source,
        "target": target,
        "construction_count": count,
        "construction_positive_contract_surplus": surplus,
    }


def focus_cell_shift(
    metadata: Mapping[str, np.ndarray],
    focus: Mapping[str, float | int],
    *,
    requested_gamma: float,
) -> tuple[np.ndarray, P0Shift]:
    """Turn the locked focus cell into an exact finite-reference Q law."""

    environment = int(focus["environment"])
    source = int(focus["source"])
    target = int(focus["target"])
    env = np.asarray(metadata["environment"], dtype=int)
    src = np.asarray(metadata["source"], dtype=int)
    tgt = np.asarray(metadata["target"], dtype=int)
    env_mask = env == environment
    focus_mask = env_mask & (src == source) & (tgt == target)
    environment_count = int(env_mask.sum())
    focus_count = int(focus_mask.sum())
    if environment_count == 0 or focus_count == 0 or focus_count == environment_count:
        raise ValueError("focus cell is not a proper supported subcell")
    probability = focus_count / environment_count
    if requested_gamma * probability > 1.0 + 1e-12:
        raise ValueError("requested gamma cannot be realized by the selected cell")
    nonfocus_weight = (1.0 - probability * requested_gamma) / (1.0 - probability)
    weights = np.ones(len(env), dtype=float)
    weights[env_mask & ~focus_mask] = max(0.0, nonfocus_weight)
    weights[focus_mask] = requested_gamma
    if not np.isclose(weights.mean(), 1.0, atol=1e-10):
        raise RuntimeError("focus-cell density ratios do not normalize")
    probabilities = weights / len(weights)
    shift = P0Shift(
        requested_gamma=float(requested_gamma),
        focus_environment=environment,
        focus_source=source,
        focus_target=target,
        focus_probability_within_environment=float(probability),
        nonfocus_weight=float(max(0.0, nonfocus_weight)),
        global_density_ratio_cap=float(weights.max()),
        target_profile=conditional_density_ratio_profile(weights, env),
        source_profile=conditional_density_ratio_profile(weights, src),
    )
    return probabilities, shift


def q_metrics(
    candidate: Mapping[str, np.ndarray], probabilities: np.ndarray, attackers: Sequence[str]
) -> tuple[float, float, dict[str, float]]:
    """Compute the exact finite-reference shifted target and attacker risks."""

    if not np.isclose(float(probabilities.sum()), 1.0):
        raise ValueError("Q probabilities must sum to one")
    target_risks = []
    for environment in sorted(map(int, np.unique(candidate["environment"]))):
        mask = candidate["environment"] == environment
        conditional = probabilities[mask] / probabilities[mask].sum()
        target_risks.append(float(np.dot(conditional, candidate["target_harm"][mask])))
    attacker_risks: dict[str, float] = {}
    for attacker in attackers:
        recalls = []
        for source in (0, 1):
            mask = candidate["source"] == source
            conditional = probabilities[mask] / probabilities[mask].sum()
            recalls.append(
                float(np.dot(conditional, candidate[f"leakage::{attacker}"][mask]))
            )
        attacker_risks[attacker] = float(np.mean(recalls))
    return max(target_risks), max(attacker_risks.values()), attacker_risks


def allocation_from_construction(
    construction: Mapping[str, np.ndarray],
    shift: P0Shift,
    attackers: Sequence[str],
    *,
    target_threshold: float,
    leakage_threshold: float,
    total_budget: int,
    floor_fraction: float,
) -> tuple[dict[str, int], dict[str, float]]:
    """Allocate samples using only construction outcomes and the fixed profile."""

    if not 0.0 < floor_fraction < 1.0:
        raise ValueError("floor fraction must lie in (0, 1)")
    target_scores: dict[str, float] = {}
    target_margins: list[float] = []
    for environment, gamma in shift.target_profile.items():
        values = construction["target_harm"][
            construction["environment"] == int(environment)
        ]
        risk = empirical_reweighting_risk(values, gamma)
        margin = target_threshold - risk
        target_margins.append(margin)
        target_scores[f"target::{environment}"] = (gamma / max(0.01, margin)) ** 2
    leakage_margins: list[float] = []
    for attacker in attackers:
        recalls = []
        for source, gamma in shift.source_profile.items():
            values = construction[f"leakage::{attacker}"][
                construction["source"] == int(source)
            ]
            recalls.append(empirical_reweighting_risk(values, gamma))
        leakage_margins.append(leakage_threshold - float(np.mean(recalls)))
    leakage_margin = min(leakage_margins)
    scores = dict(target_scores)
    for source, gamma in shift.source_profile.items():
        scores[f"source::{source}"] = (0.5 * gamma / max(0.01, leakage_margin)) ** 2
    minimum = max(1, int(np.ceil(floor_fraction * total_budget)))
    return allocate_integer_budget(
        scores, total_budget=total_budget, minimum_per_cell=minimum
    ), scores


def sample_streams(
    metadata: Mapping[str, np.ndarray],
    allocation: Mapping[str, int],
    rng: np.random.Generator,
) -> tuple[dict[str, np.ndarray], dict[int, np.ndarray]]:
    target_indices: dict[str, np.ndarray] = {}
    source_indices: dict[int, np.ndarray] = {}
    for cell, count in allocation.items():
        family, value = cell.split("::", 1)
        if family == "target":
            indices = np.flatnonzero(metadata["environment"] == int(value))
            target_indices[f"target::environment={value}"] = rng.choice(
                indices, size=count, replace=True
            )
        elif family == "source":
            source = int(value)
            indices = np.flatnonzero(metadata["source"] == source)
            source_indices[source] = rng.choice(indices, size=count, replace=True)
        else:
            raise ValueError(f"unexpected allocation cell: {cell}")
    if set(source_indices) != {0, 1}:
        raise ValueError("allocation must sample both source classes")
    return target_indices, source_indices


def certification_samples(
    candidate: Mapping[str, np.ndarray],
    target_indices: Mapping[str, np.ndarray],
    source_indices: Mapping[int, np.ndarray],
    attackers: Sequence[str],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], np.ndarray]:
    target = {
        key: candidate["target_harm"][indices] for key, indices in target_indices.items()
    }
    source = np.concatenate(
        [np.full(len(source_indices[value]), value, dtype=int) for value in (0, 1)]
    )
    leakage = {
        attacker: np.concatenate(
            [
                candidate[f"leakage::{attacker}"][source_indices[value]]
                for value in (0, 1)
            ]
        )
        for attacker in attackers
    }
    return target, leakage, source


def _point_metrics(
    target: Mapping[str, np.ndarray], leakage: Mapping[str, np.ndarray], source: np.ndarray
) -> tuple[float, float]:
    target_max = max(float(values.mean()) for values in target.values())
    leakage_max = max(
        0.5
        * sum(float(values[source == source_class].mean()) for source_class in (0, 1))
        for values in leakage.values()
    )
    return target_max, leakage_max


def _choose(
    evaluated: Sequence[Mapping[str, Any]], field: str | None
) -> Mapping[str, Any] | None:
    eligible = list(evaluated) if field is None else [row for row in evaluated if row[field]]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda row: (row["point_leakage"], row["point_target"], row["candidate"]),
    )


def evaluate_configuration(
    candidates: Sequence[Mapping[str, Any]],
    metadata: Mapping[str, np.ndarray],
    probabilities: np.ndarray,
    shift: P0Shift,
    allocation: Mapping[str, int],
    attackers: Sequence[str],
    *,
    fixed_design_candidate: str,
    rng: np.random.Generator,
    delta: float,
    target_threshold: float,
    leakage_threshold: float,
    gamma_cap: float,
    heldout_name: str,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Evaluate the P0 deployment rules from one shared certification stream."""

    target_indices, source_indices = sample_streams(metadata, allocation, rng)
    target_profile = {
        f"target::environment={environment}": gamma
        for environment, gamma in shift.target_profile.items()
    }
    candidate_count = len(candidates)
    family_size = candidate_count * (len(target_profile) + len(attackers))
    evaluated: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for candidate in candidates:
        target, leakage, source = certification_samples(
            candidate["reference"], target_indices, source_indices, attackers
        )
        point_target, point_leakage = _point_metrics(target, leakage, source)
        iid = certify_balanced_iut_profile(
            target,
            leakage,
            source,
            target_profile={key: 1.0 for key in target},
            source_profile={"0": 1.0, "1": 1.0},
            delta=delta,
            candidate_count=candidate_count,
            target_threshold=target_threshold,
            leakage_threshold=leakage_threshold,
        )
        envelope = certify_balanced_shift_envelope(
            target,
            leakage,
            source,
            delta=delta,
            family_size=family_size,
            target_threshold=target_threshold,
            leakage_threshold=leakage_threshold,
            registered_target_environments=sorted(map(int, shift.target_profile)),
            gamma_cap=gamma_cap,
        )
        q_target, q_leakage, attacker_q = q_metrics(
            candidate["reference"], probabilities, attackers
        )
        heldout = candidate["reference"][f"heldout::{heldout_name}"]
        heldout_candidate = {
            **candidate["reference"],
            f"leakage::{heldout_name}": heldout,
        }
        _, heldout_leakage, _ = q_metrics(
            heldout_candidate, probabilities, (heldout_name,)
        )
        q_safe = q_target <= target_threshold and q_leakage <= leakage_threshold
        record = {
            "candidate": candidate["candidate"],
            "method": candidate["method"],
            "point_target": point_target,
            "point_leakage": point_leakage,
            "point_feasible": (
                point_target <= target_threshold and point_leakage <= leakage_threshold
            ),
            "iid_eligible": iid.decision == "EDIT",
            "vector_eligible": balanced_profile_in_envelope(
                envelope,
                target_profile=shift.target_profile,
                source_profile=shift.source_profile,
            ),
            "q_safe": q_safe,
            "q_target": q_target,
            "q_leakage": q_leakage,
            "registered_attacker_q": attacker_q,
            "heldout_knn_leakage": heldout_leakage,
            "heldout_knn_stress_violation": heldout_leakage > leakage_threshold,
            "envelope": envelope.to_dict(),
            "iid_limiting_contracts": list(iid.limiting_contracts),
            "family_size": family_size,
        }
        evaluated.append(record)
        details.append(
            {
                **record,
                "target_sufficient_statistics": {
                    key: {
                        "n": len(values),
                        "positive_count": int(np.sum(values == 1)),
                        "zero_count": int(np.sum(values == 0)),
                        "negative_count": int(np.sum(values == -1)),
                    }
                    for key, values in target.items()
                },
                "leakage_sufficient_statistics": {
                    attacker: {
                        str(source_class): {
                            "n": int(np.sum(source == source_class)),
                            "correct_count": int(
                                np.sum(leakage[attacker][source == source_class])
                            ),
                        }
                        for source_class in (0, 1)
                    }
                    for attacker in attackers
                },
            }
        )
    by_key = {str(row["candidate"]): row for row in evaluated}
    always = by_key.get(fixed_design_candidate)
    if always is None:
        raise RuntimeError("construction-selected candidate is absent from frontier")
    selections = {
        "always_deploy": always,
        "validation_point_selection": _choose(evaluated, "point_feasible"),
        "iid_ltt": _choose(evaluated, "iid_eligible"),
        "vera_vector_envelope": _choose(evaluated, "vector_eligible"),
        "exact_shift_oracle": _choose(evaluated, "q_safe"),
    }
    decisions = {
        rule: {
            "deployed": selected is not None,
            "safe": bool(selected is not None and selected["q_safe"]),
            "violation": bool(selected is not None and not selected["q_safe"]),
            "selected_candidate": "" if selected is None else selected["candidate"],
            "selected_method": "" if selected is None else selected["method"],
            "q_target": None if selected is None else selected["q_target"],
            "q_leakage": None if selected is None else selected["q_leakage"],
            "registered_attacker_q": (
                {} if selected is None else selected["registered_attacker_q"]
            ),
            "heldout_knn_leakage": (
                None if selected is None else selected["heldout_knn_leakage"]
            ),
            "heldout_knn_stress_violation": bool(
                selected is not None and selected["heldout_knn_stress_violation"]
            ),
            "family_size": family_size,
        }
        for rule, selected in selections.items()
    }
    return decisions, details
