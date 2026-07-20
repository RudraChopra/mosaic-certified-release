# K=8 high-support v1 erratum

The first high-support K=8 protocol is preserved as a pre-outcome execution
record. Its runner stopped before loading a candidate or writing an outcome
because the execution environment lacked the Python package `tqdm`.

Its specification also described the 12,817-row value from the synthetic
scaling table as a K=8 extrapolation. That value instead belongs to the
largest ($K=64$) synthetic cell. The v2 protocol replaces that wording with a
directly stated support intervention: 16,000 rows per source--label stratum,
where the locked ACS stores have that support. No v1 outcome is used in the
paper.
