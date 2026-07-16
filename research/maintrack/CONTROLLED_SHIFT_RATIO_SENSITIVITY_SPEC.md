# Controlled-Shift Vector/Common Ratio Sensitivity

This outcome-blind supplementary analysis was fixed before aggregate access to
seeds 45--108. It does not change the registered vector/common point-ratio gate
or the locked analyzer. It prevents bootstrap samples with zero common-rule
retention from disappearing silently.

## Shared Counts

For each whole-seed bootstrap sample, let `O` be the exact shifted-law
external-oracle-safe opportunity count, `V` the number of those opportunities
safely retained by the vector rule, and `C` the number safely retained by the
common-radius rule. The two retention rates share denominator `O`, so their
ratio is `V/C` whenever `C > 0`.

Use the same 20,000 whole-seed resamples and random seed 2027071601 as the
registered usefulness bootstrap. Record the counts of samples in each case:

1. `C > 0`;
2. `C = 0` and `V > 0`;
3. `C = 0` and `V = 0`; and
4. `O = 0`.

## Extended-Ratio Interval

For percentile reporting, define the bootstrap statistic as follows:

- `V/C` when `C > 0`;
- positive infinity when `C = 0` and `V > 0`; and
- zero when `C = 0` and `V = 0` or when `O = 0`.

Assigning zero to undefined zero-over-zero samples is conservative for a lower
advantage bound: such a sample contains no evidence that vector retention
exceeds common retention. Do not discard any sample. Report the 2.5% and 97.5%
extended-real quantiles, using `+infinity` explicitly when applicable, together
with the four case counts.

## Division-Free Twofold Contrast

Also compute

`D_2 = (V - 2 C) / O`

when `O > 0`, and set `D_2 = 0` when `O = 0`. Report its percentile interval
over all 20,000 resamples. A positive lower bound supports more-than-twofold
retention without dividing by a possibly zero common count. A nonpositive bound
does not alter the registered gate but must remain visible.

## Reporting Boundary

The locked analyzer's original finite-only ratio interval remains reported and
is labeled as such. The extended-ratio and `D_2` intervals are supplementary
sensitivity analyses. They cannot convert a registered point ratio below two
into a pass, replace a failed usefulness gate, or justify omitting zero-common
bootstrap samples.
