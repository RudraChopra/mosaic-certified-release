# MOSAIC v2: Theorem-First Specification

**Working title:** *MOSAIC: Minimax-Optimized Source-Agnostic Invariant
Channels for Certifiable Representation Release under Shift*

**Status (July 18, 2026):** active theorem specification under adversarial
proof, collision, and usefulness testing. Nothing in this document is yet a
paper claim. The two earlier models are retained as negative controls.

## 1. Why the shift must occur before release

Let `S in [G]` be a source, `Y in [J]` a task label, and `C in [K]` a fine token
from a tokenizer fixed without the certification fold. A row-stochastic release
channel `M in Stoch(K,L)` produces the only public representation `Z`.

The external shift acts on `C` and must then pass through the same software
channel `M`. This matters. A constant-row channel mechanically releases no
input information, so a threat model that allows arbitrary source-specific
tokens to appear after `M` cannot support a faithful impossibility theorem for
software-enforced release.

For a fixed label, write `p_s(c)=P(C=c | S=s,Y=y)`. The balanced accuracy of the
best arbitrary source attacker on released tokens is

`A(P,M) = G^{-1} sum_z max_s (p_s M)(z)`.

The normalized advantage is `Adv(P,M)=(G A(P,M)-1)/(G-1)`. It is zero at chance
and one at perfect source recovery. No probe class is involved.

## 2. One confidence event covers every selected stochastic channel

For empirical laws `p_hat_s` and simultaneous multinomial radii `epsilon_s`,
define the event

`E = {for all supported (s,y), ||p_hat_s-p_s||_1 <= epsilon_s}`.

The radii may come from an exact multinomial method or a valid concentration
inequality with failure probability allocated across every prespecified
source-label stratum. Counts may be conditioned on. A zero-count stratum uses
the full simplex (`epsilon=2`); a deployment contract that requires nontrivial
task utility will normally abstain there.

For example, choose fixed allocations `delta_sy` with
`sum_{s,y} delta_sy <= delta_ref`. Conditional on a positive stratum count
`n_sy`, the Weissman radius

`epsilon_sy = min{2, sqrt(2 log((2^K-2)/delta_sy)/n_sy)}`

gives `P(E) >= 1-delta_ref` by a union bound. For `n_sy=0`, setting
`epsilon_sy=2` covers the simplex deterministically and consumes no failure
probability. The guarantee is conditional on a tokenizer and fine alphabet
fixed without this certification table; learning those objects on the same
observations is outside Theorem 1.

For a bounded vector `v`, define the exact support function

`Phi(p_hat,epsilon;v) = max_{p in Delta_K, ||p-p_hat||_1<=epsilon} p^T v`.

It is computed exactly by moving at most `epsilon/2` mass from the smallest
coordinates of `v` to the largest. Equivalently, it is the linear-program dual

`min_{nu,lambda,theta} nu + p_hat^T theta + epsilon lambda`

subject to `nu+theta_c >= v_c`, `-lambda <= theta_c <= lambda`, and
`lambda>=0`.

For attacker assignment `a in [G]^L`, let

`v_{M,a,s}(c) = sum_z M(c,z) 1{a(z)=s}`.

Define

`Abar(P_hat,M) = G^{-1} max_{a in [G]^L}`
`                  sum_s Phi(p_hat_s,epsilon_s;v_{M,a,s})`.

**Theorem 1 (exact adaptive universal-attacker envelope).** On `E`,
simultaneously for every stochastic release channel `M`, including one chosen
as an arbitrary function of the same certification table,

`A(P,M) <= Abar(P_hat,M)`.

For each fixed `M`, `Abar` is exactly the supremum of `A(P,M)` over the product
of the stated fine-token L1 balls. Therefore selecting among finitely many,
countably many, or an uncountable continuum of channels needs no
channel-family multiplicity correction.

**Proof.** Every optimal finite-alphabet attacker is deterministic. Hence

`A(P,M)=G^{-1} max_a sum_s p_s^T v_{M,a,s}`.

For fixed `a`, the source confidence sets separate, and each inner maximum is
`Phi`. The assignment family is finite, so the maxima commute. On `E`, the true
laws lie in the balls. The implication holds pointwise for every row-stochastic
matrix, hence also for a data-selected matrix. QED.

## 3. The release channel's exact differential-shift capacity

Define the `G`-source leakage capacity of `M` by

`Cap_G(M) = G^{-1} max_{a in [G]^L} sum_s max_c v_{M,a,s}(c)`.

**Lemma 2 (exact arbitrary-shift capacity).**

`Cap_G(M) = sup_{r_1,...,r_G in Delta_K} A(R,M)`.

**Proof.** Expand `A(R,M)` using attacker assignments. For fixed `a`, each
source law can place all mass on a fine token maximizing `v_{M,a,s}`. The
finite maxima commute. QED.

