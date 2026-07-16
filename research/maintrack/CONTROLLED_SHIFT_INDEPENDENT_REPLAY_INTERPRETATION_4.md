# Controlled-Shift Independent Replay: Interpretation 4

This outcome-blind addendum was fixed during receipt generation and before any
candidate metric, decision, radius, gate, or aggregate scientific outcome from
seeds 45--108 was viewed. It resolves an output-sufficiency gap found by static
source review. The locked analyzer evaluates full coupled leakage-envelope
inequalities when deciding whether a requested profile is inside the envelope,
but its serialized decision rows retain only coordinate-axis intercepts and a
common radius. Those intercepts do not by themselves reconstruct the coupled
two-source leakage inequalities.

All requirements of the base replay specification and Interpretations 1--3
remain mandatory. The locked cap-4 analyzer stays byte-unchanged. The
protocol-compliant cap-8 analyzer remains subject to the radius-correction
semantic-diff rule; this addendum does not authorize a new selection, bound,
random stream, statistic, endpoint, or gate.

## Full Envelope Record

The independent cap-8 replay must emit one stably sorted envelope-detail record
for every candidate and every dataset, seed, requested cap, evidence budget,
and registered allocation. The expected cardinality is

`4 datasets * 64 seeds * 3 caps * 4 budgets * 2 allocations * 12 candidates = 73,728`.

Every record must include:

1. the complete configuration key, candidate key, eraser family, family-size
   denominator, local error budget, thresholds, and cap;
2. target-cell sample sizes and positive, zero, and negative counts;
3. attacker-by-source sample sizes and correct/incorrect counts;
4. the exact Clopper--Pearson sufficient statistics and upper/lower probability
   limits used by every target and leakage curve;
5. the exact requested environment/source conditional profile and whether its
   full coupled inequalities pass;
6. target coordinate-axis intercepts and source coordinate-axis intercepts,
   each explicitly labeled as an intercept with every other coordinate fixed at
   one;
7. the coupled common radius, right-censoring flags, and limiting common-radius
   contracts computed from the simultaneous all-coordinate path; and
8. hashes of the certification indices and source arrays needed to link the
   detail record to the receipt and normalized decision rows.

The stored sufficient statistics must reconstruct every upper curve at any
profile inside the cap without rereading model predictions. The replay may
store raw certification values only by content hash; it must not duplicate
private arrays into an anonymous package.

## Terminology And Invariants

`target_environment_radii` and `source_class_radii` are coordinate-axis
intercepts. Their minimum is an axis-intercept summary, not automatically the
coupled common radius and not automatically the limiting common-radius
contract. These objects must have distinct field names.

For every configuration:

- full-envelope membership recomputed from the stored curve statistics must
  equal the replay's vector eligibility exactly;
- common-profile membership at the requested maximum coordinate must equal
  common-radius eligibility within the registered `1e-4` bisection tolerance;
- every selected candidate in the 55,296 normalized decision rows must resolve
  to exactly one of the 73,728 detail records;
- every common limiting contract must attain the minimum coupled margin at the
  reported common radius within tolerance; and
- cap-8 right-censoring must be derived from a pass at 8, never from an axis
  intercept copied from the cap-4 output.

The result figures and generated text must call the intercepts intercepts and
must use the coupled curve statistics for any displayed anisotropic profile.

## Mandatory Failure Fixtures

Tests must reject a missing or duplicate detail key; altered positive or
negative target count; altered attacker/source count; wrong local alpha;
swapped source classes; an intercept mislabeled as a common radius; a selected
candidate without one matching detail record; a vector decision inconsistent
with the coupled inequalities; and a limiting contract that does not attain the
reported common-radius margin.

Any failed invariant blocks envelope, radius, geometry, or limiting-contract
claims. It cannot be waived because the primary efficacy or safety gates are
otherwise favorable.
