# Persistent and bounded-query release semantics

## Registered interface

MOSAIC's default runtime contract is persistent release. For each protected
item, the mechanism samples one token `Z` from the registered channel row
`M(C,.)`, stores that token in private mechanism state, and returns the same
token on every later access. The attacker may know the complete channel and use
any function of the persistent token, but does not receive the fine token,
original feature vector, private mechanism state, or an unregistered side
channel.

## Proposition 1: Persistence does not compose leakage

Let one sampled token be `Z` and let the transcript of any number of persistent
queries be `(Z,...,Z)`. The transcript and `Z` generate the same sigma-field:
each is a deterministic function of the other. Consequently the optimal source
attacker has exactly the same balanced accuracy from the repeated persistent
transcript as from one token. Every one-token MOSAIC privacy and utility
certificate therefore applies unchanged.

This is why the production mechanism must randomize once per item. Returning a
fresh independent draw on every call is a different registered mechanism.

## Proposition 2: Exact bounded-query reduction

If a service deliberately permits at most `r` fresh independent draws, define
the product channel

```
M^[r](c,(z_1,...,z_r)) = product_j M(c,z_j).
```

An attacker observing the complete transcript sees exactly one output of
`M^[r]`. Replacing `M` by `M^[r]` in the MOSAIC attacker envelope, structured
shift certificate, and capacity calculation therefore gives an exact
finite-sample certificate for the registered query budget. The result follows
by equality of the transcript laws, not by a union bound over queries.

The output alphabet grows from `L` to `L^r`, so this exact audit is practical
only for modest budgets. It is implemented by
`independent_repetition_channel`; the runtime defaults to persistence.

## Proposition 3: Fresh draws can destroy a one-token contract

For two distinct channel rows `M(c,.)` and `M(c',.)`, their product laws become
asymptotically distinguishable under repeated independent sampling. Their total
variation distance tends to one, so the binary worst-case source-inference
capacity of `M^[r]` tends to one. Thus a nontrivial one-token certificate cannot
be advertised for unbounded fresh queries unless all relevant channel rows are
identical. This is the repeated-query counterpart of MOSAIC's no-free-lunch
result.

## Operational requirements

The service binds each stable item identifier to one immutable fine token and
one sampled release token. Rebinding an identifier to a different fine token is
an error. Private state must be durable and transactional in a multi-process
deployment. Channel updates require a new versioned namespace; silently
rerandomizing old items would create additional independent observations.
