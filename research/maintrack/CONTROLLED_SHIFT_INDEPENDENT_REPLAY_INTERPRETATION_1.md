# Controlled-Shift Independent Replay: Interpretation 1

This outcome-blind interpretation strengthens the replay timing and code-path
separation without changing any statistic, tolerance, endpoint, or comparison
in `CONTROLLED_SHIFT_INDEPENDENT_REPLAY_SPEC.md`.

## Source Freeze Before Outcomes

After the 1,280-run matrix and full structural receipt audit complete, but
before any aggregate scientific outcome is opened, implement the replay in a
new source file and test module. Commit and push that source with:

- its exact input schema and normalized output schema;
- small deterministic fixtures for all nine rules;
- exact discrete-bound, allocation, shift-membership, selection, bootstrap,
  sentinel, and Holm checks;
- deliberate missing-array, hash, support, allocation, radius, nonfinite,
  sorting, and tie-break failures; and
- a static independence audit.

The static audit parses imports and source text and fails if the replay imports,
loads through, shells out to, or dynamically evaluates the locked analyzer,
controlled-shift design helpers, robust-certificate implementation, generated
rows, result builder, or their private modules. It records the replay source
hash and all forbidden-source hashes. Prior exposure to those sources is
disclosed; this remains code-path independence rather than a blind human
implementation.

## Sealed Execution Order

1. Require the full receipt audit to report 1,280 valid and zero missing,
   invalid, proxy, or revision-mismatched receipts.
2. Run the committed replay from a clean environment with only the audited
   preregistration, immutable receipts, and raw NPZs readable.
3. Suppress all metric-bearing console output. The launcher may reveal only
   process status, normalized row count, output path, byte size, and SHA-256.
4. Make the replay output read-only and record its hash in the outcome-access
   ledger without opening its scientific fields.
5. Run the unchanged locked analyzer. Record its command, source hash, input
   hashes, output hash, and the first actual scientific-outcome access.
6. Only after both outputs and source revisions are frozen, run a third
   comparison program that reads their normalized records and emits equality or
   mismatch diagnostics.

No replay source change is permitted after either sealed output exists. If the
replay crashes, its failure is fixed by a new disclosed revision before the
locked analyzer is run; the failed attempt remains logged. If the locked
analyzer has already been opened before a replay fix, the replay is no longer
outcome-blind and must be labeled as such.

## Clean Runtime Boundary

Run the replay with an empty project `PYTHONPATH`, no importable checkout path
except its own isolated package, no analyzer output present in the readable
input tree, no network, a fresh temporary cache and home, fixed locale and time
zone, and explicit NumPy/SciPy/Python versions. The replay may use standard
library and public numerical/statistical APIs but must implement VERA-specific
formulas, random-key derivations, decisions, and inference independently.

The launcher records every opened project file where the platform permits, or
otherwise runs inside an allowlisted copy containing only the preregistration,
sidecar, replay source, receipts, and NPZs. Any attempt to open a forbidden
source or analyzer output fails.

## Normalization and Comparison

Before hashing, serialize finite JSON with stable UTF-8 encoding, sorted keys,
stable row ordering, explicit null/reason records, and no timestamps, absolute
paths, hostnames, usernames, or nondeterministic dictionary/set order. Runtime
metadata belongs in a separate sealed execution manifest.

The third comparison checks all 3,072 candidate records and every normalized
profile, budget, allocation, and rule record, not only aggregate headlines. It
reports mismatch counts and first differing logical keys without overwriting
either source output. Discrete values must be exact; non-radius floating values
use the frozen `1e-10` absolute/relative tolerance and radii the frozen `1e-4`
tolerance. Any mismatch blocks the controlled result and remains visible.
