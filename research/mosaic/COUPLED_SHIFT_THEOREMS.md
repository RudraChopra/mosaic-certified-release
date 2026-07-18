# MOSAIC Replacement Theorems: Adaptive Channels under Coupled Shift

> **Superseded intermediate model (July 18, 2026).** The finite-sample
> adaptive-channel envelope in this document remains mathematically useful,
> but the deployment model applies differential contamination after release.
> That abstraction is too loose for a fixed software release mechanism and led
> to an overbroad unsupported-stratum claim. It is retained as an audit trail,
> not as the proposed method. The active pre-release theorem is
> [PRE_RELEASE_SHIFT_THEOREMS.md](PRE_RELEASE_SHIFT_THEOREMS.md).

**Working title:** *MOSAIC: Post-Selection-Safe Universal Source Erasure under
Coupled Deployment Shift*

**Status (July 18, 2026):** theorem specification under active falsification.
Nothing in this document is a publication claim. The earlier independent
likelihood-ratio shift model remains useful as a negative control, but it is not
the proposed method: even perfectly source-independent reference tokens can
acquire attacker advantage `1 - 1/Gamma` under independently chosen shifts.

## 1. Setting and threat model

Let `S in [G]` be a source (hospital, scanner, site, or acquisition pipeline),
`Y in [J]` a task label, and `C in [K]` a fine token produced by a tokenizer
trained without the certification fold. For each supported stratum, write

`p_{s,y}(c) = P(C=c | S=s,Y=y)`.

A **release channel** `M in Stoch(K,L)` maps a fine token to a released token
`Z in [L]`. Deterministic token merging is the special case in which every row
of `M` is one-hot. Crucially, `M` may be chosen after inspecting the
certification contingency table, but the fine tokenizer may not be retrained on
that fold.

For an arbitrary attacker `h:[L]->[G]`, define conditional balanced source
accuracy

`BA_y(h;P,M) = G^{-1} sum_s P(h(Z)=s | S=s,Y=y)`.

Its optimum is normalized to an advantage in `[0,1]` by

`Adv_y^*(P,M) = (G sup_h BA_y(h;P,M)-1)/(G-1)`.

This threat model includes every measurable attacker on the released alphabet;
it does not depend on a probe class.

## 2. Exact support function of a multinomial L1 ball

For an empirical distribution `p_hat`, radius `epsilon in [0,2]`, and bounded
score vector `v in [0,1]^K`, define

`Phi(p_hat,epsilon;v) = max { p^T v : p in Delta_K, ||p-p_hat||_1 <= epsilon }`.

**Lemma 1 (water-filling support).** `Phi` is obtained by moving at most
`epsilon/2` probability mass from the smallest coordinates of `v` to the
largest coordinates of `v`, respecting donor mass and receiver capacity. The
greedy two-pointer algorithm is exact.

**Proof.** Write `p-p_hat=d^+-d^-`, where `d^+,d^- >= 0`, their supports may be
made disjoint, and `1^T d^+=1^T d^- <= epsilon/2`. The objective increment is
`v^T d^+-v^T d^-`. Any feasible transfer from a larger-score donor while a
smaller-score donor has mass, or into a smaller-score receiver while a
larger-score receiver has capacity, can be exchanged without reducing
feasibility and weakly increases the objective. Repeating the exchange yields
the stated greedy transport. The resulting transport is feasible and therefore
attains the upper bound. QED.

## 3. Exact adaptive-channel certificate

For each supported `(s,y)`, let `p_hat_{s,y}` be the empirical fine-token law
from `n_{s,y}>0` certification observations. Choose radii so that

`Pr(E) >= 1-delta`, where

`E = {for every supported (s,y), ||p_hat_{s,y}-p_{s,y}||_1 <= epsilon_{s,y}}`.

One valid construction allocates failure probability across the supported
strata and applies the Weissman multinomial inequality conditional on the
observed stratum counts. A zero-count stratum forces abstention.

For channel `M` and attacker assignment `a in [G]^L`, define the soft
correct-decision vector

