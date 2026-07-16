# VERA External Cold-Review Packet

## Purpose

Four researchers with peer-reviewed machine-learning publications should review
the frozen anonymous package. They must cover four distinct roles: theory and
statistical validity; distribution shift or conformal risk; representation
erasure or fairness; and general machine learning with no prior involvement in
the project. After all major findings are resolved, a fifth, previously unused
reviewer reads the revised package. This gate measures adversarial scrutiny; it
cannot guarantee acceptance.
Human authors may use `EXTERNAL_REVIEW_OUTREACH.md` to request these reviews;
an invitation or automated review never counts as a completed role review.

## Frozen Package

Send only these finalized artifacts, recording each SHA-256 in the private
review registry:

- anonymous main paper PDF:
  `dist/private-review/vera_aaai2027_anonymous.pdf`;
- anonymous supplement PDF:
  `dist/private-review/vera_aaai2027_supplement_anonymous.pdf`;
- anonymous reproduction archive:
  `dist/private-review/vera_anonymous_submission_v2.zip`.

The private registry must record hashes from the final rebuilt package. Earlier
draft hashes are invalid review provenance.

Regenerate the final private archive audit from the V2 archive. A counted
package must have zero identity, path, commit-linkage, and legacy-name hits and
must pass compact one-command reproduction from extraction; an audit of an
earlier archive does not satisfy this gate. Keep the private audit and frozen
package outside the named branch.

Do not send internal readiness audits, prior critiques, response drafts, author
identity, or claimed target scores before the reviewer writes the cold review.

## Review Form

Ask each reviewer to assess the work as a top-tier general machine-learning
conference submission and identify the strongest reasons to reject it. The
written review must contain all of the following fields:

1. Summary
2. Strengths
3. Weaknesses
4. Novelty score (1--7)
5. Correctness score (1--7)
6. Experimental-quality score (1--7)
7. Clarity score (1--7)
8. Significance score (1--7)
9. Overall score (1 strong reject, 2 reject, 3 weak reject, 4 borderline,
   5 weak accept, 6 accept, 7 strong accept)
10. Confidence (1--5)
11. Most likely rejection reason
12. One change most likely to raise the score

The free-form review must explicitly address:

1. correctness and scope of the external-distribution guarantee;
2. novelty relative to Learn Then Test, Prompt Risk Control, conformal risk
   control, fairness certification, and concept erasure;
3. whether the unsupported-support impossibility result is meaningful;
4. whether the experiments demonstrate a need for certification;
5. whether any claim is stronger than its receipt-backed evidence;
6. the single most important missing experiment or ablation;
7. whether the controlled `Gamma>1` design genuinely establishes ambiguity
   membership and whether its finite-reference claim boundary is clear;
8. whether the additive multi-cell evidence allocation is correctly derived and
   novel enough after accounting for Neyman/stratified allocation, active
   testing, shared-observation experimental design, and adaptive sampling;
   specifically, whether the paper clearly separates its general allocator from
   the locked square-score primary study;
9. whether the rotating-sentinel average-risk claim and the supplementary
   any-dataset/per-dataset bounds rule out hidden safety concentration without
   overstating simultaneous control;
10. whether the predefined always-deploy/validation/VERA comparison at all
    three contract severities demonstrates a real deployment problem without
    selecting a favorable severity, and whether useful retention rules out
    trivial safety by universal abstention; and
11. whether the cap-4/cap-8 implementation correction is disclosed clearly,
    cap 8 is unmistakably the preregistered authority, and the independent
    replay plus protocol-compliant analyzer agreement is enough to restore
    confidence in the result.

After the free-form review is complete, ask two binary follow-ups: "Does the
paper explicitly and adequately address its overlap with Learn Then Test and
Prompt Risk Control?" and "Is the contribution merely Learn Then Test applied
to representation erasure?"

## Required Attestations

Each reviewer record must include its assigned role, a verifiable ML
publication URL, conflict disclosure, confirmation that the review is
human-authored and cold, all numeric scores, the exact main-PDF hash reviewed,
explicit overlap verdicts, and confirmation that every finding was transcribed
into the private registry.

## Resolution

Transcribe every finding without softening it. Every critical or major item
must be fixed in the paper/code or rebutted with a concrete location. Rebuild
and re-audit the anonymous package after fixes; do not edit original review
files. The gate passes only if no reviewer reports a fatal correctness flaw,
no reviewer says the contribution is merely LTT applied to erasure, at least
three of the four role reviews score weak accept or better, at least two score
accept or better, every critical/major finding is resolved in the submission,
and a new reviewer completes a post-revision read.
