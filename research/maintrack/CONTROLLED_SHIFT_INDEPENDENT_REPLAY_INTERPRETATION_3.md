# Controlled-Shift Independent Replay: Interpretation 3

This outcome-blind addendum reconciles the replay equality rule with the
pre-outcome radius-cap mismatch documented in
`CONTROLLED_SHIFT_RADIUS_CAP_CORRECTION_SPEC.md`. All source-sealing,
independence, cardinality, invariant, and tolerance requirements from the base
specification and Interpretations 1--2 remain mandatory.

The sealed execution order in
`CONTROLLED_SHIFT_RADIUS_CAP_CORRECTION_SPEC.md` supersedes Step 5 of
Interpretation 1. All three analyzers generate metric-bearing outputs with
console values suppressed, all outputs are hashed and made read-only, and the
committed three-way comparator performs the first permitted scientific-outcome
access. The unchanged cap-4 analyzer is therefore never the first-read or
confirmatory authority.

The independent replay must read `gamma_cap=8.0` from the verified
preregistration. Its primary equality target is the separately committed
protocol-compliant cap-8 analyzer. Exact/discrete and floating/radius comparison
tolerances remain unchanged.

The original locked cap-4 analyzer is a required third output, not the primary
equality target for cap-dependent fields. The comparator must still require it
to agree on every cap-independent record and may classify only the differences
explicitly allowed by the correction specification. A cap-4 mismatch outside
that allowlist, or a cap-8 mismatch of any kind, blocks the controlled result.

The replay must emit both the uncapped pass/fail curve information needed to
verify truncation and the reported cap-8 radii/censor flags. It must never copy
cap-4 decisions into its normalized output merely to force equality. The final
comparison report records cap-dependent candidate, row, selection, decision,
aggregate, and gate difference counts even when all counts are zero.
