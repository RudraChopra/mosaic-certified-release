# MOSAIC K=8 high-support extension specification

## Status

This is a post-review, pre-outcome extension of the ACS natural geographic
shift study. It uses the already locked 2018 ACS stores but a new, fixed
high-support sampling cap. It is not part of the original 60-job confirmation.

## Question

The original $K=8$ cells use at most 24,000 bridge and reference rows in total,
or 6,000 rows per source--label stratum after balancing. The scaling curve
predicts that approximately 12,817 rows per stratum recover the corresponding
$K=4$ radius. Can a complete official frontier certify a nonconstant $K=8$
interface when both certification tables have 16,000 rows per stratum?

## Locked jobs

- ACS employment, California to Florida, seed 1400.
- ACS employment, California to Illinois, seed 1400.
- ACS employment, California to New York, seed 1400.

The three target PUMA partitions already contain at least 16,000 examples in
every bridge source--label stratum. The California reference validation split
also contains at least 16,000 examples in every required stratum.

## Protocol

Each job uses 64,000 reference and 64,000 bridge rows, balanced over the four
source--label strata. The held-out diagnostic PUMA fold remains separate and
is capped at 24,000 rows. Run identity plus all twelve registered official
INLP, LEACE, R-LACE, TaCo, and MANCE++ candidates with eight fine tokens, two
released tokens, source advantage 0.35, and the primary utility threshold
$\tau_U=0.40$. No candidate, threshold, or PUMA split is selected after an
outcome is observed.

## Reporting and boundary

Report all three jobs, all 39 candidate rows, every abstention, and every
diagnostic. This extension measures whether added support changes $K=8$
feasibility for these registered employment transfers. It does not turn the
original all-task/all-state $K=8$ abstention result into a universal claim.
