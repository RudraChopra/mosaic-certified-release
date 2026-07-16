# Controlled-Shift Receipt Audit: Interpretation 3

This outcome-blind interpretation adds one shared-comparator invariant to the
strict receipt audit. It was fixed during receipt generation and before any
candidate metric, deployment decision, risk, radius, violation, retention
value, or aggregate outcome from seeds 45--108 was viewed. It changes no
receipt, model, candidate, array, random stream, threshold, endpoint, or gate.
Every requirement in Receipt Audit Interpretations 1--2 remains mandatory.

## Shared Identity Comparator

Paired target harm is meaningful across the 12-candidate frontier only if every
candidate in one dataset--seed block uses the same identity target comparator.
For each certification and external split, hash the identity-target-error
array using a domain-separated serialization of its dtype, shape, and
contiguous bytes. Require exactly one such hash across all 12 candidates and
all five official-method receipts in that dataset--seed block.

This check is separate from paired-harm reconstruction. Reconstruction proves
that one candidate's stored harm equals its edited error minus its stored
identity error; it would not detect different identity comparators across
candidates. Shared labels, split indices, and metadata also do not imply shared
identity predictions. Any identity-array disagreement blocks the official
frontier comparison and every downstream analysis.

The report must record the number of dataset--seed--split blocks checked and
the complete list of disagreement keys, which must be empty for a pass. It must
not report identity error counts or rates during the sealed pre-outcome audit.

## Mandatory Corruption Fixture

Starting from an otherwise valid multi-method fixture, flip one identity-error
bit in one candidate, reconstruct that candidate's paired-harm array so its
local reconstruction still passes, update the NPZ hash, and require the strict
audit to fail specifically on the cross-candidate identity-comparator
invariant. This demonstrates that the new check is not merely another local
harm-reconstruction test.

## Outcome-Blind Structural Check

A hash-only check over all receipts available at the time of this
interpretation covered all 256 dataset--seed blocks and both certification and
external splits (512 block--split comparisons) and found zero identity-hash
disagreements. It did not compute or display an identity error count, rate,
candidate risk, decision, radius, violation, retention value, or aggregate
scientific outcome. The final pass still requires the committed implementation,
the corruption fixture above, and the complete 1,280-receipt audit.
