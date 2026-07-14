# VERA Novelty Audit, 2026-07-13

## Scope

This audit asks whether a finite candidate set, simultaneous confidence bounds,
thresholded acceptance, and abstention are novel enough for an AAAI or ICLR
main-track paper on representation erasure. The search covered concept erasure,
distribution-free risk control, covariate-shift risk control, robust model
evaluation, fair-representation certificates, and impossibility under shift.
The search was performed on July 13, 2026. It prioritized primary conference
papers and arXiv records. Search phrases included `Learn Then Test covariate
shift`, `worst-group risk mixture shift`, `certified representation fairness`,
`concept erasure multiple adversaries`, and `distributionally robust model
evaluation f-divergence`.

## Decision

The original VERA mechanism is not a sufficient top-conference novelty claim.
Learn Then Test already calibrates a finite family by testing risk constraints,
and Conformal Risk Control already treats monotone risks and discusses
distribution shift. Weighted and high-probability extensions cover covariate
shift. A group-wise Hoeffding bound followed by a union bound is useful, but is
not a defensible headline theorem by itself.

The project therefore changes its primary object. VERA now means **Verified
Erasure under Reweighting Ambiguity**. It studies the incremental, paired harm
of editing a representation instead of the absolute performance of an edited
model. It seeks a certificate that holds simultaneously for every deployment
distribution whose density ratio relative to validation is bounded, without
requiring one known target weighting function. The generic curve applies to
any registered audit cell; the locked study uses observed environment cells
for target harm and source-class cells for balanced leakage. Arbitrary mixtures
of the observed target environments are covered. Leakage
is audited against a heterogeneous, preregistered attacker portfolio because
protection against one nonlinear probe is known not to transfer reliably to
another.

This is a candidate contribution, not a claim that novelty has been proved by
search. The final novelty claim remains conditional on a broader citation sweep
and external expert review.

## Closest Prior Work And Consequences

1. Angelopoulos et al., *Learn Then Test: Calibrating Predictive Algorithms to
   Achieve Risk Control*, arXiv:2110.01052 and Annals of Applied Statistics
   (2025). This invalidates any claim that finite-family testing, acceptance,
   and abstention are themselves new.
   https://arxiv.org/abs/2110.01052

2. Bates et al., *Distribution-Free, Risk-Controlling Prediction Sets*, JACM
   68(6), 2021. This is foundational risk-control work and must be cited.
   https://doi.org/10.1145/3478535

3. Angelopoulos et al., *Conformal Risk Control*, ICLR 2024. The paper controls
   general monotone losses and includes a distribution-shift extension, so a
   generic shift-aware risk-control claim is not new.
   https://openreview.net/forum?id=33XGfHLtZg

4. Tibshirani et al., *Conformal Prediction Under Covariate Shift*, NeurIPS
   2019. Known or accurately estimated likelihood ratios can restore weighted
   validity under covariate shift.
   https://arxiv.org/abs/1904.06019

5. Almeida et al., *High Probability Risk Control Under Covariate Shift*,
   COPA/PMLR 2025. This directly extends LTT with importance-weighted
   calibration losses.
   https://proceedings.mlr.press/v266/almeida25a.html

6. Ai and Ren, *Not All Distributional Shifts Are Equal: Fine-Grained Robust
   Conformal Inference*, ICML 2024. This combines identifiable reweighting with
   worst-case conditional shift in an f-divergence ball.
   https://proceedings.mlr.press/v235/ai24a.html

7. Najafi et al., *Certifiably Robust Model Evaluation in Federated Learning
   under Meta-Distributional Shifts*, ICML 2025. This gives worst-case uniform
   evaluation guarantees under Wasserstein and f-divergence shifts.
   https://proceedings.mlr.press/v267/najafi25a.html

8. Klivans et al., *Testable Learning with Distribution Shift*, COLT 2024.
   Certify-or-reject learning under test-distribution access is already a
   developed theoretical model.
   https://proceedings.mlr.press/v247/klivans24a.html

9. Ben-David et al., *Impossibility Theorems for Domain Adaptation*, AISTATS
   2010. Any new impossibility statement must be positioned as a
   representation-intervention result, not as the first impossibility under
   distribution shift.
   https://proceedings.mlr.press/v9/david10a.html

10. Jovanovic et al., *FARE: Provably Fair Representation Learning with
    Practical Certificates*, ICML 2023. FARE already gives finite-sample upper
    certificates on downstream unfairness for restricted encoders, so VERA
    must not claim the first certified fair or erased representation.
    https://proceedings.mlr.press/v202/jovanovic23a.html

11. Deka and Sutherland, *MMD-B-Fair: Learning Fair Representations with
    Statistical Testing*, AISTATS 2023. Kernel testing for hiding protected
    information while retaining target utility is established.
    https://proceedings.mlr.press/v206/deka23a.html

