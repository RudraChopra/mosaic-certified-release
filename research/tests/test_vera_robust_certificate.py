from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from vera_robust_certificate import (  # noqa: E402
    certify_balanced_iut_fixed_profile,
    certify_balanced_shift_radius,
    certify_discrete_iut_fixed_profile,
    certify_discrete_group_shift_envelope,
    certify_discrete_shift_radius,
    certify_shift_radius,
    certify_edits,
    empirical_reweighting_risk,
    exact_balanced_leakage_certificate,
    exact_discrete_risk_certificate,
    robust_risk_certificate,
)


class EmpiricalReweightingRiskTests(unittest.TestCase):
    def test_gamma_one_is_sample_mean(self) -> None:
        values = np.array([0.0, 0.25, 0.75, 1.0])
        self.assertAlmostEqual(empirical_reweighting_risk(values, 1.0), values.mean())

    def test_gamma_two_averages_upper_half(self) -> None:
        values = np.array([0.0, 0.25, 0.75, 1.0])
        self.assertAlmostEqual(empirical_reweighting_risk(values, 2.0), 0.875)

    def test_large_gamma_reaches_maximum(self) -> None:
        values = np.array([-1.0, -0.5, 0.4])
        self.assertAlmostEqual(empirical_reweighting_risk(values, 10.0), 0.4)


