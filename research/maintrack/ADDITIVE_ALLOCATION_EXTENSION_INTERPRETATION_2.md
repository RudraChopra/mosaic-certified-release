# Additive Allocation Extension: Interpretation 2

This outcome-blind addendum strengthens numerical optimality verification for
the already-frozen additive and inverse-budget programs. It does not change
their objectives, coefficients, margins, floors, budgets, streams, comparisons,
or title rule.

## Fixed-Budget Dual Certificate

For coefficients `a_jc`, floors `ell_c`, and total budget `N`, the primal is

`minimize max_j sum_c a_jc / sqrt(n_c)`

subject to `sum_c n_c = N` and `n_c >= ell_c`.

For any contract weights `mu_j >= 0` with `sum_j mu_j = 1` and any `nu > 0`,
put `A_c = sum_j mu_j a_jc` and

`n_c_dual = max(ell_c, (A_c / (2 nu))^(2/3))`,

using `n_c_dual = ell_c` when `A_c = 0`. The value

`g(mu, nu) = sum_c [A_c / sqrt(n_c_dual) + nu n_c_dual] - nu N`

is a valid dual lower bound on the continuous primal optimum. Maximize this
concave dual deterministically over the simplex and positive `nu`, using at
least the uniform contract weights, each simplex vertex, and the recovered
primal-active weights as fixed starts. Every feasible dual iterate is a valid
bound even if the dual optimizer stops early.

For every real row, record the primal objective recomputed from the returned
counts, best feasible dual lower bound, absolute and relative primal--dual gap,
active contracts, active floors, contract multipliers, `nu`, stationarity
residual, primal feasibility residual, complementarity residual, and all dual
solver diagnostics. Require the dual lower bound not to exceed the primal by
more than `1e-9` numerical tolerance and the absolute gap to be at most
`1e-8 * max(1, abs(primal))`. A failed or nonfinite check fails the row; it does
not trigger another unregistered allocation.

## Inverse-Budget Dual Certificate

For the inverse program

`minimize sum_c n_c`

subject to `sum_c a_jc / sqrt(n_c) <= 1` and `n_c >= ell_c`, let any
`mu_j >= 0`, set `A_c = sum_j mu_j a_jc`, and define

`n_c_dual = max(ell_c, (A_c / 2)^(2/3))`,

again using the floor when `A_c = 0`. Then

`g_inverse(mu) = sum_c [A_c / sqrt(n_c_dual) + n_c_dual] - sum_j mu_j`

is a valid lower bound on the continuous minimum evidence. Maximize it from the
same deterministic contract-weight starts. Record the same primal, dual,
stationarity, feasibility, complementarity, and gap diagnostics and apply the
same fail-closed gap tolerance before integer recommendation or top-up.

The continuous optimum is a lower bound on the deterministic integer
recommendation. The integer recommendation remains a sufficient greedy result,
not a global integer-optimality claim.

## Jacobian and Scaling Checks

Before real analysis:

1. compare every analytic primal and dual gradient with central finite
   differences on deterministic interior fixtures;
2. require the one-contract no-floor primal and dual values to match the
   two-thirds-power formula;
3. require the one-cell-per-contract values to match square-score allocation;
4. verify zero-coefficient cells, active floors, tied active contracts, nearly
   clamped margins, and the exact-budget boundary;
5. multiply all coefficients by fixed positive constants and require the
   fixed-budget counts to remain unchanged while its primal and dual values
   scale by the same constant; on no-floor inverse fixtures, require counts and
   primal/dual values to scale by the square of that constant, and on floored
   inverse fixtures verify the transformed problem directly rather than claim
   a simple scaling law;
6. permute contracts and cells and require keyed counts, objectives, dual
   bounds, and active sets to agree; and
7. deliberately corrupt a multiplier, gradient, floor, budget, coefficient,
   primal objective, dual value, or tolerance and require failure.

The small exhaustive integer tests from Interpretation 1 remain mandatory and
separate: dual equality certifies the continuous convex program, while grid
comparison characterizes deterministic rounding.

## Claim Boundary

A small primal--dual gap supports numerical solution of the stated DKW-surrogate
program only. It does not establish that the surrogate is the unique or
universally optimal data-collection objective, that plug-in margins are true,
that integer rounding is globally optimal, or that the additive extension can
replace a failed locked primary result.
