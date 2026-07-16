# External Review Response Ledger

## Status

Role reviews completed: **0 of 4**. Fresh post-revision reviews completed:
**0 of 1**.

This ledger is intentionally fail-closed. No reviewer identity, review, score,
or resolution may be invented. Internal audits and automated critiques do not
count toward this gate.

Reviewers receive the cold-review instructions in
`EXTERNAL_REVIEW_PACKET.md`; reviewer identities and original review files stay
in the ignored private registry.

## Frozen Materials

| Artifact | Version | SHA-256 | Status |
|---|---|---|---|
| Anonymous main paper | final candidate pending | pending | current draft is not review-countable |
| Anonymous supplement | final candidate pending | pending | current draft is not review-countable |
| Anonymous code archive | final candidate pending | pending | current archive is not review-countable |

Regenerate `research/artifacts/vera_anonymous_archive_audit.json` after the final
candidate is frozen. An audit or review of an earlier package does not satisfy
this gate.

## Reviewer Provenance

| Reviewer | ML publication evidence | Conflict disclosure | Requested | Received | PDF SHA-256 | Counts |
|---|---|---|---|---|---|---|
| Reviewer 1 | pending | pending | pending | pending | pending | no |
| Reviewer 2 | pending | pending | pending | pending | pending | no |
| Reviewer 3 | pending | pending | pending | pending | pending | no |
| Reviewer 4 | pending | pending | pending | pending | pending | no |
| Fresh post-revision reviewer | pending | pending | pending | pending | pending | no |

## Findings

| ID | Reviewer | Severity | Finding | Resolution | Paper/code location | Status |
|---|---|---|---|---|---|---|
| pending | pending | pending | No external finding received yet. | pending | pending | open |

## Hard Checks

- [ ] Four real reviewers cover theory/statistics, shift/risk control,
      erasure/fairness, and general ML; each has a verifiable ML publication.
- [ ] All four reviewers received a frozen anonymous package.
- [ ] Every counted review contains all 12 required fields, including
      significance, overall recommendation, confidence, and strongest
      rejection reason.
- [ ] Every role review explicitly considered the Learn Then Test and Prompt
      Risk Control overlap.
- [ ] No reviewer reports a fatal correctness flaw or calls the work merely LTT
      applied to erasure.
- [ ] At least three overall scores are weak accept or better and at least two
      are accept or better.
- [ ] Every reviewer attests that all findings were transcribed without omission.
- [ ] Every fatal and major finding is fixed or explicitly rebutted.
- [ ] A fifth, previously unused reviewer reads the revised paper after fixes.
- [ ] Revised PDFs and archive pass anonymity and reproducibility audits.
