# VERA Component Ablation Specification

These analyses explain mechanism and failure modes. They are secondary or
diagnostic and cannot replace a failed controlled-study primary gate. The seed
is the independent unit whenever fresh real-data rows are used.

## Controlled-Study Ablations

1. **Paired harm versus edited-only error.** Recompute selection after replacing
   identity-subtracted harm with edited target error. Report changed deployment,
   false acceptance, and whether baseline task error is mistaken for edit harm.
2. **Balanced leakage versus ordinary accuracy.** Recompute the source contract
   with empirical source prevalence. Report decisions changed by prevalence and
   construct a deterministic prevalence-shift example from the same class
   recalls.
3. **One attacker versus the portfolio.** Run every registered singleton,
   leave-one-out portfolio, and the full portfolio. Report added deployment,
   registered-contract violations, and held-out boosted-tree failures.
4. **IID versus shifted certification.** Compare IID LTT, robust point
   estimation, fixed-profile certification, and the vector envelope on matched
   candidates and streams.
5. **Scalar versus vector contracts.** Compare the generic pooled normalized
   certificate with VERA and count pooled passes containing a violated required
   coordinate.
6. **Common radius versus anisotropic profile.** Report safe retention,
   violations, vector-only deployments, and limiting coordinates.
7. **Uniform versus prospective allocation.** Use the same total budgets and
   common random streams. Report retention, radius, violation, and per-cell
   evidence changes.
8. **Full frontier versus construction-only screening.** Apply only the locked
   design-fold screen; certification and final outcomes may not choose the
   reduced family.
9. **Five versus 12 candidates.** Keep one lowest-strength candidate per eraser
   for the five-candidate family and compare multiplicity cost, opportunity,
   retention, and violations.
10. **One versus all target environments.** Report false acceptance from
    omitting each environment and the evidence saved.
11. **Evidence budget.** Compare 1,000, 2,000, 4,000, and 8,000 observations,
    including deployment, retention, radius, and limiting-cell curves.
12. **Exact versus generic bounded-loss bounds.** Use identical samples and
    family corrections; report decisions recovered by the exact discrete audit.
13. **Registered versus held-out attacker.** The boosted tree remains stress
    evidence only. Report portfolio-safe edits that fail it and the registered
    attacker most predictive of those failures.

## Separate Diagnostic Ablations

14. **Native eraser probe versus fresh attackers.** Method-native probe outputs
    are not part of the common receipt schema and cannot be reconstructed from
    correctness arrays. Re-run the fixed seeds 45--60 on all four supported
    datasets through each pinned official entry point, retain its native
    objective or probe output, and compare it with freshly retrained linear,
    RBF, forest, and MLP attackers. Label this method-specific stress analysis;
    methods with no native classifier report `NA`, and no cross-method probe
    equivalence is implied.
15. **No multiplicity correction versus valid correction.** Use the locked exact
    finite-law simulation and candidate/group-count grid, where the truth is
    known. Report familywise false acceptance as candidate count grows, then
    confirm the real study uses the valid correction only.
16. **No support check versus support-aware abstention.** Use the registered
    Camelyon17 center-2 case and the two-world construction. The no-check rule is
    a deliberately invalid diagnostic; report unsupported deployments
    separately from measurable external violations.

## Reporting Rule

For every ablation, name one observed consequence: more false acceptance,
lower safe retention, invalid familywise coverage, a smaller radius, held-out
attacker failure, unsupported extrapolation, or source-prevalence sensitivity.
Report null and unfavorable effects. Do not count candidates, attackers,
budgets, or profiles sharing a seed as independent samples.
