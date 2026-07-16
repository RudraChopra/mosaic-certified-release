# Additive Allocation Literature Refresh Addendum

This addendum extends `FINAL_LITERATURE_REFRESH_SPEC.md` without modifying its
frozen contents. It was written before seeds 45--108 outcome access and must be
executed against primary papers after the controlled matrix finishes.

## Exact Queries

Search proceedings, journal sites, arXiv, and citation graphs for:

1. `minimax sample allocation multiple estimands additive confidence radius`;
2. `optimal stratified sampling multiple outcomes max variance allocation`;
3. `convex resource allocation sum inverse square root sample size`;
4. `Neyman allocation multiple constraints worst case confidence interval`;
5. `active testing multiple risk constraints calibration sample allocation`;
6. `optimal computing budget allocation multiple feasibility constraints`;
7. `best arm identification shared observations multiple constraints`;
8. `multi-task experimental design shared samples confidence bounds`;
9. `conformal risk control adaptive calibration allocation groups`; and
10. `distributionally robust certification evidence allocation density ratio`.

Run backward and forward citation searches from every close allocation paper
found by the original refresh. Search theorem statements and supplements for an
objective equivalent to
`min_n max_j sum_c a_jc / sqrt(n_c)` under a fixed budget and floors, including
equivalent epigraph, dual, or variance notation.

## Comparison Fields

For every close primary paper, record:

- fixed-budget objective and decision variable;
- whether one estimand or several contracts share evidence cells;
- whether confidence radii add across cells;
- floors, integer rounding, and deterministic tie-breaking;
- design-fold versus outcome-adaptive allocation;
- finite-sample power or validity statement;
- closed-form one-contract or one-cell special case;
- lower bound, if any;
- application to calibration, risk control, distribution shift, or
  representation intervention; and
- the exact VERA sentence that must cite or narrow around it.

## Collision Rules

- If prior work already proves the same convex program generically, cite it and
  present VERA's theorem as a certificate-specific specialization, not a new
  optimization result.
- If prior work combines the same program with finite-family risk control or a
  simultaneous robust-risk envelope, remove allocation-level novelty from the
  title unless VERA has a separate substantive theorem or empirical delta.
- If only the one-contract two-thirds-power rule or one-cell square-score rule is
  known, cite it and limit novelty to the multi-contract shared-cell certificate
  formulation and its representation-edit application.
- If the empirical additive allocator does not beat both uniform and the locked
  square-score rule on the frozen usefulness analysis without worse safety,
  remove `Evidence-Efficient` from the title regardless of theorem correctness.
- No search result, citation count, or internal matrix may be treated as an
  external novelty review.

## Required Output

Append a dated, URL-backed section to the novelty matrix with all included and
excluded papers, primary-source links, capability comparison, and the resulting
claim decision. A human reviewer must independently challenge the search before
submission.
