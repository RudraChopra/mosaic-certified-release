# VERA Seven-Page Manuscript Outline

## Working Title

**VERA: Support-Aware Shift Envelopes for Representation Erasure**

## Abstract (170-190 words)

- Problem: an eraser can reduce measured leakage while damaging the target task
  or failing under deployment reweighting.
- Prior boundary: finite candidate testing and abstention are Learn Then Test
  style risk control, not the contribution.
- Method: paired target-harm variables, four fresh leakage attackers, bounded
  density-ratio ambiguity, simultaneous upper curves, and inversion into a
  support-aware groupwise shift envelope with a common-radius summary.
- Theory: uniform shift guarantee, arbitrary observed-group mixtures, and
  unsupported-cell impossibility.
- Evidence: exact 54-cell fixed-profile study, exact 216-cell family-size study,
  and the 5-dataset x 5-eraser x 8-seed official matrix.
- One receipted sentence with point-selection violations, VERA violations, and
  retained safe deployments. The sentence remains absent until the final audit
  matches it byte-for-byte to regenerated artifacts.

## 1. Introduction (0.8 page)

Open with the deployment decision, not a catalog of erasers. A representation
edit is an intervention; average IID utility and one native probe do not state
where that intervention remains acceptable. Explain paired harm using the same
example under identity and edited representations. Define the desired output
in one sentence: the largest declared reweighting budget under which target
harm and every registered leakage contract certify.

Address the closest overlap in the introduction. Learn Then Test, risk-control
prediction sets, Conformal Risk Control, and Pareto Testing already provide
finite-family calibration and multiple-risk selection. VERA uses that machinery
and does not claim it. Robust Validation and covariate-shift risk control also
preclude a generic “first shift-aware validation” claim. State the proposed
delta as the erasure-specific paired multi-contract shift radius, its limiting
contract, and its support-identification boundary.

End with three contributions in prose: the object and guarantee, the
unsupported-support theorem, and the official cross-modal deployment study.

## Figure 1: Method in Ten Seconds (0.65 page, two columns)

Panel A shows identity and edited predictions on the same examples, producing
paired harm in `{-1,0,1}`, alongside four post-edit attacker correctness
variables. Panel B shows validation mass reweighted under `0 <= dQ/dP <= Gamma`
and simultaneous target/leakage upper-risk curves. Panel C shows curve inversion:
one candidate has a nonzero certified radius, another reaches `ABSTAIN`, and an
unsupported environment is outside the guarantee. The final panel includes one
real receipt only after the matrix audit passes.

## 2. Related Work (0.75 page)

Concept erasure: INLP, R-LACE, LEACE, kernel erasure, TaCo, KRaM, SPLINCE,
Obliviator, MANCE++, FARE, MMD-B-Fair, and fundamental erasure limits. Distinguish
edit construction from decision certification and avoid any state-of-the-art
eraser claim.

Risk control and selective prediction: distribution-free risk-controlling
prediction sets, Learn Then Test, Conformal Risk Control, Pareto Testing,
selective classification, and recent joint selective certificates. State that
edit-level abstention is a domain application, not a new abstention mechanism.

Distribution shift: conformal prediction under covariate shift, high-probability
weighted risk control, robust validation, fine-grained robust conformal
inference, CVaR concentration, robust evaluation, group DRO, WILDS, and domain
adaptation impossibility. Distinguish one known target weighting from uniform
control over all unknown bounded reweightings.

## 3. Problem and Method (1.15 pages)

Define frozen representation `Z`, target `Y`, sensitive/source concept `S`,
optional observed group `G`, identity edit, registered edit family, and an
independent certification fold. Every candidate edit and attacker is fixed
without certification outcomes. Define paired target harm as edited zero-one
loss minus identity zero-one loss. Define leakage as correctness of each fresh
attacker, conditioned on registered audit strata where applicable.

Define the ambiguity set `Q_Gamma(P)` and robust risk. For each candidate,
require target robust risk at most `tau` and every attacker robust risk at most
`lambda`. Define the population and certified erasure shift radii. Explain the
zero convention, right censoring at `Gamma_max`, limiting contracts, and
`ABSTAIN`.

