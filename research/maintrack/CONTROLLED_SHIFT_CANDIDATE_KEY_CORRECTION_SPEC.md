# Controlled-Shift Candidate-Key Correction Specification

## Static Defect And Scope

This correction was fixed while the official receipt matrix was still running
and before any fresh candidate metric, decision, radius, gate, or aggregate
scientific outcome was viewed. The locked receipts store the official R-LACE
candidate token as `R-LACE`, so their stable keys are `R-LACE::rank=1` and
`R-LACE::rank=4`. The locked cap-4 analyzer instead reconstructs candidate keys
from the preregistration's receipt-level display name `RLACE`, producing
`RLACE::rank=1` and `RLACE::rank=4` after the receipt has been loaded.

The preregistered selection utility ends with the stable candidate key. The
receipt's audited `candidate_key == method + "::" + strength` field is therefore
the protocol authority. This correction changes no array, edit, attacker,
threshold, confidence bound, random stream, eligibility test, or non-tie
selection ordering. The original cap-4 analyzer and its executable dependencies
remain byte-unchanged as the required sensitivity output.

## Canonical Execution Rule

The protocol-compliant cap-8 analyzer and independent replay must read each
candidate's `candidate_key`, `method`, and `strength` directly from its audited
receipt. They must reject an unknown token, a key/method/strength mismatch, or a
key that is absent from the exact 12-candidate frontier. The canonical R-LACE
method token is `R-LACE`; `RLACE` remains valid only as the locked receipt's
top-level display name and as the disclosed legacy cap-4 execution token.

Every normalized candidate and decision record must contain
`canonical_candidate_key`. Cap-8 and replay selection tie-breaks use that field.
The cap-8 analyzer may additionally retain `legacy_cap4_candidate_key` solely
for comparison. No generated paper, table, figure, archive, or named result may
present the legacy token as the candidate identity.

## Sealed Three-Way Comparison

The committed comparator must construct the exact one-to-one crosswalk

- `RLACE::rank=1` to `R-LACE::rank=1`; and
- `RLACE::rank=4` to `R-LACE::rank=4`.

All other keys map identically. The comparator must reject a missing,
many-to-one, one-to-many, or unknown mapping. Cap-8 analyzer and replay records
must agree under canonical keys with no candidate-key exception.

For the exact 12-candidate frontier, this crosswalk is order-preserving. INLP,
LEACE, and MANCE++ sort before both R-LACE spellings, TaCo sorts after both, and
the two R-LACE rank keys retain their internal order. The comparator must prove
that sorting all 12 canonical keys gives the same candidate order as sorting
their legacy images and mapping back. Therefore key spelling alone cannot
change the preregistered stable-key tie-break, and no candidate-key-driven
selection, row, aggregate, or primary-gate difference is permitted. Any such
difference blocks the controlled result rather than being classified as an
allowed correction effect.

## Mandatory Fixtures

Before sealed execution, deterministic tests must show that:

1. all 12 receipt keys normalize one-to-one;
2. canonical and legacy sorting induce the same order on all 12 candidates;
3. both non-tied and exact-tied selections are unchanged by the crosswalk;
4. a deliberately order-changing crosswalk fails;
5. `RLACE` in a cap-8 or replay candidate record fails;
6. an unknown or duplicate crosswalk fails; and
7. any candidate-key-attributed selection difference fails.

## Reporting Rule

The shared manifest must record this specification's source hash, both
candidate-key vocabularies, the crosswalk hash, the order-preservation check,
and zero candidate-key-attributed selection, row, aggregate, and gate
differences. This pre-outcome normalization correction is disclosed even when
all scientific difference counts are zero.
