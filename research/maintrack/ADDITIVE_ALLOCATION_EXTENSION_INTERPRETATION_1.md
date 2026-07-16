# Additive Allocation Extension: Interpretation 1

This outcome-blind interpretation makes
`ADDITIVE_ALLOCATION_EXTENSION_SPEC.md` at SHA-256
`e4c41f09a7cc1e6d47a0ac9cc149f5f2c79c52b248b318eedf9aae9129e567b1`
fully executable without changing its objective, comparisons, or claim
boundary. It was fixed before seeds 45--108 outcome access.

## Contract and Curve Constants

- Use allocation confidence level `delta_alloc = 0.05` and power error
  `beta_alloc = 0.20`.
- Let `D` equal the number of nonzero target-environment and
  attacker-by-source cell-risk curves for the selected design-fold candidate.
- Give every nonzero curve `alpha_jc = delta_alloc / D`. These constants are
  common across curves; they remain in receipts even when a common factor
  cancels from a relative allocation.
- Target-environment contracts use weight `1`, range length `2`, the induced
  environment-conditional Gamma, and margin
  `target_threshold - design_target_risk`.
- Each balanced-leakage attacker contract uses weight `1/2` for each source
  class, range length `1`, the induced source-conditional Gamma, and margin
  `leakage_threshold - design_balanced_attacker_risk`.
- Clamp design margins below `0.01` to `0.01` for allocation only, matching the
  locked square-score rule. Record unclamped and clamped margins. This clamp has
  no role in certificate validity or external safety labels.
- Select the design-fold candidate by the unchanged largest-minimum normalized
  margin rule with the existing leakage, target, and stable candidate tie-breaks.

With these definitions, target coefficients are proportional to
`2 * Gamma / margin` and source-class contributions to
`0.5 * Gamma / margin`. The locked square-score rule is therefore the
one-cell reduction of the same coefficients; the additive rule differs by
optimizing their sums inside balanced-leakage contracts.

## Continuous Solver

Use SciPy SLSQP on the epigraph program with:

- `ftol = 1e-12`;
- `maxiter = 2000`;
- analytic objective and constraint Jacobians;
- initialization at the feasible locked square-score allocation converted to
  real counts; and
- variable lower bounds equal to `ceil(0.15 * N)` for every registered cell.

Require solver success, budget error at most `1e-8`, floor error at most
`1e-8`, contract-constraint error at most `1e-8`, and finite objective and
gradient values. A failed check fails the row; it does not trigger an unrecorded
fallback. Record SciPy, NumPy, Python, and platform versions plus all solver
diagnostics.

## Deterministic Integer Rounding

Take the floor of each continuous count. The floor is already integer-valued, so
this preserves it. Allocate the remaining at most `C-1` observations one at a
time to the cell that gives the largest decrease in the current maximum
normalized additive slack. Recompute the exact objective after each addition and
break equal decreases by the stable cell key. Require exact integer budget and
floor equality checks.

## Common Random Streams

Use common random numbers across uniform, locked square-score, and additive
allocations. For each dataset, seed, requested Gamma, and evidence cell, define

`key = "vera-additive-allocation-v1|<dataset>|<seed>|<Gamma>|<cell>"`.

The NumPy generator seed is the unsigned big-endian integer represented by the
first eight bytes of SHA-256 over the UTF-8 key. Generate one with-replacement
index stream of length 8,000 from that cell's finite reference atoms. Every
allocation and budget uses the prefix of length `n_c` from this same cell stream.
Thus allocation rules are paired, budget curves are nested, and all extension
streams are disjoint by namespace from the locked primary streams. Hash the key,
full stream, and every used prefix.

The stream excludes method and candidate because all official candidates in one
dataset--seed block share the same registered split and reference-atom indexing.
Fail the block if receipt hashes do not verify that alignment.

## Exact Small-Case Checks

Before real analysis, require:

1. the one-contract SLSQP solution matches the two-thirds-power formula within
   `1e-6` observations and `1e-10` objective;
2. the one-cell-per-contract solution matches square-score allocation within
   the same tolerances;
3. for every three-cell integer case with budget at most 40 in a fixed test
   grid, deterministic rounding is compared with exhaustive allocation and its
   objective gap is reported;
4. permuting contract or cell input order leaves keyed counts unchanged; and
5. deliberate solver, floor, hash, alignment, and budget corruptions fail
   closed.

The real comparison may run only after these checks pass and their artifact is
committed.
