# Controlled-Shift Independent Replay Specification

This specification was written before aggregate scientific outcome access for
seeds 45--108. It changes no preregistered choice. Its purpose is to require a
second implementation of the confirmatory analysis rather than a wrapper around
the locked analyzer.

## Independence Boundary

The replay implementation must be written after this specification is frozen
and may read only:

- 'research/prereg_controlled_shift.json' and its SHA-256 sidecar;
- the full audited receipt directory;
- the raw per-candidate NPZ archives named and hashed by those receipts; and
- standard numerical and statistical libraries.

It may not import executable functions, constants, or generated rows from
'analyze_controlled_shift_confirmatory.py',
'design_vera_controlled_shift_study.py', 'vera_controlled_shift.py', or any
result-builder, and it may not copy their decision blocks. Its normalized output
must be frozen and hashed before it is compared with the locked analyzer.
Prior source exposure by an implementer must be disclosed; this code-path
independence does not count as a blind human reproduction. Shared
official-method fitting code is irrelevant because the replay begins from raw
audit arrays.

## Required Reconstruction

For every dataset and seed cluster, the replay must independently:

1. verify the preregistration hash and exact seed, dataset, candidate, attacker,
   threshold, shift, evidence-budget, and allocation declarations;
2. verify every receipt and NPZ hash, runner commit, upstream commit, split
   identity, array length, dtype, and required support;
3. reconstruct paired target harm from identity and edited target-error arrays
   and require exact equality to the stored paired array;
4. reconstruct the supported focus cell, finite-reference probabilities,
   induced environment and source profiles, and density-ratio membership;
5. reconstruct targeted and uniform integer evidence allocations, including
   the 15% floor and deterministic rounding;
6. regenerate certification sample indices from registered random seeds;
7. recompute point risks, exact shifted risks, discrete confidence bounds,
   candidate IUT decisions, simultaneous envelopes, coordinate radii, common
   radii, limiting coordinates, and all nine matched deployment rules;
8. recompute exact shifted finite-law contract labels and the independent
   50,000-draw Monte Carlo diagnostics;
9. recompute the held-out boosted-tree stress metrics without using them for
   eligibility or selection; and
10. emit one normalized row per dataset, seed, profile, budget, allocation, and
    rule with stable sorting and content hashes.

## Primary Inference Replay

From the independently reconstructed primary rows, the replay must recompute:

- the 64 within-seed violation-count differences and exact two-sided sign test;
- the prespecified rotating sentinel events and registered safety gate;
- the zero-event heterogeneous-risk validity calculation;
- safe opportunities, vector safe retention, common safe retention, and their
  whole-seed bootstrap with the registered 20,000 replicates and random seed;
- the vector-to-common retention ratio and vector-only deployment count;
- absolute and relative violation reductions, deployment rates, and intervals;
- per-dataset paired effects with Holm adjustment;
- common-radius and limiting-coordinate summaries; and
- held-out attacker safety, complementarity, and predictor diagnostics.

The replay must additionally report a heterogeneity-robust safety bound and a
ratio interval that does not silently discard bootstrap samples with zero
common-rule retention. These are supplementary sensitivity analyses and may not
replace a failed registered gate.

## Equality And Failure Rules

The replay passes only if:

- all 1,280 receipts and 3,072 candidate archives are present and valid;
- all normalized primary rows agree exactly on discrete fields;
- non-radius floating-point fields agree within absolute and relative tolerance
  no larger than 1e-10, while radii agree within the registered 1e-4 bisection
  tolerance;
- every selected candidate, deployment decision, violation label, radius
  censoring flag, limiting coordinate, primary estimate, interval, p-value, and
  pass/fail gate agrees;
- no proxy row, missing field, unsupported extrapolation, or unregistered
  exclusion is present; and
- the replay output and comparison report are content hashed.

Any mismatch remains visible and blocks a submission-facing controlled-shift
headline until resolved. The replay cannot make a failed confirmatory result
pass, replace a registered statistic, or count as human scientific
verification.
