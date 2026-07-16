# Controlled-Shift Sensitivity Interpretation 1

This interpretation was fixed during receipt generation and before any
candidate, decision, risk, radius, or aggregate outcome from seeds 45--108 was
viewed. It resolves two reporting ambiguities in the frozen supplementary
safety and vector/common ratio specifications. It changes no primary endpoint,
gate, random stream, threshold, shift, allocation, candidate, or rule.

## Dataset-Specific Safety

The phrase `simultaneous one-sided bounds formed with Holm's step-down
procedure` is replaced by two separate, fully specified objects:

1. For each rule and dataset, report the ordinary one-sided 95% exact
   Clopper--Pearson upper bound using `alpha=0.05`.
2. Report a conservative rectangular familywise 95% upper-confidence set over
   the four datasets by using one-sided Clopper--Pearson bounds with
   `alpha=0.05/4` for each dataset.
3. Separately test `H0: p >= 0.05` against `H1: p < 0.05` for each dataset.
   The exact raw value is the lower binomial tail at `p=0.05`; apply Holm's
   step-down adjustment to those four values within each rule.

The Bonferroni bounds are the simultaneous confidence statements. The
Holm-adjusted values are threshold tests and must not be called confidence
bounds. Both are supplementary and cannot replace the rotating-sentinel gate.
Report them for all nine matched rules so the main rule table and sensitivity
artifact cannot disagree by omission.

For the VERA vector rule, additionally report the symmetric 4-by-4 within-seed
violation co-occurrence matrix and the mutually exclusive counts of seeds with
zero, one, two, three, or four violating datasets. The matrix diagonal must
equal the corresponding per-dataset event count; the five multiplicity counts
must sum to 64.

## Vector/Common Bootstrap Cases

The four zero-denominator case counts are mutually exclusive and exhaustive:

1. `O > 0` and `C > 0`;
2. `O > 0`, `C = 0`, and `V > 0`;
3. `O > 0`, `C = 0`, and `V = 0`; and
4. `O = 0`, which requires `V = C = 0`.

They must sum to 20,000. A sample with `O=0` belongs only to case 4, not also
to the zero-common/zero-vector case. The extended-ratio percentile interval
must serialize a positive-infinite endpoint as the JSON string
`+infinity`; JSON `Infinity`, silent clipping, and dropping a resample are
forbidden. The division-free interval remains finite and uses all resamples.

## Required Validation

The shared manifest and its semantic validator must reject wrong alpha levels,
calling a Holm test a bound, overlapping or incomplete ratio cases, an
unserialized infinite endpoint, an asymmetric co-occurrence matrix, a diagonal
that disagrees with per-dataset events, or multiplicity counts that do not sum
to 64. Every sensitivity remains non-rescuing and must be reported whether
favorable or not.