For two sources,

`2 Cap_2(M)-1 = alpha(M)`

where `alpha(M)=max_{c,c'} TV(M(c,.),M(c',.))` is the Dobrushin contraction
coefficient. Thus the capacity is computable from channel rows without data.

## 4. Invariance to common pre-release drift

Let `T` be a row-stochastic channel on fine tokens representing a source-blind
deployment transformation before release. Define the release-invariance defect

`rho_T(M) = max_c TV((T M)(c,.),M(c,.))`,

and for a prespecified uncertainty set `Tset`,

`rho_Tset(M)=sup_{T in Tset} rho_T(M)`.

For a finite library, or the convex hull of a finite library, the supremum is
attained by a listed extreme channel. The defect is zero exactly when every
allowed common transformation is absorbed by the release channel (`T M=M`).

**Lemma 3 (approximate invariance transfer).** For every source experiment `P`,

`A(P,T M) <= min{Cap_G(M), A(P,M)+rho_T(M)}`.

**Proof.** For any attacker, changing `p_s M` to `p_s T M` changes source `s`'s
correct-decision probability by at most their total variation distance. By
convexity of total variation,

`TV(p_s T M,p_s M) <= sum_c p_s(c) TV((T M)(c,.),M(c,.)) <= rho_T(M)`.

Average over sources and optimize the attacker. The capacity bound follows
from Lemma 2. QED.

## 5. Main external-shift theorem

For every label `y`, assume the external fine-token laws have the decomposition

`q_s = t_y p_s T_y + (1-t_y) r_s`,

where `t_y >= 1-eta_y`, the same `T_y in Tset_y` and retained mass `t_y` apply
to every source, and each residual `r_s` is otherwise arbitrary. This separates
large source-blind drift from a bounded fraction of differential drift without
allowing either component to bypass `M`.

Let

`B_y(M)=min{Cap_G(M), Abar_y(P_hat,M)+rho_Tset_y(M)}`.

For a balanced-accuracy scalar `b`, write
`Adv_G(b)=(G b-1)/(G-1)`.

**Theorem 4 (post-selection-safe pre-release coupled-shift certificate).** On
the same event `E`, simultaneously for every adaptively selected stochastic
channel `M` and every external experiment satisfying the decomposition,

`A(Q,M) <= (1-eta_y) B_y(M) + eta_y Cap_G(M)`.

Equivalently, after the affine normalization,

`Adv(Q,M) <= (1-eta_y) Adv_G(B_y(M))`
`              + eta_y Adv_G(Cap_G(M))`.

**Proof.** Balanced Bayes accuracy is convex in the source experiment. Lemma 3
bounds the retained common component by `B_y(M)` and Lemma 2 bounds every
differential residual by `Cap_G(M)`. Since `B_y(M)<=Cap_G(M)`, the upper bound
is largest over `t_y>=1-eta_y` at `t_y=1-eta_y`. Theorem 1 permits replacement
of the unknown reference accuracy by its adaptive confidence envelope. QED.

This theorem has two useful limits. If `eta_y=0` and `T_y M=M`, the external
certificate equals the reference certificate despite arbitrarily large common
drift inside `Tset_y`. If `eta_y=1`, the exact worst-case certificate is the
channel capacity rather than the vacuous value one.

### Exact population risk used to falsify the certificate

The certificate above need not be tight because `rho` separates a total-
variation comparison from the attacker optimization. For a known reference
population, however, the exact worst external risk in the stated model is a
finite expression. If `Tset_y` is the convex hull of listed extremes, then

`R^*_y(M) = G^{-1} max_{T in ext(Tset_y)} max_{a in [G]^L}`
`             sum_s [(1-eta_y) p_sy^T T v_{M,a,s}`
`                    + eta_y max_c v_{M,a,s}(c)]`.

This follows by expanding the deterministic-attacker representation. For fixed
`T` and `a`, every residual law concentrates on a maximizing fine token. The
residual term is at least the common term source by source, so the supremum over
all retained masses `t_y >= 1-eta_y` occurs at `t_y=1-eta_y`. The objective is a
maximum of linear functions of `T`, so a convex-hull maximum is attained at a
listed extreme. This identity is not the deployable certificate: it requires
the unknown population laws. It is the independent ground-truth quantity used
to count false acceptances in synthetic experiments.

## 6. Utility is certified under the same event

Fix a decoder `g:[L]->[J]`, which may be selected jointly with `M`. For label
`y`, let `ell_y(z)=1{g(z)!=y}` and `u_y(c)=(M ell_y)(c)`. Define

`Ebar_{s,y}(M,g)=Phi(p_hat_{s,y},epsilon_{s,y};u_y)`,

the directional common-shift defect

`kappa_y(M,g)=sup_{T in Tset_y} max{0, max_c ((T M-M)ell_y)(c)}`,

