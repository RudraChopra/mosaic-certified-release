# Shared Result Manifest Specification

This outcome-blind specification was fixed before scientific access to seeds
45--108. It defines the one result record consumed by the AAAI-27, ICLR 2027,
and NeurIPS 2027 scientific-content variants. It changes no experiment,
endpoint, threshold, or decision rule.

The exact supplementary-sensitivity interpretation is
`CONTROLLED_SHIFT_SENSITIVITY_INTERPRETATION_1.md` with SHA-256
`583cd054d3fa24511c86c15d083489440b3bcc1a076e4a65fd4bd8df0b244608`.
That interpretation separates simultaneous confidence bounds from Holm tests
and makes the vector/common zero-denominator cases mutually exclusive. Its
hash is mandatory provenance in the final manifest.

The exact three-rule, three-threshold supporting analysis is
`THREE_RULE_THRESHOLD_STRESS_SPEC.md` with SHA-256
`dbb4e0364768bf82440ac956756e7ae184a89baeefb58bdcced8837582c36a7c`.
Its complete grid and readiness decision are mandatory, non-rescuing fields in
the final manifest.

## Authoritative Outputs

The final result builder must produce two equivalent files from the audited
analysis outputs:

1. `vera_shared_result_manifest.json`, the machine-readable authority; and
2. `vera_shared_controlled_results.tex`, a generated presentation layer whose
   values are derived only from that JSON.

Both files must record their input hashes and the locked protocol hash. Neither
file may be hand-edited. The JSON is authoritative if generated prose and JSON
disagree.

## Schema V2 Fail-Closed Contract

The authoritative machine schema is release format V2. V1 fixed the outer
record and exact rule/dataset sets but left several nested `effect`, `test`,
`per_dataset`, radius, allocation, and evidence-cell objects too permissive.
V2 replaces those open objects with exact required fields. In particular, it
requires the efficacy sign-test numerator and nonzero denominator, sentinel
count and upper bound, whole-seed retention bootstrap constants and complete
zero-opportunity sensitivity, vector/common zero-denominator status and
non-rescuing sensitivity, exact 256-decision and
64-per-dataset denominators, all four per-dataset rule rows, radius quartiles
and censoring, allocation contrasts and solver/stream hashes, and cell-level
evidence recommendations backed by a hashed full record artifact.

For all nine rules, V2 also requires a 64-seed familywise safety event and,
for each dataset, the ordinary one-sided 95% Clopper--Pearson upper bound, the
Bonferroni simultaneous component bound at `alpha=0.05/4`, the exact lower-tail
test of `H0: p >= 0.05`, and its within-rule four-dataset Holm adjustment.
Holm-adjusted values are tests, never confidence bounds. For the vector rule,
V2 requires a symmetric 4-by-4 within-seed violation co-occurrence matrix and
counts of seeds with zero through four violating datasets. The matrix diagonal
must equal the corresponding per-dataset event counts and the multiplicity
counts must sum to 64.

V2 also enforces reporting logic. Overall `pass` is legal only when all four
primary gates pass and `failed_gates` is empty. A failed or invalid gate must be
named in `failed_gates` and receive its own negative-result record. Historical
GaitPDB floor failure and the Camelyon17 support boundary are mandatory negative
or boundary records. The strong-title allocation condition is false whenever
either the registered allocation comparison or no-worse-safety condition is
false. Named provenance hashes are required for the receipt audit, locked
analyzer and output, protocol-compliant cap-8 analyzer and output, three-way cap
comparator, replay, sensitivities, ablations, diagnostics, allocation, schema,
and result builder.

V2 additionally requires the complete candidate-key correction crosswalk with
zero key-attributed scientific differences, 16 ordered ablation records rather
than an ablation count alone, the full GaitPDB diagnosis, the held-out boosted-
tree result, and the deterministic certificate-anatomy figure candidate. Each
record names its backing artifact hash. A provenance hash without the
corresponding scientific record is incomplete and fails schema validation.

The three-rule threshold stress must contain all 36 ordered
severity-by-rule-by-dataset rows, exact transformed thresholds, fixed
denominators, and its five-component supporting-readiness decision. A failed
supporting condition requires the negative result
`three_rule_threshold_stress_failed` and forbids a threshold-selected headline;
it does not change the registered four-gate primary decision.

