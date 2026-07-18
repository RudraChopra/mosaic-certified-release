# VERA P0 Result Summary

This record reports the complete version-4 P0 matrix without pooling earlier
seed blocks. It is a result summary, not a replacement protocol.

## Integrity

- Matrix: 1,280/1,280 claim-grade receipts; zero failed cells.
- Mechanical audit: 3,072 candidate audit arrays verified; zero findings.
- Primary reader: 1,024 supported shift profiles and 49,152 candidate details.
- Independent replay: 1,024 profiles; all density-ratio memberships verified.
- Reader-agreement audit: zero discrepancies across construction choices,
  finite-reference probability hashes, and 49,152 candidate exact-risk records.

The full primary artifact has SHA-256
`d0389191d91f206a3fdb6b82e793be7b07d4421e4345a2e9c33fbc24a1c17ecf`.
Its lossless compressed copy has SHA-256
`20bea2ceab443c052e371fa9b9edb5ee520282405c499b03f9b93ad7d271ba10`.

## Primary Findings

At the prespecified 12,000-observation budget and Gamma = 1.25:

| Rule | Deployments | Exact shifted-contract violations | Exact-safe deployments |
|---|---:|---:|---:|
| Always deploy | 256 | 140 | 116 |
| Validation point selection | 190 | 52 | 138 |
| IID LTT | 118 | 2 | 116 |
| VERA vector envelope | 11 | 0 | 11 |
| Exact shift oracle | 194 | 0 | 194 |

The prespecified VERA rotating-sentinel safety endpoint passes: 0/64 events,
with one-sided 95% Clopper--Pearson upper bound 4.57%. The VERA usefulness
endpoint passes at Gamma = 1.1 (27.6%, 95% bootstrap interval [23.2%, 32.0%])
but fails at Gamma = 1.25 (5.7%, [2.6%, 9.0%]). The IID-LTT shifted-exposure
endpoint fails: its Gamma = 1.25 rate is 2/118 = 1.69%, below the registered
20% threshold. The paired VERA-versus-IID-LTT endpoint also fails (2 favorable,
0 adverse, 62 tied seed clusters; exact two-sided p = 0.5).

## Interpretation

The complete P0 study supports the narrow statement that uncorrected validation
point selection can deploy unsafe representation edits under the declared
finite-reference shift, and that VERA's vector envelope can abstain to avoid
observed registered-portfolio violations. It does **not** support the planned
main-track claim that VERA materially improves on IID LTT in this protocol:
IID LTT has low shifted violation exposure and VERA is excessively conservative
at the primary shift. The held-out KNN diagnostic also flags 3 violations among
11 VERA deployments; it lies outside the registered formal guarantee, but it
reinforces that the portfolio is not a claim of universal concept erasure.

Accordingly, P0 is a negative confirmation for the intended superiority
headline. It must be reported as such; no threshold, seed, or secondary row may
replace this primary result.
