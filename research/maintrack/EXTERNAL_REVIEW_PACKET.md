# VERA External Cold-Review Packet

## Purpose

Four researchers with peer-reviewed machine-learning publications should review
the frozen anonymous package. They must cover four distinct roles: theory and
statistical validity; distribution shift or conformal risk; representation
erasure or fairness; and general machine learning with no prior involvement in
the project. After all major findings are resolved, a fifth, previously unused
reviewer reads the revised package. This gate measures adversarial scrutiny; it
cannot guarantee acceptance.

## Frozen Package

Send only these finalized artifacts, recording each SHA-256 in the private
review registry:

- anonymous main paper PDF:
  `research/maintrack/aaai2027_template/AuthorKit27/vera_aaai2027_anonymous.pdf`
  SHA-256 `6c185279753aba5d35441c87ef2f2ded716ae587671ee8a494c30ffc2ba3cc83`;
- anonymous supplement PDF:
  `research/maintrack/aaai2027_template/AuthorKit27/vera_aaai2027_supplement_anonymous.pdf`
  SHA-256 `a83c0008fd5c8794a3240e80003b506bbed299345e699cdfa1d740306fc75699`;
- anonymous reproduction archive:
  `dist/vera_anonymous_submission.zip`
  SHA-256 `35c8bffee22c09a4849427f75baf28a931211053ec229380cc85e2dfa691bb88`,
  source commit `404f3b2ef61e3df0a62578cf1e6ca9539e1f54f9`.

The archive audit in `research/artifacts/vera_anonymous_archive_audit.json`
records that the package had no identity hits, no legacy-name hits, and passed
compact one-command reproduction.

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
8. Overall score (1 strong reject, 2 reject, 3 weak reject, 4 borderline,
   5 weak accept, 6 accept, 7 strong accept)
9. Confidence (1--5)
10. Most likely rejection reason
11. One change most likely to raise the score

The free-form review must explicitly address:

1. correctness and scope of the external-distribution guarantee;
2. novelty relative to Learn Then Test, Prompt Risk Control, conformal risk
   control, fairness certification, and concept erasure;
3. whether the unsupported-support impossibility result is meaningful;
4. whether the experiments demonstrate a need for certification;
5. whether any claim is stronger than its receipt-backed evidence;
6. the single most important missing experiment or ablation.

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
