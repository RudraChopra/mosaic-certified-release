# Controlled-Shift Receipt Audit: Interpretation 1

This outcome-blind addendum strengthens the official-receipt audit before any
candidate metric, decision, risk, radius, violation, retention value, or
aggregate outcome from seeds 45--108 is read. It changes no receipt, candidate,
array, random stream, threshold, endpoint, or gate. The running matrix remains
untouched.

## Exact File Set

Construct the expected receipt basename set directly from the locked
dataset--method--seed Cartesian product. After the matrix completes, require the
preregistered receipt root to contain exactly those 1,280 direct regular JSON
files and no additional file, symlink, normalized-name collision, or case-fold
collision. Reject a missing, extra, duplicate, nested, or differently named
receipt before loading scientific arrays.

Across those receipts require exactly 3,072 candidate records and 3,072 unique
audit NPZ paths. For every dataset--seed block, require exactly 12 distinct
candidate keys. A candidate's `method` must equal the receipt's registered
display name, and its `candidate_key` must equal `method + "::" + strength`.
Reject a duplicate candidate key or audit path before any dictionary or later
row can overwrite it.

## Root And Path Boundary

Resolve the receipt root and require equality with
`real_study.freshness_guard.fresh_receipt_dir`. Resolve every candidate audit
path and require it to be a regular, non-symlink `.npz` file below
`real_study.freshness_guard.fresh_audit_dir`, inside the subdirectory named by
that receipt's exact run key. The array root, receipt root, receipt files, run
subdirectories, and NPZ files must not resolve through a symlink. Reject
absolute-path substitution outside either preregistered root, traversal,
hardlinks with multiple candidate paths, devices, sockets, FIFOs, or any
unregistered file under either controlled-study root.

The audit continues to verify each stored NPZ SHA-256. Path containment never
replaces content hashing, and content equality never excuses a path-boundary
failure.

## Closed Array Contract

Each NPZ must contain exactly the 22 registered one-dimensional arrays:

- certification and external target harm;
- certification and external identity and edited target errors;
- certification and external source, environment, and target metadata;
- certification and external correctness for linear, RBF, forest, and MLP
  attackers; and
- certification and external correctness for the held-out boosted tree.

Reject unknown or missing arrays, object/string dtypes, non-one-dimensional
arrays, nonfinite values, split-length disagreement, nonbinary target-error or
correctness arrays, paired harm outside `{-1,0,1}`, paired-harm reconstruction
failure, or metadata disagreement across candidates in one dataset--seed
block. Existing split-index, official-entry-point, upstream revision,
preprocessing, and runner-commit checks remain mandatory.

## Mandatory Corruption Fixtures

Before the real full audit is accepted, tests must reject at least: an extra
receipt, an unexpected basename, a receipt symlink, a case-colliding receipt,
an outside-root NPZ, an NPZ symlink, a duplicate candidate key, a duplicate NPZ
path, a method/key/strength mismatch, an extra NPZ member, an unknown file in a
controlled root, and metadata disagreement across two official-method
receipts.

The final audit report records expected and observed file sets, resolved roots,
candidate and NPZ cardinalities, duplicate counts, unknown-file counts, and
every corruption-fixture result. Any mismatch blocks the sealed analyzers and
independent replay; it cannot be waived because aggregate outputs later agree.
