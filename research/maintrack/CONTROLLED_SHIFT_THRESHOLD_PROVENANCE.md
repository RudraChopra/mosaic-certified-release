# Controlled-Shift Threshold Provenance

This note records how the fixed dataset contracts used for seeds 45--108 were
chosen. It was written before aggregate access to any outcome from that seed
block. It changes no threshold, dataset, candidate, seed, attacker, shift,
allocation, endpoint, test, multiplicity rule, exclusion, or success gate.

## Original Design Step

The thresholds were selected on the completed seeds 5--12 block by
`research/scripts/design_vera_independent_stress_replication.py`. That block
was the original balanced confirmation and was explicitly reused only as
exploratory design data for the later disjoint protocols. The script searched
the declared Cartesian grid

- target-harm thresholds: `0.025, 0.05, 0.075, 0.10, 0.15, 0.20, 0.30, 0.40`;
- balanced-leakage thresholds: `0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85,
  0.90, 0.95, 0.975, 0.99`.

Within each dataset, the deterministic design rule first sought regimes with
zero certificate-selected external violations and at least 20% validation-point
violations on the eight design seeds. It then preferred a nonzero certified
deployment and used fixed tie-breaks based on point-only discordance, certified
deployment, safe retention, point deployment, and threshold order. The selected
operating points were:

| Dataset | Paired target-harm threshold | Balanced-leakage threshold |
| --- | ---: | ---: |
| Bios | 0.40 | 0.70 |
| CivilComments-WILDS | 0.075 | 0.80 |
| GaitPDB | 0.20 | 0.55 |
| Waterbirds | 0.10 | 0.90 |

The resulting design report has SHA-256
`c1facabe3059f94c0e5333c535574a216ceeada5cc97fa40ad6150da131e3889`.
The thresholds were then copied into the independently preregistered seeds
13--44 protocol, whose JSON has SHA-256
`348c2784ec8d6bc9cef3c8449dccd4a07c394f1e3b54f8231b7c9c88b52caad3`.
They were inherited unchanged by the controlled supported-shift protocol before
seeds 45--108 began.

## Interpretation Boundary

These thresholds are benchmark operating points chosen to make decision-rule
comparisons informative rather than all-pass or all-abstain. They are not
clinical tolerances, legal fairness standards, estimates of stakeholder
preferences, or evidence that one amount of leakage or harm is acceptable in a
real deployment. Their design-set selection can make naive selection look more
failure-prone than an arbitrary unselected operating point; the two disjoint
seed blocks test whether the rule comparison persists, but they do not turn the
thresholds into normative quantities.

Every reported rule uses exactly the same thresholds within a dataset, seed,
candidate frontier, and shift profile. The current primary endpoint does not
require the naive rule to cross a per-dataset severity floor. Fresh outcomes may
not change these operating points, and any threshold-sensitivity analysis must
be labeled secondary or exploratory.
