# Controlled-Shift Radius-Cap Protocol Correction

This outcome-blind correction was fixed during receipt generation and before
aggregate or candidate-level scientific access to seeds 45--108. Static source
review found one implementation mismatch:

- `research/prereg_controlled_shift.json` fixes `real_study.gamma_cap = 8.0`;
- every venue manuscript and reporting specification states `Gamma_max = 8`;
  but
- the locked analyzer reaches `evaluate_configuration`, where
  `certify_balanced_shift_envelope` is called with `gamma_cap=4.0`.

Receipt generation fits erasers and stores raw audit arrays; it does not call
this analysis path. The running 1,280-receipt matrix is therefore unaffected.
No outcome was read to discover or resolve the mismatch.

## Frozen Authority Rule

The explicit preregistered value 8.0 is the scientific authority. The cap-8
analysis is the protocol-compliant confirmatory analysis. The original cap-4
analyzer must remain byte-unchanged, be executed and archived, and be labeled
the original locked-implementation sensitivity. Outcomes may not determine
which cap is primary.

Before outcome access, create and commit a protocol-compliant analyzer whose
scientific difference from the locked analyzer is limited to reading and
requiring `real_study.gamma_cap == 8.0` and passing that value to envelope
inversion. A static semantic-diff audit must reject any other change in
datasets, seeds, arrays, shifts, allocations, random streams, bounds, rules,
tie-breaks, endpoints, bootstrap, tests, or success gates.

The code-path-independent replay must separately implement cap 8 directly from
the preregistration. It may not import either analyzer. The protocol-compliant
analyzer and independent replay must agree under the frozen replay tolerances
before a controlled result becomes submission-facing.

## Sealed Execution and Comparison

After the full receipt audit and pre-outcome source commit:

1. run the independent cap-8 replay with metric-bearing output suppressed;
2. run the protocol-compliant cap-8 analyzer with metric-bearing output
   suppressed;
3. run the unchanged locked cap-4 analyzer with metric-bearing output
   suppressed;
4. hash and make all three outputs read-only; and
5. open them first through a committed comparator that verifies cap-8 equality
   and classifies every cap-4 difference.

The cap-4 comparison must agree exactly or within the registered tolerances on
all quantities that do not depend on envelope truncation. Permitted differences
are limited to coordinate/common radii, right-censoring, limiting coordinates
at a cap boundary, vector-profile eligibility when a required coordinate is
above 4 and at most 8, common-radius eligibility above 4 and at most 8, and
decisions or aggregates downstream of those eligibility changes. Any other
difference is a separate analysis failure.

## Mandatory Tests

Before real execution, require deterministic fixtures in which:

1. every true coordinate radius is below 4 and cap-4/cap-8 outputs agree;
2. at least one coordinate radius lies strictly between 4 and 8;
3. at least one coordinate exceeds 8 and is right-censored only at 8;
4. an anisotropic required profile with a coordinate between 4 and 8 is
   evaluated correctly under the cap-8 envelope;
5. a common required profile between 4 and 8 changes only the expected
   cap-dependent eligibility;
6. the cap is read from the verified preregistration rather than duplicated as
   another literal; and
7. wrong-cap, changed-RNG, changed-threshold, changed-rule, changed-tie-break,
   and unclassified-output corruptions fail closed.

## Reporting Rule

The shared manifest must record both analyzer source/output hashes, the replay
hash, both cap values, all cap-dependent row and decision difference counts,
and whether any primary gate differs. Every paper must disclose this
pre-outcome implementation correction even when it changes no decision. If a
primary decision or gate differs, report both results and identify cap 8 as the
preregistered authority; do not describe the original locked implementation as
confirmatory authority and do not hide the discrepancy in a supplement.
