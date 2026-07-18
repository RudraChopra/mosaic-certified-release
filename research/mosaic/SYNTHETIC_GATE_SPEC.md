# MOSAIC v2 Synthetic Usefulness Gate

**Status:** historical development protocol written before the MOSAIC v2
usefulness pilots. It is not the final locked preregistration. All disclosed
pilot seeds are permanently excluded from the hash-locked confirmation.

**Pre-confirmation amendment (July 18, 2026):** the initial candidate-threshold
sentence below accidentally omitted `0.30`, although the first archived hard
pilot used `0.30`. The discrepancy is preserved here rather than silently
rewritten. The pilots are therefore exploratory design runs, and the
hash-locked JSON preregistration is the authoritative confirmatory protocol.

## 1. Question and falsification rule

The study asks whether same-table optimization of a source-blind stochastic
release channel provides useful certified deployments under the exact shift
model in `PRE_RELEASE_SHIFT_THEOREMS.md`. The study is not allowed to establish
only that MOSAIC abstains safely. It must show a material utility or deployment
advantage over valid fixed-channel and finite-family certification protocols.

MOSAIC v2 is rejected as the paper's main method if any of these occurs:

1. a theorem-covered deployment violates its exact external privacy or utility
   contract above the registered familywise failure level;
2. the global optimizer disagrees with independent exhaustive solutions;
3. no prespecified regime produces at least a 20% false-acceptance rate for a
   natural plug-in deployment rule;
4. MOSAIC retains less than 30% of exact certifiable opportunities at the
   primary sample size; or
5. MOSAIC has no material advantage over both a held-out fixed-channel
   certificate and a finite-family LTT rule.

No threshold, sample size, seed block, or scenario may be replaced after the
confirmatory hash is written. A failed gate remains a reported negative result.

## 2. Population experiment

Each scenario fixes two task labels, two sources, a fine alphabet of three to
six tokens, a released alphabet of two or three tokens, and exact conditional
laws `p(c | s,y)`. Every replicate draws exactly `n` independent fine tokens
within each of the four source-label strata. The fixed-stratum design isolates
the multinomial confidence claim from random stratum counts.

Every label has a prespecified finite library of source-blind fine-token
channels. The deployment class is

`q_s = (1-eta) p_s T + eta r_s`,

where `T` is one common library member and each `r_s` is arbitrary. The
confirmatory study never samples a convenient residual. It enumerates attacker
assignments and residual simplex vertices to compute the exact worst external
privacy and utility risks for every selected channel.

The core stochastic-necessity scenario starts from the fully disclosed laws

```
Y=0: S=0 [0.80, 0.15, 0.05], S=1 [0.65, 0.30, 0.05]
Y=1: S=0 [0.05, 0.20, 0.75], S=1 [0.05, 0.35, 0.60]
```

with identity and nearest-neighbor smoothing as common transformations. It is
included because a stochastic middle-token release has a strictly better
certified privacy-utility tradeoff than every deterministic release. Additional
scenarios may vary only the registered source contrast, common-drift strength,
and differential fraction. The design pilot may retain at most three scenarios
from that grid and must publish all pilot outcomes used for the choice.

Candidate sample sizes are `n in {125, 250, 500, 1000, 2000}` per source-label
stratum. Candidate differential fractions are `eta in {0.00, 0.05, 0.10,
0.20}`. The design pilot was intended to choose one primary privacy threshold
from `{0.25, 0.35, 0.45}` and one primary worst-conditional-error threshold
from `{0.40, 0.45, 0.50}`. In fact, the archived hard pilot used privacy
threshold `0.30`; the locked confirmation retains that disclosed choice and
does not represent it as having come from the originally written set. The
complete confirmation reports both retained scenarios.

## 3. Exact deployment contract

For a selected release `M` and decoder `g`, the ground-truth privacy risk for
label `y` is computed directly as

`max_T G^{-1} max_a sum_s [(1-eta) p_sy T v_Mas`
`                              + eta max_c v_Mas(c)]`.

The ground-truth utility risk for stratum `(s,y)` is

`max_T [(1-eta) p_sy T M ell_y + eta max_c (M ell_y)(c)]`.

These are exact finite maxima for the registered model, not theorem upper
bounds and not finite external-test estimates. A deployment is a false
acceptance if either exact risk exceeds its registered threshold. A safe
opportunity exists when the exact-model oracle finds at least one feasible
channel-decoder pair meeting both thresholds.

## 4. Deployment rules

