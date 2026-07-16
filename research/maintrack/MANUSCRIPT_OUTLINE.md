# VERA Seven-Page Manuscript Outline

## Title

**VERA: Support-Aware Certification of Representation Edits Under Deployment Shift**

The title describes the actual guarantee. Leave VERA unexpanded in
submission-facing text because the guarantee covers a registered attacker
portfolio, not all recovery algorithms.

## Abstract (180-210 words)

Open with the deployment problem: an edit that appears useful on IID validation
data can damage its target or leak a source concept after reweighting. State the
output, not the machinery: a support-aware vector of environment- and
source-conditional shift budgets, a common-radius summary, limiting dimensions,
or abstention. Attribute finite-candidate testing to Learn Then Test in the
abstract. Name the support impossibility result.

Report two empirical claims separately. The prior 32-seed IID study measures
uncertainty control and must disclose its failed auxiliary baseline-severity
gate. The prospective 64-seed controlled study measures robustness at
`Gamma=1.1` under deployment laws whose ambiguity membership is known. Its
single memorable sentence is generated only after all four primary gates and
the receipt audit are evaluated, and only if the separately frozen three-rule
threshold stress passes without selecting a supplementary severity.

## 1. Introduction (0.8 page)

Define a representation edit as an intervention and ask one question: should
this edit be deployed under this declared supported shift? Explain why average
target accuracy and one native probe do not answer it. State the thesis in one
sentence:

> VERA certifies whether a representation edit can be deployed under a
> declared, supported reweighting shift while jointly controlling incremental
> target harm and recovery by a registered attacker portfolio.

State exactly four contributions: a support-aware vector certificate for paired
interventions; simultaneous validity across edits, environments, attackers,
source classes, and a continuum of budgets together with prospective evidence
allocation for additive multi-cell contracts and its locally matching
compact-interior independent-cell lower bound; an
unsupported-support impossibility result; and a preregistered cross-modal study
of safety and useful retention.

## Figure 1: Method in Ten Seconds (0.65 page)

Panel A shows independent-fold additive evidence allocation, then pairs identity
and edited predictions on the same examples and trains fresh heterogeneous
attackers. Panel B shows component upper curves, the fixed
profile decision, and their inversion into an envelope with a limiting common
radius. Panel C contrasts certification on observed support with abstention at
new support. Curves must be labeled schematic unless they come from a receipt.

## 2. Related Work (0.75 page)

Concept erasure covers INLP, R-LACE, LEACE, kernel methods, TaCo, SPLINCE,
MANCE++, and fundamental limits. The paper compares candidate construction but
does not claim eraser state of the art.

Risk control covers risk-controlling prediction sets, Learn Then Test,
Conformal Risk Control, Pareto Testing, Prompt Risk Control, group-conditional
control, and selective prediction. Explicitly state that VERA does not invent
finite-family acceptance, multiple-risk testing, or abstention.

Shift work covers covariate-shift weighting, robust validation,
distributionally robust evaluation, distributional fairness certification,
group DRO, and support/transport impossibility. Evidence allocation must be
positioned against active testing and adaptive sampling. The narrow delta is
the paired representation-intervention vector under supported conditional
reweighting, together with its evidence requirement and support boundary.

## 3. Problem and Method (1.15 pages)

Define the frozen representation, target, source concept, observed environment,
identity edit, registered edit family, and independent certification stream.
Define paired target harm in `{-1,0,1}` and per-attacker correctness in `{0,1}`.
Define the bounded density-ratio ambiguity set, environment-conditional target
risk, and source-prior-invariant balanced leakage.

Present the full vector envelope first. The common radius is its diagonal
summary, not the method's only output. Explain the candidate-wise fixed-profile
intersection-union test and the separately simultaneous post-inspection
envelope. State that unsupported required cells receive zero deployable radius.

## 4. Guarantees and Evidence Requirements (0.95 page)

State the fixed-profile false-acceptance theorem and attribute its finite-family
logic to Learn Then Test. State the simultaneous vector-envelope theorem and
why one coverage event is uniform over a continuum of budgets. Give the DKW
sufficient evidence bound, additive multi-cell convex allocation, and Bernoulli
lower bound, emphasizing the unavoidable local quadratic dependence on shift
and inverse margin in compact interior regimes and the exact-KL lower bound for
the stated independent Bernoulli comparison experiment without an interior
restriction. State the two-world
unsupported-cell impossibility theorem. Full derivations remain in the
supplement, but every assumption and conclusion needed for the main claim must
appear in the paper.

