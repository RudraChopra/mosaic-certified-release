# VERA Main-Track Research Program

## Identity

**VERA: Verified Erasure under Reweighting Ambiguity**

VERA is a general machine-learning method for deciding whether a proposed
representation edit remains acceptable under a declared deployment shift. It is
software-only and domain-general; the evidence spans vision, medical vision,
text, and time series. Camelyon17 is a high-stakes reliability benchmark, not a
clinical-safety claim.

## Core Thesis

Concept erasers construct interventions, but a deployment system still needs to
know how much shift an intervention can survive. VERA evaluates paired target
harm against the identity edit and leakage from fresh, heterogeneous attackers.
For each candidate, it lower-certifies a support-aware vector of groupwise
density-ratio budgets under which every registered contract holds. The output
is a certified shift envelope, its common-radius summary, limiting contracts,
or `ABSTAIN`.

The finite-candidate decision layer is an application of Learn Then Test and
related distribution-free risk control. The novelty claim is deliberately
narrower: the paired multi-contract erasure shift envelope, its simultaneous
lower certificate over a continuum of deployment budgets, its common-radius
geometry, and its support-mismatch boundary.

## Evidence Contract

The locked evidence package has three parts. The exact balanced study contains
54 cells: six validation sizes, three error levels, three shift budgets, and
2,000 replicates per cell. An independent implementation replays every seeded
cell and checks both false acceptance and predicted abstention. A separate
216-cell exact grid varies validation size, candidate-family size,
validated-environment count, and error level, again with 2,000 replicates per
cell; each family includes the identity control action in its multiplicity
count.

The real study is a preregistered 200-run matrix:

- five official-code erasers: INLP, R-LACE, LEACE, TaCo, and MANCE++;
- five datasets: Waterbirds, Camelyon17-WILDS, CivilComments-WILDS, Bios, and
  GaitPDB; and
- eight untouched seeds (5--12) with one shared split, preprocessing,
  target-probe, and attacker protocol per dataset. Pilot seeds 0--4 are
  excluded from confirmation.

Every run must carry the locked preregistration hash, the same runner commit, a
pinned and clean upstream checkout, split hashes, and hashes for its per-example
audit arrays. Missing or proxy rows fail closed.

## Scientific Boundaries

VERA does not certify clinical deployment, universal concept removal, or
security against every measurable attacker. Its shift guarantee is restricted
to deployment distributions absolutely continuous with respect to the
certification distribution and bounded by the declared density ratio. A
deployment environment absent from certification is not covered; the
unsupported-cell theorem shows why no validation-only protocol can repair that
without an additional structural assumption.

Configuration-level tests that reuse the same seeds, samples, thresholds, or
nested fractions are not treated as independent evidence. The analysis retains
the preregistered diagnostics but uses seed-blocked sensitivity analyses for
inferential claims. Corrections are recorded in
[`ANALYSIS_CORRECTION_LEDGER.md`](ANALYSIS_CORRECTION_LEDGER.md).

## Completion Rule

The source of truth is [`VERA_AIRTIGHT_SPEC.md`](VERA_AIRTIGHT_SPEC.md), and the
machine-readable decision is produced by
`research/scripts/audit_goal_completion.py`. Submission readiness requires all
scientific gates, a complete anonymous and named paper package, and two genuine
cold reviews from researchers who publish in machine learning. Internal scripts
cannot substitute for those reviews or guarantee acceptance. OpenAI Codex's
extensive assistance is disclosed in the manuscript; every listed human author
must complete [`HUMAN_AUTHOR_VERIFICATION_GATE.md`](HUMAN_AUTHOR_VERIFICATION_GATE.md)
and personally verify the entire submission.
