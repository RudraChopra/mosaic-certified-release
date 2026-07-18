# MOSAIC: Certifiable Stochastic Representation Release under Structured Deployment Shift

MOSAIC (Minimax-Optimized Source-Agnostic Invariant Channels) is a
software-only method for deciding whether an edited representation is safe to
release. It jointly selects a stochastic finite-token channel and a task
decoder, certifies them against the strongest downstream source attacker, and
returns `ABSTAIN` when privacy or worst-stratum utility cannot be certified
under a registered deployment-shift model.

This branch contains the AAAI 2027 research candidate, its theorem and proof
record, hash-locked protocols, official-method real-feature confirmation,
independent replay programs, receipts, figures, and named/anonymous manuscript
sources. It does not claim that conference acceptance or real-world safety is
guaranteed.

## What Is New

- One multinomial confidence event over fine-token laws covers every stochastic
  release channel selected from the same table, including a continuum of
  channels, without a channel-count correction.
- An exact structured-shift certificate handles a common pre-release transform
  plus bounded source-specific contamination and matches it with a task-utility
  certificate.
- A finite-alphabet optimizer globally selects the channel and decoder by linear
  optimization and abstains on unsupported, infeasible, or numerically
  inconsistent cases.
- No-free-lunch and missing-source theorems state when nontrivial certification
  is impossible.

The paper does **not** claim that stochastic mappings, Learn Then Test,
contraction coefficients, concept erasure, or abstention are individually new.
The narrow contribution is their adaptive, universal-attacker, shift-aware
combination and the transform-exact certificate.

## Headline Evidence

- Naive continuum selection falsely accepts 42.1% of 1,000 locked hard-boundary
  tables; MOSAIC records zero false acceptances.
- On 1,000 paired low-data tables, the transform-exact certificate safely
  deploys on 53.0%, versus 0.3% for the capacity-transfer fallback. At the next
  sample size, the rates are 99.9% and 57.8%.
- The transform-exact audit independently replays 10,000 decisions, 20,000
  privacy certificates, 40,000 utility certificates, and 20,000 external risks
  with zero mismatch.
- The locked real-feature study evaluates 325 official-method rows across
  Waterbirds, Camelyon17-WILDS, CivilComments-WILDS, BiasBios, and GaitPDB.
  Every externally estimable selected release passes its natural-split
  diagnostic; unsupported and utility-limited cases are reported as abstentions
  or unestimable, not safe.
- A post-outcome exploratory exact replay is pointwise no worse on all 325 real
  rows and strictly improves 133. It converts two Waterbirds jobs from abstain
  to deployment; all seven estimable exact selections pass the natural
  diagnostic. An independent 325-optimization replay has zero mismatch.
- The repository-wide test run passes 154 tests plus 14 subtests.

These empirical statements are scoped to their locked studies. Favorable
benchmark behavior does not prove that a deployment population belongs to the
paper's structured shift class.

## Start Here

- Main paper: `research/maintrack/mosaic_aaai2027/mosaic_aaai2027_named.pdf`
- Anonymous paper: `research/maintrack/mosaic_aaai2027/mosaic_aaai2027_anonymous.pdf`
- Supplement: `research/maintrack/mosaic_aaai2027/mosaic_aaai2027_supplement_named.pdf`
- Reproducibility checklist: `research/maintrack/mosaic_aaai2027/mosaic_aaai2027_reproducibility_checklist.pdf`
- Anonymous code/data ZIP: `research/maintrack/mosaic_aaai2027/mosaic_aaai2027_code_data_anonymous.zip`
- Claim ledger: `research/mosaic/MOSAIC_CLAIM_LEDGER.md`
- Current theorem record: `research/mosaic/PRE_RELEASE_SHIFT_THEOREMS.md`
- Novelty collision audit: `research/mosaic/MOSAIC_NOVELTY_COLLISION_AUDIT_2026-07-18.md`
- Numerical audit erratum: `research/mosaic/TRANSFORM_EXACT_AUDIT_ERRATUM.md`
- Exploratory real exact analysis: `research/artifacts/mosaic_real_transform_exact_exploratory_v1.json`
- Exploratory real exact audit: `research/artifacts/mosaic_real_transform_exact_exploratory_audit_v1.json`

## Verification

Install the lightweight confirmation environment and run the complete tests:

```bash
python -m pip install -r research/mosaic/requirements-confirmation.txt
PYTHONPATH=research/mosaic:research/scripts python -m pytest research/tests -q
```

The anonymous code/data ZIP contains exact Git snapshots for the locked
synthetic and transform-exact studies, because later theorem and audit
improvements intentionally changed files covered by the original hashes. Build
and extract it, then follow its `README.md` to replay both studies without
weakening their immutable checks:

```bash
python research/maintrack/mosaic_aaai2027/build_anonymous_code_package.py
```

Verify the official-method result package after installing the separate real
environment and mounting the pinned feature/method stores recorded by the
preregistration:

```bash
python -m pip install -r research/mosaic/requirements-real.txt
python research/mosaic/run_mosaic_real_confirmation.py --verify-only
python research/mosaic/audit_mosaic_real_frontier.py \
  research/artifacts/mosaic_real_confirmation_v1/*.json \
  --output /tmp/mosaic_real_confirmation_audit.json
python research/mosaic/audit_mosaic_real_transform_exact.py \
  --output /tmp/mosaic_real_transform_exact_audit.json
```

Build the papers with the official template copy included in the repository:

```bash
cd research/maintrack/mosaic_aaai2027
latexmk -pdf mosaic_aaai2027_anonymous.tex
latexmk -pdf mosaic_aaai2027_named.tex
latexmk -pdf mosaic_aaai2027_supplement_anonymous.tex
latexmk -pdf mosaic_aaai2027_supplement_named.tex
latexmk -pdf mosaic_aaai2027_reproducibility_checklist.tex
python build_anonymous_code_package.py
```

Raw third-party datasets, frozen embedding stores, virtual environments, and
external-drive-only generated arrays are excluded from GitHub. Their provenance,
versions, hashes, and compact replay receipts are retained in the locked
manifests. The checked-in synthetic receipts contain no private or human-subject
data.

## Historical Record

This repository began as VERA, a finite-candidate risk-control approach. Its
negative P0 result and immutable preregistrations remain in the history because
they explain why MOSAIC was developed instead of hiding a failed direction.
Files that explicitly identify VERA as historical evidence are not current
MOSAIC claims.

OpenAI Codex assisted extensively with ideation, literature discovery, theorem
and proof drafting, implementation, experiment orchestration, statistical
analysis, figures, and manuscript drafting. It is not an author or an
independent scientific reviewer. Any submission requires human verification of
the complete work and compliance with the venue's current disclosure policy.
