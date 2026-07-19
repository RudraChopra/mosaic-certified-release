# Cold AAAI Main-Track Review: MOSAIC

Review date: 2026-07-18

## Recommendation

**Weak accept / accept-leaning (approximately 6 on a 10-point scale).** The
submission now clears the bar for a serious AAAI main-track paper. I would not
assign strong accept because its real-domain diagnostic evidence remains small
and the deployment guarantee is necessarily conditional on a structured shift
model whose membership is not established by the benchmarks.

## Summary

MOSAIC certifies a stochastic finite-token representation release against an
unrestricted downstream source attacker while controlling worst-stratum task
error under a common-transform plus differential-contamination shift class. A
single confidence region on the pre-release token table covers an adaptively
optimized continuum of channels. The method jointly selects a channel and
decoder by global finite-alphabet optimization and abstains when the registered
contract cannot be certified.

## Strengths

1. The paper directly addresses the earlier Learn Then Test overlap. It does
   not claim risk control, randomization, or abstention as new; the technical
   delta is the same-table continuum event, universal attacker, exact structured
   shift envelope, matching utility certificate, and joint optimizer.
2. The main theorem certifies the stated external shift class rather than
   assuming that validation and external metrics are close. The no-free-lunch
   and missing-source results identify meaningful boundaries of the guarantee.
3. The killer synthetic comparison is convincing: naive adaptive selection has
   42.1% false acceptance in the registered hard cell, while MOSAIC has none.
   Transform-exact improves safe deployment from 0.3% to 53.0% at the hardest
   retained sample size.
4. The fresh real-feature study is pre-outcome locked, uses untouched seeds and
   five official erasure families with no proxies, and reports all 325 paired
   rows. Exact is pointwise no worse and strictly improves 135 rows, including
   one additional safe Waterbirds selection.
5. Reproducibility is unusually strong. Independent programs replay 64,000
   broad-comparison receipts, 10,000 exact-refinement receipts, and 650 fresh
   real-feature optima with zero mismatch. The anonymous archive passes a clean
   extraction, checksum verification, focused tests, and every replay.

## Weaknesses

1. The shift guarantee is conditional. Natural benchmark diagnostics cannot
   establish membership in the registered common-transform and contamination
   class, so claims of real-world safety would be unjustified. The manuscript
   states this limitation correctly.
2. Only six fresh selected releases are externally estimable. Zero observed
   false acceptances therefore has a two-sided 95% Clopper-Pearson upper bound
   of 45.9%. The paired objective result is much stronger than the frequency
   evidence.
3. The finite-token construction fixes the tokenizer independently of the
   certification fold, and decoder enumeration scales exponentially with the
   released alphabet. Larger interfaces require column generation or another
   structured solver.
4. The mathematical and novelty audits are internal. A cold external expert
   could still identify a proof gap or a closer unpublished/very recent method.
5. The paper is dense. Reviewers who miss the distinction between a channel
   grid and a separately learned tokenizer may underrate the novelty despite
   the explicit related-work discussion.

## Verification Performed

- All ten fresh real-feature gates pass under preregistration digest
  `d88d42e813d65c7d725e923c94be0518d7049e0b62131be96ffbec748d5e5775`.
- The fresh manifest and audit digests are respectively
  `c12f18c9b52bb68522691386131faad966c1ae60d9cb0c540af8b909dd1eecc8`
  and `becebaa2839c776fcd806d3d8222a1e28c213259300a7781a124bf3feb8fd600`.
- The repository suite passes 158 tests plus 14 subtests.
- Named and anonymous main PDFs have seven content pages plus two reference
  pages; both supplements have six pages. There are no overfull boxes,
  unresolved references, missing citations, unembedded fonts, or visible
  layout defects.
- The final anonymous archive passes its own identity and integrity scans and
  all clean-extraction replays.

## Final Judgment

This is no longer the short, finite-candidate VERA paper criticized in the
earlier reviews. It has a materially different theorem, method, optimizer, and
evaluation. I would vote weak accept because the technical construction and
audit evidence outweigh the limited real-domain frequency evidence. A strong
accept rating would require independent expert validation and broader
confirmatory real-domain evidence, not another round of wording changes.
