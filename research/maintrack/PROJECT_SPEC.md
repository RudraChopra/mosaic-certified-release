# VERA Main-Track Project Spec

## Project

VERA is an evidence-efficient, support-aware edit-or-abstain protocol for
representation interventions under distribution shift. The project is a method
paper prepared for AAAI, ICLR, NeurIPS, and a later journal expansion.

## Core Claim

VERA does not claim to be a universal replacement for erasure methods such as
INLP, LEACE, RLACE, TaCo, SPLINCE, or MANCE++. Given identity and edited
representations for the same examples, it certifies paired target harm and
post-edit leakage for every deployment distribution in a declared bounded
reweighting class. It abstains when the evidence cannot support that deployment
contract. A finite-family testing layer is inherited from Learn Then Test style
risk control and is not itself a novelty claim.
Prospective evidence allocation minimizes the registered worst normalized
additive DKW slack across supported audit cells for a candidate chosen on an
independent design fold. The one-cell special case reduces to square scores; it
is not claimed to optimize power over the whole frontier or solve every possible
data-collection objective.

## Evidence Program

The package contains exact small-case enumeration, controlled simulations, a
200-run official-method confirmation, an 800-run disjoint-seed IID replication,
and a prospective 1,280-run controlled supported-shift study. The final study
uses 64 fresh seed clusters, four supported datasets, five official eraser
families, a registered four-attacker portfolio, and one held-out boosted-tree
stress attacker. Camelyon17 remains a separate support-impossibility case.

## Submission Boundary

The paper may claim shift-robust paired edit certification only if every locked
controlled-study gate passes. A failed gate remains failed and is disclosed.
The paper may not claim state-of-the-art erasure, universal removal, coverage
against unregistered attackers, or transfer to unsupported deployment support.
The finite-candidate validation test is inherited machinery, not the headline
contribution.
