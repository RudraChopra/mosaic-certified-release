# VERA Top-Conference Execution Specification

This file preserves the current requested completion standard. A passing
internal script is evidence only for the exact condition it checks. It is never
evidence of novelty, scientific importance, or acceptance probability.

The claim-grade study has a preregistered scientific ledger. In particular:

- Seeds 0-4 became exploratory when they informed protocol design. The original
  balanced matrix uses seeds 5-12, the disjoint IID replication uses seeds
  13--44, and the controlled supported-shift study uses seeds 45--108.
- Configuration-level McNemar tests reuse seeds, threshold families, and
  nested validation samples. The claim-grade test is instead an exact
  seed-blocked sign-flip test with Holm correction; McNemar is descriptive.
- A 20% naive failure rate is required in at least one prespecified supported
  dataset/threshold regime. Confirmatory outcomes cannot be changed to
  manufacture that result.
- Seeds 13--44 are the completed disjoint IID replication. Seeds 45--108 are
  the separately locked controlled supported-shift study and are analyzed only
  at its preregistered profiles, budgets, and seed-cluster endpoints.

`audit_goal_completion.py` reports every scientific, presentation, submission,
and human gate independently.

## Scientific Contribution

VERA is submission-facing shorthand, not a universal-erasure claim. Given
identity and edited representations for the same examples, VERA certifies the incremental
target harm and post-edit sensitive leakage over a declared deployment-shift
class. Its primary class is all distributions with a bounded density ratio
relative to the certification reference law. Annotated worst-group mixtures are a corollary. VERA
returns a support-aware vector envelope, its common-radius summary and limiting
dimensions, or `ABSTAIN` when the declared profile cannot be established.

The finite-candidate testing layer is explicitly attributed to Learn Then Test
and related risk-control work. It is not claimed as novel.

## Gate 1: Theory

- Prove bounded-reweighting certification for paired edit harm.
- Control target harm and every preregistered attacker simultaneously.
- Invert the risk bands into a simultaneous lower confidence bound on each
  edit's maximum common deployment-shift radius.
- Prove that the radius remains valid for a deployment budget chosen after the
  certificate is observed.
- Derive worst-group mixture certification as a corollary.
- Prove support-mismatch impossibility with a two-world or Le Cam argument.
- Derive a sufficient evidence bound, a minimax prospective cell allocation,
  an additive multi-cell extension for balanced leakage, an exact-KL
  independent-cell lower bound, and locally matching shift--margin scaling in
  compact interior regimes.
- Derive false-acceptance control at level `delta`.
- Validate coverage for every tested `(n, m, attackers, shift cap, delta)` cell.
- Hash and commit `prereg.json` before claim-grade certification runs.

## Gate 2: Theory Matched By Data

- Run 2,000 synthetic replicates at six certification sizes, three delta levels,
  and three shift budgets (54 cells).
- Run and independently replay a 216-cell extension over candidate-family and
  validated-environment counts.
- Report Clopper-Pearson intervals for empirical false acceptance.
- Overlay predicted and observed abstention curves.
- Subsample each real dataset at 5%, 10%, 25%, 50%, and 100%.
- Require observed transitions to lie in preregistered predicted bands on at
  least four of five datasets.

## Gate 3: Killer Experiment

- Compare always deploy, best validation point estimate, IID LTT, VERA, and
  oracle.
- Use five datasets, five official erasers, nine contract pairs, eight untouched
  seeds, and five validation sizes.
- Find an honest, prespecified supported regime where naive selection violates
  the locked external contract at least 20% of the time.
- Require VERA false acceptance at or below `delta` in every claim-grade cell.
- Report exact paired McNemar tests with Holm correction and discordant counts.
- Quantify deployment retention relative to the oracle with intervals.
- Separately compare nine matched deployment rules on 64 fresh seeds under
  exact supported laws at `Gamma=1.1`; require the locked paired, safety,
  usefulness, and vector-advantage gates without substituting secondary results.

## Gate 4: Zero-Proxy Baselines

- Pin official upstream commits for INLP, R-LACE, LEACE, MANCE++, and TaCo.
- Run Waterbirds, Camelyon17 WILDS, Bios, CivilComments WILDS, and GaitPDB.
- Use the same frozen representations, splits, probe family, and seeds 5--12
  within each dataset.
- Emit one JSON receipt per run.
- Fail table generation if any cell lacks a receipt or uses proxy code.
- Repeat the zero-proxy receipt requirement for all 1,280 controlled-shift
  dataset--eraser--seed runs.

## Gate 5: Abstract Number

- Verify the sentence reporting naive false acceptance, VERA false acceptance,
  and deployment retention directly from regenerated receipts.
- Require at least a 15 percentage-point false-acceptance reduction in an
  honest regime, or lead with the theory and forced-abstention result instead.

## Gate 6: Presentation

- Figure 1 must teach the method in three panels: paired harm and fresh
  attackers, fixed-profile curves and the vector/common envelope, and
  certification versus abstention at a real support boundary.
- Use vector, colorblind-safe figures readable at 50% zoom.
- Fill the venue's permitted content pages without formatting hacks.
- Include at least 40 verified references spanning erasure, risk control,
  selective prediction, distribution shift, probing, fairness certificates,
  and deployment auditing.
- Purge stale project names from source, figures, artifacts, and PDF metadata.
- Produce anonymous and named source/PDF variants with clean metadata.

## Gate 7: External Adversarial Review

- Obtain four role-specific cold reviews from researchers who publish in
  machine learning, followed by a fifth previously unused post-revision
  reviewer.
- Record every critical and major finding in `review_response_ledger.md`.
- Fix or rebut each finding in the paper itself.
- Require every reviewer to address LTT and Prompt Risk Control overlap; at
  least three must score weak accept or better and at least two accept or
  better, with no fatal correctness finding.

## Submission Machinery

- Register OpenReview and use one identity consistently.
- Verify current official deadlines and style files for each target venue.
- Compile at the exact page limit with no margin or spacing manipulation.
- Anonymize paper, supplement, code archive, links, and PDF metadata.
- Provide a seeded anonymous archive that reproduces the main table in one
  command.
- Complete the venue reproducibility checklist.
- Upload proofs, full tables, and per-dataset details by the supplement deadline.
- Register the abstract before the venue's abstract deadline.
- Use the primary area closest to trustworthy ML, distribution shift, or
  uncertainty quantification.

## Completion Rule

Every gate must have authoritative evidence. Missing human reviews, missing
official baselines, unrun experiment cells, unverified references, or an
uncompiled final PDF keep the project incomplete. No conference acceptance can
be guaranteed; completion means submission-ready evidence meeting this spec.