`analysis_status=complete` requires all 1,280 official receipts, zero missing,
invalid, or proxy rows, both cap-8 paths, and the independent replay to pass.
`analysis_status=invalid` forces all four primary gates and the overall decision
to `invalid`; a global execution failure may never coexist with a displayed
primary pass.

Before real result generation, the schema must pass Draft 2020-12 meta-schema
validation, one complete legal fixture, and deliberate fixtures that omit a
sign-test denominator, use a vague per-dataset row, suppress a failed-gate
negative result, retain an illegal strong title, omit a cell top-up, omit a
named artifact hash, duplicate a dataset, or mark the overall result passed
while a gate fails. Additional fixtures must reject a wrong fixed denominator
and any attempt to let the zero-common sensitivity rescue the registered
point-ratio gate. The semantic validator must additionally reject wrong safety
alpha levels, asymmetric co-occurrence matrices, diagonal/event disagreement,
violation-multiplicity counts that do not sum to 64, overlapping or incomplete
ratio bootstrap cases, and any nonstandard representation of positive
infinity. A deliberate fixture must also reject an invalid global analysis that
retains passing primary gates.

## Required Identity Fields

The manifest must include:

- schema and release-format versions;
- controlled protocol, interpretation, receipt-audit, analyzer, replay,
  radius-cap-correction, candidate-key-correction, sensitivity-interpretation,
  safety-sensitivity, usefulness-sensitivity,
  ratio-sensitivity, three-rule-threshold-stress, ablation, GaitPDB,
  held-out-attacker,
  additive-allocation, and evidence-diagnostic hashes;
- runner and upstream implementation identifiers in the named private record;
- datasets, methods, candidates, seeds, profiles, budgets, thresholds,
  allocations, attackers, and independent-unit definition; and
- completion and validity counts for all 1,280 official receipts.

It must also contain the complete pre-outcome radius-cap correction record:
registered cap 8, original locked-analyzer cap 4, cap 8 as the scientific
authority, preservation of the unchanged cap-4 output, two passing independent
cap-8 paths, zero cap-independent mismatches, cap-dependent candidate/decision
counts, every primary-gate difference, and mandatory disclosure. A primary-gate
difference requires its own negative-result record.

The anonymous public view follows the double-blind boundary and may replace
author-linked transport identifiers with nonidentifying content identifiers.
Scientific fields and hashes may not change.

## Required Confirmatory Fields

For the declared primary profile, the manifest must record:

1. point-versus-vector seed-cluster violation-count effect, exact sign-test
   numerator, denominator, statistic, two-sided value, and interval;
2. rotating-sentinel VERA false-acceptance count, seed denominator, registered
   one-sided upper bound, and pass/fail decision;
3. exact shifted-law oracle-safe opportunity count, vector-retained count,
   whole-seed bootstrap interval, zero-opportunity resample counts, conservative
   completed-statistic and division-free sensitivity intervals, and 20%
   lower-bound pass/fail decision;
4. vector and common-radius safe-retention values, the registered ratio or
   explicit zero-denominator status, its frozen sensitivity results, and the
   twofold pass/fail decision; and
5. the overall intersection--union decision with the exact list of failed
   primary gates.

The primary safety field is the rotating sentinel. Seed-familywise and
per-dataset bounds are labeled sensitivity analyses and cannot replace it.

For each of the nine matched rules, the seed-familywise sensitivity is the
count of whole 64-seed clusters with at least one supported-dataset violation,
with an ordinary one-sided 95% Clopper--Pearson upper bound. For each of the
rule's four dataset rows, report both the ordinary one-sided 95% exact bound and
the Bonferroni simultaneous component bound at `alpha=0.0125`, plus the raw
exact lower-binomial-tail value and its Holm adjustment across those four
datasets. These supplementary fields must be emitted even for rules that are
unfavorable; undefined quantities use `null` and a reason code where the schema
permits them.

## Required Rule Table

For all nine matched deployment rules, aggregate and per-dataset records must
contain:

