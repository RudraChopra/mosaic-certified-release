# Final Adversarial Assessment: VERA

## Verdict

**Do not submit the current VERA paper to AAAI main track.** My honest
prediction is reject or weak reject, not strong accept. This conclusion follows
from the completed, independently checked P0 study rather than from stylistic
judgment.

## Blocking Findings

1. **The planned empirical delta over IID LTT failed.** At the P0 primary
   profile, IID LTT made 2 exact shifted-contract violations among 118
   deployments (1.69%), while VERA made zero violations but only 11 deployments
   among 194 exact-safe opportunities. The prespecified IID-exposure and paired
   comparison gates both fail. The paper cannot honestly say that VERA is the
   reason to prefer a new decision layer over existing risk control.

2. **The usefulness claim fails at the primary shift.** VERA retains 5.7% of
   exact-safe opportunities at Gamma = 1.25, with 95% seed-bootstrap interval
   [2.6%, 9.0%]. The safety result is real but too abstention-heavy to support
   the planned practical-impact claim.

3. **The guarantee remains portfolio-scoped.** The unregistered KNN stress
   attacker finds 3 violations among 11 P0 VERA deployments. This does not
   invalidate the theorem for the registered portfolio, but it rules out any
   broad "concept erased" language.

4. **Novelty is still application-level relative to LTT/risk control.** The
   paper now cites that literature and scopes its contribution correctly, but
   the empirical result does not establish that the paired multi-attacker
   envelope solves a problem existing LTT cannot handle well enough.

5. **Human and production gates remain open.** There is no independent proof
   review, cold external ML/statistics review, human authorship review, or
   verified anonymous upload. The current workstation also lacks `pdflatex`, so
   the updated manuscript source has not received a fresh local PDF build and
   visual inspection.

## What Survives

- The study is unusually reproducible: all 1,280 P0 receipts, 3,072 candidate
  audit arrays, and the independently written replay pass their integrity and
  agreement checks.
- The support boundary and finite-reference conditional claim are carefully
  scoped. The negative result is informative: uncorrected validation selection
  fails badly under the declared stress, but a naive vector envelope can be
  much too conservative.
- The work is plausible as a transparent negative-results report, a science
  fair project about evidence-aware abstention, or an early technical report.
  It is not evidence for an AAAI-main superiority paper.

## Required New Research Direction

More threshold sweeps, seed blocks, or presentation polish cannot repair this
submission. A new project needs a distinct technical contribution that reduces
the conservatism while preserving a shift-aware guarantee, for example a
formally valid adaptive attacker-discovery procedure or a data-dependent
envelope with a theorem that remains valid after the allocation and attacker
portfolio are chosen. That would require a new proof, a fresh preregistration,
and new independent experiments; it cannot be inferred from the existing P0
data.
