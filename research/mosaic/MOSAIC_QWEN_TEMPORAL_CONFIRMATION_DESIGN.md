# MOSAIC Qwen Temporal Confirmation Design

Status: frozen design only; not an authorization to run confirmation.

This document was committed while the unlocked Qwen architecture pilot was
still extracting representations and before any pilot result existed. It fixes
the confirmation population and evaluation rule without binding an
architecture. A later confirmation lock may bind only the candidate selected by
the pilot's prewritten rule. If that pilot returns no eligible candidate, this
design is not activated.

## Why a temporal target

CivilComments-WILDS is a subpopulation benchmark, but its standard labeled
train, validation, and test splits are identically distributed. They therefore
do not support a claim of temporal deployment shift. The confirmation instead
uses the dataset's original comment timestamps to define an earlier reference
population and a later target population.

Before fixing the cutoffs, the only confirmation-partition information
inspected was timestamp coverage and the count in each binary toxicity by
identity-mention stratum. No Qwen representation, tokenizer, channel, bridge,
certificate, diagnostic risk, or task score from confirmation IDs was computed.

## Immutable population and roles

- Confirmation IDs satisfy integer dataset `id % 4 != 0`; pilot IDs satisfy
  `id % 4 == 0`, so the two populations cannot overlap.
- Construction: comments before 2016-10-01 UTC.
- Reference: comments from 2016-10-01 through 2017-03-31 UTC.
- Target: comments on or after 2017-04-01 UTC.
- Rows with missing or invalid timestamps are excluded and counted.
- Within each role, sample equally from the four toxicity by identity-mention
  strata, with total caps 4,000 construction, 8,000 reference, and 12,000
  target rows.
- The target rows are split within every stratum into a two-thirds labeled
  bridge fold and a one-third untouched diagnostic fold.

The cutoffs were chosen from support counts, not model outcomes. In the full
confirmation-ID pool, the smallest stratum has 1,733 construction, 4,687
reference, and 8,458 target rows, so every capped role is estimable before any
Qwen computation.

## Candidate and contracts

- Model, prompt, maximum length, hidden layer, pooling rule, and fine alphabet
  are inherited exactly from the pilot; only the pilot's deterministic selected
  candidate may be bound.
- Five registered partition seeds are 3201, 3202, 3203, 3204, and 3205.
- Released alphabet size is two and runtime semantics are one persistent token
  per immutable item identifier.
- Maximum normalized identity-mention inference advantage is 0.35 within each
  toxicity label.
- Worst source-label conditional toxicity errors are evaluated at thresholds
  0.30, 0.35, 0.40, 0.45, and 0.49; 0.40 is primary.
- Familywise delta 0.05 is divided across both tables and all five jobs before
  each table divides its allocation across four strata.
- The optimizer and bridge use no diagnostic row or diagnostic outcome.
- Each primary release receives 100 seeded persistent-token diagnostic replays.

## Reporting and inclusion gate

Every seed, abstention, solver error, certified bound, retained mass, held-out
diagnostic, and operational replay is reportable. The main-paper LLM result is
included only if at least three of five seeds release at the primary 0.40
utility threshold, all released primary interfaces satisfy both held-out
diagnostics, and all primary operational replays satisfy both empirical
contracts. Otherwise the repository records the complete negative or mixed
confirmation and the V9 main-paper evidence remains the fallback.

The source annotation is whether a comment mentions an annotated demographic
identity. It is not the comment author's demographic identity, and no manuscript
or artifact may describe it as such.