Every rule receives the same total number of observations and the same shift
specification. All tie-breaking is lexicographic and fixed before confirmatory
runs.

1. **Plug-in continuum:** optimize the stochastic channel on empirical laws
   with zero confidence radius and deploy when empirical risks pass.
2. **Always deploy:** deploy the plug-in optimum even when its empirical utility
   contract fails. This is a stress reference, not a serious safety method.
3. **Held-out fixed-channel certificate:** use half the observations to choose
   one channel, then certify only that fixed channel on the untouched half.
   This is described as a FARE-style *protocol comparison* unless official FARE
   code is separately run; it must not be reported as a FARE implementation.
4. **Finite-family LTT:** test a preregistered channel grid with valid
   simultaneous bounded-score confidence bounds, including every candidate,
   label, source, and attacker assignment in its error allocation.
5. **Deterministic MOSAIC:** use the same fine-table confidence event as MOSAIC
   but restrict every channel row to a simplex vertex.
6. **Shift-unaware structural certificate:** use the same adaptive confidence
   event while incorrectly setting common and differential shift to zero. Its
   external failures measure why the shift terms are necessary; it is never
   presented as a valid shifted guarantee.
7. **MOSAIC v2:** optimize over the continuum of stochastic channels using the
   registered L1 radii, common-transform library, differential fraction, and
   full sample.
8. **Exact-model oracle:** optimize with the known population laws and exact
   external risks. It is an unattainable denominator, never a deployable
   baseline.

The final implementation must include a second, separately written evaluator
for exact external risk and a brute-force audit on the smallest alphabets.

## 5. Pilot and confirmatory separation

- Design-pilot seeds are `0` through `199`.
- Confirmatory seeds begin at `10000` and cannot overlap any development run.
- The intended pilot restriction was the bounded scenario and threshold set
  above, the confirmatory replicate count, and a feasible fixed LTT grid. The
  disclosed `0.30` amendment is the only threshold exception.
- Before the first confirmatory replicate, the complete JSON protocol, runner
  hash, evaluator hash, scenario laws, seed list, and stopping rule are written
  to a SHA-256 sidecar.
- At least 1,000 confirmatory replicates are required per primary cell. Runs may
  be sharded for speed, but every registered shard must finish or be reported
  missing. There is no outcome-based early stopping.

## 6. Primary outcomes and hard pass conditions

The primary unit is one independently sampled certification table. Report
deployment rate, false-acceptance rate, safe-retention rate, certified worst
error, and exact worst privacy advantage for every rule and cell. Runtime is a
separate machine-specific benchmark rather than a confirmatory endpoint.

The method passes the synthetic usefulness gate only if all conditions hold:

1. **Coverage:** in every primary cell, MOSAIC false acceptance is at most the
   registered `delta=0.05`; additionally report two-sided 95% exact
   Clopper--Pearson intervals and every failure's confidence-event status.
2. **Killer contrast:** plug-in continuum false acceptance is at least 20% in
   at least one prespecified primary stress cell, while MOSAIC is at most 5% in
   that same cell.
3. **Safe retention:** at the primary `n`, MOSAIC deploys safely in at least 30%
   of replicates where the exact oracle finds a safe opportunity.
4. **Decision-layer value:** in at least one prespecified primary cell, MOSAIC
   improves safe retention by at least 10 percentage points over both the
   held-out fixed-channel certificate and finite-family LTT, without a larger
   false-acceptance rate.
5. **Stochastic value:** in the stochastic-necessity scenario, MOSAIC reduces
   median certified worst conditional error by at least 0.10 relative to the
   best deterministic certified channel, or turns at least 20% of deterministic
   abstentions into safe deployments.
6. **Theory match:** the observed abstention-versus-`n` curve is shown beside a
   precomputed finite-sample concentration envelope and a local active-set
   delta-method power prediction. Only the concentration envelope is a
   guarantee. In the retention scenario, the preregistered prediction must
   achieve mean absolute deployment-rate error at most `0.10`, primary-cell
   error at most `0.12`, stable finite-difference diagnostics, and monotonicity
   in sample size.

All methods and cells remain in the result artifact even if one condition
fails. The paper may quote a memorable reduction only if it is regenerated
from the locked confirmatory receipt with its denominator and exact interval.

## 7. Claims this study cannot establish

Passing this gate would not prove that real hospital, text, or sensor shifts
belong to the registered transformation-plus-contamination class. Membership
requires a separately justified engineering specification or independent
bridge data with its own confidence allocation. The study also cannot establish
novelty, clinical safety, or superiority to an official method whose code was
not actually run.
