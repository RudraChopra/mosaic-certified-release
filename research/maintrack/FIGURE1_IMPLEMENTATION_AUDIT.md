# Figure 1 Implementation Audit

Audit time: 2026-07-15 11:37 PDT

This audit covers the outcome-independent VERA method overview. It does not
inspect or encode a controlled-study outcome.

## Frozen Purpose

The three panels teach the complete method in order:

1. independent design margins determine certification-stream allocation before
   certification outcomes;
2. a candidate intersection--union test decides one registered profile while
   simultaneous curves report the inspectable envelope and common radius; and
3. a required cell outside certification support forces abstention rather than
   extrapolation.

The curves are schematic. The Camelyon17 panel states an identification
boundary and does not claim a positive empirical certificate or clinical harm.

## Reproducible Artifacts

| Artifact | SHA-256 |
| --- | --- |
| `figures/generate_vera_method_overview.py` | `d6fe651b2c1273daae93a547874ac8e371d38900762f3e46cfafff74305166ba` |
| `figures/vera_method_overview.pdf` | `a217e23a66ae47ca7bd39c5b846cafa540c268f406c08cc755a939de60c663f3` |
| `figures/vera_method_overview.png` | `2464f5cd4408d383ab00cf909b325f1795bec11c0366a7bd52177646e79d5e41` |
| `figures/vera_method_overview_caption.md` | `5fef68f41527fd00c576a9529d7b868a1923bb7af338407c3c4585a915237770` |

Two consecutive generator executions produced byte-identical PDF and PNG
hashes. The PDF uses fixed, explicit metadata rather than a wall-clock creation
time.

## Mechanical Checks

- Exactly three panels are present in one full-width figure.
- The PDF media box is 504 by 166 points, exactly 7.0 inches wide.
- The minimum explicit text size is 7 points before inclusion.
- Text is embedded as Type 0/CIDFontType2 vector fonts; no Type 3 font marker is
  present.
- Color is redundant with line style, hatching, boxes, and markers.
- A grayscale rendering at 50 percent remains legible and preserves the five
  curve identities.
- The anonymous AAAI close-layout build remains nine total pages and renders
  Figure 1 without overlap or clipping.
- Neutral ICLR and NeurIPS builds include the identical figure and caption.
- AAAI, ICLR, and NeurIPS logs contain no overfull box, undefined reference,
  undefined citation, or fatal LaTeX error after insertion.

## Open Gates

- The repository has no PDFLaTeX executable. The AAAI check used a disposable
  copy of the official style with only its engine/font guard disabled; the
  repository style was not modified. An unmodified official PDFLaTeX build is
  still required.
- A human cold reader must confirm that the allocation, certification object,
  and abstention reason are understandable in ten seconds.
- The final named and anonymous PDFs must be rechecked after generated results
  and final venue wrappers are inserted.