- decision and deployment counts;
- violation counts per all decisions and per deployments, each with explicit
  denominator;
- seed-cluster intervals for deployment and violation quantities;
- oracle-safe and retained-opportunity counts plus seed-cluster retention
  intervals;
- common-radius median, quartiles, censor count, and undefined status where the
  rule has no certificate;
- sentinel and seed-familywise safety fields where defined; and
- `null` plus a reason code rather than numeric zero for undefined quantities.

All rules must remain present even when they are unfavorable or never deploy.
The VERA vector rule must additionally populate the top-level four-dataset
co-occurrence matrix and zero-through-four multiplicity counts specified above.

The manifest must also contain the fixed three-rule stress at
`kappa={0.75,1,1.25}`. Each profile contains always-deploy, validation-point,
and vector-envelope rows in that order; each rule contains Waterbirds,
CivilComments-WILDS, Bios, and GaitPDB rows in that order. Thresholds are
derived exactly from `tau(kappa)=kappa*tau` and
`lambda(kappa)=0.5+kappa*(lambda-0.5)`. Each dataset row reports all-decision
and deployed-only violations, deployment, exact shifted-law opportunity,
retention, and whole-seed intervals with an all-decision denominator of 64.
The grid also records candidate, registered per-cell allocation, and
certification-stream manifest hashes and verifies that all severities reuse the
`kappa=1` objects rather than reallocating or redrawing evidence.

## Required Secondary and Diagnostic Fields

The manifest must contain complete cells for:

- all four supported datasets, five eraser families, 64 seeds, nine rules,
  three registered shift caps, four evidence budgets, and targeted and uniform
  allocations;
- all 16 registered ablations, including null and harmful effects;
- the complete three-rule threshold-stress grid and its non-rescuing supporting
  readiness decision;
- every registered attacker portfolio and the held-out boosted-tree stress;
- vector-coordinate axis intercepts, full coupled-envelope curve statistics
  from the independent replay, common radii, distinct common-radius limiting
  contracts, right-censoring, and deterministic Figure 1/result-panel candidate
  selection;
- GaitPDB limiting-contract and cell-level evidence diagnosis;
- uniform, locked square-score, and additive allocation objectives, safety,
  retention, continuous/integer gap, and title-retention decision;
- inverse evidence requirements, current counts, recommended integer counts,
  top-ups, cap censoring, and design-fold versus oracle-only provenance; and
- every protocol deviation, missing value, zero denominator, failed check, or
  excluded unsupported endpoint with a reason code.

The 20,000 whole-seed vector/common bootstrap resamples must be partitioned
exactly once among four cases: `(O>0,C>0)`, `(O>0,C=0,V>0)`,
`(O>0,C=0,V=0)`, and `(O=0,V=C=0)`. Their counts must sum to 20,000. A
positive-infinite endpoint in the extended-ratio interval is serialized only
as the JSON string `+infinity`; JSON non-finite numbers, clipping, or dropped
resamples are invalid. The division-free interval uses all resamples and stays
finite. Neither sensitivity may rescue the registered point-ratio gate.

No secondary result may be promoted into a primary field.

## Required Historical and Boundary Fields

The manifest must preserve the prior IID result as a separate record:

- validation-only selection: 35 violations among 128 decisions;
- fixed-profile certification: 1 violation among 128 decisions;
- fixed-profile safe retention: 52 among 102 oracle-safe opportunities; and
- failed GaitPDB baseline-severity condition: 5 violations among 32 decisions,
  below the registered 20% floor.

It must also record Camelyon17 as an unsupported-support boundary, excluded
from supported-shift efficacy and safety endpoints. It may not encode the
abstention as evidence that center 2 is safe or unsafe.

## Generated Text Interface

Every final venue wrapper must define fallback values for
`\VERAPaperPDFTitle`, `\VERAPaperDisplayTitle`, and `\VERAPaperPDFSubject`,
then load the shared TeX layer before constructing its title or PDF metadata.
The generated layer must renew all three commands from the manifest's locked
title branch. The evidence-efficient branch uses the strong title; every other
legal branch uses `VERA: Support-Aware Certification of Representation Edits
Under Deployment Shift` and its matching subject. The compiled title, source
title, PDF title metadata, PDF subject metadata, supplement title, and all
three venue variants must agree.