## 5. Experimental Protocol (0.9 page)

The central matrix contains four supported datasets, five pinned official
eraser families, 12 candidates per dataset-seed block, and 64 fresh seeds
(45--108): 1,280 method runs and 3,072 candidate archives. Construction data fit
edits, target probes, and four registered attackers. A boosted tree is held out
for stress evaluation only.

Official validation audit atoms define the finite reference law. A disjoint
design fold chooses the rare supported focus cell from metadata and computes a
prospective evidence allocation. Independent certification and 50,000-draw
final streams are generated from the reference and exact shifted laws. Every
profile has a machine-verified density-ratio membership receipt.
Primary violation labels and oracle opportunities use exact shifted finite-law
expectations; the 50,000-draw stream is a Monte Carlo replay.

The primary setting is `Gamma=1.1`, `delta=0.05`, 4,000 contract observations,
and a targeted allocation with a 15% per-cell floor. Compare always deploy,
validation point selection, IID LTT, robust point estimation, scalar robust
certification, VERA fixed profile, VERA vector envelope, VERA common radius,
and the exact shifted-law opportunity oracle (machine key `external_oracle`).
All rules share candidates, outcomes, thresholds, shifts, and seed clusters.

Report the predefined always-deploy/validation/VERA stress at
`kappa={0.75,1,1.25}` using the same registered allocation and certification
draws. Both naive rules must separately reach 20% violations on a registered-
contract dataset, VERA must remain at or below 5% in every cell, and registered
safety/usefulness must pass before the memorable three-rule sentence is legal.
This supporting condition cannot change the four-gate primary result.

Label the primary allocator as the registered square-score rule. Separately
report the pre-outcome additive envelope-aware extension against uniform and
square-score allocation on disjoint certification streams; it cannot replace a
failed primary gate.

Primary gates are the seed-cluster exact sign test, the rotating-sentinel
zero-event safety gate that is conservative for average heterogeneous risk,
the seed-cluster lower bound on safe retention, and at least twofold
vector/common retention. Per-dataset tests use Holm correction. A separately
frozen sensitivity reports both per-dataset safety and the probability of any
violation among the four dataset decisions within a seed; it cannot replace the
primary sentinel.

## 6. Results (1.2 pages)

Lead with the prospective `Gamma=1.1` result whether it passes or fails. Report
absolute and relative violation reduction, exact safety bound, safe-retention
interval, deployment interval, vector/common ratio, and the count of vector
deployments that the common radius would reject. Follow with per-dataset effects
and limiting-coordinate frequencies.

The sole main table compares deployment rules, not erasers. The main result
figure has three panels: violations by rule and dataset; safe retention versus
evidence budget for vector and common rules; and the upper curves, coordinate
radii, threshold crossings, and limiting dimensions for the deterministically
selected certificate-anatomy example fixed by
`CONTROLLED_SHIFT_REPORTING_SPEC.md`.
The supplement includes the complete four-panel three-rule threshold-stress
curve and deployment-rate strip, including a mandatory negative result if its
supporting condition fails.
Report held-out boosted-tree stress in one clearly non-guaranteed supplement
panel or main-text paragraph.

Then give the prior IID uncertainty-control result and its failed auxiliary
gate. Keep Camelyon17 as the support-boundary case. Controlled exact studies
validate implementation; observed benchmark shifts remain stress tests unless
ambiguity membership is proven.

## 7. Limitations and Conclusion (0.45 page)

The guarantee covers bounded audit variables, registered candidates and
attackers, supported deployment laws, and an independent certification stream.
It is not universal erasure, causal transport, clinical safety, or proof that an
unmodeled real deployment lies in the ambiguity class. Algorithmic seeds do not
make four datasets a random sample of domains. Conclude with the practical
output: a falsifiable supported-shift deployment statement or abstention.

## Supplement

Include one authoritative theory source, exact small-case enumeration, the full
theorem-to-code mapping, all profile and allocation receipts, every candidate
margin, the GaitPDB evidence analysis, all registered ablations, held-out
attacker diagnostics, upstream and data-license records, clean-clone commands,
negative results, the complete threshold-stress grid and reuse hashes, and the
anonymous reproducibility package.
