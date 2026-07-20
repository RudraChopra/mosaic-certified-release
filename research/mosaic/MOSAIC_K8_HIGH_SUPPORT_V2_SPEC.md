# MOSAIC K=8 high-support extension v2

## Status

This is a post-review, pre-outcome extension of the ACS natural geographic
shift study. It reuses the locked 2018 ACS stores with a fixed high-support
sampling cap. It is separate from the original 60-job confirmation and from
the v1 runner, which stopped before producing an outcome because an execution
dependency was absent.

## Question

The original $K=8$ ACS cells use at most 24,000 reference and bridge rows in
total, or 6,000 balanced rows per source--label stratum. This study asks a
direct question: for three locked employment transfers whose frozen stores
contain the required support, does increasing both certification tables to
16,000 rows per source--label stratum yield any nonconstant, certified $K=8$
release?

The intervention is deliberately empirical. The synthetic scaling curve shows
that confidence radii grow with the fine alphabet, but its 12,817-row value
belongs to a $K=64$ synthetic cell and is not used as a prediction for this
$K=8$ result.

## Locked jobs

- ACS employment, California to Florida, seed 1400.
- ACS employment, California to Illinois, seed 1400.
- ACS employment, California to New York, seed 1400.

Each target PUMA partition and the California reference-validation split
contains at least 16,000 rows in every required source--label stratum.

## Protocol

Each job uses 64,000 reference and 64,000 bridge rows, balanced over the four
source--label strata. The held-out diagnostic PUMA fold remains separate and
is capped at 24,000 rows. The runner evaluates identity plus all twelve
registered official INLP, LEACE, R-LACE, TaCo, and MANCE++ candidates with
eight fine tokens, two released tokens, source advantage $0.35$, and primary
utility threshold $\tau_U=0.40$. No candidate, threshold, or PUMA split is
selected after an outcome is observed.

## Reporting and boundary

Report all three jobs, all 39 candidate rows, every abstention, and every
diagnostic. This extension measures whether added support changes $K=8$
feasibility for these registered employment transfers. It does not change the
original all-task/all-state $K=8$ result into a universal claim.
