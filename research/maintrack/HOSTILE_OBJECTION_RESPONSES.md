# VERA Hostile Objection Responses

This is an internal author checklist, not rebuttal text for the anonymous
submission. Every response must be visible in the main paper before review;
supplement-only defenses do not close a Phase-1 rejection path.

## 1. "This is Learn Then Test plus CVaR"

Agree that finite-family testing, CVaR duality, and bounded-reweighting risk
control are inherited. The proposed object is the paired representation-edit
contract: environment-conditional incremental target harm, source-balanced
leakage from a freshly retrained attacker portfolio, a simultaneous anisotropic
shift envelope, its limiting coordinates, and an explicit support boundary.
The main paper includes direct IID-LTT, generic scalar robust, fixed-profile,
vector-envelope, and common-radius comparisons.

## 2. "The experiment does not test shift robustness"

The prior 35/128 versus 1/128 result is labeled IID uncertainty control only.
The central study uses fresh seeds 45--108 and exact supported deployment laws
whose density ratios are machine verified at `Gamma > 1`. The abstract may make
a shift claim only after all controlled-study gates and the receipt audit are
evaluated.

## 3. "The robust result is vacuous"

Report safe retention with a seed-cluster interval, deployment rate, evidence
budget curves, targeted versus uniform allocation, vector versus common
retention, and limiting coordinates. The primary usefulness lower bound must
reach 20%, and vector retention must be at least twice common retention. If
either gate fails, report the failure rather than substituting a secondary
profile.

## 4. "Gamma is arbitrary"

`Gamma` is a declared sensitivity budget, not an estimated fact. Report the
primary 1.1 profile, secondary 1.25 and 1.5 profiles, and the exact induced
environment/source caps. Interpret claims conditionally: VERA states what is
supported if deployment obeys the declared caps.

## 5. "The external law may not lie in the ambiguity set"

For the central experiment, membership is known by construction under a finite
reference law and verified in every profile receipt. Existing benchmark test
splits are separate stress evidence and never prove ambiguity membership.
Resampled atoms are not described as new people, images, comments, or records.

## 6. "The result is driven by abstention"

Violation control and usefulness are separate endpoints. Report safe retention
relative to an exact shifted-law oracle, deployment rate, evidence curves, and
the number of vector deployments rejected by the common radius. Abstention is
the correct output when the evidence cannot establish every required contract,
but it is not counted as predictive improvement.

## 7. "The attacker portfolio is arbitrary and finite"

Agree that formal coverage is finite and portfolio scoped. The registered
linear, RBF, forest, and MLP attackers are heterogeneous and are retrained after
every edit. Report the existing portfolio ablation and the separately held-out
boosted-tree challenge, including which registered attacker best predicts
held-out failure. The boosted tree never changes certification or selection.

## 8. "The support theorem is obvious"

State the indistinguishable-world theorem quantitatively: with an unsupported
required cell, any uniformly level-`delta` validation-only protocol accepts in
the safe world with probability at most `delta`. Camelyon17 instantiates the
identification boundary without manufacturing a measured contract violation.
State what extra support or structural transport assumption would be needed.

## 9. "GaitPDB has no useful retention"

The prior IID replication retained zero of 31 oracle-safe Gait opportunities.
The final supplement must identify every limiting target environment, attacker,
source class, candidate multiplicity cost, sample-size cost, shift cost, and
required evidence level; it must also report doubled evidence, targeted
allocation, and vector-profile diagnostics. Describe non-certification, not a
fabricated unsafe edit.

## 10. "The registered study failed"

Disclose the older result precisely: all four paired comparisons favored the
fixed-profile certificate after Holm correction, but the composite endpoint
failed because Gait point selection violated 5/32 decisions, below the locked
20% baseline-severity floor; VERA violated 0/32. The new controlled study has a
different, prospectively locked endpoint hierarchy and must be reported whether
it passes or fails.

## 11. "The utility order was estimated on certification data"

The realized tie-break order is data dependent, but the rule itself is
prespecified. Fixed-profile validity does not require a certification-independent
ordering: on the simultaneous candidate event, every accepted candidate is
safe, so any measurable choice among accepted candidates remains safe. The main
paper and theorem must not condition on the realized utility order.

