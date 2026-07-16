# VERA External Review Outreach

This file supports the human-only review gate. Sending a request, identifying a
reviewer, judging conflicts, and recording a received review require a human
author. An automated critique or an unanswered request does not count.

## Required Review Roles

Use one different reviewer for each cold role:

1. theory and statistical validity;
2. distribution shift, conformal inference, or risk control;
3. representation editing, probing, privacy, or algorithmic fairness; and
4. general machine learning with no prior involvement in VERA.

After all major findings from those four reviews are resolved and a new
anonymous package is frozen, invite a fifth, previously unused general-ML
reader. The fifth reader must not receive the earlier reviews or response
ledger.

Before contacting anyone, the author must verify a relevant peer-reviewed ML
publication, check conflicts, and use contact information obtained from the
reviewer's official institutional or personal academic page. Do not infer or
publish private contact information.

## Initial Cold-Review Request

Subject: Request for a cold review of an anonymous machine-learning paper

Hello [Name],

I am preparing an anonymous machine-learning methods paper on certifying
representation edits under supported deployment shift. Would you be willing to
give it a cold, adversarial review in the role of [role]?

The packet contains an anonymous main paper, supplement, and reproducibility
archive. I am specifically looking for the strongest correctness, novelty, and
experimental reasons a top-tier reviewer might reject it, especially overlap
with Learn Then Test, conformal risk control, robust validation, active testing,
and representation-erasure work. The structured form has twelve fields and is
designed to take about [honest estimate after the final PDF is frozen].

Please decline if you have a conflict or prior involvement that would prevent a
cold review. If you can help, I will send one frozen anonymous package with
content hashes and a requested return date. I will not send internal audits,
earlier critiques, or suggested scores.

Thank you,
[Human author]

## Package Message After Agreement

Subject: Anonymous VERA review packet and frozen hashes

Hello [Name],

Thank you for agreeing to review the paper. Attached are the frozen anonymous
main paper, supplement, code archive, and the review form. Their SHA-256 hashes
are listed below so the exact reviewed version can be recorded:

- main PDF: [hash]
- supplement PDF: [hash]
- anonymous archive: [hash]

Please return the completed form by [date]. Be direct: a rejection recommendation
is useful, and every critical or major concern will be preserved verbatim in the
private response ledger. Please confirm that the review is human-authored, cold,
and conflict-free, and include a public URL for one relevant ML publication so
the role requirement can be verified.

Thank you,
[Human author]

## Fifth Post-Revision Request

Subject: Request for a fresh review of a revised anonymous ML paper

Hello [Name],

Would you be willing to review a revised anonymous machine-learning paper on
certifying representation edits under supported deployment shift? You are being
asked as a fresh reader after an earlier revision cycle. I will send only the
revised anonymous paper, supplement, reproduction archive, and review form; you
will not receive the earlier reviews or response ledger.

The goal is to learn whether a new top-tier reviewer still sees a fatal novelty,
correctness, significance, or empirical problem. Please decline if you have a
conflict or prior involvement with the project.

Thank you,
[Human author]

## Recording Rule

Keep reviewer identities and original reviews outside the public and anonymous
repositories. Record only coded reviewer IDs and frozen artifact hashes in the
submission-facing ledger. Never edit an original review; append resolutions and
paper locations separately. Run `audit_external_reviews.py` only after all
required private records and review files exist.
