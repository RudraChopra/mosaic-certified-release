# Data-certified structured-shift bridge

## Scope

The original MOSAIC theorem guarantees a release for every deployment law in a
registered common-transform plus differential-contamination class. It does not
by itself establish that a natural deployment population belongs to that
class. The bridge certificate below turns a labeled bridge sample from the
deployment population into a finite-sample membership certificate. This is a
testable assumption, not a favorable benchmark diagnostic.

Fix a task label `y`. For each source `s`, let `p_s` be the reference fine-token
law and `q_s` the deployment fine-token law. Let `C_s` and `D_s` be simultaneous
multinomial L1 confidence sets for `p_s` and `q_s`. Write

```
h_s(w) = max_{p in C_s} p^T w,
l_s(z) = min_{q in D_s} q(z).
```

The bridge program chooses retained mass `t`, a source-blind stochastic
transform `T`, and `W=tT` by maximizing `t` subject to

```
W(c,z) >= 0,
sum_z W(c,z) = t                 for every c,
h_s(W(:,z)) <= l_s(z)            for every source s and token z,
0 <= t <= 1.
```

Each support constraint has an exact linear-program dual. For empirical center
`p_hat_s` and radius `rho_s`, introduce free `lambda`, free `mu`, and
nonnegative `gamma` such that

```
W(c,z) <= lambda(c) + mu,
|lambda(c)| <= gamma,
p_hat_s^T lambda + mu + rho_s gamma <= l_s(z).
```

Strong LP duality makes this formulation exact for the stated confidence set.

## Theorem 1: Adaptive finite-sample bridge membership

Suppose the reference and bridge confidence sets jointly cover every `p_s` and
`q_s` with probability at least `1-delta`. Let `(t_hat,W_hat)` be any feasible
solution of the bridge program, including the maximizer selected from the same
confidence tables. If `t_hat>0`, define `T_hat=W_hat/t_hat`. Then, on the joint
confidence event, simultaneously for every source,

```
q_s = t_hat p_s T_hat + (1-t_hat) r_s
```

for some probability vector `r_s`. Therefore the deployment experiment belongs
to the MOSAIC structured-shift class with the data-selected source-blind
transform `T_hat` and contamination `eta_hat=1-t_hat`. The statement holds
simultaneously across task labels when their confidence allocations are
included in the same joint event.

### Proof

On the joint event, `p_s` belongs to `C_s` and `q_s` belongs to `D_s`. For every
output token `z`, feasibility gives

```
q_s(z) >= l_s(z) >= h_s(W_hat(:,z)) >= p_s^T W_hat(:,z).
```

Thus `q_s-p_s W_hat` is coordinatewise nonnegative. Its coordinates sum to
`1-t_hat`, because `q_s` sums to one and every row of `W_hat` sums to
`t_hat`. If `t_hat<1`, normalize this difference by `1-t_hat` to obtain a
probability vector `r_s`; if `t_hat=1`, the difference is zero and any residual
law may be chosen. Because the implication is simultaneous for every feasible
`W`, selecting the optimizer from the same tables does not add a channel-count
correction. This proves the result.

## Proposition 1: Robust optimality

For the product confidence region `C_1 x ... x C_G x D_1 x ... x D_G`, the
bridge LP returns the largest retained mass for which one fixed source-blind
transform certifies the mixture decomposition uniformly over every law in the
region.

For fixed `(t,T)`, the decomposition exists for every `(p,q)` in the product
region if and only if `q_s(z)>=t(p_sT)(z)` for every source and coordinate. The
worst `p` and `q` separate, so this is equivalent to
`h_s(tT(:,z))<=l_s(z)`. Substituting `W=tT` gives exactly the bridge program.
The support dual is exact by finite-dimensional LP strong duality.

## Corollary 1: End-to-end external release certificate

Use the learned singleton transform family `{T_hat_y}` and contamination
`eta_hat_y=1-t_hat_y` in MOSAIC's transform-exact privacy and utility optimizer.
On the same joint event, every channel and decoder selected from the tables
satisfies its certified source-inference and worst-stratum utility contracts on
the deployment population. No extra multiplicity correction is needed for the
continuum release-channel search, bridge-transform optimization, registered
utility thresholds, or a finite set of released alphabet sizes. Separate
tokenizers or erasers still require their registered familywise allocation.

## Theorem 2: Missing-source impossibility

If a required bridge source-label stratum is unobserved, its honest multinomial
confidence region is the full simplex. Every coordinate lower bound is then
zero. For any `t>0` and any stochastic `T`, `p_sT` is a probability vector and
has at least one positive coordinate, contradicting
`0>=t(p_sT)(z)`. Hence the maximum certifiable retained mass is zero and the
contamination budget is one. The downstream no-free-lunch theorem then permits
only a fine-token-independent release under a nontrivial source-inference
contract. This formalizes the Camelyon17 abstention case rather than treating
missing support as evidence of safety.

## Interpretation and prior art boundary

The existence of a source-blind stochastic `T` is the classical Blackwell
garbling relation between finite statistical experiments. Approximate
comparison by Markov kernels and contamination neighborhoods are also
classical. The claimed addition is narrower: a finite-sample, simultaneous,
one-sided contamination certificate that selects the common garbling and its
largest certifiable retained mass from reference and bridge confidence tables,
then composes that same event with an adaptively optimized stochastic release
and task decoder. Testable learning under distribution shift motivates the
accept-or-abstain semantics but does not supply this finite-experiment bridge
program or the downstream source-inference certificate.
