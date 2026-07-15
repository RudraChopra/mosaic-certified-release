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
| Anonymous main paper | `404f3b2` frozen package | `6c185279753aba5d35441c87ef2f2ded716ae587671ee8a494c30ffc2ba3cc83` | frozen, not yet reviewed |
| Anonymous supplement | `404f3b2` frozen package | `a83c0008fd5c8794a3240e80003b506bbed299345e699cdfa1d740306fc75699` | frozen, not yet reviewed |
| Anonymous code archive | `404f3b2` frozen package | `35c8bffee22c09a4849427f75baf28a931211053ec229380cc85e2dfa691bb88` | frozen, audit passed |

Archive audit: `research/artifacts/vera_anonymous_archive_audit.json`.

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
