# MOSAIC K=8 high-support extension v3

## Status

This is a post-review, pre-outcome extension of the ACS natural geographic
shift study. It uses the same fixed high-support design as v2, after v2 stopped
before a candidate frontier or receipt because its Python 3.9 environment was
incompatible with the official LEACE package.

## Runtime preflight

Before locking, the runner must import the five official adapter entry points:
INLP, LEACE, R-LACE, TaCo, and MANCE++. The locked environment is the existing
Python 3.12 real-experiment runtime with its exact NumPy, SciPy,
scikit-learn, PyTorch, and tqdm versions recorded in the lock.

## Question

The original $K=8$ ACS cells use at most 24,000 reference and bridge rows in
total, or 6,000 balanced rows per source--label stratum. For three locked
employment transfers whose frozen stores contain the required support, does
increasing both certification tables to 16,000 rows per source--label stratum
yield any nonconstant, certified $K=8$ release?

This is a direct support intervention. The synthetic scaling curve shows that
confidence radii grow with the fine alphabet, but its 12,817-row value belongs
to a $K=64$ synthetic cell and is not used as a prediction for this $K=8$
result.

## Locked jobs and protocol

- ACS employment, California to Florida, seed 1400.
- ACS employment, California to Illinois, seed 1400.
- ACS employment, California to New York, seed 1400.

Each job uses 64,000 reference and 64,000 bridge rows, balanced over four
source--label strata. The held-out diagnostic PUMA fold remains separate and is
capped at 24,000 rows. The runner evaluates identity plus all twelve registered
official INLP, LEACE, R-LACE, TaCo, and MANCE++ candidates with eight fine
tokens, two released tokens, source advantage $0.35$, and primary utility
threshold $\tau_U=0.40$. No candidate, threshold, or PUMA split is selected
after an outcome is observed.

## Reporting and boundary

Report all three jobs, all 39 candidate rows, every abstention, and every
diagnostic. This extension tests whether added support changes $K=8$
feasibility for these registered employment transfers. It does not turn the
original all-task/all-state $K=8$ abstention result into a universal claim.