## 12. "The rotating safety sentinels are not identically distributed"

Agree: dataset-specific sentinel risks may differ. The registered
Clopper--Pearson gate can pass at 64 seeds only with zero events. For independent
heterogeneous Bernoulli risks with average $\bar p$, AM--GM gives
$\Pr(S=0)=\prod_i(1-p_i)\leq(1-\bar p)^{64}$, so the zero-event gate is
conservative for average sentinel risk. If any event occurs, the gate fails;
nonzero-event binomial intervals are descriptive and a heterogeneity-robust
bound is supplementary.

## 13. "The 50,000 deployment draws add outcome noise to safety labels"

They do not determine the primary labels. Primary contract status and the
external-oracle denominator use exact $Q$-weighted expectations over every atom
of the finite reference law. The independent 50,000-draw stream is a registered
Monte Carlo replay and sampling diagnostic. Both must be reported, with the
finite-reference population boundary explicit.

## 14. "The allocation theorem treats attacker samples as independent"

The experiment allocates over evidence cells, not attacker-specific streams.
One source-class draw evaluates all registered attackers, and its design score
uses the worst attacker margin for that shared cell. The theory aggregates
shared components by taking the maximum sufficient-evidence score within each
cell; satisfying that maximum satisfies all components, after which the same
minimax allocation proof applies.

## 15. "The rotating sentinel can hide a failing dataset"

The registered sentinel controls average risk over the prespecified rotating
dataset sequence, not a simultaneous per-dataset maximum. Do not claim more.
The outcome-blind supplementary sensitivity reports both the probability that
any of the four dataset decisions violates within a seed and per-dataset exact
bounds, with within-seed dependence preserved. This stricter diagnostic cannot
replace a failed sentinel. If it is unfavorable, the abstract and limitations
must state the concentration rather than presenting the average gate as
every-dataset control.

## 16. "The evidence allocation is standard active design"

Do not claim invention of inverse-margin allocation, Neyman allocation, active
testing, best-arm identification, or optimal experimental design. The proved
claim is narrower: under the certificate's sufficient-evidence scores, the
fixed-budget convex allocation minimizes the worst normalized additive DKW
slack, with a closed-form one-contract solution, square-score one-cell special
case, exact-KL lower bound, and locally matching shift--margin scaling for
compact independent-cell instances.
Position this result against the
closest allocation literature and show its empirical value against a matched
uniform allocation. If the literature contains the same certificate-specific
object or the controlled ablation shows no useful gain, narrow the title and
novelty claim rather than arguing from algebra alone.

## 17. "The allocator leaves cross-contract sample sharing on the table"

Agree. One source-class draw evaluates every registered attacker, and the
additive theorem handles that sharing. The registered empirical architecture
still uses separate target-environment and source-class streams so each
confidence curve has its declared conditional i.i.d. law. It does not solve the
more general joint environment--source stratified design in which one draw
informs both target and leakage contracts. State this limitation in the main
paper and restrict optimality to the registered stream architecture; do not
call the allocator globally sample optimal.

## 18. "The naive rules are not meaningfully unsafe, so the method has no empirical reason to exist"

Report the complete predefined three-rule threshold stress, not a favorable
profile chosen after inspection. At the registered contract, always deploy and
validation point selection must each reach 20% violations on at least one fully
reported dataset. Across all three severities, VERA must remain at or below 5%
measured violations in every dataset cell, and its registered safety and safe-
retention gates must pass so abstention cannot manufacture the comparison. All
severities reuse the registered allocation and certification draws. If this
supporting condition fails, report `three_rule_threshold_stress_failed`, remove
the memorable naive-versus-VERA headline, and do not rescue it with another
threshold. The four-gate primary decision remains separate and unchanged.

## Final Evidence Fields

- Controlled primary result: pending full matrix and outcome-blind analysis.
- Held-out attacker result: pending full matrix.
- GaitPDB limiting-contract diagnosis: pending full matrix.
- Seed-familywise and per-dataset safety sensitivity: pending full matrix.
- Three-rule threshold-stress result: pending full matrix and independent
  allocation/stream reuse audit.
- Allocation nearest-work refresh: pending official-source search.
- Four cold role reviews: human-only and incomplete.
- Fifth post-revision review: human-only and incomplete.
