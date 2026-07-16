"""Temporary protocol-cap evaluator; repository integration follows matrix completion."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

import numpy as np

from design_vera_controlled_shift_study import (
    ATTACKERS,
    candidate_certification_data,
    choose,
    point_metrics,
    sample_streams,
)
from vera_robust_certificate import (
    balanced_contract_certificates,
    balanced_profile_contract_certificates,
    balanced_profile_in_envelope,
    certify_balanced_iut_profile,
    certify_balanced_shift_envelope,
)


def array_fingerprint(array: np.ndarray, domain: str) -> str:
    contiguous = np.ascontiguousarray(array)
    header = json.dumps(
        {
            "domain": domain,
            "dtype": contiguous.dtype.str,
            "shape": list(contiguous.shape),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256()
    digest.update(header)
    digest.update(b"\0")
    digest.update(contiguous.tobytes())
    return digest.hexdigest()


def common_radius_details(
    target: Mapping[str, np.ndarray],
    leakage: Mapping[str, np.ndarray],
    source: np.ndarray,
    *,
    radius: float,
    gamma_cap: float,
    delta: float,
    family_size: int,
    target_threshold: float,
    leakage_threshold: float,
    tolerance: float = 1e-4,
) -> dict[str, Any]:
    evaluation_gamma = 1.0 if radius <= 0.0 else float(radius)
    certificates = balanced_contract_certificates(
        target,
        leakage,
        source,
        gamma=evaluation_gamma,
        local_failure_probability=delta / family_size,
    )
    margins = {
        key: (
            target_threshold if key.startswith("target::") else leakage_threshold
        )
        - certificate.upper_confidence_bound
        for key, certificate in certificates.items()
    }
    worst_margin = min(margins.values())
    right_censored = bool(radius >= gamma_cap - tolerance and min(margins.values()) >= 0.0)
    limiter_tolerance = tolerance if radius > 0.0 and not right_censored else 1e-12
    limiting_contracts = sorted(
        key
        for key, margin in margins.items()
        if margin <= worst_margin + limiter_tolerance
    )
    return {
        "evaluation_gamma": evaluation_gamma,
        "right_censored": right_censored,
        "limiting_contracts": limiting_contracts,
        "contract_margins": margins,
        "certificates_at_radius": {
            key: certificate.to_dict() for key, certificate in certificates.items()
        },
    }


def evaluate_configuration_cap(
    candidates: list[dict[str, Any]],
    metadata: Mapping[str, np.ndarray],
    probabilities: np.ndarray,
    target_profile: Mapping[str, float],
    source_profile: Mapping[str, float],
    allocation: Mapping[str, int],
    *,
    rng: np.random.Generator,
    delta: float,
    target_threshold: float,
    leakage_threshold: float,
    gamma_cap: float,
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    if gamma_cap < max(*target_profile.values(), *source_profile.values()):
        raise ValueError("gamma_cap is below the requested profile")
    target_indices, source_indices = sample_streams(metadata, allocation, rng)
    candidate_count = len(candidates)
    environment_count = len(target_profile)
    family_size = candidate_count * (environment_count + len(ATTACKERS))
    common_budget = max(*target_profile.values(), *source_profile.values())
    evaluated: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    for candidate in candidates:
        target, leakage, source = candidate_certification_data(
            candidate["reference"], target_indices, source_indices
        )
        point_target, point_leakage = point_metrics(target, leakage, source)
        target_key_profile = {
            f"target::environment={environment}": gamma
            for environment, gamma in target_profile.items()
        }
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
        fixed = certify_balanced_iut_profile(
            target,
            leakage,
            source,
            target_profile=target_key_profile,
            source_profile=source_profile,
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
            registered_target_environments=sorted(map(int, target_profile)),
            gamma_cap=gamma_cap,
        )
        common_details = common_radius_details(
            target,
            leakage,
            source,
            radius=envelope.observed_common_radius,
            gamma_cap=gamma_cap,
            delta=delta,
            family_size=family_size,
            target_threshold=target_threshold,
            leakage_threshold=leakage_threshold,
        )
        profile_certificates = balanced_profile_contract_certificates(
            target,
            leakage,
            source,
            target_profile=target_key_profile,
            source_profile=source_profile,
            local_failure_probability=delta / family_size,
        )
        empirical_profile = {
            key: certificate.empirical_robust_risk
            for key, certificate in profile_certificates.items()
        }
        robust_point_feasible = all(
            value
            <= (target_threshold if key.startswith("target::") else leakage_threshold)
            for key, value in empirical_profile.items()
        )
        scalar_score = float(
            np.mean(
                [
                    certificate.upper_confidence_bound
                    / (
                        target_threshold
                        if key.startswith("target::")
                        else leakage_threshold
                    )
                    for key, certificate in profile_certificates.items()
                ]
            )
        )
        q_target, q_leakage = candidate["q_metrics"]
        evaluation_target, evaluation_leakage = candidate["evaluation_metrics"]
        q_safe = q_target <= target_threshold and q_leakage <= leakage_threshold
        evaluation_safe = (
            evaluation_target <= target_threshold
            and evaluation_leakage <= leakage_threshold
        )
        coordinate_radii = {
            **{
                f"target::environment={group}": radius
                for group, radius in envelope.target_environment_radii.items()
            },
            **{
                f"source::{source_class}": radius
                for source_class, radius in envelope.source_class_radii.items()
            },
        }
        minimum_axis_radius = min(coordinate_radii.values())
        axis_limiting_coordinates = tuple(
            sorted(
                key
                for key, value in coordinate_radii.items()
                if value <= minimum_axis_radius + 1e-12
            )
        )
        record = {
            "candidate": candidate["candidate"],
            "legacy_cap4_candidate_key": candidate.get(
                "legacy_cap4_candidate_key", candidate["candidate"]
            ),
            "method": candidate["method"],
            "point_target": point_target,
            "point_leakage": point_leakage,
            "point_feasible": (
                point_target <= target_threshold and point_leakage <= leakage_threshold
            ),
            "iid_eligible": iid.decision == "EDIT",
            "robust_point_eligible": robust_point_feasible,
            "scalar_eligible": scalar_score <= 1.0,
            "fixed_eligible": fixed.decision == "EDIT",
            "vector_eligible": balanced_profile_in_envelope(
                envelope,
                target_profile=target_profile,
                source_profile=source_profile,
            ),
            "common_eligible": envelope.deployment_common_radius >= common_budget,
            "q_safe": q_safe,
            "evaluation_safe": evaluation_safe,
            "q_target": q_target,
            "q_leakage": q_leakage,
            "evaluation_target": evaluation_target,
            "evaluation_leakage": evaluation_leakage,
            "envelope_radius": envelope.deployment_common_radius,
            "target_environment_radii": dict(envelope.target_environment_radii),
            "source_class_radii": dict(envelope.source_class_radii),
            "limiting_coordinates": axis_limiting_coordinates,
            "axis_limiting_coordinates": axis_limiting_coordinates,
            "common_limiting_contracts": tuple(common_details["limiting_contracts"]),
            "common_radius_right_censored": common_details["right_censored"],
            "fixed_profile_limiting_contracts": fixed.limiting_contracts,
        }
        evaluated.append(record)
        details.append(
            {
                **record,
                "canonical_candidate_key": candidate["candidate"],
                "legacy_cap4_candidate_key": candidate.get(
                    "legacy_cap4_candidate_key", candidate["candidate"]
                ),
                "eraser_family": candidate["method"],
                "family_size": family_size,
                "local_error_budget": delta / family_size,
                "target_threshold": target_threshold,
                "leakage_threshold": leakage_threshold,
                "gamma_cap": gamma_cap,
                "requested_target_profile": dict(target_profile),
                "requested_source_profile": dict(source_profile),
                "requested_profile_in_envelope": record["vector_eligible"],
                "envelope": envelope.to_dict(),
                "common_radius_details": common_details,
                "target_sufficient_statistics": {
                    key: {
                        "n": len(value),
                        "positive_count": int(np.sum(value == 1)),
                        "zero_count": int(np.sum(value == 0)),
                        "negative_count": int(np.sum(value == -1)),
                    }
                    for key, value in target.items()
                },
                "leakage_sufficient_statistics": {
                    attacker: {
                        str(source_class): {
                            "n": int(np.sum(source == source_class)),
                            "correct_count": int(
                                np.sum(leakage[attacker][source == source_class])
                            ),
                            "incorrect_count": int(
                                np.sum(source == source_class)
                                - np.sum(leakage[attacker][source == source_class])
                            ),
                        }
                        for source_class in (0, 1)
                    }
                    for attacker in ATTACKERS
                },
                "target_coordinate_axis_intercepts": dict(
                    envelope.target_environment_radii
                ),
                "source_coordinate_axis_intercepts": dict(
                    envelope.source_class_radii
                ),
                "coupled_common_radius": envelope.observed_common_radius,
                "deployment_common_radius": envelope.deployment_common_radius,
                "common_radius_right_censored": common_details["right_censored"],
                "common_radius_limiting_contracts": list(
                    common_details["limiting_contracts"]
                ),
                "certification_index_sha256": {
                    "target": {
                        key: array_fingerprint(value, f"target indices::{key}")
                        for key, value in target_indices.items()
                    },
                    "source": {
                        str(source_class): array_fingerprint(
                            value, f"source indices::{source_class}"
                        )
                        for source_class, value in source_indices.items()
                    },
                },
                "sampled_source_sha256": array_fingerprint(
                    source, "sampled certification source labels"
                ),
                "certification_source_sha256": array_fingerprint(
                    np.asarray(metadata["source"]),
                    "full certification source labels",
                ),
                "receipt_certification_split_sha256": candidate.get(
                    "receipt_certification_split_sha256"
                ),
                "audit_npz_sha256": candidate.get("audit_npz_sha256"),
            }
        )
    selections = {
        "always_deploy": choose(evaluated, None),
        "validation_point_selection": choose(evaluated, "point_feasible"),
        "iid_ltt": choose(evaluated, "iid_eligible"),
        "robust_point_estimate": choose(evaluated, "robust_point_eligible"),
        "generic_scalar_robust_certificate": choose(evaluated, "scalar_eligible"),
        "vera_fixed_profile": choose(evaluated, "fixed_eligible"),
        "vera_vector_envelope": choose(evaluated, "vector_eligible"),
        "vera_common_radius": choose(evaluated, "common_eligible"),
        "external_oracle": choose(evaluated, "q_safe"),
    }
    decisions = {
        rule: {
            "deployed": selected is not None,
            "safe": bool(selected is not None and selected["q_safe"]),
            "violation": bool(selected is not None and not selected["q_safe"]),
            "evaluation_violation": bool(
                selected is not None and not selected["evaluation_safe"]
            ),
            "selected_candidate": "" if selected is None else selected["candidate"],
            "canonical_candidate_key": (
                "" if selected is None else selected["candidate"]
            ),
            "legacy_cap4_candidate_key": (
                ""
                if selected is None
                else str(selected["legacy_cap4_candidate_key"])
            ),
            "selected_method": "" if selected is None else selected["method"],
            "q_target": None if selected is None else selected["q_target"],
            "q_leakage": None if selected is None else selected["q_leakage"],
            "evaluation_target": (
                None if selected is None else selected["evaluation_target"]
            ),
            "evaluation_leakage": (
                None if selected is None else selected["evaluation_leakage"]
            ),
            "certified_common_radius": (
                0.0 if selected is None else selected["envelope_radius"]
            ),
            "target_environment_radii": (
                {} if selected is None else selected["target_environment_radii"]
            ),
            "source_class_radii": (
                {} if selected is None else selected["source_class_radii"]
            ),
            "limiting_coordinates": (
                [] if selected is None else list(selected["limiting_coordinates"])
            ),
            "axis_limiting_coordinates": (
                [] if selected is None else list(selected["axis_limiting_coordinates"])
            ),
            "common_limiting_contracts": (
                [] if selected is None else list(selected["common_limiting_contracts"])
            ),
            "common_radius_right_censored": bool(
                selected is not None and selected["common_radius_right_censored"]
            ),
            "fixed_profile_limiting_contracts": (
                []
                if selected is None
                else list(selected["fixed_profile_limiting_contracts"])
            ),
        }
        for rule, selected in selections.items()
    }
    return decisions, details
