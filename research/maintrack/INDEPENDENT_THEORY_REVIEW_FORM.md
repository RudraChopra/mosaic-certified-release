# VERA Independent Theory Review Form

This form is completed by a mathematically qualified human reviewer after the
final anonymous appendix is frozen. An automated proof check, symbolic
calculation, author self-review, or language-model review does not satisfy this
gate.

## Reviewer And Artifact

- Reviewer name:
- Affiliation:
- Relevant statistics/ML publication URL:
- Conflict or prior-involvement disclosure:
- Review date:
- Anonymous main PDF SHA-256:
- Anonymous supplement PDF SHA-256:
- Authoritative appendix source SHA-256:
- Confirmation that the review was independently written:

Reviewer identity and the signed form stay in the private submission registry.
Only completion status and resolved findings enter the public project ledger.

## Reconstruction Checklist

For each item, write a derivation in the reviewer's own notation, identify every
assumption used, and mark correct, fixable, or incorrect.

1. Reweighting--CVaR dual identity, including the Gamma=1 boundary.
2. DKW robust-risk upper curve and its simultaneous continuum validity.
3. Exact Bernoulli and {-1,0,1} robust-risk formulas.
4. Clopper--Pearson substitutions, paired-tail split, and simplex clipping.
5. Balanced leakage and source-prevalence invariance.
6. Candidate-wise fixed-profile intersection--union test and why selection
   among accepted candidates may use certification values.
7. Arbitrary observed-environment mixture corollary.
8. Simultaneous vector-envelope validity after edit and profile inspection.
9. Common-radius lower certificate and right-censoring convention.
10. Sufficient evidence upper bound and all constants.
11. Minimax prospective evidence allocation, including shared-cell maxima.
12. Additive multi-cell power guarantee, one confidence allocation per reused
    distinct curve, floor-budget feasibility, convexity, and the inactive-floor
    and represented-cell assumptions for both analytic special cases.
13. Multi-component Bernoulli lower bound and Bretagnolle--Huber constant.
14. Unsupported-cell indistinguishability theorem for target and leakage cells.
15. Conditional versus unconditional probability statement.
16. Identity-as-comparator versus identity-as-selectable-candidate multiplicity.

## Implementation Match

Independently inspect the final theorem-to-code mapping and one raw receipt.
Confirm or reject:

- theorem variables map to the declared arrays and ranges;
- candidate, environment, attacker, and source multiplicities are correct;
- fixed-profile and simultaneous-envelope error budgets are not conflated;
- missing cells and identity receive the stated treatment;
- exact interval tails and numerical radius tolerances match the source;
- shared source draws across attackers are handled as dependent components; and
- the controlled-study allocation is fixed from the design fold before
  certification outcomes.

## Findings

| ID | Severity | Theorem, equation, or code location | Finding | Required correction | Resolved location | Status |
|---|---|---|---|---|---|---|
| T1 | pending | pending | pending | pending | pending | open |

Every finding must be retained verbatim. Critical and major findings must be
fixed in the source or remain explicitly unresolved; they cannot be closed by a
repository audit alone.

## Final Verdict

- Every listed proof reconstructed: yes / no
- Every assumption visible in the main paper or supplement: yes / no
- Central fixed-profile guarantee correct: yes / no
- Central vector-envelope guarantee correct: yes / no
- Evidence upper/allocation/lower-bound package correct: yes / no
- Unsupported-cell theorem correct and honestly scoped: yes / no
- Implementation mapping consistent with theory: yes / no
- Any fatal correctness issue remains: yes / no
- Reviewer signature or attested email reference:

The theory gate passes only when every reconstruction item is complete, every
central verdict is yes, no fatal issue remains, and all critical or major
findings are resolved in a newly frozen package.
