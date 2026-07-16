# Theorem-to-Code Mapping V2 Specification

This outcome-blind specification was fixed while the controlled-shift matrix
was running and before seeds 45--108 scientific outcome access. It extends the
original five-row map to the complete VERA theorem and diagnostic package. It
does not change a theorem, experiment, endpoint, threshold, allocation, or
decision rule.

## Authority and Versioning

The final mapping is a new schema-version-2 JSON artifact. The existing
schema-version-1 mapping and auditor remain historical evidence for the locked
primary implementation. They may not be silently overwritten or used to imply
coverage of code that did not exist when they were produced.

The V2 artifact must identify, hash, and assign one of three roles to every
source it references:

1. `certificate`: code that constructs a bound or deployment decision;
2. `planning_or_diagnostic`: code that allocates evidence or explains power but
   cannot change a confirmatory decision; or
3. `theory_verification`: code that checks a theorem identity, reduction,
   lower bound, or impossibility behavior without becoming a deployment rule.

## Required Components

The final mapping must contain exactly one row for each component below.

1. `paired_target_harm`
2. `balanced_attacker_leakage`
3. `fixed_profile_candidate_iut`
4. `vector_shift_envelope`
5. `controlled_shift_membership`
6. `sample_complexity_upper`
7. `square_score_allocation`
8. `additive_multicell_allocation`
9. `inverse_evidence_requirement`
10. `sample_complexity_lower`
11. `unsupported_cell_impossibility`

Every row must preserve the original mapping columns and add:

- `theory_label`;
- `role`;
- `implementation_sources`;
- `verification_tests`;
- `assumptions`;
- `validity_effect`;
- `failure_behavior`;
- `provenance_fields`; and
- `claim_boundary`.

Lists must be nonempty, source paths must exist, theorem labels must occur in
the authoritative appendix, and code symbols must occur in at least one hashed
source. Components that do not alter validity must say so explicitly.

## Extension-Specific Obligations

The additive row must map Theorem `thm:additive-allocation` to the fixed-budget
continuous solver, deterministic integer rounding, 15% cell floor, stable-key
tie breaking, solver diagnostics, and disjoint common-random-stream manifest.
It must distinguish unnormalized power coefficients `b_jc` from
margin-normalized allocation coefficients `a_jc`.

The inverse-evidence row must map the same coefficients to the minimum-total
continuous program, deterministic sufficient integer recommendation,
operational top-up from current counts, one-million-observation right-censoring
cap, and design-fold versus oracle-only labels.

The upper-bound and square-score rows must map
`thm:sample-complexity-upper` and `cor:evidence-allocation` to analytic identity
tests and the locked primary allocator. The additive row must state that it is
a prospectively specified extension and cannot rescue the square-score primary.

The lower-bound row must map `thm:sample-complexity-lower` to exact Bernoulli-KL
and Bretagnolle--Huber numerical checks. It must label the globally valid claim
as the exact-KL inequality inside the stated independent Bernoulli experiment;
quadratic shift--margin matching is restricted to compact-interior independent
cells.

The unsupported-cell row must map `thm:unsupported` to missing-environment and
missing-source-class fail-closed paths, plus a two-world test that gives
identical protocol observations but opposite contract truth. It must not map
Camelyon17 to a measured violation; that dataset is an identification-boundary
example only.

## Auditor Contract

The V2 auditor must fail closed on:

- a missing, duplicate, or extra component;
- a missing theorem label, source path, code symbol, test, receipt field, hash,
  role, or claim boundary;
- a source hash that differs from the mapped hash;
- an additive mapping that omits floors, rounding, coefficient normalization,
  solver checks, or stream separation;
- an inverse mapping that merges planning and oracle quantities;
- a lower-bound mapping that states uniform quadratic matching;
- an unsupported-cell mapping that treats absent support as a measured harmful
  outcome;
- any code-path test that does not fail on deliberate negative-margin, support,
  alignment, budget, floor, stream-hash, or source-hash corruption; or
- a report generated from a dirty or different implementation revision without
  an explicit revision record.

The audit report must contain the mapping hash, every referenced source hash,
the authoritative theory hash, test command and exit status, exact component
set, failure list, Git revision, and `formal_proof_verified: false`. A passing
software audit is reproducibility evidence; it is not an independent proof
review.

## Completion Boundary

The V2 mapping, auditor, and deliberate-corruption tests may be implemented only
after the locked 1,280-run matrix and full receipt audit have completed. The
final paper may call theorem-to-code coverage complete only when the V2 audit
passes on the committed implementation revision and an independent human proof
review remains separately reported.
