# VERA Venue Content Variants

This directory holds outcome-blind content plans for the later ICLR 2027 and
NeurIPS 2027 variants. The active official-format source remains the AAAI-27
source under `aaai2027_template/AuthorKit27/`.

The variants are different explanations of one scientific record, not three
independent experiments and not permission for simultaneous archival review.
They follow `../THREE_VENUE_CONTENT_VARIANT_SPEC.md` and must consume the same
final result manifest, theory source, bibliography, negative results, and claim
ledger. Exact ICLR and NeurIPS formatting remains pending official 2027
materials.

Files here are planning artifacts until controlled results are frozen. They
must never be labeled submission ready merely because every section heading has
draft prose.

Current outcome-blind content sources:

- `ICLR_2027_SCIENTIFIC_CONTENT.tex` contains the representation-learning and
  intervention-evaluation variant;
- `NEURIPS_2027_SCIENTIFIC_CONTENT.tex` contains the statistical-decision and
  evidence-design variant; and
- both include the identical deterministic method overview through
  `\VERAMethodOverviewPath`, which defaults to
  `../figures/vera_method_overview.pdf`; and
- both consume the command interface frozen in
  `../SHARED_RESULT_MANIFEST_SPEC.md` and
  `../SHARED_RESULT_MANIFEST_SCHEMA.json` once audited results exist.

The section-by-section scientific equivalence obligation is recorded in
`../VENUE_VARIANT_CLAIM_MAP.md`.

These files intentionally have no venue wrapper. Official ICLR 2027 and
NeurIPS 2027 materials must be verified before format-specific sources are
created. Each wrapper must load `graphicx`; a wrapper that relocates the source
must define `\VERAMethodOverviewPath` before inputting the scientific content.
