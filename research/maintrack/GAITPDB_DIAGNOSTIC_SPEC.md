# GaitPDB Evidence Diagnosis

This diagnostic was specified before aggregate analysis of seeds 45--108. It
explains non-certification; it does not change the primary contracts or rescue
a failed confirmatory gate.

## Unit And Scope

The independent unit is the seed. Report all 12 registered candidates for each
of 64 fresh seeds at the locked GaitPDB contract, with no performance-based
candidate or seed exclusion. Candidate-level rows are descriptive and are not
counted as independent replicates.

## Required Candidate Fields

For every seed, candidate, allocation, budget, and registered `Gamma`, record:

1. point target harm and target threshold;
2. exact upper target-harm bound in each environment and its threshold margin;
3. each registered attacker's robust balanced leakage bound and margin;
4. each source-class recall bound, evidence count, induced density-ratio cap,
   and contribution to balanced leakage;
5. the held-out boosted-tree leakage as non-guaranteed stress evidence;
6. fixed-profile eligibility, vector-profile eligibility, common-radius
   eligibility, coordinate radii, and limiting coordinates;
7. exact shifted-law and 50,000-draw target/leakage values;
8. candidate correction `delta/12` and envelope correction divided by the full
   candidate-contract family;
9. the selected candidate under every matched deployment rule.

## Registered Contrasts

Report the locked 1,000, 2,000, 4,000, and 8,000 evidence budgets under uniform
and targeted allocation. The 8,000 row is the prespecified doubled-evidence
answer. Compare `Gamma` 1.0, 1.1, 1.25, and 1.5; one versus all target
environments; each single attacker versus the full portfolio; five
lowest-strength candidates versus all 12; exact discrete versus generic bounded
loss bounds; fixed vector profile versus common radius; and IID versus shifted
certification. Secondary contrasts never replace the primary 1.1/4,000/targeted
result.

## Limitation Attribution

Within each candidate, define a limiting contract as any bound whose
threshold-minus-bound margin is within `1e-12` of the minimum margin. Aggregate
limiting frequencies over seeds and report ties. Separately identify whether
the dominant limitation is target harm, a registered attacker, a source class,
candidate multiplicity, evidence scarcity, or the declared shift budget.
These are mathematical decompositions of the certificate, not causal claims
about Parkinson disease or clinical deployment.

## Evidence Requirement

For each currently oracle-safe candidate, compute two labeled quantities:

1. a theorem-level sufficient sample size from the registered DKW bound using
   its shifted-law contract margin; and
2. a plug-in exact requirement obtained by scaling the observed discrete cell
   proportions and finding the smallest integer count whose exact bound clears
   the threshold under the locked multiplicity allocation.

The plug-in value is a planning diagnostic, not a guarantee that future samples
retain the same proportions. Report right-censoring when the search cap is
reached and report impossible cases when the population margin is nonpositive.

## Required Outputs

- candidate-level machine-readable rows;
- a seed-cluster summary with confidence intervals;
- a limiting-coordinate frequency table;
- a safe-retention-versus-evidence curve;
- a targeted-versus-uniform evidence plot;
- a concise manuscript paragraph stating whether one attacker, one source
  class, target harm, multiplicity, sample size, or shift budget dominates;
- a receipt-backed answer to whether doubled evidence, prospective allocation,
  or the vector profile creates nonzero safe retention.