and the differential-shift error capacity

`U_y(M,g)=max_c (M ell_y)(c)`.

**Corollary 5 (adaptive shifted-utility certificate).** On `E`, the external
conditional task error satisfies

`Err_{s,y}(Q,M,g) <= (1-eta_y) D_{s,y}(M,g)+eta_y U_y(M,g)`,

where

`D_{s,y}(M,g)=min{U_y(M,g),Ebar_{s,y}(M,g)+kappa_y(M,g)}`.

The proof repeats Theorem 4 for the bounded loss `ell_y`. Thus the tokenizer's
release channel, its decoder, privacy, and diagnostic utility can be selected
on one certification table under one simultaneous event.

With known population laws, the matching exact external utility risk is

`R^*_{s,y}(M,g) = max_{T in ext(Tset_y)}`
`  [(1-eta_y) p_sy^T T M ell_y + eta_y max_c (M ell_y)(c)]`.

The separately implemented synthetic evaluator enumerates these extremes and
does not reuse either certificate formula.

## 7. A sharp no-free-lunch boundary

**Theorem 6 (unrestricted differential shift forces a zero-capacity release).**
For any `G>=2`, `Cap_G(M)=1/G` if and only if every row of `M` is identical.
Therefore exact source erasure under arbitrary source-specific pre-release
shift is possible only when the public representation is independent of the
fine token.

**Proof.** Identical rows make every released source law identical. Conversely,
if two rows differ, choose two source residuals concentrated on those rows and
the remaining residuals on either row. Uniform-prior Bayes accuracy is strictly
above chance whenever the source laws are not all identical. Lemma 2 completes
the claim. QED.

For two sources, suppose fine tokens `c_0,c_1` carry different task labels and
a decoder has row-wise errors at most `e_0,e_1`. The decoder's decision event
has probability at least `1-e_0` under `M(c_0,.)` and at most `e_1` under
`M(c_1,.)`. Hence

`2 Cap_2(M)-1 = alpha(M) >= 1-e_0-e_1`.

In particular, row-wise task error at most `e` forces worst-case differential
source advantage at least `1-2e`. This is the quantitative reason a bounded
`eta` assumption is necessary rather than cosmetic.

An unsupported stratum does not logically force privacy abstention: `Cap_G(M)`
remains distribution-free. It does prevent a nontrivial data-derived utility
claim unless the task is guaranteed mechanically by the channel. MOSAIC must
return `ABSTAIN_NO_FEASIBLE_CHANNEL`, with unsupported utility recorded as the
reason, whenever its full privacy-and-utility deployment contract cannot be
proved from those worst-case quantities.

## 8. Optimization consequence

For fixed output size, fixed decoder, a finite extreme-channel library `Tset`,
and fixed radii:

- `Abar(P_hat,M)` is convex and piecewise linear in `M`;
- `Cap_G(M)` is convex and piecewise linear;
- `rho_Tset(M)`, `kappa_y(M,g)`, and `U_y(M,g)` are convex and piecewise linear;
- every `Phi` term has the linear-program dual in Section 2.

Therefore each branch obtained by choosing the capacity bound or the
coupled-shift bound is a finite linear program after epigraph expansion. The
implementation uses binary variables to choose these branches in one exact
mixed-integer linear program for each decoder assignment, then enumerates the
finite decoder family. Subject to the solver's optimality certificate, this
selects the globally best worst-stratum certified utility for the stated finite
problem. Theorem 4 and Corollary 5 continue to cover that selection.
Failure of every branch to satisfy the registered privacy and utility contract
returns `ABSTAIN_NO_FEASIBLE_CHANNEL`.

More precisely, global optimality is asserted only when the output alphabet,
finite transform extremes, and decoder family are all completely enumerated;
the requested relative MIP gap is zero; the solver reports a gap at numerical
zero; primal constraints pass a direct residual check; and the objective agrees
with independently recomputed privacy and utility certificates. A timeout,
nonzero gap, oversized attacker family, or post-hoc mismatch is not a global
solution and cannot produce a deployment. The implementation records the MIP
gap, dual bound, maximum constraint violation, and post-hoc certificates.

The optimization claim is tested against exhaustive channel grids on small
alphabets and a constructed case in which a stochastic channel strictly
outperforms every deterministic channel. Those numerical checks support the
encoding; they do not replace the algebraic proof or an independent review.

### 8.1 A finite-sample abstention envelope

Let `V(P,e)` denote the globally optimal certified worst conditional error when
the confidence balls are centered at table `P` with common radius `e`, while
all privacy constraints and the registered shift model remain fixed. Let
`e_n` be the deployed simultaneous radius and define

`r_n^* = sup{r>=0 : V(P,e_n+r) <= tau_U}`.