12. Ravfogel et al., *Kernelized Concept Erasure*, EMNLP 2022. This work finds
    that erasure against one kernel or one nonlinear adversary often fails to
    transfer to another, and that even convex kernel combinations did not solve
    the problem. This motivates, but also constrains, VERA's attacker audit.
    https://arxiv.org/abs/2201.12191

13. Chowdhury et al., *Fundamental Limits of Perfect Concept Erasure*, AISTATS
    2025. Information-theoretic limits on erasure and utility are already
    established and must anchor VERA's limitations.
    https://proceedings.mlr.press/v258/chowdhury25a.html

14. Ravfogel et al., *Null It Out*, ACL 2020; Ravfogel et al., *Linear
    Adversarial Concept Erasure*, ICML 2022; Belrose et al., *LEACE*, 2023;
    Jourdan et al., *TaCo*, 2023; Holstege et al., *SPLINCE*, NeurIPS 2025; and
    Avitan et al., *MANCE*, 2026 define the eraser frontier against which VERA
    must be evaluated.

## Remaining Novelty Risk

Bounded-density-ratio robust risk is a standard distributionally robust
optimization object, and paired treatment-effect analyses are also standard.
The defensible claim must therefore be the complete representation-editing
problem and its evidence: paired edit-versus-identity contracts, simultaneous
target-harm and heterogeneous-attacker leakage certificates, a useful
finite-sample abstention rule, and an impossibility boundary for unsupported
deployment mass. The paper must present this as an extension and synthesis of
risk control for representation intervention, not as invention of risk control
or distributional robustness.

## Second-Pass Red Team: DKW/CVaR Is Not The Headline

A targeted second search found that finite-sample CVaR concentration through
DKW is itself established. Thomas and Learned-Miller derive concentration
bounds for CVaR, and Budde et al. explicitly use DKW confidence bands for CVaR
in statistical model checking. Najafi et al. provide robust DKW-style model
evaluation under meta-distributional shifts. These results rule out presenting
the robust-risk upper bound as a new theorem.

15. Thomas and Learned-Miller, *Concentration Inequalities for Conditional
    Value at Risk*, ICML 2019.
    https://proceedings.mlr.press/v97/thomas19a.html

16. Budde et al., *Statistical Model Checking Beyond Means: Quantiles, CVaR,
    and the DKW Inequality*, 2025.
    https://arxiv.org/abs/2509.11859

17. Jeong and Namkoong, *Robust Causal Inference under Covariate Shift via
    Worst-Case Subpopulation Treatment Effects*, COLT 2020. This is especially
    close to the paired-harm robust-risk interpretation and must be discussed.
    https://proceedings.mlr.press/v125/jeong20a.html

The revised candidate novelty is the **support-aware erasure shift envelope**:
a simultaneous vector of groupwise bounded-reweighting budgets under which one
edit satisfies paired target-harm and all registered leakage contracts. The
original common erasure shift radius is the minimum coordinate over a declared
deployment support. The unsupported-cell theorem explains why an unobserved
required environment or environment--source cell receives radius zero without
additional structure. This remains a candidate domain-specific contribution,
not proof of novelty; the cold external reviews are still mandatory.

## Third-Pass Update: Robust Validation and 2026 Risk-Control Work

A July 13, 2026 search specifically targeted `risk control ambiguity set`,
`bounded likelihood ratio risk control`, `certified distribution shift radius`,
and `concept erasure certification distribution shift`. It adds the following
closest work and further narrows the claim.

18. Cauchois et al., *Robust Validation: Confident Predictions Even When
    Distributions Shift*, JASA 2024. This gives finite-sample conformal coverage
    uniformly over an $f$-divergence ball. It invalidates any broad claim that
    VERA is the first validation procedure robust to an ambiguity set. Its
    object is prediction-set coverage, not paired representation-edit harm,
    attacker leakage, or an erasure shift radius.
    https://arxiv.org/abs/2008.04267

19. Timans et al., *On Continuous Monitoring of Risk Violations under Unknown
    Shift*, UAI 2025. This monitors bounded deployment risks under arbitrary
    evolving shifts using testing by betting. It is a post-deployment detector,
    whereas VERA is a pre-deployment, support-scoped certificate.
    https://proceedings.mlr.press/v286/timans25a.html

20. Akbari, Afshari, and Boddeti, *Obliviator Reveals the Cost of Nonlinear
    Guardedness in Concept Erasure*, NeurIPS 2025. This strengthens the need for
    nonlinear attacker audits and prevents VERA from equating linear leakage
    control with complete erasure.
    https://proceedings.neurips.cc/paper_files/paper/2025/hash/d55f39791f04745b2e0c8abebf3dd5d7-Abstract-Conference.html