class CertificateTests(unittest.TestCase):
    def test_balanced_leakage_scores_constant_attacker_at_chance(self) -> None:
        source = np.asarray([0] * 500 + [1] * 500)
        correct = np.asarray([1] * 500 + [0] * 500)
        certificate = exact_balanced_leakage_certificate(
            "constant",
            correct,
            source,
            gamma=1.0,
            failure_probability=0.05,
        )
        self.assertAlmostEqual(certificate.empirical_robust_risk, 0.5)
        self.assertGreaterEqual(certificate.upper_confidence_bound, 0.5)
        self.assertLess(certificate.upper_confidence_bound, 0.51)

    def test_balanced_leakage_rejects_missing_source_class(self) -> None:
        with self.assertRaises(ValueError):
            exact_balanced_leakage_certificate(
                "missing",
                np.ones(20),
                np.zeros(20, dtype=int),
                gamma=1.0,
                failure_probability=0.05,
            )

    def test_balanced_iut_and_envelope_use_distinct_multiplicity(self) -> None:
        source = np.asarray([0] * 500 + [1] * 500)
        leakage = {"linear": np.asarray([1] * 500 + [0] * 500)}
        target = {"target::environment=0": np.zeros(1000, dtype=int)}
        iut = certify_balanced_iut_fixed_profile(
            target,
            leakage,
            source,
            gamma=1.25,
            delta=0.05,
            candidate_count=12,
            target_threshold=0.1,
            leakage_threshold=0.7,
        )
        envelope = certify_balanced_shift_radius(
            target,
            leakage,
            source,
            delta=0.05,
            family_size=24,
            target_threshold=0.1,
            leakage_threshold=0.7,
            gamma_cap=2.0,
        )
        self.assertEqual(iut.decision, "EDIT")
        self.assertGreaterEqual(envelope.certified_radius, 1.25)

    def test_iut_fixed_profile_spends_alpha_over_candidates_only(self) -> None:
        samples = {
            "target": np.asarray([-1] * 20 + [0] * 470 + [1] * 10),
            "leakage_a": np.asarray([0] * 350 + [1] * 150),
            "leakage_b": np.asarray([0] * 340 + [1] * 160),
        }
        supports = {
            "target": (-1, 0, 1),
            "leakage_a": (0, 1),
            "leakage_b": (0, 1),
        }
        thresholds = {"target": 0.1, "leakage_a": 0.6, "leakage_b": 0.6}
        result = certify_discrete_iut_fixed_profile(
            samples,
            gamma=1.25,
            delta=0.05,
            candidate_count=12,
            supports=supports,
            thresholds=thresholds,
        )
        self.assertAlmostEqual(result.candidate_failure_probability, 0.05 / 12)
        self.assertTrue(
            all(
                certificate.simultaneous_failure_probability == 0.05 / 12
                for certificate in result.certificates
            )
        )

    def test_empirical_paired_formula_matches_greedy_linear_program(self) -> None:
        for positive in range(6):
            for negative in range(6 - positive):
                zero = 5 - positive - negative
                values = np.asarray([1] * positive + [0] * zero + [-1] * negative)
                p_positive = positive / 5
                p_negative = negative / 5
                for gamma in (1.0, 1.25, 2.0, 5.0):
                    if gamma * p_positive >= 1.0:
                        expected = 1.0
                    elif gamma * (1.0 - p_negative) >= 1.0:
                        expected = gamma * p_positive
                    else:
                        expected = gamma * p_positive - (
                            1.0 - gamma * (1.0 - p_negative)
                        )
                    self.assertAlmostEqual(
                        empirical_reweighting_risk(values, gamma), expected
                    )

    def test_exact_bernoulli_certificate_rejects_high_leakage(self) -> None:
        certificate = exact_discrete_risk_certificate(
            "leakage",
            [1] * 80 + [0] * 20,
            gamma=1.0,
            failure_probability=0.05,
            support=(0, 1),
        )
        self.assertGreater(certificate.upper_confidence_bound, 0.8)

    def test_exact_paired_certificate_uses_beneficial_negative_harm(self) -> None:
        certificate = exact_discrete_risk_certificate(
            "harm",
            [-1] * 100 + [0] * 900,
            gamma=1.0,
            failure_probability=0.05,
            support=(-1, 0, 1),
        )
        self.assertLess(certificate.upper_confidence_bound, 0.0)

    def test_exact_paired_probability_bounds_respect_simplex(self) -> None:
        certificate = exact_discrete_risk_certificate(
            "harm",
            [1] * 2 + [-1] * 98,
            gamma=1.25,
            failure_probability=0.05,
            support=(-1, 0, 1),
        )
        details = certificate.confidence_details
        assert details is not None
        positive = min(
            float(details["positive_probability_upper"]),
            1.0 - float(details["negative_probability_lower"]),
        )
        self.assertLessEqual(
            positive + float(details["negative_probability_lower"]), 1.0
        )

    def test_exact_shift_radius_spends_alpha_over_full_family(self) -> None:
        report = certify_discrete_shift_radius(
            {"harm": np.zeros(1000), "leakage": np.zeros(1000)},
            delta=0.05,
            supports={"harm": (-1, 0, 1), "leakage": (0, 1)},
            thresholds={"harm": 0.1, "leakage": 0.1},
            family_size=20,
            gamma_cap=4.0,
        )
        self.assertEqual(report.decision, "EDIT")
        self.assertGreaterEqual(report.certified_radius, 1.0)
        self.assertTrue(
            all(
                certificate.simultaneous_failure_probability == 0.05 / 20
                for certificate in report.certificates_at_radius
            )
        )

    def test_group_envelope_minimum_matches_joint_radius(self) -> None:
        grouped_samples = {
            "0": {
                "target::0": np.r_[np.ones(2), np.zeros(998)],
                "leakage::0": np.r_[np.ones(300), np.zeros(700)],
            },
            "1": {
                "target::1": np.r_[np.ones(5), np.zeros(995)],
                "leakage::1": np.r_[np.ones(350), np.zeros(650)],
            },
        }
        grouped_supports = {
            group: {"target::" + group: (-1, 0, 1), "leakage::" + group: (0, 1)}
            for group in grouped_samples
        }
        grouped_thresholds = {
            group: {"target::" + group: 0.1, "leakage::" + group: 0.7}
            for group in grouped_samples
        }
        envelope = certify_discrete_group_shift_envelope(
            grouped_samples,
            delta=0.05,
            grouped_supports=grouped_supports,
            grouped_thresholds=grouped_thresholds,
            family_size=20,
            gamma_cap=4.0,
        )
        flat_samples = {
            key: values for samples in grouped_samples.values() for key, values in samples.items()
        }
        flat_supports = {
            key: value for supports in grouped_supports.values() for key, value in supports.items()
        }
        flat_thresholds = {
            key: value
            for thresholds in grouped_thresholds.values()
            for key, value in thresholds.items()
        }
        joint = certify_discrete_shift_radius(
            flat_samples,
            delta=0.05,
            supports=flat_supports,
            thresholds=flat_thresholds,
            family_size=20,
            gamma_cap=4.0,
        )
        self.assertAlmostEqual(
            envelope.observed_common_radius, joint.certified_radius, delta=1e-4
        )

    def test_group_envelope_assigns_zero_to_unsupported_group(self) -> None:
        envelope = certify_discrete_group_shift_envelope(
            {"seen": {"target": np.zeros(1000)}},
            delta=0.05,
            grouped_supports={"seen": {"target": (-1, 0, 1)}},
            grouped_thresholds={"seen": {"target": 0.1}},
            family_size=4,
            registered_groups=["seen", "unseen"],
            gamma_cap=4.0,
        )
        self.assertEqual(envelope.group_radii["unseen"], 0.0)
        self.assertEqual(envelope.deployment_common_radius, 0.0)
        self.assertEqual(envelope.decision, "ABSTAIN")
        self.assertEqual(envelope.unsupported_groups, ("unseen",))

    def test_ucb_is_at_least_empirical_robust_risk(self) -> None:
        cert = robust_risk_certificate(
            "risk",
            [0.0] * 90 + [1.0] * 10,
            gamma=2.0,
            failure_probability=0.05,
            lower=0.0,
            upper=1.0,
        )
        self.assertGreaterEqual(cert.upper_confidence_bound, cert.empirical_robust_risk)
        self.assertLessEqual(cert.upper_confidence_bound, 1.0)

    def test_edit_rule_abstains_when_target_cannot_certify(self) -> None:
        n = 200
        target = {"weak": np.ones(n), "strong": np.ones(n)}
        leakage = {
            ("weak", "linear"): np.zeros(n),
            ("strong", "linear"): np.zeros(n),
        }
        decision = certify_edits(
            target,
            leakage,
            edit_order=["weak", "strong"],
            gamma=1.0,
            delta=0.05,
            target_threshold=0.1,
            leakage_threshold=0.6,
        )
        self.assertEqual(decision.decision, "ABSTAIN")
        self.assertIsNone(decision.selected_edit)

    def test_edit_rule_selects_strongest_certified_edit(self) -> None:
        n = 10_000
        target = {"weak": np.zeros(n), "strong": np.zeros(n)}
        leakage = {
            ("weak", "linear"): np.zeros(n),
            ("strong", "linear"): np.zeros(n),
        }
        decision = certify_edits(
            target,
            leakage,
            edit_order=["weak", "strong"],
            gamma=1.0,
            delta=0.05,
            target_threshold=0.1,
            leakage_threshold=0.1,
        )
        self.assertEqual(decision.decision, "EDIT")
        self.assertEqual(decision.selected_edit, "strong")

    def test_shift_radius_abstains_when_iid_contract_fails(self) -> None:
        report = certify_shift_radius(
            {"harm": np.ones(500)},
            delta=0.05,
            bounds={"harm": (0.0, 1.0)},
            thresholds={"harm": 0.2},
            gamma_cap=4.0,
        )
        self.assertEqual(report.decision, "ABSTAIN")
        self.assertEqual(report.certified_radius, 0.0)

    def test_shift_radius_is_positive_and_limiting_contract_is_reported(self) -> None:
        samples = {
            "harm": np.r_[np.ones(20), np.zeros(9980)],
            "leakage": np.r_[np.ones(3000), np.zeros(7000)],
        }
        report = certify_shift_radius(
            samples,
            delta=0.05,
            bounds={"harm": (0.0, 1.0), "leakage": (0.0, 1.0)},
            thresholds={"harm": 0.1, "leakage": 0.55},
            gamma_cap=8.0,
        )
        self.assertEqual(report.decision, "EDIT")
        self.assertGreaterEqual(report.certified_radius, 1.0)
        self.assertLess(report.certified_radius, 8.0)
        self.assertIn("leakage", report.limiting_contracts)


if __name__ == "__main__":
    unittest.main()
