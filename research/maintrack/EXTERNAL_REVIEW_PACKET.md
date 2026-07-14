# VERA External Cold-Review Packet

## Purpose

Two researchers with peer-reviewed machine-learning publications should review
the same frozen anonymous package. The review gate is evidence of adversarial
feedback, not evidence that acceptance is guaranteed.

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

## Unprompted Review

Ask the reviewer to assess the work as a conference submission and identify the
strongest reasons to reject it. Request explicit comments on:

1. correctness and scope of the external-distribution guarantee;
2. novelty relative to Learn Then Test, Prompt Risk Control, conformal risk
   control, fairness certification, and concept erasure;
3. whether the unsupported-support impossibility result is meaningful;
4. whether the experiments demonstrate a need for certification;
5. whether any claim is stronger than its receipt-backed evidence;
6. the single most important missing experiment or ablation.

After the free-form review is complete, ask one binary follow-up: "Does the
paper explicitly and adequately address its overlap with Learn Then Test and
Prompt Risk Control?"

## Required Attestations

Each reviewer record must include a verifiable ML publication URL, conflict
disclosure, confirmation that the review is human-authored and cold, the exact
main-PDF hash reviewed, an explicit LTT/Prompt-Risk-Control overlap verdict,
and confirmation that every finding was transcribed into the private registry.

## Resolution

Transcribe every finding without softening it. Every critical or major item
must be fixed in the paper/code or rebutted with a concrete location. Rebuild
and re-audit the anonymous package after fixes; do not edit the original review
files.