21. Bai and Jin, *Conformal Selective Prediction with General Risk Control*,
    arXiv:2603.24704, 2026. This combines selective prediction, e-values, and
    general bounded risks, with an extension to distribution shift. VERA must
    distinguish whole-edit abstention and its bounded-reweighting intervention
    contracts from example-level selective prediction.
    https://arxiv.org/abs/2603.24704

## Fourth-Pass Update: Joint and Group-Conditional Certificates

A July 14, 2026 search added three recent preprints that materially narrow the
claim and must appear in the submission-facing discussion.

22. Yu and Liu, *A Joint Finite-Sample Certificate for Adaptive Selective
    Conformal Risk Control*, arXiv:2606.08517, 2026. This jointly certifies
    selected risk, acceptance, and utility under adaptive threshold choice. It
    further rules out claiming that coupling several finite-sample bounds is
    new. Its decision is example-level selective prediction; it does not report
    a support-aware distribution-shift envelope for a representation
    intervention or retrained-attacker family.
    https://arxiv.org/abs/2606.08517

23. Huang et al., *Conditional Performance Guarantee for Large Reasoning
    Models*, arXiv:2601.22790, 2026. This establishes group-conditional PAC risk
    control for routing between reasoning models. It prevents VERA from
    claiming generic group-conditional certification. VERA's remaining delta is
    the simultaneous groupwise reweighting envelope for paired erasure harm and
    leakage, its common-radius geometry, and its unsupported-cell boundary.
    https://arxiv.org/abs/2601.22790

24. Kotte, *When Can Conformal Risk Control Certify LLM Outputs? Bounds,
    Impossibility, and Adaptation for Structured Generation*,
    arXiv:2606.29054, 2026. Its feasibility and impossibility results are in a
    different structured-generation setting, but they reinforce that an
    abstention/impossibility story is not novel without an
    intervention-specific identification boundary.
    https://arxiv.org/abs/2606.29054

These additions do not establish priority. They establish the exact statement
that must survive external review: **VERA is an erasure-specific robust
selection layer whose proposed object is a simultaneous support-aware envelope
of groupwise bounded-reweighting budgets under which paired edit harm and every
registered retrained-attacker leakage contract hold.** The common radius is the
minimum coordinate over declared support. CVaR duality, concentration tools,
finite-family testing, group-conditional risk control, abstention, and generic
support impossibility are all prior machinery and must be credited as such. No
search establishes absence of all prior overlap; two external cold reviews
remain a hard gate.

## Fifth-Pass Update: Fairness Certificates and Shifted Interventions

A July 14, 2026 search targeted `representation erasure distribution shift
certification`, `fairness audit shift certificate`, `concept intervention OOD`,
and the exact phrase `support-aware concept erasure`. It found no paper with the
complete VERA object, but it found four neighbors that materially raise the
novelty bar.

25. Kang et al., *Certifying Some Distributional Fairness with Subpopulation
    Decomposition*, NeurIPS 2022. This certifies model performance over shifted
    fairness-constrained distributions. VERA cannot claim to introduce
    distribution-shift fairness certification.
    https://proceedings.neurips.cc/paper_files/paper/2022/hash/c8e9a2beb84ab1a616edb89581c4b32a-Abstract-Conference.html

26. Ehyaei, Farnadi, and Samadi, *From Fragile to Certified: Wasserstein Audits
    of Group Fairness Under Distribution Shift*, arXiv:2509.26241. Its public
    ICLR 2026 reviews are a direct warning: applying established DRO machinery to
    a fairness functional was judged application-relevant but theoretically
    incremental. VERA must demonstrate an intervention-specific scientific
    object and decision consequence, not rely on CVaR/DRO algebra as novelty.
    https://arxiv.org/abs/2509.26241

27. Espinosa Zarlenga et al., *Avoiding Leakage Poisoning: Concept
    Interventions Under Distribution Shifts*, ICML 2025. This studies a
    different intervention in concept bottleneck models, but directly shows that
    leaked information can become harmful OOD. It strengthens the motivation
    while ruling out a first-study-of-shifted-concept-interventions claim.
    https://proceedings.mlr.press/v267/espinosa-zarlenga25a.html

28. Yang et al., *Concept Concentration for Faithful Representation
    Intervention*, ICML 2026. This gives a different nonlinear infeasibility
    result and an OOD-robust intervention method for LLM safety. VERA's
    unsupported-cell impossibility is an identification boundary for validation
    support, not a first impossibility theorem for representation intervention.
    https://openreview.net/forum?id=g6fTNu8z0f

The remaining proposed delta is therefore intentionally narrow: the selected
edit is evaluated by paired incremental target harm and a retrained heterogeneous
attacker portfolio; each contract receives a simultaneous groupwise
bounded-reweighting curve; the vector of admissible budgets is reported with an
explicit zero boundary for unsupported required cells; and the empirical study
tests whether that object prevents contract-violating deployments. This is still
a candidate synthesis contribution until cold expert review.
