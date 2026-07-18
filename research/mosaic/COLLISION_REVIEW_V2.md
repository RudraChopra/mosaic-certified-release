# MOSAIC v2 Primary-Source Collision Review

**Search date:** July 18, 2026
**Status:** provisional development audit, not a novelty claim

## Candidate claim under review

MOSAIC v2 proposes a source-blind stochastic release channel selected on the
same finite contingency table used for certification. One simultaneous
fine-token multinomial confidence event gives an exact envelope for every
downstream source attacker and every selected channel. A pre-release shift is
decomposed into a shared Markov transformation and bounded differential
contamination; the external bound combines a release-invariance defect with the
channel's exact worst-case Bayes leakage capacity. Fixed-decoder task utility is
covered by the same event, and the resulting piecewise-linear branches are
intended to be solved globally.

The question is not whether each ingredient is known. Most are classical. The
question is whether the exact finite-sample, adaptive, pre-release-shift, and
optimization result already appears as one method or theorem.

## Closest primary sources

| Work | What it already establishes | What remains different in MOSAIC v2 |
|---|---|---|
| [FARE: Provably Fair Representation Learning with Practical Certificates](https://arxiv.org/abs/2210.07213), ICML 2023 | Finite-support encoders permit finite-sample, high-confidence certificates for every downstream classifier. The certificate is derived for a fixed encoder on data held out from encoder training. | MOSAIC's fine-token confidence event is uniform over all stochastic post-channels, so the release channel may be optimized on the same certification table. MOSAIC also targets pre-release shift and exact multiclass source Bayes accuracy. |
| [Learning Smooth and Fair Representations](https://proceedings.mlr.press/v130/gitiaux21a.html), AISTATS 2021 | Characterizes when empirical demographic-parity certificates converge for representation maps through finite chi-squared information and gives finite-sample rates for smooth stochastic encoders. | MOSAIC does not claim that stochastic smoothing makes fairness auditable. Its narrower result is an exact finite-alphabet confidence envelope uniform over a post-channel selected on the same table, coupled to explicit pre-release shift and utility constraints. |
| [Fair Representation Learning with High-Confidence Guarantees](https://arxiv.org/abs/2510.21017), revised arXiv manuscript | Splits candidate-selection and fairness-test data, returns no solution, and explicitly avoids testing a second candidate because of multiple comparisons. Its theoretical test assumes an optimal adversary; experiments approximate that adversary. | MOSAIC computes the finite-alphabet optimal attacker exactly and uses one uniform confidence region to cover arbitrary repeated channel selection without a candidate split or candidate-count penalty. |
| [Optimized Pre-Processing for Discrimination Prevention](https://proceedings.neurips.cc/paper/6988-optimized-pre-processing-for-discrimination-prevention), NeurIPS 2017 | Learns a randomized preprocessing map through convex optimization and gives finite-sample degradation bounds for discrimination and utility. | The transformation is group-aware and controls specified output-discrimination constraints; it is not a same-table exact certificate for every downstream attacker, and it has no MOSAIC-style pre-release shared/differential shift decomposition. Randomized convex preprocessing is therefore not a MOSAIC novelty. |
| [On the Power of Randomization in Fair Classification and Representation](https://arxiv.org/abs/2406.03142), arXiv 2024 manuscript | Characterizes optimal randomized fair classifiers and constructs group-aware randomized fair representations with optimal task accuracy under population fairness constraints. | No finite-sample confidence certificate, adaptive post-selection result, or external-shift transfer. The value of stochastic rather than deterministic representations is prior art. |
| [Efficient Fairness-Performance Pareto Front Computation](https://arxiv.org/abs/2409.17643), arXiv 2024/2025 revision | Optimizes population total-variation fairness and task performance over stochastic representations and develops structural/factorization results. | It estimates population inputs and does not certify a data-selected channel with simultaneous finite-sample coverage or provide the proposed shift decomposition. Global fairness-utility optimization and TV-based universal downstream control are prior art. |
| [On the Benefits of Representation Regularization in Invariance-Based Domain Generalization](https://arxiv.org/abs/2105.14529), Machine Learning 2022 | Uses the Dobrushin coefficient of a stochastic representation to contract raw-space total-variation shift and bound unseen-environment task risk; explains the utility cost of a constant channel. | MOSAIC cannot claim Dobrushin-based shift robustness as new. Its narrower target is exact source leakage after a source-blind finite channel, same-table finite-sample selection, a shared/differential pre-release decomposition, and simultaneous privacy/utility certification. |
| [Impossibility Results for Fair Representations](https://arxiv.org/abs/2107.03483) | Shows that no nonconstant representation guarantees demographic-parity fairness under arbitrary marginal shifts and gives broader task/fairness impossibilities. | MOSAIC's no-free-lunch theorem must be presented as a quantitative channel-capacity refinement under its finite stochastic model, not as the first arbitrary-shift impossibility. |
| [Optimal Fair Learning Robust to Adversarial Distribution Shift](https://proceedings.mlr.press/v267/agarwal25b.html), ICML 2025 | Proves robustness properties of randomized fair Bayes-optimal classifiers under malicious distribution noise. | Classifier-level fairness and accuracy are the objects, not a public representation protected against every downstream source attacker; there is no same-table multinomial channel certificate. Randomization under adversarial fairness shift is prior art. |
| [On the Contractivity of Privacy Mechanisms](https://arxiv.org/abs/1801.06255) | Relates the Dobrushin coefficient of a privacy mechanism to maximal leakage and local differential privacy. | The identity between binary worst-case distinguishability and channel Dobrushin contraction is classical and must be cited, not claimed. |
| [From the Information Bottleneck to the Privacy Funnel](https://arxiv.org/abs/1402.1774) | Optimizes probabilistic privacy mappings under utility constraints. | Probabilistic privacy-utility channel design is prior art; MOSAIC's potential delta is its exact universal source metric, finite-sample adaptive coverage, and structured shift theorem. |
| [Learn Then Test](https://arxiv.org/abs/2110.01052) and conformal/risk-control follow-ups | Certify data-selected decisions from finite candidate families and abstain when none pass. | MOSAIC must cite this decision layer. Its confidence-region theorem covers a continuum of stochastic channels through a sufficient statistic rather than testing a finite candidate list. |

Classical Blackwell comparison of experiments, Bayes vulnerability, total
variation, Huber contamination, strong data processing, multinomial confidence
sets, and robust linear optimization are also foundational prior art.

## Search protocol and negative-result scope

Primary-source searches covered arXiv, PMLR, official NeurIPS proceedings,
OpenReview manuscripts, and forward/related works visible from FARE, FRG,
smooth fair representations, randomized fair representations, robust fair
classification, Dobrushin channel regularization, privacy funnels, and
fair-representation impossibility papers.
Representative exact searches included:

- `"finite-sample" "stochastic channel" "fair representation"`
- `"post-selection" "fair representation" certificate`
- `Dobrushin distribution shift fairness representation`
- `robust fair representation Markov kernel contamination shift theorem`
- `stochastic channel design Dobrushin utility linear program privacy mechanism`
- `common Markov channel contamination distribution shift fairness`

No reviewed primary source was found that states the combined MOSAIC v2 result.
This is a negative search result, not proof of novelty. Terminology varies across
fairness, privacy, domain generalization, statistical experiments, and robust
statistics, so the search must continue through citations and an external expert
review.

## Provisional verdict

**No exact collision found, but the novelty surface is narrow.** The following
claims are prohibited because they are already known:

1. stochastic mappings can improve fairness-utility tradeoffs;
2. finite representations permit universal downstream fairness certificates;
3. Dobrushin coefficients quantify representation smoothness and shift
   contraction;
4. arbitrary marginal shift makes nontrivial universal fair representation
   impossible; and
5. confidence-based accept-or-abstain decision rules solve multiple-testing
   problems for registered families.

The defensible technical target is the exact combination of:

1. one simultaneous finite-token confidence event covering every source-blind
   stochastic post-channel selected on that same table;
2. an exact multiclass Bayes leakage envelope and exact arbitrary differential
   shift capacity;
3. transfer through a pre-release shared Markov shift plus bounded differential
   contamination, with utility certified on the same event; and
4. a globally solved finite piecewise-linear program whose output inherits the
   certificate without a candidate-count penalty.

That target should enter a paper only after the LP equivalence, large-scale
coverage audit, usefulness experiment, and independent collision review pass.
