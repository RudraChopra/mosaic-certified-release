# VERA Venue Format Plan

Date checked: July 14, 2026

## Immediate Target: AAAI-27 Main Technical Track

Official sources:

- `https://aaai.org/conference/aaai/aaai-27/`
- `https://aaai.org/conference/aaai/aaai-27/main-technical-track-call/`
- `https://aaai.org/conference/aaai/aaai-27/submission-instructions/`
- `https://aaai.org/conference/aaai/aaai-27/supplementary-material/`
- `https://aaai.org/conference/aaai/aaai-27/areas-and-topics/`
- `https://aaai.org/aaai-publications/aaai-publication-policies-guidelines/`

Verified Anywhere-on-Earth deadlines are July 21, 2026 for the genuine
abstract, July 28 for the full paper, and July 31 for supplementary material and
code. The main submission permits seven pages of technical content; later pages
are reserved for references. The reproducibility checklist is uploaded
separately.

AAAI-27 is double blind. The anonymous paper and supplement must omit author,
affiliation, acknowledgement, named-repository, and identifying metadata. The
supplement must be uploaded through OpenReview and must not point to mutable web
material. Critical evidence must remain in the seven-page main paper because
reviewers are not required to inspect supplements.

AAAI-27 permits judicious generative-AI assistance, but the human authors remain
fully responsible for every claim, reference, experiment, and ethical obligation.
AAAI's publication policy also requires the role of any AI system used in
developing the publication to be documented in the manuscript. AI systems are
not authors or citable sources. Because AI assistance in this project was
extensive, both paper variants contain a full-scope disclosure. The author must
understand and personally verify this submission.

The registered primary topic is `ML: Machine Unlearning, Data Deletion & Model
Editing`, with secondary topics for robustness, representation learning, AI
evaluation/auditing, and uncertainty representations. These are exact AAAI-27
labels and remain subject to the author's final reviewer-matching judgment.

The active sources are:

- `aaai2027_template/AuthorKit27/vera_aaai2027_anonymous.tex`
- `aaai2027_template/AuthorKit27/vera_aaai2027_named.tex`
- `aaai2027_template/AuthorKit27/vera_aaai2027_supplement_anonymous.tex`
- `aaai2027_template/AuthorKit27/vera_aaai2027_supplement_named.tex`

These are modular authoring sources. The final upload must use the four
single-file derivatives required by
[`AAAI_SOURCE_FINALIZATION_SPEC.md`](AAAI_SOURCE_FINALIZATION_SPEC.md); the
modular wrappers themselves do not satisfy the official one-TeX-file source
rule.

They use the unmodified official `aaai2027.sty`. Its SHA-256 is
`391bce82815bf698b8e382dd3ae7e30c75d7ab46df140cb295b1266016bc8623`, exactly
matching the copy inside the retained official author-kit ZIP, whose SHA-256 is
`e28c6ac9bc6eb3b4e2d849547d2cefb5162610ee39d0a12e0dc62d1126b44a7d`.
Earlier anonymous and named revisions compiled locally with PDFLaTeX; the
current revised sources require a fresh clean PDFLaTeX build. Final readiness
requires exactly seven content pages, clean metadata and source scans, the
separate checklist, verified flattened sources, and a reproducing anonymous
ZIP.
On July 15, 2026, a direct Tectonic attempt reached the unmodified style and was
rejected by its explicit pdfTeX-only engine check; no `pdflatex` executable is
currently installed. Neutral source builds pass, but they do not satisfy this
official-format gate. The final build must use a clean pdfTeX toolchain without
modifying the official style.
The anonymous ZIP, anonymous submission PDFs, and flattened anonymous upload
sources must follow
[`DOUBLE_BLIND_RELEASE_BOUNDARY.md`](DOUBLE_BLIND_RELEASE_BOUNDARY.md) and must
not be committed to the named GitHub branch.

## Later Target: ICLR 2027

As of July 14, 2026, an official ICLR 2027 call, author guide, and style package
were not discoverable from the official conference site. The 2026 rules are not
a valid substitute. Do not claim an ICLR 2027 deadline or compile a nominal
ICLR 2027 submission until the official materials are released and rechecked.

AAAI-27 and ICLR 2027 are archival venues. The same or substantially similar
paper cannot be under simultaneous archival review. Venue order must follow the
official multiple-submission policies and actual decisions or withdrawals.

Until the official ICLR 2027 package exists, the project may maintain a
scientifically complete, venue-neutral ICLR content variant, but it must be
labeled `format pending` rather than submission ready. The checked-in ICLR 2026
style is a legacy layout reference only.
The scientific completeness and cross-variant consistency requirements are
fixed in `THREE_VENUE_CONTENT_VARIANT_SPEC.md`.

## Later Target: NeurIPS 2027

As of July 14, 2026, no official NeurIPS 2027 call, author guide, deadline, or
style package was available in the project. Do not infer 2027 requirements from
NeurIPS 2026. A scientifically complete NeurIPS content variant may be prepared
after the controlled-study results are frozen, but exact page-limit, checklist,
anonymity, data-policy, and generative-AI compliance remain `format pending`
until verified from official 2027 sources.
The scientific completeness and cross-variant consistency requirements are
fixed in `THREE_VENUE_CONTENT_VARIANT_SPEC.md`.

AAAI, ICLR, and NeurIPS variants must not be submitted simultaneously when that
would violate duplicate-submission rules. "Three papers ready" means three
complete scientific-content variants and, for each venue whose official kit is
available, a separately verified format package. It does not authorize
simultaneous archival review or fabricated venue metadata.

## Legacy Drafts

Files named for earlier project names or 2026 venue templates are historical
development artifacts only. They are not submission sources, are excluded from
the anonymous package, and must not be cited as current venue-ready versions.
