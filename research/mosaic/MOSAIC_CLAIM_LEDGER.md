# MOSAIC Claim Ledger

**Rule:** A manuscript claim is allowed only when the listed receipt exists,
passes its independent replay where specified, and supports the claim at the
same scope. A green keyword or file-existence check is never sufficient.

| ID | Candidate claim | Required evidence | Current status |
|---|---|---|---|
| T1 | One simultaneous fine-table event covers every same-table-selected stochastic channel against the exact finite-alphabet Bayes attacker. | Algebraic proof in `PRE_RELEASE_SHIFT_THEOREMS.md`; exact-support and adaptive-selection verifier with no failure on the confidence event. | Proof written; 60,000 adaptive candidate checks and 5,000 coverage repetitions passed. Human proof review remains required. |
| T2 | The structured external-shift bound holds for common pre-release Markov drift plus bounded differential contamination. | Theorem 4 proof; exact population external-risk enumeration; randomized deterministic identity checks. | Proof written; exact-risk and invariant verifiers passed with worst numerical gap at machine precision. Human proof review remains required. |
| T3 | Unrestricted differential shift forces a constant-row chance-capacity release, with a binary privacy--utility lower bound. | Theorem 6 proof and deterministic witness tests. | Proof and tests written; external mathematical review remains required. |
| O1 | The finite decoder/branch MILP returns a globally optimal certified channel for the enumerated finite problem. | Zero MIP gap and dual-bound receipt; independent post-hoc certificate replay; exhaustive channel-grid comparisons. | Passed 30 randomized MILP-versus-grid comparisons; worst objective mismatch below `1.9e-15`. Scope is limited to fully enumerated finite alphabets and transforms. |
| O2 | A stochastic release can strictly outperform every deterministic release under the same certificate. | Exhaustive deterministic enumeration and globally solved stochastic witness. | Passed: certified worst error `0.371588` versus deterministic optimum `1.0`. This is a constructed theorem witness, not a broad empirical superiority claim. |
| S1 | MOSAIC controls false acceptance at the registered familywise level on every locked synthetic cell. | Hash-locked 8,000-table confirmation; exact external-risk labels; independent row and aggregate replay. | **Passed within the registered synthetic study.** Zero false acceptances in all eight MOSAIC cells; independent replay checked 64,000 receipts, 128,000 exact risks, and 128,000 decisions with zero mismatch. This does not establish shift-class membership on a real domain. |
| S2 | Naive plug-in selection violates the external contract materially in the registered hard cell while MOSAIC does not. | Locked primary-cell rates and exact Clopper--Pearson intervals. | **Passed.** Plug-in false acceptance is 42.1% (421/1,000; 95% CI 39.0--45.2%) versus 0% for MOSAIC (upper endpoint 0.368%); paired exact McNemar `p=3.69e-127`. |
| S3 | MOSAIC retains at least 30% safe deployments and improves by at least 10 percentage points over held-out fixed-channel and finite LTT at the registered retention cell. | Locked primary-cell rates, exact intervals, and independent replay. | **Passed.** Safe deployment is 56.3% for MOSAIC, 2.5% held-out, and 3.3% finite LTT; paired margins are 53.8 and 53.0 points. |
| S4 | Stochastic MOSAIC materially improves safe retention over deterministic MOSAIC. | Locked retention cell with the preregistered 20-point margin. | **Passed.** Stochastic MOSAIC safely deploys on 56.3% versus 0% for deterministic MOSAIC; paired 95% interval for the difference is 53.2--59.3 points. |
| S5 | The preregistered local power curve tracks observed deployment versus sample size. | Pre-outcome theory receipt; locked confirmation; alignment audit with MAE and primary-cell thresholds. | **Passed.** Mean absolute deployment error is 0.001968 and primary-cell error is 0.004389; all active-set and gradient-stability checks pass. |
| R1 | MOSAIC has practical value beyond the synthetic finite-token witness. | Fresh multi-domain experiments with official or faithfully reimplemented baselines, immutable preprocessing manifests, repeated seeds, and uncertainty. | Missing. No real-world or broad-domain claim permitted. |
| N1 | No prior work states the complete MOSAIC theorem/method combination. | Primary-source collision review across fairness, privacy, robust statistics, experiment comparison, shift, and risk control; external expert review. | Provisional negative search only. Novelty claim prohibited until the sweep is expanded and externally challenged. |
| P1 | The AAAI paper is reproducible and anonymity-clean. | Named and anonymous PDFs, source manifest, page/metadata/font checks, artifact regeneration, citation audit, and adversarial paper review. | In progress. |

The final abstract may contain only claims whose status is supported by completed
evidence. Conditional guarantees must name the shift-membership assumption;
synthetic confirmation cannot establish real-domain membership, clinical
safety, or novelty.
