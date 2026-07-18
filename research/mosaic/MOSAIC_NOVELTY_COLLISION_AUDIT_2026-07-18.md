# MOSAIC novelty-collision audit

Date: 2026-07-18

## Claim under audit

MOSAIC does not claim stochastic mappings, finite-sample fairness certificates,
distributionally robust optimization, contraction coefficients, or
accept-or-abstain testing individually. The narrow claim is the combined
construction:

1. one multinomial confidence event on pre-release fine-token laws;
2. uniform same-table coverage of a continuum of source-blind stochastic
   release channels and task decoders;
3. exact balanced Bayes risk for every downstream released-token attacker;
4. an exact external supremum under a common-transform polytope plus bounded
   source-specific contamination;
5. matching worst-stratum task utility and a globally solved finite-alphabet
   release-or-abstain rule.

## Nearest neighbors checked

| Work | Genuine overlap | Remaining distinction |
|---|---|---|
| [FARE](https://arxiv.org/abs/2210.07213) | Finite restricted representations and a high-confidence certificate for any downstream classifier. | FARE certifies a restricted encoder on its reference distribution. It does not optimize a same-table stochastic post-channel under a common-transform/differential-contamination external class. |
| [Learning Smooth and Fair Representations](https://proceedings.mlr.press/v130/gitiaux21a.html) | Finite-sample fairness guarantees for randomized/smoothed representations. | Uses smoothness and chi-squared mutual information; no exact finite-alphabet Bayes envelope, transform-exact shift supremum, or joint decoder optimization. |
| [Learn Then Test](https://doi.org/10.1214/24-AOAS1998) and [Pareto Testing](https://openreview.net/forum?id=cyg2YXn_BqF) | Registered risk tests, multiplicity control over candidates, and abstention. | Tests a finite candidate family. MOSAIC covers an uncountable channel family through one sufficient-table event, then optimizes inside that event. Separate learned tokenizers still pay multiplicity. |
| [Optimal Fair Learning Robust to Adversarial Distribution Shift](https://proceedings.mlr.press/v267/agarwal25b.html) | Randomization, fairness, and robustness to malicious distribution noise. | Optimizes a fair predictor and studies robustness of its accuracy; it does not certify a public representation against every downstream attacker from a finite table. |
| [Optimized Pre-Processing for Discrimination Prevention](https://proceedings.neurips.cc/paper/2017/hash/9a49a25d845a483fae4be7e341368e36-Abstract.html) | Stochastic preprocessing and privacy-utility tradeoffs. | Population optimization without MOSAIC's adaptive finite-sample or structured external-shift certificate. |
| [Fundamental Limits of Perfect Concept Erasure](https://openreview.net/forum?id=bppVexkY5N) | Information-theoretic privacy-utility limits for concept erasure. | Establishes erasure limits, not the confidence envelope, external shift class, or release-or-abstain optimizer. |
| [On the Contractivity of Privacy Mechanisms](https://arxiv.org/abs/1801.06255) | Dobrushin-style channel contraction. | Supplies a classical ingredient. MOSAIC's exact transform-polytope envelope is tighter than the contraction fallback and is coupled to adaptive finite-sample selection. |

The sweep also included conformal risk control under covariate or likelihood-ratio
shift, privacy funnels, distributionally robust fair representation learning,
concept-erasure methods, and 2025--2026 OpenReview results on representation
drift and robust erasure.

## Verdict

No exact collision was found for the five-part construction above. The strongest
collision risk is a reviewer interpreting MOSAIC as merely Learn-Then-Test over
channels or FARE with a randomized encoder. The paper addresses both directly:
it states what is inherited, identifies the confidence-table object that removes
channel-count multiplicity, and isolates the transform-exact external theorem as
the new technical component.

This audit cannot prove worldwide novelty. The paper must keep its contribution
claim narrow, cite all component literatures, and avoid claiming that
randomization, universal downstream fairness, risk-control abstention, or
Dobrushin contraction are new by themselves.
