# Double-Blind Release Boundary: Interpretation 3

This outcome-blind addendum was fixed before scientific access to seeds
45--108. It adds a license-ownership check to the private V2 review package and
changes no experiment, statistic, claim, title condition, or prior release
boundary.

## VERA License Gate

The human author must approve the exact license and copyright line for
independently authored VERA code and documentation. Until that approval is
recorded, the named repository and private review package are license-pending
and may not be described as release ready. Automation may recommend MIT but
may not grant it on the author's behalf.

After approval, the V2 package must include the exact committed top-level
license bytes and record their SHA-256 hash. A nonidentifying copyright line
such as `VERA Authors` may be used in both named and anonymous copies so the
legal grant is byte-identical and does not create an anonymity-specific
license. The package manifest must identify which original VERA paths are
covered.

## Third-Party Boundary

The VERA license must not purport to relicense third-party datasets,
biographies, comments, images, recordings, embeddings, model weights,
upstream eraser implementations, official venue styles, bibliography styles,
or trademarks. The archive must include a machine-readable exclusion list and
all notices required for any third-party file that venue policy requires it to
carry. An upstream remote, commit, entry point, citation, or checksum is
provenance, not a license grant.

No upstream repository tree or raw/derived dataset asset may enter the package
merely because VERA-authored adapter code is licensed. Missing or unresolved
upstream terms remain no-redistribution under
`DATA_SOFTWARE_LICENSE_LEDGER.md`.

## Required Failure Checks

The V2 builder and auditor must reject a missing VERA license, an unapproved
license record, a license hash mismatch, different named and anonymous grant
text, an identity-bearing anonymous copyright line, a missing third-party
exclusion list, an excluded asset present in the archive, an upstream notice
required by the rights ledger but absent, or text implying that the VERA grant
covers externally owned material.

## Pass Condition

The license boundary passes only after the human approval is recorded, the
committed license and archive copy agree byte for byte, every required notice
is present, every excluded class is absent, and deliberate corruption fixtures
fail closed. This gate establishes packaging consistency only; it is not legal
advice and does not replace source-by-source rights verification.
