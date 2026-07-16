# Controlled-Shift Results Reporting Specification

This outcome-blind reporting specification was fixed before aggregate access to
seeds 45--108. It changes no endpoint, rule, threshold, shift, or analysis. Its
purpose is to prevent favorable-only table, figure, and abstract choices.

## Main Result Table

Use one main result table organized by deployment rule. The aggregate row for
each of the nine matched rules must report:

1. declared primary profile (`Gamma=1.1`, budget 4,000, targeted allocation);
2. deployments and deployment rate over 256 seed-dataset decisions;
3. exact shifted-law contract violations among all decisions and among deployed
   decisions, with both denominators explicit;
4. seed-cluster confidence interval for deployment rate;
5. externally safe opportunities, retained opportunities, and seed-cluster
   safe-retention interval;
6. common-radius median and interquartile range where the rule returns a
   certificate;
7. rotating-sentinel event count and registered upper bound for VERA rules;
8. seed-familywise any-dataset event count and upper bound as supplementary
   safety scope; and
9. `NA` rather than zero for quantities a rule does not define.

The main table may use compact aggregate rows plus four per-dataset VERA rows if
space permits. Complete per-dataset, eraser, attacker, budget, allocation, and
profile tables belong in the supplement. No eraser leaderboard enters the main
paper.

## Main Results Figure

Build one colorblind-safe vector figure with three panels and stable dimensions.

### Panel A: Safety by Decision Rule

Plot the exact shifted-law contract-violation rate for all nine matched rules at
the primary profile. Preserve the distinction between violation per decision
and violation conditional on deployment. Show seed-cluster intervals and mark
abstention/deployment rate without treating 256 within-seed decisions as
independent. Never omit a rule because its result is unfavorable or visually
awkward.

### Panel B: Usefulness and Evidence

Plot safe retention against evidence budgets 1,000, 2,000, 4,000, and 8,000 for
the VERA vector and common-radius rules under both targeted and uniform
allocation. Show whole-seed intervals. Mark the registered primary point and
the 20% lower-bound requirement. Report zero denominators explicitly; do not
drop them from ratio calculations or curves.

### Panel C: Certificate Anatomy

Show target-harm and attacker-leakage upper curves, thresholds, coordinate
radii, common radius, limiting contracts, and the registered anisotropic profile
for one primary-profile candidate. Choose the candidate deterministically:

1. restrict to candidates selected by the VERA vector rule at the primary
   profile;
2. order them by common radius, then dataset order (Waterbirds,
   CivilComments-WILDS, Bios, GaitPDB), seed, method order, and candidate key;
3. select the lower median of that stable order; and
4. if no candidate is selected, show the stable first external-oracle-safe
   candidate and label it `not certified`; if no oracle-safe candidate exists,
   show the stable first candidate and label both facts.

The caption must state this selection rule. Panel C is explanatory, not an
additional independent result.

## Three-Rule Threshold-Stress Figure

In the supplement, report the complete analysis frozen in
`THREE_RULE_THRESHOLD_STRESS_SPEC.md`. Use four dataset panels with
`kappa={0.75,1,1.25}` on the horizontal axis and all-decision violation rate on
the vertical axis for always deploy, validation point selection, and the VERA
vector envelope. Show a 5% reference line, whole-seed 95% intervals, and an
aligned deployment-rate strip so abstention is visible. The registered
`kappa=1` column is visually marked. No cell, zero deployment, or unfavorable
curve may be omitted.

## Abstract Branches

The abstract must distinguish the prior IID result from the controlled
`Gamma>1` result.

- If all four registered controlled-study gates pass, report the exact
  point-versus-vector violation reduction, sentinel upper bound, vector safe
  retention with interval, and vector/common ratio in one sentence.
- If any gate fails, state which registered gate failed and report the observed
  effect without calling the overall controlled claim confirmed.
- If the vector rule records no false acceptance, say `zero observed` and give
  the upper bound; never say `zero risk`.
- The seed-familywise and per-dataset sensitivity cannot replace the registered
  sentinel in the headline.
- The memorable three-rule sentence is allowed only when the threshold-stress
  supporting condition passes. It must use `kappa=1`; neither supplementary
  severity may supply or rescue the headline.

## Required Negative Results

The main or supplement must retain every failed gate, all nine decision rules,
all four datasets, all five eraser families, both allocations, every evidence
budget, all registered Gamma values, held-out attacker failures, and the GaitPDB
diagnosis. A failed three-rule threshold stress is reported under the exact ID
`three_rule_threshold_stress_failed`. Result builders must fail if any required
cell or receipt is absent.
