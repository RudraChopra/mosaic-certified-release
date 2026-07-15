# Reference Baseline Matrix

Date: July 14, 2026

## Purpose

This matrix prevents VERA from overstating baseline coverage. A baseline can be
used in one of three ways: as a local reference implementation, as an official
upstream reference implementation, or as a scoped proxy stress test. Only the
second category supports reference-parity claims.

## Current Status

| Baseline | Status | Evidence | Allowed claim |
| --- | --- | --- | --- |
| ERM probe | Local reference | Shared frozen representations and locked splits | Standard linear-probe baseline under matched conditions |
| Source-balanced ERM | Local reference | Shared frozen representations and locked splits | Source-reweighted linear baseline |
| Group-reweighted ERM | Local reference | Shared target-source group weights | Robust linear-probe baseline |
| GroupDRO-style probe | Local reference | Shared group-weighted solver | Strong robust probe baseline, not full deep GroupDRO training |
| INLP | Official upstream entry point | `independent_stress_replication_receipt_audit.json`; `official_eraser_adapters.py` | Official INLP candidate rows on every dataset and seed in the independent matrix |
| LEACE | Official upstream entry point | Same receipt audit and adapter source | Official closed-form LEACE candidate rows on every dataset and seed |
| R-LACE | Official upstream entry point | Same receipt audit and adapter source | Official `rlace.solve_adv_game` candidate rows on every dataset and seed |
| TaCo | Official upstream entry points with registered protocol heads/PCA | Same receipt audit and adapter source | Official TaCo concept ranking/cropping rows under the shared frozen-feature protocol |
| MANCE++ | Official upstream entry point | Same receipt audit and adapter source | Official MANCE++ candidate rows on every dataset and seed |
| SPLINCE | Not run in the claim-grade matrix | Literature comparison only | No empirical or reference-parity claim |

## Reviewer-Facing Boundary

The independent matrix contains 800/800 official upstream run receipts across
INLP, LEACE, R-LACE, TaCo, and MANCE++, five datasets, and 32 disjoint seeds;
the audit reports zero proxy rows. The paper may claim this exact coverage. It
must not claim universal erasure state of the art, implementation identity
outside the recorded entry points, or empirical coverage of SPLINCE.

## Scope Note

TaCo's official feature-level functions are called inside registered protocol
heads and randomized PCA so that every eraser shares the same frozen-feature
splits and downstream audits. This is an explicit adaptation boundary, not a
proxy row. VERA's empirical claim remains about the certification layer, not
which eraser is intrinsically best.
