# MOSAIC symmetric scope stress specification

## Status

This is a post-review deterministic analysis of the already locked
12,000-table bridge-misspecification study. It creates no new samples, changes
no fitted release, and does not estimate a deployment frequency.

## Question

The admitted-shift stress asks whether a direct target-table release can fail
on a law in MOSAIC's learned bridge class but outside its direct target region.
The complementary question is whether a declared bridge violation can occur
while the true target law remains inside the direct target-table confidence
region, and whether MOSAIC's bridge gate rejects it.

## Construction

Use every replicate from the two invalid, prelocked target laws:

1. `underdeclared_contamination`: true retained mass is 0.775, below the
   declared 0.80 minimum.
2. `source_specific_transform`: true retained mass is 0.50, below the
   declared 0.80 minimum.

For a replicate with target empirical table `qhat` and simultaneous target
radius `epsilon`, define the direct target-table region rowwise as
`D(qhat, epsilon) = {q : ||q - qhat||_1 <= epsilon}`. The known constructed
target law is counted as inside the direct region exactly when it satisfies all
four source--label inequalities. Its bridge status uses the prelocked
population retained-mass calculation. MOSAIC abstains when the stored bridge
membership gate does not accept.

## Required checks

- Retain all 8,000 invalid rows from the frozen report.
- Verify each scenario's target law against the implementation registry.
- Report every target-region event, bridge violation, and gate decision.
- Require zero bridge-gate acceptances on invalid rows.
- On every direct-region event, require both an out-of-class target law and
  MOSAIC abstention.

## Interpretation

This is a scope test, not a claim that the direct target-table rule is unsafe
inside its own region. Its target confidence statement remains valid there.
Instead, the two stress cells make the distinction explicit: the direct region
and the bridge class are different declared sets, while MOSAIC has a measured
rejection path when the bridge assumption is violated.