`v_{M,a,s}(c) = sum_z M(c,z) 1{a(z)=s}`.

Define

`Abar_y(M) = G^{-1} max_{a in [G]^L}`
`             sum_s Phi(p_hat_{s,y},epsilon_{s,y};v_{M,a,s})`,

and `Advbar_y(M)=(G Abar_y(M)-1)/(G-1)`.

**Theorem 1 (exact post-selection-safe universal attacker envelope).** On event
`E`, simultaneously for every label `y`, every stochastic release channel
`M in Stoch(K,L)` of every finite output size covered by the computation, and
every attacker `h:[L]->[G]`,

`BA_y(h;P,M) <= Abar_y(M)`.

Moreover, for fixed empirical distributions, radii, and `M`, `Abar_y(M)` is the
exact supremum of optimal balanced source accuracy over the product of the
stated L1 balls. Consequently, a channel selected as an arbitrary function of
the same certification table remains covered. There is no candidate-count or
partition-count correction.

**Proof.** For fixed source laws and channel,

`sup_h BA_y(h;P,M)`
` = G^{-1} sum_z max_s (p_{s,y} M)(z)`
` = G^{-1} max_{a in [G]^L} sum_s p_{s,y}^T v_{M,a,s}`.

The assignment family is finite, so supremum and maximum commute. The source
laws vary independently inside their L1 balls, so the inner supremum separates
over `s`; Lemma 1 gives each exact term. This proves exactness for every fixed
`M`. On `E`, the true laws belong to the balls. Because the deterministic
implication was established for all stochastic matrices at once, it also holds
for a matrix selected after observing the table. QED.

This theorem is stronger than contraction-only coarsening: it covers the
uncountable family of randomized channels and computes the exact fine-ball
support rather than replacing it with a generally larger coarse confidence
ball.

## 4. Coupled deployment shift

Independent source-specific shift sets are too pessimistic for erasure. Instead,
MOSAIC separates arbitrary **source-blind drift** from bounded
**source-specific drift**.

For a selected release channel `M`, an external conditional experiment belongs
to `C_eta(P,M)` when, for every label `y`, there exist

- a retained common mass `t_y >= 1-eta_y`;
- one Markov kernel `T_y` shared by every source; and
- arbitrary source-specific distributions `r_{s,y}`

such that

`q_{s,y} = t_y (p_{s,y} M) T_y + (1-t_y) r_{s,y}`.

The common channel can be arbitrarily severe and may create new token support.
Only the fraction allowed to behave differently by source is bounded.

**Theorem 2 (coupled-shift transfer).** On the same event `E`, simultaneously
for every selected `M`, every `eta_y in [0,1]`, every external experiment in
`C_eta(P,M)`, and every external token attacker,

`A_y^*(Q) <= (1-eta_y) Abar_y(M) + eta_y`,

or equivalently,

`Adv_y^*(Q) <= (1-eta_y) Advbar_y(M) + eta_y`.

The bound is minimax sharp when the deployment alphabet can contain one private
contamination symbol per source.

**Proof.** For any source experiment `R=(r_s)` and common Markov kernel `T`,

`A^*(RT) = G^{-1} sum_u max_s sum_z r_s(z)T(z,u)`
`        <= G^{-1} sum_{u,z} T(z,u) max_s r_s(z) = A^*(R)`.

Balanced Bayes accuracy is convex in the experiment, so

`A_y^*(Q) <= t_y A_y^*(PMT_y)+(1-t_y)A_y^*(R)`
`          <= t_y Abar_y(M)+(1-t_y)`.

The right side is nonincreasing in `t_y`, hence is at most the displayed bound.
The normalized form is algebra. For sharpness, use the identity common channel
and place each contamination law on a distinct new source-specific symbol; the
common and private contributions then add exactly. QED.

If reference normalized advantage is zero, the external advantage is at most
`eta_y`. Unlike independent likelihood-ratio shifts, source-blind drift alone
cannot manufacture source information.