Give concise algorithm pseudocode. Construction data produce edits and probes;
certification data produce simultaneous exact discrete curves; external data
are never used by the selection rule. Selection among certified edits minimizes
registered validation leakage, then paired harm, then a fixed key.

## 4. Guarantees and Boundary (0.95 page)

State the reweighting-CVaR identity with attribution. State the uniform paired
certificate over all candidates, contracts, and `Gamma >= 1`. Present the exact
Clopper--Pearson specialization for Bernoulli leakage and paired
`{-1,0,1}` harm. State the shift-radius theorem and arbitrary mixture of
within-group shifted distributions.

State unsupported-cell impossibility with the two indistinguishable worlds.
Connect it to Camelyon17 center 2 only after stating the general theorem. Keep
full proofs in the supplement and identify which ingredients are standard.

## 5. Experimental Protocol (0.85 page)

Describe the locked preregistration and the 200 official-code receipts. Methods:
INLP, R-LACE, LEACE, TaCo, MANCE++. Datasets: Waterbirds, Camelyon17-WILDS,
CivilComments-WILDS, Bios, and GaitPDB. State frozen representation sources,
split sizes, caps, target/source/group meanings, and the support mismatch.

Every candidate retrains one target probe and four leakage attackers: linear,
RBF-Nystroem, random forest, and MLP. State all `tau`, `lambda`, `Gamma`, `delta`,
validation fractions, candidate strengths, and multiplicity family. Explain the
five deployment rules: always deploy, point selection, IID LTT, VERA, and
external oracle.

Define two external endpoints separately: measured contract violation and
procedurally uncertifiable deployment. State that configuration-level tests are
dependent diagnostics and seed-blocked inference governs claims.

## 6. Results (1.25 pages)

Lead with the exact synthetic overlay and false-acceptance coverage. Then report
the head-to-head deployment experiment, not raw eraser accuracy. Show violation
and abstention rates by dataset, validation size, and rule. Report the
support-mismatch abstention as an identification result, not an observed outcome
violation.

The main table contains all five official erasers with target harm, worst
registered attacker leakage, certified radius, limiting contract, and external
contract status. Every estimate includes seed dispersion or a justified exact
interval and links to receipt counts in the supplement.

Required ablations: IID versus `Gamma=1.25`; paired versus unpaired target
analysis; each attacker removed from the portfolio; Bonferroni family size;
threshold sensitivity across all nine locked pairs; validation size; and
leave-one-eraser-family-out frontier granularity. No ablation may reuse the
external split for tuning.

## Figure 2: Theory and Data (0.45 page, two columns)

Use the independently replayed exact synthetic figure as the primary theory
check. A smaller real-data panel may show observed curves against the explicitly
labeled full-certification plug-in bootstrap diagnostic. Do not call the latter
independent validation.

## Figure 3: Deployment Rules (0.55 page, two columns)

For each dataset, plot measured contract-violation rate and deployment retention
for always deploy, point selection, IID LTT, and VERA. Use seed points and
cluster-respecting intervals. Mark Camelyon17 unsupported support separately
from measured failures.

## 7. Limitations and Conclusion (0.45 page)

The guarantee assumes bounded outcomes, certification independence, correct
support scope, and a finite registered attacker portfolio. It does not imply
perfect erasure, fairness for unmeasured concepts, clinical safety, or validity
under new support. Density-ratio budgets are user-declared sensitivity
parameters, not estimated facts. Eight-seed evidence still has limited power for
two-sided seed-blocked inference; report exact tests and dependence-aware
diagnostics without treating nested configuration rows as independent replicates.

Conclude with the practical contribution: VERA turns “apply this eraser” into a
falsifiable, support-scoped deployment statement and makes insufficient evidence
an explicit output.

## Supplement

Include full proofs, exact certificate derivations, all 200 receipt rows, every
candidate and threshold result, dataset/store provenance, upstream commit
proofs, attacker details, timing, sensitivity analyses, reference-verification
records, negative results, correction ledger, and the anonymous one-command
reproduction instructions.
