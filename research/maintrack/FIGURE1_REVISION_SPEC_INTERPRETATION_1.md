# Figure 1 Revision Specification: Interpretation 1

This outcome-blind addendum preserves
`FIGURE1_REVISION_SPEC.md` at SHA-256
`637e79d5b45ac63d4c563917b45e45124b4a30fc2f60ead6c998b497de76d8e1` and
aligns Panel A with the subsequently frozen additive allocation extension at
SHA-256
`e4c41f09a7cc1e6d47a0ac9cc149f5f2c79c52b248b318eedf9aae9129e567b1`.
It changes no experiment, endpoint, result, or other panel requirement.

## Superseding Panel-A Detail

Replace the original compact `n_j proportional to A_j` arrow with:

`design margins -> minimize max_j sum_c a_jc / sqrt(n_c) -> cell counts`.

Use a short `one cell: square scores` annotation only if it remains legible.
The visual must make clear that:

- one target contract can use one environment cell;
- one balanced-leakage contract adds two source-class cells;
- a source-class draw can evaluate several attackers without becoming several
  independent samples; and
- the allocation is selected before certification outcomes.

The figure depicts the general additive VERA allocator. Its caption must
separately state that the locked primary controlled study used the earlier
square-score allocation, while the additive comparison was fixed before fresh
outcome access and uses disjoint certification streams. Do not visually imply
that the extension can replace a failed primary gate.

All other wording, visual constraints, and acceptance checks in the original
Figure 1 revision specification remain unchanged.
