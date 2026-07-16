# Evidence-Requirement Diagnostic: Interpretation 1

This outcome-blind interpretation makes
`EVIDENCE_REQUIREMENT_DIAGNOSTIC_SPEC.md` at SHA-256
`83b685c723c58d49ad48eb216aafd6e584b44ebb93f3d4644234b04421252239`
executable when total budget is itself the optimization output.

## Continuous Inverse-Budget Solver

Solve the stated convex program over real counts with the same coefficient,
margin-clamp, floor, confidence, SLSQP tolerance, analytic-Jacobian, version,
and fail-closed rules as
`ADDITIVE_ALLOCATION_EXTENSION_INTERPRETATION_1.md`. Initialize by doubling a
uniform integer budget from the registered 4,000-observation point until the
fixed-budget additive allocation has maximum normalized slack at most one, then
use that feasible allocation as the inverse-program start.

Require solver success, finite values, each contract slack at most
`1 + 1e-8`, floor error at most `1e-8`, and stationarity/constraint diagnostics
to be recorded. Right-censor the estimate if no feasible initialization exists
at total budget 1,000,000. Do not substitute a different margin, candidate,
threshold, confidence level, or solver after failure.

## Deterministic Integer Recommendation

Take the floor of every continuous count, respecting the integer floor. While
any contract has normalized slack above one, add one observation to the cell
that gives the largest decrease in the current maximum normalized contract
slack. Recompute all slacks after each addition and break equal decreases by the
stable cell key. Stop when all slacks are at most one or the total reaches
1,000,000.

This is a deterministic sufficient integer recommendation, not a claim of
global integer optimality. Report:

- the continuous lower bound on total evidence;
- the integer recommended total;
- their absolute and relative gap;
- the complete addition sequence hash;
- every final contract slack; and
- right-censoring or failure reason.

For the small exhaustive grid, report the gap from the true minimum feasible
integer total and allocation. A nonzero gap remains visible and narrows any
algorithmic optimality wording to the continuous program.

## Top-Up Relative To A Current Budget

For each current allocation, define a cell's top-up as the positive part of
`recommended_count - current_count`. Counts already exceeding the recommendation
are retained; they are not moved or treated as negative evidence. Starting from
the actual current counts, run the same one-observation greedy rule until every
slack is at most one. Report this operational top-up separately from the
from-scratch recommendation because an existing nonoptimal allocation can need
more total evidence than the continuous minimum.

The design-fold and oracle-only labels fixed in the base specification apply to
all continuous, integer, and operational top-up fields.
