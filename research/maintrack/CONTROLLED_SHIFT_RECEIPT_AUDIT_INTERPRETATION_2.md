# Controlled-Shift Receipt Audit: Interpretation 2

This outcome-blind interpretation supersedes only the candidate-method naming
clause in `CONTROLLED_SHIFT_RECEIPT_AUDIT_INTERPRETATION_1.md`. Every exact-file,
root-containment, symlink, hardlink, closed-array, reconstruction, provenance,
and corruption-fixture requirement in Interpretation 1 remains mandatory.

## Canonical Candidate Tokens

The locked preregistration's top-level `method_name` remains checked literally
against each method's registered `display_name`. Candidate records use the
official candidate token emitted by the frozen adapter, which differs only for
the R-LACE punctuation. The canonical mapping is:

| Registered method key | Receipt `method_name` | Candidate `method` |
| --- | --- | --- |
| `inlp` | `INLP` | `INLP` |
| `rlace` | `RLACE` | `R-LACE` |
| `leace` | `LEACE` | `LEACE` |
| `taco` | `TaCo` | `TaCo` |
| `mance` | `MANCE++` | `MANCE++` |

For every candidate, require
`candidate_key == candidate.method + "::" + candidate.strength`. Derive the
expected strengths from the locked `candidate_configuration`, yielding exactly
these 12 keys in every dataset--seed block:

- `INLP::rank=1`, `INLP::rank=2`, `INLP::rank=4`, and `INLP::rank=8`;
- `R-LACE::rank=1` and `R-LACE::rank=4`;
- `LEACE::closed_form`;
- `TaCo::components_removed=1`, `TaCo::components_removed=2`,
  `TaCo::components_removed=3`, and `TaCo::components_removed=5`; and
- `MANCE++::epsilon=0.05,steps=3`.

These strings are fixed by the locked protocol and frozen adapter source, not
inferred from candidate metrics or controlled-study outcomes. The audit must
fail on an unknown registered method key, a missing expected key, an extra key,
a strength mismatch, or use of `RLACE` as the candidate token.

## Additional Fixture

In addition to every Interpretation 1 corruption fixture, a fixture must change
an otherwise valid R-LACE candidate's `method` to `RLACE` and demonstrate that
the strict audit rejects the resulting method/key mismatch.

## Pass Condition

The full receipt audit can pass only under this canonical-token rule and every
unchanged Interpretation 1 requirement. This clarification changes no receipt,
array, candidate, threshold, random stream, endpoint, or scientific gate.
