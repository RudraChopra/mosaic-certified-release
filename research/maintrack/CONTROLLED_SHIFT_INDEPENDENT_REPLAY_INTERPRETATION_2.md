# Controlled-Shift Independent Replay: Interpretation 2

This outcome-blind addendum strengthens normalized-record completeness and
zero-denominator checks. It changes no registered statistic, random stream,
endpoint, tolerance, gate, or execution order in the replay specification and
Interpretation 1.

## Exact Cardinality and Key Audit

Before aggregation, require exactly:

- 1,280 valid dataset--method--seed receipts;
- 3,072 unique dataset--seed--candidate audit records;
- 768 unique shift profiles (`4 datasets * 64 seeds * 3 Gamma values`);
- 6,144 unique allocation records (`4 * 64 * 3 * 4 budgets * 2 locked allocations`);
- 55,296 unique decision rows (`6,144 * 9 rules`); and
- 2,304 primary rows (`4 * 64 * 9`) at Gamma 1.1, budget 4,000, and the
  targeted allocation.

Build each count from stable logical keys before constructing lookup maps.
Reject duplicate keys rather than allowing a dictionary, database constraint,
or later row to overwrite an earlier row. Require every expected Cartesian key
exactly once and every unsupported or extra key to fail.

## Decision Invariants

For every normalized rule row:

1. `deployed=false` implies no selected candidate, `safe=false`, and
   `violation=false`;
2. `deployed=true` implies exactly one registered selected candidate and
   exactly one of `safe` or `violation`;
3. every safe vector or common-radius deployment implies that the exact
   shifted-law opportunity oracle deploys for the same dataset, seed, profile,
   budget, and allocation;
4. retained safe-opportunity counts never exceed exact shifted-law opportunity
   counts in a row, seed cluster, dataset, or aggregate;
5. the opportunity oracle never selects a contract-violating candidate;
6. every rule's selected candidate is the deterministic minimum under the
   shared point-leakage, point-harm, stable-key tie-break among that rule's
   independently reconstructed eligible set; and
7. held-out-attacker fields do not affect any eligible set, selected candidate,
   certificate, or exact registered-portfolio safety label.

Deliberate duplicate, missing-key, extra-key, safe-without-opportunity,
safe-and-violation, oracle-violation, and held-out-selection corruptions must
fail before real comparison.

## Usefulness Bootstrap Audit

Reproduce the locked analyzer's finite-only usefulness interval exactly for
comparison. Separately implement
`CONTROLLED_SHIFT_USEFULNESS_SENSITIVITY_SPEC.md` from the normalized primary
rows. Retain all 20,000 registered resamples, require the positive- and
zero-opportunity case counts to sum to 20,000, require zero cases with positive
retention but no opportunity, and emit the conservative completed-statistic
and division-free intervals.

The sensitivity cannot alter or rescue the registered gate. A disagreement
between the finite-only primary interval and the sensitivity must survive into
the shared result manifest and venue prose as a named qualification.

## Comparison Extension

The third comparator must verify these cardinalities and invariants for the
independent replay and reconstruct them directly from the locked analyzer's raw
rows. Agreement on aggregate headlines does not pass when either normalized
record set has a duplicate, omission, impossible state, or unreported
zero-denominator case.
