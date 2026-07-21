# MOSAIC Qwen CivilComments Pilot Protocol

## Status and role

This is an unlocked architecture pilot. It is not confirmatory evidence and
will not enter any confidence interval, headline count, or diagnostic result in
the paper. Its only role is to decide whether a separately locked confirmation
is scientifically warranted.

The existing 25 CivilComments strict-v2 jobs first undergo a frozen receipt
diagnosis. The Qwen pilot proceeds only if every required source--label stratum
is present and the previous abstention is attributable to joint
privacy--utility feasibility rather than missing support.

## Fixed pilot data boundary

- Dataset: CivilComments-WILDS v1.0.
- Task: toxicity at the released `toxicity >= 0.5` threshold.
- Source: whether the comment mentions any annotated demographic identity,
  `identity_any >= 0.5`. This is not an author-demographic label.
- Pilot rows: integer dataset IDs congruent to zero modulo four.
- Any later confirmation rows: all remaining IDs. No pilot row may enter a
  confirmation estimate, bridge, diagnostic, or model-selection decision.

## Model and candidate search

The encoder is `Qwen/Qwen2.5-1.5B-Instruct`. Text is truncated to 96 tokens.
One forward pass records mean-pooled layer 14, mean-pooled final layer, and the
final non-padding-token state. The pilot crosses those three representations
with fine alphabets K in {4, 8}; the released alphabet is L=2. A balanced
logistic toxicity score is fit on pilot training rows and quantile-tokenized.

The six pilot candidates share familywise level .05 across both their reference
and bridge tables. The source-advantage threshold is .35. Utility thresholds
are .30, .35, .40, .45, and .49, with .40 primary.

## Predetermined go/no-go rule

Proceed to a locked confirmation only if at least one pilot candidate:

1. has every source--label stratum in the reference, bridge, and diagnostic
   folds;
2. certifies minimum bridge retained mass at least .50;
3. returns a nonconstant two-token release channel; and
4. has certified worst-stratum error at most .49 while satisfying source
   advantage at most .35.

If several candidates pass, select the one with the lowest certified error,
then highest minimum retained mass, then lexical candidate name. The later lock
must name exactly that representation, layer, pooling rule, K, model revision,
text length, split rule, thresholds, confirmation seeds, and stopping rule.
Every locked confirmation seed remains reportable, including abstentions and
diagnostic violations.
