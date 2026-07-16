# Controlled-Shift Safety Sensitivity Specification

This outcome-blind supplementary analysis was fixed before aggregate access to
seeds 45--108. It does not alter the preregistered rotating-sentinel endpoint,
cannot replace a failed primary gate, and must be reported whether favorable or
not. Primary violation labels use exact shifted finite-law expectations.

## Seed-Level Familywise Safety

For each of the 64 fresh seeds, define `any_vector_violation` to equal one when
the VERA vector-envelope rule deploys a contract-violating edit on at least one
of the four supported datasets, and zero otherwise. Abstention and safe
deployment both count as zero. Report:

1. the event count and rate over 64 independent seed clusters;
2. the one-sided 95% Clopper--Pearson upper bound on the probability that a new
   seed produces any supported-dataset false acceptance under this finite-law
   protocol;
3. the exact number and identity of datasets contributing to every event; and
4. the same quantities for point selection, IID LTT, generic scalar robust
   certification, fixed-profile VERA, and the common-radius rule.

This familywise cluster endpoint is deliberately stricter than the rotating
sentinel. It is supplementary because it was not the registered primary safety
gate.

## Dataset-Specific Safety

For each supported dataset and matched deployment rule, report the event count,
rate, and one-sided 95% Clopper--Pearson upper bound across the 64 seeds. Also
report simultaneous one-sided bounds formed with Holm's step-down procedure
over the four dataset-specific null tests. Do not describe an unadjusted bound
as simultaneous, and do not infer equality of event probabilities across
datasets.

## Concentration And Dependence

Report a 4-by-4 table of within-seed violation co-occurrence and the number of
seeds with zero, one, two, three, or four violating datasets. Dataset decisions
inside a seed are correlated and are never counted as 256 independent trials.
The rotating-sentinel AM--GM calculation remains the registered average-risk
gate; the familywise and per-dataset calculations are supplementary scope
checks.

## Failure Rule

Every nonzero event, upper bound above 0.05, and dataset concentration remains
visible. No secondary rule, evidence budget, allocation, threshold, or Gamma
may replace the primary `Gamma=1.1`, budget-4,000, targeted-allocation result.
If the registered sentinel passes while the familywise analysis is unfavorable,
the abstract must state the narrower average-sentinel claim and the limitation
must identify the concentration directly.
