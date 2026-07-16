# Evidence-Requirement Diagnostic Specification

This outcome-blind diagnostic was fixed before seeds 45--108 scientific outcome
access. It complements the additive allocation extension by estimating how much
additional certification evidence an abstaining edit would need and where that
evidence should be collected. It changes no primary endpoint, threshold,
candidate, allocation, or deployment decision.

## Two Distinct Quantities

Report two quantities and never merge their interpretations.

### Design-Fold Planning Estimate

For the candidate selected by the frozen design-fold max-min-margin rule, use
the additive coefficients and clamped design-fold margins fixed in
`ADDITIVE_ALLOCATION_EXTENSION_INTERPRETATION_1.md`. Solve

`minimize sum_c n_c`

subject to

`sum_c a_jc / sqrt(n_c) <= 1` for every contract `j`,

and `n_c >= ell_c` for every registered evidence cell. This convex program is
the minimum continuous total budget predicted to clear the normalized additive
DKW power surrogate under the plug-in design margins. Apply the same solver
tolerances, analytic Jacobians, stable keys, fail-closed checks, and
deterministic integer rounding as the additive allocation extension.

For each requested budget in `{1000, 2000, 4000, 8000}`, report the estimated
additional total observations, the recommended integer count and top-up for
every cell, the currently limiting contracts, and the objective before and
after the top-up. A nonpositive unclamped design margin is explicitly labeled
`no positive-margin planning estimate`; the 0.01 clamp may still produce an
allocation stress diagnostic but cannot be presented as evidence that the edit
is certifiable.

### Oracle-Only Benchmark Explanation

After the locked primary analysis, use exact finite-reference shifted-law
contract margins only to explain benchmark power. For every external-oracle-safe
candidate, compute the theorem-level sufficient count and additive minimum-total
budget using those population margins. Label every such value `oracle-only` and
exclude it from candidate selection, allocation, certification, or any
deployment-facing recommendation.

This quantity asks whether abstention is explained by evidence scarcity under
the known benchmark law. It is not available in a real deployment and cannot
rescue a failed gate.

## Cell-Level Recommendation

For both quantities, report:

- target-environment and source-class cell keys;
- current and recommended counts;
- absolute and percentage top-up;
- contracts sharing each cell;
- each contract's normalized additive slack;
- the cell receiving the next deterministic observation under the greedy
  integer objective; and
- whether the recommendation is driven by target harm, one attacker, one source
  class, multiplicity, declared shift, or the registered floor.

A source-class observation shared by several attackers is counted once. Do not
sum attacker-specific pseudo-samples.

## Numerical Checks

Before real reporting, require:

1. one-contract inverse-budget solutions to agree with the analytic
   two-thirds-power form and its closed-form total-budget inversion;
2. one-cell-per-contract solutions to agree with square-score inversion;
3. small three-cell inverse-budget cases to be compared with exhaustive integer
   search;
4. monotonic nonincrease of required top-up as the current budget grows;
5. permutation invariance under contract and cell reorderings;
6. exact reconstruction of every reported slack from receipt fields; and
7. deliberate negative-margin, solver, floor, budget, hash, and alignment
   corruptions to fail closed.

## Reporting Scope

Produce per-candidate rows and seed-cluster summaries for Waterbirds,
CivilComments-WILDS, Bios, and GaitPDB at all registered Gamma values. The main
paper may report one compact aggregate sentence and one certificate-anatomy
annotation; full cell recommendations belong in the supplement and software
demo.

The design-fold value is a planning estimate conditional on plug-in margins,
not a promise that newly collected observations will have those margins. The
oracle value is an ex-post finite-law explanation, not deployable information.
Neither quantity changes false-acceptance validity, and neither may replace an
unfavorable controlled-study or additive-allocation result.
