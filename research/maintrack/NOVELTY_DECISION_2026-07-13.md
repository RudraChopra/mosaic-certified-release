# Novelty Decision

## Verdict

The original VERA paper is beyond repair as a top-main-track submission if its
only new claim is finite-candidate confidence-bound selection with abstention.
That mechanism is an application of Learn Then Test style risk control. It can
remain an implementation component, but it cannot remain the contribution.

## Replacement Research Question

What is the largest deployment reweighting budget under which a representation
edit can be simultaneously certified to preserve target utility and resist
registered sensitive-attribute recovery attacks, and when must that radius
collapse to zero?

The paired quantity matters. For target loss, VERA evaluates the incremental
harm of an edit relative to the identity intervention on the same example. For
leakage, VERA audits fresh heterogeneous attackers and certifies the worst
preregistered attacker, not the eraser's native probe. The locked study uses
observed environment cells to scope target guarantees and source-class cells
to define prevalence-invariant balanced leakage; it does not claim to discover
latent environments.

## Submission Name

Use **VERA: Evidence-Efficient Certification of Representation Edits Under
Deployment Shift**. The evidence-efficiency claim is scoped to prospective
minimax allocation of certification observations for additive contracts across
supported audit cells; its square-score and two-thirds-power formulas are
special cases, not generic novelty claims. It is not a claim of globally
optimal data collection. Leave VERA unexpanded
in the paper: the formal guarantee covers a finite registered attacker
portfolio, not all measurable recovery algorithms.

## Scope Escalation Completed After This Decision

The project now adds a support-aware vector envelope, sample-complexity upper
and lower bounds, prospective additive multi-cell evidence allocation, exact
small-case enumeration, and a 64-seed controlled `Gamma>1` study with known
ambiguity membership. This is the minimum expanded scope used for the current
submission. The finite-family acceptance rule remains inherited from Learn Then
Test.

## Required Delta Over Prior Work

The final paper must prove and evaluate all of the following together:

1. a simultaneous lower confidence bound on each edit's maximum common shift
   radius, obtained by inverting robust paired-harm and attacker-leakage bands
   over a continuum of density-ratio budgets;
2. a worst-group mixture corollary for the annotated-group setting;
3. a support-mismatch impossibility theorem showing that a nontrivial
   distribution-free certificate is impossible when deployment can put mass
   where validation has none;
4. a comparison showing why point selection, an IID LTT certificate, and a
   shift-robust paired certificate make measurably different deployment
   decisions; and
5. an honest boundary that no finite attacker portfolio certifies erasure
   against all measurable recovery algorithms.

The paper must also distinguish this package from distributional fairness
certification and Wasserstein fairness auditing. Those neighboring literatures
already combine ambiguity sets, fairness functionals, and finite-sample bounds.
The remaining claim is the selected representation-intervention contract and
its support-aware paired-harm/multi-attacker envelope, not generic robust
auditing.

## Kill Criteria

The pivot fails and must be redesigned again if the literature audit finds the
same erasure-shift-radius object and guarantee, the robust bounds are vacuous on
all five real datasets, or naive selection does not produce honest external
contract violations. Internal audit scripts cannot waive these criteria.
