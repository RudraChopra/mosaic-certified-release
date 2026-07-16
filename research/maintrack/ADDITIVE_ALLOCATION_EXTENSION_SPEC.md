# Additive Multi-Cell Evidence Allocation Extension

This specification was fixed while the 1,280-run controlled matrix was still
running and before any seeds 45--108 scientific outcome was read. It addresses
a theory-to-protocol gap: a target-environment contract uses one evidence cell,
but balanced leakage is the average of two source-class robust recalls, so one
contract depends additively on multiple cells. The registered square-score
allocation remains the locked primary rule and may not be changed or rescued by
this extension.

## Additive Contract Model

Let `j = 1,...,J` index registered contracts and `c = 1,...,C` index evidence
cells. Contract `j` has nonnegative cell weights `w_jc`, population risk

`R_j = sum_c w_jc rho_jc`,

threshold `q_j`, and positive design-fold margin estimate `mhat_j`. A target
environment has one nonzero weight equal to one. A balanced-leakage contract
has weights one half on each represented source class. One source-class sample
may evaluate several attackers; those dependencies remain shared rather than
being counted as independent evidence.

For the DKW power surrogate, define

`b_jc = w_jc * Gamma_jc * range_jc / sqrt(2)
         * (sqrt(log(2/alpha_jc)) + sqrt(log(2D/beta)))`,

where `D` is the number of distinct registered cell-risk curves receiving a
power event. Define normalized coefficients `a_jc = b_jc / mhat_j`, with the
registered positive margin clamp used only on the independent design fold.

## Envelope-Aware Allocation

For total evidence budget `N` and registered cell floors `ell_c`, solve the
continuous convex program

`minimize t`

subject to

`sum_c a_jc / sqrt(n_c) <= t` for every contract `j`,

`sum_c n_c = N`, and `n_c >= ell_c`.

Use a deterministic convex solver with fixed tolerances. Convert the continuous
solution to integers by starting at each floor, taking lower integer parts, and
assigning remaining observations one at a time to the cell giving the largest
deterministic decrease in the current maximum contract slack; break ties by the
stable cell key. Record the continuous objective, integer objective, solver
status, tolerance, and complete allocation in every result row.

For one additive contract with inactive floors, the analytic solution is

`n_c = N * a_c^(2/3) / sum_d a_d^(2/3)`.

When each contract depends on exactly one independent cell, the program reduces
to the registered squared-score allocation after taking the maximum coefficient
for contracts sharing a cell. Thus the extension strictly generalizes the
proved special case rather than changing certificate validity.

## Outcome-Blind Empirical Comparison

After the full controlled receipt audit and locked primary analysis, compare:

1. uniform allocation;
2. the registered `targeted_floor_0.15` square-score allocation; and
3. additive envelope-aware allocation with the same 15% per-cell floor.

Use the same four supported datasets, five official eraser families, candidate
frontier, 64 seed clusters, thresholds, attackers, shift laws, and budgets
`{1000, 2000, 4000, 8000}`. Evaluate requested Gamma values
`{1.1, 1.25, 1.5}`. The new allocator may read only the already registered
independent design fold. It may not read primary certification draws, exact
shifted-law labels, Monte Carlo deployment draws, or any analyzer output.

Generate new certification streams under a versioned deterministic random
namespace, `vera-additive-allocation-v1`, disjoint from every locked primary
stream. Reuse the finite reference atoms and fitted candidate arrays; do not
refit erasers or probes. Hash the stream indices and allocator inputs.

## Frozen Analyses

The independent unit is the 64-seed cluster. Report for each allocation:

- exact shifted-law violations per decision and conditional on deployment;
- safe opportunity retention with 20,000 whole-seed bootstrap resamples;
- abstention and deployment rate;
- common-radius and vector-envelope usefulness;
- per-dataset and aggregate results; and
- allocation counts, normalized contract slacks, and limiting contracts.

Compare additive allocation with uniform and registered targeted allocation by
two-sided exact sign tests on within-seed safe-retention count differences and
report Hodges--Lehmann-style median paired differences descriptively. Apply Holm
correction across the two aggregate allocation contrasts. Safety is not traded
for retention: report the same rotating-sentinel, seed-familywise, and
per-dataset event summaries, but do not reinterpret them as new primary gates.

## Interpretation Rule

- This is a prospectively specified extension, not part of the locked primary
  controlled-study decision.
- It cannot replace a failed registered efficacy, safety, usefulness, or
  vector-advantage gate.
- If additive allocation does not improve the frozen power surrogate and show a
  useful empirical retention advantage without worse safety, remove
  `Evidence-Efficient` from the title and present allocation as a negative
  ablation.
- If it succeeds, claim only minimax optimality for the stated additive DKW
  surrogate conditional on the design fold. Do not claim generic active-design
  novelty or population-optimal data collection.
- Every result remains subject to the final primary-source nearest-work search
  and external reviewer challenge.

## Required Outputs

1. theorem and proof for the additive power guarantee and convex minimax program;
2. exact reduction checks for the one-contract and one-cell special cases;
3. solver-versus-grid tests on small integer allocations;
4. a versioned allocation implementation independent of the locked analyzer;
5. receipt-like allocation and stream manifests;
6. aggregate and per-dataset tables;
7. a targeted-versus-uniform-versus-additive figure; and
8. manuscript text that labels the registered primary and this extension
   separately.