## 5. Utility selected on the same fold

Let a diagnostic decoder `g:[L]->[J]` be selected jointly with `M`. In stratum
`(s,y)`, define the fine-token error vector

`e_{M,g,y}(c) = sum_z M(c,z) 1{g(z) != y}`.

**Corollary 3 (post-selection-safe utility).** On `E`, simultaneously for every
`M` and `g`, reference conditional diagnostic error is at most

`ebar_{s,y}(M,g) = Phi(p_hat_{s,y},epsilon_{s,y};e_{M,g,y})`.

Suppose the common deployment channel changes the selected decoder output with
probability at most `kappa_y` from every released token. Then under the coupled
shift model,

`Q(g(Z_ext) != y | s,y)`
` <= (1-eta_y) min{1, ebar_{s,y}(M,g)+kappa_y} + eta_y`.

Thus representation, attacker certificate, and diagnostic decoder may be
selected together on the certification fold without a second statistical test.
The shift-side parameters `eta` and `kappa` remain explicit assumptions; they
are not inferred from the same data by wishful thinking.

## 6. Impossibility and rejected shift model

**Theorem 4 (differential-shift necessity).** If source-specific contamination
is unrestricted (`eta_y=1`), no protocol can provide a nontrivial external
universal-attacker certificate from reference data alone. Even if all reference
source laws are identical, deployment laws may occupy disjoint source-specific
symbols, giving balanced attacker accuracy one. An unseen `(s,y)` reference
stratum has the same obstruction and must produce `ABSTAIN_UNSUPPORTED`.

**Proposition 5 (independent likelihood-ratio leakage floor).** Let `G=2` and
`Gamma>1`. There is a perfectly source-independent two-token reference law for
which independently shifting each source under
`Gamma^{-1} <= dQ_s/dP_s <= Gamma` produces

`TV(Q_0,Q_1) >= 1-1/Gamma`.

**Construction.** Let an event have common reference mass `1/(Gamma+1)`. Shift
its source-1 mass to `Gamma/(Gamma+1)` and its source-0 mass to
`1/[Gamma(Gamma+1)]`; valid complement ratios exist inside the same bounds.
Their event-mass difference is `(Gamma-1)/Gamma`. QED.

At `Gamma=1.25`, the floor is `0.20`. This is why the earlier independent-shift
version is retained only as a negative control.

## 7. Operational compatibility LP

For finite reference laws `P=(p_s)` and observed external laws `Q=(q_s)`, define
the largest empirically compatible common-channel mass as the linear program

`t^*(P,Q) = max t`

subject to a nonnegative subchannel matrix `B` satisfying

`sum_j B(i,j)=t` for every input token `i`, and

`sum_i p_s(i) B(i,j) <= q_s(j)` for every source `s` and output token `j`.

Then `eta_min(P,Q)=1-t^*(P,Q)` is exactly the smallest contamination fraction
for which `Q` has the coupled-shift decomposition. For `t>0`, set `T=B/t`; the
nonnegative residual has mass `1-t`. Conversely, every coupled decomposition
defines such a `B=tT`.

This LP is an empirical compatibility diagnostic, not automatically a
future-distribution guarantee. A final paper must either preregister `eta` as a
stress parameter or add a separate confidence construction around bridge data.

## 8. Claims that are and are not new

Classical ingredients that must be cited rather than claimed include total
variation, Bayes classification on finite experiments, data processing under
Markov kernels, randomized fair representations, multinomial concentration,
and Learn Then Test-style abstention.

The provisional technical claim to test for novelty is their combination:

1. an exact finite-sample envelope over every stochastic release channel and
   every downstream attacker;
2. validity after selecting that channel and diagnostic decoder on the same
   certification contingency table, with no channel-family multiplicity term;
3. a minimax-sharp transfer to coupled source-blind deployment drift with
   bounded differential contamination; and
4. an operational common-channel compatibility LP plus the matching
   impossibility boundary.

The claim remains provisional until the collision review, exhaustive verifier,
and usefulness experiments pass.
