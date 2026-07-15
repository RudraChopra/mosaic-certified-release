# VERA Closest-Work Capability Matrix

Search frozen: July 14, 2026.

## Exact Claim Under Review

VERA returns a simultaneous, support-aware vector of deployment reweighting
budgets for a selected representation edit's paired target harm and balanced
leakage against a registered, freshly retrained attacker portfolio. The vector
can be inspected after certification, reduced to a common robust radius, or
converted to abstention when a required support cell is absent. The guarantee
does not require a target-deployment sample and does not claim universal
erasure.

The finite-candidate testing layer is inherited from Learn Then Test. Bounded
density-ratio robustness, exact binomial intervals, CVaR duality, balanced
accuracy, and union bounds are also prior machinery. The claimed contribution
is the intervention-specific certificate assembled from those ingredients and
its use as a deployment decision object.

## Search Protocol

The search covered arXiv, PMLR/OpenReview proceedings, journal versions, and
backward/forward citations for the queries `representation erasure
certification deployment shift`, `robust risk control bounded density ratio`,
`distributional fairness certification`, `concept erasure attacker portfolio`,
and the names of all methods below. Inclusion required a primary paper that
could plausibly provide at least one of the 13 capabilities. A row records what
the cited method reports, not what could be built by combining it with another
paper.

Legend: `Y` = explicit capability; `P` = partial, variant-specific, or a related
but materially different capability; `-` = not reported as an output or
guarantee. `P` is intentionally conservative: it prevents the matrix from
turning differences of application into false novelty claims.

| Method family | Finite selection | Multiple risks | Paired harm | Fresh attacker portfolio | Bounded reweighting | Continuum budgets | Lower bound on safe radius | Support mismatch | Whole-edit abstention | Valid after inspection | Environment mixtures | Source-prior invariance | No target sample |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Learn Then Test | Y | Y | - | - | - | - | - | - | P | Y | - | - | Y |
| Conformal Risk Control | P | P | - | - | P | - | - | - | - | P | - | - | P |
| Pareto Testing | Y | Y | - | - | - | - | - | - | P | Y | - | - | Y |
| Prompt Risk Control | Y | Y | - | - | P | - | - | - | P | Y | - | - | P |
| Weighted risk control | P | P | - | - | P | - | - | P | - | P | - | - | - |
| Distributionally robust validation | - | P | - | - | Y | P | - | - | - | P | - | - | Y |
| Group-conditional risk control | P | Y | - | - | P | - | - | P | - | P | P | - | Y |
| Selective prediction | P | P | - | - | - | - | - | - | - | P | - | - | Y |
| Distributional fairness certification | - | P | - | - | Y | P | - | P | - | P | P | P | Y |
| FARE | - | P | - | P | - | - | - | - | - | - | - | P | Y |
| MMD-based fairness certification | - | P | - | P | P | - | - | - | - | - | - | P | Y |
| Concept erasure and probing | P | P | P | P | - | - | - | - | - | - | - | P | Y |
| Robust representation learning | P | P | - | - | Y | P | - | P | - | - | P | - | Y |
| **VERA** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** | **Y** |

## Three Separating Examples

### IID LTT can accept an edit that VERA rejects

Suppose a leakage indicator is Bernoulli with population recall `p = 0.04` and
the contract is at most `0.05`. Even with the population value known exactly,
the IID contract passes. Under VERA's density-ratio class at `Gamma = 2`, the
worst-case recall is `min(1, Gamma p) = 0.08`, so the declared-shift contract
fails. Sampling uncertainty is not the distinction: IID risk control and
shift-robust risk control ask different population questions.

### Worst-group evaluation is not a shift envelope

Let two observed environments have Bernoulli harm rates `0.04` and `0.03` under
a threshold of `0.05`. IID worst-group harm is `0.04`, so the edit passes. Under
within-environment reweighting, the two robust risks are `min(1, 0.04 Gamma)`
and `min(1, 0.03 Gamma)`. VERA reports environment radii `1.25` and `1.67`, the
common radius `1.25`, and environment 1 as limiting. A scalar worst-group value
does not report this admissible budget vector and cannot answer a post-hoc
question such as whether `(Gamma_1, Gamma_2) = (1.2, 1.5)` is certified.

### A finite attacker portfolio is not universal erasure

Let `U` and `V` be independent fair bits and encode the sensitive label as
`S = U XOR V` in an edited representation `(U, V)`. Every linear attacker has
balanced accuracy `0.5`, while an XOR attacker recovers `S` perfectly. A
certificate over a registered finite portfolio is a simultaneous guarantee for
those attackers only. VERA therefore says "portfolio leakage is controlled,"
not "the representation contains no sensitive information."

## Closest-Work Conclusions

Learn Then Test is the closest source for finite-family error control. Prompt
Risk Control is the closest application template because it couples multiple
risks with a finite candidate family and includes a covariate-shift correction.
Distributionally robust validation and distributional fairness certification
are the closest sources for ambiguity-set guarantees. Concept-erasure papers
are the closest application domain. None of the reviewed papers was found to
return the full VERA object: a post-inspection-valid, support-aware shift-budget
vector and common radius for paired representation-intervention harm plus a
fresh balanced attacker portfolio, without a target-deployment sample.

This is an internal literature conclusion, not an external novelty verdict. The
submission gate still requires cold reviews from risk-control, distribution
shift, representation-erasure, and general-ML researchers, each naming the
closest paper and judging whether the combination is nonobvious.

## Primary Sources

- Angelopoulos et al., *Learn Then Test*, arXiv:2110.01052 and AOAS (2025).
- Angelopoulos et al., *Conformal Risk Control*, ICLR 2024, arXiv:2208.02814.
- Laufer-Goldshtein et al., *Efficiently Controlling Multiple Risks with Pareto Testing*, ICLR 2023, arXiv:2210.10800.
- Zollo et al., *Prompt Risk Control*, ICLR 2024, arXiv:2311.14084.
- Tibshirani et al., *Conformal Prediction Under Covariate Shift*, NeurIPS 2019, arXiv:1904.06019.
- Cauchois et al., *Robust Validation: Confident Predictions Even When Distributions Shift*, JASA 2024, arXiv:2008.04267.
- Kang et al., *Certifying Some Distributional Fairness with Subpopulation Decomposition*, NeurIPS 2022, arXiv:2205.15494.
- Jovanovic et al., *FARE: Provably Fair Representation Learning*, ICLR 2023.
- Deka et al., *MMD-B-Fair: Learning Fair Representations with Statistical Testing*, NeurIPS 2023.
- Ravfogel et al., *Null It Out* (ACL 2020) and *Linear Adversarial Concept Erasure* (ICML 2022).
- Belrose et al., *LEACE: Perfect Linear Concept Erasure in Closed Form*, NeurIPS 2023.
- Jourdan et al., *TaCo: Targeted Concept Removal*, NeurIPS 2023 workshop/arXiv.
