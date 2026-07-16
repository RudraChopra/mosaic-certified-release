# Double-Blind Release Boundary: Interpretation 2

This outcome-blind addendum preserves the original release boundary and
Interpretation 1 while fixing archive-hardening details before controlled-study
outcome access. It changes no scientific result or submission policy.

## Private Output Root

The V2 builder accepts only an explicit private root. After resolving symlinks,
the output, staging tree, temporary extraction, logs, and private registry must
all remain below that root or a system temporary directory created with private
permissions. The builder fails if the output is Git-tracked, lies inside a
tracked directory without an active ignore rule, is a symlink, already exists
without an explicit non-destructive replacement flag, or resolves to the named
repository's public `dist/` path.

No private path or archive hash is printed into a tracked file. Console output
may identify only the private output path and nonidentifying content summary.

## Deterministic Member Contract

Every archive member must come from one versioned allowlist or be a generated
file named by that allowlist. The dependency-closure audit parses flattened TeX
sources, bibliography/style references, reproduction imports, and manifest
references and fails on a missing or unlisted dependency.

Member names must be normalized UTF-8 NFC relative POSIX paths. Reject absolute
paths, `..`, empty components, backslashes, control or zero-width characters,
Unicode-normalization collisions, case-fold collisions, duplicate members,
symlinks, hardlinks, devices, FIFOs, sockets, encrypted entries, archive
comments, extra fields, macOS resource forks, `.DS_Store`, extended-attribute
sidecars, bytecode, caches, editor backups, and nested archives not explicitly
allowed. Fix timestamps, permissions, compression method, compression level,
member order, newline policy for generated text, and JSON key ordering.

Build the same input twice in disjoint staging directories and require
byte-identical ZIPs. The external private registry records the final ZIP hash,
size, member count, allowlist hash, builder-source hash, schema version, and
every member hash. The public in-archive manifest contains only content hashes
and nonidentifying release-format identifiers; it cannot map back to an
author-named commit or raw private receipt.

## Identity and Path Scanning

Scan both decoded text and raw bytes before compression and again after clean
extraction. The private scan configuration includes author names and variants,
initials where discriminative, affiliations, usernames, email addresses, home
and external-volume prefixes, repository owner and remote strings, branch
names, account or submission identifiers, reviewer identities, shell prompts,
and the known named-repository commit identifiers. This private token list is
never packaged.

Also fail on generic absolute POSIX and Windows paths, `file:` URIs, named
Git-host URLs, PDF author/creator/subject keywords that identify the author,
embedded attachments, document JavaScript, annotations carrying identity,
figure metadata, ZIP metadata, and source comments excluded by the venue's
anonymous-source policy. A raw-byte hit requires an explicit audited
nonidentifying exception; it may not be suppressed by decoding differently.

## Canonical Receipt Views

The canonical receipt format has its own closed JSON Schema and versioned field
allowlist. Every raw field is classified as retained scientific content,
replaced transport metadata, or forbidden private metadata. Unknown fields,
type changes, duplicate scientific keys, nonfinite numbers, altered hashes, or
unexplained omissions fail closed.

For every canonical receipt, a private comparison record stores the raw hash,
canonical hash, schema hash, transformation version, and an exact field-level
diff. The package contains only the canonical view and its nonidentifying
content hashes. An independent audit reconstructs every retained scientific
field from the immutable raw receipt and requires equality.

## Reproduction Environment

The package includes a hashed, pinned environment specification with Python
version bounds and exact direct dependency versions. A temporary environment is
created outside the named repository. Compact reproduction runs with network
access disabled, an empty relevant cache, no external volumes mounted into the
working tree, no inherited project environment variables, and a fresh user
home. It may consume only archive members.

The clean-room command must regenerate and compare the shared result manifest,
TeX result layer, main table, result figures, claim/number audit, and compact
receipt summaries. It records commands, tool versions, exit codes, and output
hashes in the private audit report. Any missing dependency, network attempt,
absolute-path access, nondeterministic output, warning promoted by the frozen
audit policy, or hash mismatch fails the package.

## Deliberate Corruption Tests

Before a real archive is accepted, tests must reject at least:

1. a public or tracked output path;
2. a symlink escaping the private root;
3. author, repository-owner, email, home-path, external-volume, commit, or
   reviewer tokens in text, raw bytes, PDF metadata, a figure, or ZIP metadata;
4. absolute, traversal, Unicode-colliding, case-colliding, duplicate, symlink,
   resource-fork, cache, bytecode, or encrypted members;
5. a stale modular source, missing flattened dependency, unlisted file, or
   unexpected receipt field;
6. a changed scientific receipt value, omitted negative result, wrong member
   hash, wrong archive hash, or non-byte-identical second build;
7. an unpinned dependency, inherited cache result, attempted network access, or
   external-path read during reproduction; and
8. a compact replay, source/PDF audit, manifest-schema validation, or
   cross-venue number audit failure.

Passing these automated checks establishes package hygiene and deterministic
reproduction only. Repository visibility, prior exposure, policy compliance,
authorship, and the actual upload/download inspection remain human gates.