**Proposition 7 (concentration upper envelope on abstention).** With `H`
prespecified source-label strata of size `n` and a `K`-token alphabet,

`P(MOSAIC abstains) <= min{1, H(2^K-2) exp(-n (r_n^*)^2/2)}`.

**Proof.** If every empirical stratum is within L1 distance `r` of its
population law, every radius-`e_n` ball around the empirical law is contained
in the radius-`e_n+r` ball around the population law. Any channel-decoder pair
feasible for the latter problem is therefore feasible for the empirical
problem. For every `r<r_n^*`, this forces the empirical optimum below `tau_U`.
Apply the Weissman inequality in each stratum, take a union bound, and let
`r` increase to `r_n^*`. QED.

This envelope is a finite-sample guarantee, but it can be deliberately loose
near the deployment boundary because it protects every direction in every
fine-table confidence ball.

### 8.2 A preregistered local power curve

For fixed `n`, write `V_n(P)=V(P,e_n)`. Suppose the optimal decoder and MILP
branches are locally unique and the resulting parametric LP satisfies the
standard nondegeneracy and strong-regularity conditions at the population
table. Then its value is differentiable there. If `h_sy` is the gradient in
stratum `(s,y)` and

`Sigma_sy = diag(p_sy)-p_sy p_sy^T`,

define `sigma_n^2=sum_sy h_{n,sy}^T Sigma_sy h_{n,sy}`.

**Proposition 8 (local deployment-power law).** Consider a sequence of the
registered stratified experiments for which the regularity conditions above
hold, `h_{n,sy}` converges to `h_sy`, `sigma^2=sum_sy h_sy^T Sigma_sy h_sy>0`,
and `sqrt(n)(tau_U-V_n(P))` converges to `b` in the extended real line. Then

`P(MOSAIC deploys) -> NormalCDF(b/sigma)`.

**Proof.** The independent stratified multinomial central limit theorem gives
a block-diagonal Gaussian limit for `sqrt(n)(P_hat-P)`. Strong regularity and
the assumed local uniqueness give the first-order expansion of the parametric
optimum with gradients `h_{n,sy}`. The triangular-array delta method therefore
gives `sqrt(n)(V_n(P_hat)-V_n(P)) -> Normal(0,sigma^2)`. Rearranging the event
`V_n(P_hat)<=tau_U` proves the result, with the usual zero and one limits when
`b` is infinite. QED.

The finite-`n` curve used as a preregistered prediction substitutes the locked
population value and numerical gradient into

`P(MOSAIC deploys) approximately`
`  NormalCDF((tau_U-V_n(P))/sqrt(n^{-1} sum_sy h_sy^T Sigma_sy h_sy))`.

The confirmation protocol computes `h_sy` by centered simplex-preserving
finite differences at two step sizes before reading any confirmatory outcome.
Agreement of those gradients is a locked local-sensitivity diagnostic. If a
tie, basis change, or numerical instability makes the diagnostic fail, the
Gaussian curve is rejected; the finite-sample certificates and Proposition 7
remain valid. This local curve is a falsifiable power prediction, not a coverage
theorem.

## 9. What is assumed versus statistically certified

The reference confidence event certifies uncertainty in `p_sy`. It does not
show that a real deployment belongs to the common-transform-plus-contamination
class. There are only two legitimate ways to use `Tset_y` and `eta_y`:

1. treat them as an explicit engineering or regulatory deployment
   specification and state the guarantee conditionally; or
2. construct a membership event `F` from separate bridge data, with
   `P(F)>=1-delta_shift`, and include the bridge procedure in the protocol.

In the second case the end-to-end probability is at least
`1-delta_ref-delta_shift` by a union bound on `E intersect F`. Independence is
not required for that union bound, but every data-dependent set and allocation
must be fixed by the bridge procedure before external labels are inspected.
Benchmark performance outside a proved membership event is stress evidence,
not certificate coverage.

## 10. Honest novelty target

The foundational ingredients are classical and must be cited: Blackwell
experiments, Bayes accuracy, Dobrushin contraction, contamination models,
randomized channels, robust optimization, multinomial confidence regions, and
Learn Then Test-style abstention.

The provisional contribution is the combination of:

1. an exact finite-sample envelope for every downstream attacker after an
   adaptively optimized stochastic representation release;
2. a pre-release shift decomposition with a computable invariance defect and
   exact differential-shift channel capacity;
3. a globally solvable piecewise-linear optimization of shifted privacy and
   utility on the same certification event; and
4. a matching no-free-lunch theorem that quantitatively links task utility to
   unavoidable leakage under unrestricted differential shift.

This target survives only if the primary-source collision review finds no
equivalent result and fresh experiments show materially better certified safe
utility than fixed-channel, deterministic, validation-only, LTT, FARE-style,
and independent-shift baselines.