The TeX layer must define the same controlled-result commands for all three
venue variants:

- `\ControlledShiftAbstractResult`;
- `\ControlledPrimaryResult`;
- `\ControlledSafetyResult`;
- `\ControlledRetentionResult`;
- `\ControlledAllocationResult`;
- `\ControlledEvidenceResult`;
- `\ControlledGaitResult`;
- `\ControlledHeldoutResult`; and
- `\ControlledNegativeResults`.

Every venue body also exposes `\ControlledMainResultTable` and
`\ControlledMainResultFigure` immediately after the controlled safety and
usefulness paragraphs. The final venue wrapper must define those hooks from
the generated table and figure files before loading the body. The hooks remain
empty in outcome-blind syntax builds and may not be moved or conditionally
suppressed after result access.

The result table and figure are generated separately from the same JSON. Venue
sources may shorten prose for space, but every displayed number must originate
from a manifest field and retain its denominator, interval type, and primary or
secondary status.

The builder must also generate
`vera_controlled_shift_supplement_results.tex` from this manifest and the
hashed full-record artifacts named by it. That file is the supplement's only
controlled-result input and must include the complete family grid,
sensitivities, ablations, and diagnostics required below. Design-era files
`vera_family_grid_results.tex`, `vera_supplement_results.tex`,
`vera_ablation_results.tex`, and `vera_real_learning_curve.pdf` are prohibited
inputs even when they remain in a historical checkout.

Normalized candidate and decision records use the receipt-authoritative
`canonical_candidate_key`. The manifest must include the exact legacy
`RLACE::...` to canonical `R-LACE::...` crosswalk and separately count every
raw key spelling normalization. It must verify that the crosswalk preserves
the complete 12-key order and that candidate-key-attributed selection, row,
aggregate, and gate difference counts are all zero. It may not merge the raw
spelling count with radius-cap differences or silently rewrite the unchanged
cap-4 artifact.

## Abstract Branch and Title Lock

If all four controlled gates pass, the shared abstract sentence reports the
point-versus-vector effect, zero-observed wording plus the sentinel upper bound,
vector safe retention with its whole-seed interval, and vector/common result.
If any gate fails, it names the failed gate or gates, reports the observed
effect, and does not call the controlled claim confirmed. Zero observed events
must never be described as zero risk.
If the registered usefulness gate passes while the frozen zero-opportunity
sensitivity does not support the 20% target, every variant must name that
qualification; the sensitivity cannot change or rescue the registered gate.
Every variant must disclose the pre-outcome cap-4/cap-8 implementation
correction. If a primary decision or gate differs, it must report both outputs
and identify the preregistered cap-8 analysis as authoritative.

The memorable three-rule abstract sentence is legal only when the threshold-
stress supporting condition passes. It uses `kappa=1` only and must report the
validation-selection and VERA denominators plus registered safe retention. If
the supporting condition fails, every variant reports that negative result and
no supplementary severity may rescue the headline.

The title field is `evidence_efficient` only if both frozen conditions pass:

1. the final primary-source literature search finds no unaddressed collision;
   and
2. additive allocation improves both uniform and locked square-score under the
   registered empirical rule without worse safety.

Otherwise every variant uses the frozen support-aware fallback title.

## Cross-Variant Audit

The audit must extract every numeric string, result command, gate description,
title branch, and required negative-result marker from all three flattened
sources and compiled PDFs. It fails on:

- a scientific number absent from the JSON manifest;
- different values, denominators, interval descriptions, or pass/fail language
  for the same endpoint;
- a missing failed gate or negative result;
- a primary/secondary status mismatch;
- a title inconsistent with the locked title field;
- a source, rendered, supplement, or PDF-metadata title inconsistent with any
  other title surface;
- prose that calls a format-pending variant submission ready; or
- any controlled-result fallback text remaining in a final source or PDF.

## Pass Condition

This gate passes only when the JSON and TeX are generated from fully audited
outputs, the code-path-independent replay agrees, all required cells are
present, the cross-variant source and PDF audit passes, and a human verifier
checks the exact headline sentences against the manifest.
