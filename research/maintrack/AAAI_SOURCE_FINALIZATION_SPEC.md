# AAAI Source Finalization Specification

The modular LaTeX files are working sources, not the final AAAI upload sources.
The official AAAI-27 author kit requires the submitted manuscript to use one
`.tex` file, with the bibliography file as the stated exception. This gate must
be completed after final result macros and prose are frozen.

## Required Deliverables

Generate four flattened files without hand-editing generated output:

1. anonymous main paper;
2. named main paper;
3. anonymous supplement; and
4. named supplement.

Each file must contain its wrapper, resolved result macros, manuscript or
supplement body, and all locally authored TeX fragments in dependency order.
Figures and the verified bibliography remain separate upload artifacts.

## Flattening Rules

- Resolve `\input`, `\include`, `\InputIfFileExists`, and local result-macro
  dependencies recursively.
- Do not inline `aaai2027.sty`, third-party packages, figure binaries, or the
  bibliography database.
- Rewrite figure and bibliography references to package-relative logical names;
  no flattened source may retain `../`, a repository-relative build path, an
  absolute path, or a filename absent from the final source allowlist.
- Preserve comments only when they communicate a venue or reproducibility
  obligation; omit build-path comments and local absolute paths.
- Add a generated-file header with the nonidentifying content-manifest hash and
  SHA-256 hashes of every inlined source. The anonymous file must not include a
  Git commit, branch, remote, repository owner, author identifier, or raw-source
  hash that maps directly to the named public repository. A named private
  record may retain the Git revision after the authorship gate is complete.
- Fail on a missing dependency, duplicate command definition with different
  content, unresolved placeholder, recursive input, or conditional branch whose
  result depends on an absent local file.

## Equivalence Checks

For each named/anonymous and main/supplement pair:

1. compile the modular and flattened sources with the same unmodified official
   `aaai2027.sty` and the same PDFLaTeX runtime;
2. require identical extracted body text after normalizing generated metadata
   and harmless line wrapping;
3. require the same page count, figure and table count, citation keys, theorem
   labels, section order, and numeric result strings;
4. visually compare every rendered page for missing or shifted content; and
5. record both source and PDF hashes in the final submission manifest.

The comparison must also compile each flattened file from a fresh package tree
that has no repository parent paths, inherited TeX search path, build cache, or
machine-specific environment variable. A flattening pass is invalid if it works
only from the authoring checkout.

## Legacy-Interface Retirement

Before flattening, retire or update every active generator, audit, and archive
allowlist that still expects `vera_results_macros.tex` or
`vera_main_results_narrative.tex`. In particular, review
`build_anonymous_archive.py`, `audit_presentation_readiness.py`,
`build_vera_results_package.py`, `build_vera_confirmatory_results.py`,
`audit_goal_completion.py`, and `build_vera_independent_stress_package.py`.
The final path must consume only the validated shared result manifest and its
generated venue layer. An active build or audit must fail if either deleted
legacy fragment is recreated or referenced.

The same prohibition applies to the design-era
`vera_family_grid_results.tex`, `vera_supplement_results.tex`,
`vera_ablation_results.tex`, and `vera_real_learning_curve.pdf` interfaces.
The final supplement may consume only
`vera_controlled_shift_supplement_results.tex`, generated from the validated
shared manifest and its hashed supporting records. A stale legacy file must
never become active merely because `\IfFileExists` finds it in the source tree.

Retire drafting-process language emitted by
`analyze_vera_confirmatory_ablations.py`, `analyze_vera_attacker_ablation.py`,
and `analyze_vera_secondary_ablations.py`; generated submission content may say
that an analysis is prespecified or secondary, but may not call it
`outcome-blindly locked` or describe internal audit chronology. Update
`audit_aaai2027_source_readiness.py` to test the current 1,280-run official
matrix, anonymous code-availability meaning, and the two-part nonclinical
boundary semantically rather than requiring obsolete literal phrases. The
final source audit must deliberately fail on the old 200-run prospective count,
either deleted fragment, any pending-result fallback, and every forbidden
process phrase.

Replace the legacy command blocks in `README.md` and
`GITHUB_EXPORT_README.md` with the final V2 one-command compact reproduction,
the explicit full external-array replay, and individually documented final
gates. Neither README may invoke a retired result generator, promise tracked
submission-mode PDFs or anonymous ZIPs, or describe an old generated readiness
artifact as authoritative. Every displayed command must run successfully from
the named release or be explicitly labeled as requiring the separately
manifested external arrays.

## Format and Anonymity Checks

- No flattened source may contain `\input`, `\include`, or
  `\InputIfFileExists`.
- No forbidden package or layout command from the official author kit may
  appear.
- The main paper must have exactly seven technical-content pages before
  references without font, spacing, margin, or table-resizing tricks.
- The anonymous files, PDFs, figure metadata, bibliography comments, archive
  names, and manifests must contain no author, affiliation, named repository,
  username, home path, external-volume path, or account identifier.
- PDFs must contain no Type 3 fonts, embedded links, bookmarks, JavaScript,
  attachments, page numbers, or identifying metadata.
- PDFs must use US letter, PDF version 1.5 or higher, embedded permitted fonts,
  and graphics whose bounding boxes do not overflow margins or the column
  gutter. The source package must contain only the flattened source,
  bibliography, official style and bibliography style, used graphics, generated
  bibliography output required by the author kit, and required PDF/checklist
  deliverables; unused modular sources are excluded.
- The named source must contain the author-approved identity and repository URL
  only after the human authorship and disclosure gates are complete.

## Pass Condition

This gate passes only when all four flattened sources compile cleanly, every
equivalence and visual check passes, and the final anonymous archive audit uses
the flattened files rather than the modular wrappers. A successful modular
build alone is not AAAI source readiness.
