# Double-Blind Release Boundary: Interpretation 1

This outcome-blind interpretation records concrete defects found in the legacy
anonymous archive builder and fixes the required behavior for its replacement.
It does not alter a scientific endpoint or claim.

## Legacy Builder Is Not Reusable

The current `research/scripts/build_anonymous_archive.py` is a historical
builder. It is not a final-submission path because it:

- defaults to `dist/vera_anonymous_submission.zip` in the named repository;
- expects the deleted `vera_main_results_narrative.tex` fragment;
- packages modular anonymous wrappers and old PDFs instead of final flattened
  sources and current clean builds;
- writes the Git source commit into the manifest;
- includes historical receipt files that may contain author-specific absolute
  paths; and
- omits the controlled-shift protocol, receipt audit, locked analyzer,
  independent replay, safety/ratio analyses, additive extension, and final
  three-venue result manifest.

The legacy ZIP and its prior green audit are historical artifacts. They cannot
be renamed or refreshed and called the final anonymous package.

## Required V2 Build Behavior

The replacement builder must:

1. default to `dist/private-review/` or an explicit external private path;
2. refuse an output path tracked by Git or outside an ignored/private root;
3. package the final anonymous flattened main and supplement sources, current
   clean PDFs, official style and bibliography, checklist, code, manifests,
   compact public artifacts, and permitted figures only;
4. derive the file list from one explicit allowlist and fail on every missing,
   duplicate, stale, or unlisted dependency;
5. omit `.git`, author names, repository URLs, usernames, affiliations, named
   branch or remote data, reviewer identities, submission IDs, acknowledgements,
   and local shell logs;
6. omit Git commit hashes that can map the archive to the author-named public
   repository, using content hashes and a nonidentifying release-format version
   instead;
7. fail if any text, path, PDF metadata, figure metadata, archive comment, or
   embedded attachment contains a forbidden identity or absolute local path;
8. create the archive deterministically from a clean anonymous staging tree;
9. record SHA-256 and byte size for every payload member plus the archive; and
10. extract into a fresh temporary directory and complete compact reproduction
    and every source/PDF/anonymity audit from that extraction.

## Receipt Canonicalization

Scientific receipts produced during execution are immutable evidence and must
not be edited in place. If a raw receipt contains an absolute storage path or
named-repository commit, the anonymous package must instead contain a
deterministic canonical public view that:

- retains dataset, method, seed, candidate, split, protocol, upstream code,
  array-content, and decision-relevant hashes;
- replaces local paths with stable logical artifact identifiers;
- omits named-repository commit linkage while retaining the locked protocol and
  runner-version identifiers needed for internal provenance;
- records the SHA-256 of the immutable raw receipt in a private, author-side
  release ledger rather than in a public mapping when that hash itself links to
  a named public artifact; and
- is regenerated and checked against the raw receipt by a canonicalization
  audit before packaging.

Canonicalization may remove identifying transport metadata only. It may not
change a dataset, method, seed, threshold, candidate, scientific value, pass or
fail result, array hash, or protocol hash. The canonicalizer must fail on any
unrecognized field rather than silently dropping it.

## Required Current Inputs

The V2 archive must include or represent, as venue policy permits:

- the base controlled-shift preregistration and SHA-256 sidecar;
- all outcome-blind interpretation and analysis specifications;
- the full 1,280-receipt structural audit and compact canonical receipt views;
- the protocol-compliant cap-8 analyzer, code-path-independent cap-8 raw-array
  replay, and their exact-agreement evidence;
- the byte-unchanged cap-4 implementation sensitivity and three-way comparison
  report;
- registered safety, ratio, ablation, held-out-attacker, GaitPDB, and additive
  allocation analyses;
- exact small-case and theorem-to-code mapping artifacts;
- the final claim-and-result manifest shared across venue variants;
- verified reference, data-right, software-license, and upstream notices; and
- clean reproduction instructions that contain no machine-specific paths.

Large public datasets, embedding stores, immutable raw audit arrays, private
review records, signed human attestations, and restricted material remain out
of the archive. Logical acquisition and verification instructions replace
machine-specific locations.

## Pass Condition

The boundary passes only when the V2 builder and auditor have deliberate tests
for public-output paths, Git tracking, source-commit linkage, author strings,
absolute paths, stale files, modular sources, metadata leaks, unexpected receipt
fields, hash corruption, archive traversal, duplicate members, and clean-room
reproduction failure. Every deliberate corruption must fail closed.
