# Controlled-Shift Usefulness Zero-Denominator Sensitivity

This outcome-blind supplementary analysis was fixed after static review of the
locked analyzer and before aggregate access to seeds 45--108. It does not edit
the analyzer or change the registered safe-retention gate. It prevents
whole-seed bootstrap resamples with zero exact shifted-law opportunities from
disappearing silently.

## Shared Counts

Use the same 20,000 whole-seed bootstrap resamples and fixed random seed
2027071601 as the registered usefulness analysis. For each resample, let `O` be
the exact shifted-law oracle-safe opportunity count and `V` the number of those
opportunities safely retained by the VERA vector rule. Require `0 <= V <= O`;
any `V > O`, negative count, missing rule, or wrong resample count fails the
sensitivity.

Record separately:

1. the number of resamples with `O > 0`;
2. the number with `O = 0` and `V = 0`; and
3. the number with `O = 0` and `V > 0`, which must be zero.

These counts must sum to 20,000. The original locked-analyzer interval computed
from finite `V/O` values remains reported exactly as generated.

## Conservative Completed Statistic

Define

`R_0 = V / O` when `O > 0`, and `R_0 = 0` when `O = 0`.

Report the 2.5% and 97.5% percentile quantiles over all 20,000 values, without
dropping any resample. Assigning zero to a resample containing no opportunity is
a conservative evidence convention: that resample supplies no support for
positive safe retention. It is a sensitivity analysis, not a redefinition of
the population ratio estimand.

Also report the division-free margin

`D_0.20 = V - 0.20 O`

and its percentile interval over all resamples. This statistic is zero when
`O=0` and avoids division while directly comparing retained opportunities with
the registered 20% target.

## Reporting Boundary

The locked finite-only interval and its registered gate remain unchanged. The
completed-statistic and division-free intervals cannot rescue a failed primary
gate. If the registered gate passes but the `R_0` lower bound is below 0.20 or
the `D_0.20` lower bound is below zero, the discrepancy must be a
named negative or qualification record in the shared manifest and every venue
must avoid unconditional usefulness wording. If the full observed data have
`O=0`, safe retention is undefined and the registered usefulness gate fails.
