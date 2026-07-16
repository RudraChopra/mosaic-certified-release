# VERA Data And Software Rights Ledger

This ledger controls redistribution in the named repository and anonymous
submission archive. A public download or Git repository is not treated as
permission to redistribute. Any row not marked verified is fail-closed: retain
only original VERA code, compact receipts, aggregate outputs, citations,
download instructions, and cryptographic hashes.

## VERA-Authored Material

The named repository currently has no top-level license. Before public release,
the human author must choose and approve a license for independently authored
VERA code and documentation. MIT is the recommended code license for
reproducibility, but no license grant may be inferred until the author approves
and the exact license file is committed. Any VERA license must state or be
accompanied by a notice that it does not relicense third-party datasets,
embeddings, model weights, upstream eraser implementations, trademarks, or
other externally owned material. The anonymous review package may use a
nonidentifying `VERA Authors` copyright line only after that same grant is
approved; anonymity is not permission to invent a license.

## Upstream Methods

| Method | Pinned upstream | Commit | Local license evidence | Redistribution status | Archive action |
|---|---|---|---|---|---|
| INLP | https://github.com/shauli-ravfogel/nullspace_projection.git | e1edcc19d808108ab71cbb3afb0389db0206a7eb | Pinned checkout contains an MIT License, copyright Shauli Ravfogel (2022), SHA-256 `fc1e4780480479458e2958c320e44d4a8eb8b44c95297cf363783dd0f573f91f`; locally rechecked 2026-07-15. | Locally verified; official page must be rechecked before release. | Do not bundle upstream tree. Retain remote, commit, entry point, and required MIT notice if any copied portion remains. |
| R-LACE | https://github.com/shauli-ravfogel/rlace-icml | 2d9b6d03f65416172b4a2ca7f6da10e374002e5f | No license or notice file found in the pinned checkout; locally rechecked 2026-07-15. | Unverified; no redistribution permission inferred. | Bundle no upstream file. Publish only VERA adapter code that is independently authored, provenance, and installation instructions. |
| LEACE | https://github.com/EleutherAI/concept-erasure | 9f51753821316a1edacf78b52b464ab26d40e60a | Pinned checkout contains an MIT License, copyright EleutherAI (2023), SHA-256 `956bd01010229da10d4a0e8c9ab848bdf55050789174dba82b2c1250559180a0`; locally rechecked 2026-07-15. | Locally verified; official page must be rechecked before release. | Do not bundle upstream tree. Retain remote, commit, entry point, and required MIT notice if any copied portion remains. |
| TaCo | https://github.com/fanny-jourdan/TaCo | 35995e44b95dc1722b03d18b9b16c5b9f8322db5 | No license or notice file found in the pinned checkout; locally rechecked 2026-07-15. | Unverified; no redistribution permission inferred. | Bundle no upstream file. Publish only independently authored protocol adaptation, provenance, and installation instructions. |
| MANCE++ | https://github.com/MatanAvitan/mance.git | d1a260f945914fa1d1c75a71163af3cd586eb241 | Pinned checkout contains an MIT License, copyright Matan Avitan (2026), SHA-256 `59105fed62098976dec40c0bce403a04f45d402c15af8b068d6b1cb133a1f1f8`; locally rechecked 2026-07-15. | Locally verified; official page must be rechecked before release. | Do not bundle upstream tree. Retain remote, commit, entry point, and required MIT notice if any copied portion remains. |

## Datasets

| Dataset | Version and acquisition record | Frozen derivative | Rights status | Redistribution action |
|---|---|---|---|---|
| Waterbirds | Official Waterbirds/WILDS split; exact upstream page and component CUB/Places terms pending official-source verification. | 11,788 frozen 512-dimensional examples; manifest SHA-256 fd4c17004512e9b38afc086eab8544dd9a15d187323747f666f3ae38d5d8c41f. | The official WILDS 2.0.0 loader states noncommercial research and educational use and names the CUB-200-2011 and Places sources; local loader SHA-256 `c1a65977f838040298fa69895f650ed30560a80284522f395909fe706f3281e5`. Final official-page and component-term verification remains pending. | No images, embeddings, labels, IDs, or raw manifest in the archive. Provide public acquisition and preprocessing instructions plus hashes. |
| Camelyon17-WILDS | WILDS Camelyon17 v1.0 metadata and images; official terms pending verification. | 455,954 frozen ResNet18 examples; controlled manifest SHA-256 6d18335f5a66a174304bbafbd7ca6efca9250fb4c450d7d35ce9791a27883fb3. | The official WILDS 2.0.0 loader states CC0 and identifies the modified CAMELYON17 source; local loader SHA-256 `2804dac01c7a1c93b170117030ca008a2ca38298e403deb095af71998623f374`. Final source-page and attribution verification remains pending. | No slide patches, embeddings, patient-linked IDs, or metadata in the archive. Release aggregate support counts, code, and hashes only. |
| CivilComments-WILDS | WILDS CivilComments v1.0; source CSV hash 5fbf41b9903e6a8f78a3c2e5ea3a659621336538a48c1be8d051d50082b5af79. | 448,000 train-only lexical/SVD examples; manifest SHA-256 bfe7394a8189cfeaa12efbaf038306b0463c70d9e05508eed6f154823b0e5c10. | The official WILDS 2.0.0 loader states CC0 and identifies the Jigsaw source; local loader SHA-256 `ea8e633df4ab4dad1bda4c179e73717f2255badfa04156972d39ad57a6658dcb`. Final source-page and text-use verification remains pending. | No comments, IDs, embeddings, or labels in the archive. Release code, aggregate rows, acquisition instructions, and hashes. |
| Bias in Bios | Official R-LACE author artifact server, https://nlp.biu.ac.il/~ravfogs/rlace-cr/bios/bios_data/; the local manifest names the train/dev/test pickle and 768-dimensional array assets and records all six content hashes. | 393,423 frozen 768-dimensional examples; manifest SHA-256 `a2f0d7cd2d67eb2cb01a05fccbd32c24519cd916ac9ceb508ca680ce1f3aa1e4`, locally rechecked 2026-07-15. | Local acquisition provenance is verified. No redistribution permission is established; original biography provenance and continued public-download authorization still require official-source review. | No biographies, pickles, embeddings, labels, or profession map in the archive. Provide citation, download instructions only if still authorized, preprocessing code, and hashes. |
| GaitPDB | PhysioNet Gait in Parkinson's Disease v1.0.0, https://physionet.org/content/gaitpdb/1.0.0/. The 308 text assets in the downloaded checksum manifest, including 306 recordings plus format and demographics text, all verify locally as of 2026-07-15. | 306 recording-level, 334-dimensional engineered feature examples from 165 subjects, split at subject level; manifest SHA-256 `8ff97ea9c25d32e58dc5551dbadfd63f12e3582b0623808713ad3a3a81c7d8bc`, locally rechecked 2026-07-15. | Local asset and derivative provenance is verified. The version-specific PhysioNet license, recommended citation, and attribution text still require official-source verification. | No recordings, subject IDs, features, or labels in the archive. Release feature-extraction code, split procedure, aggregate outputs, and hashes. |

## Citation and Attribution Gaps

These are hard release gates, not optional bibliography polish:

- add and primary-source verify the official recommended citation for PhysioNet
  Gait in Parkinson's Disease v1.0.0; it is currently absent from
  `references_verified.bib`;
- verify whether the Waterbirds release requires separate CUB-200-2011 and
  Places component citations or notices in addition to Group DRO and WILDS;
- verify the exact Camelyon17-WILDS version citation and any original-data
  notice required by the official WILDS distribution;
- verify CivilComments-WILDS/Jigsaw attribution and text-use terms;
- verify the Bias in Bios source-artifact citation, original biography
  provenance, and whether download instructions may legally remain public; and
- verify that every official eraser entry point is represented by the correct
  paper version, upstream commit, and any required license notice.

The final literature refresh must separately add primary citations for the
closest stratified/minimax evidence-allocation work. Dataset and software
citations do not count as novelty-search coverage, and novelty citations do not
clear redistribution rights.

## Preprocessing And Modification Boundary

- Every eraser candidate is generated through the pinned upstream entry point
  named in its receipt under a shared frozen-representation protocol.
- Train-only standardization and randomized PCA are VERA preprocessing steps,
  not claims that the original upstream paper pipeline was reproduced.
- CivilComments uses a hashing vectorizer followed by train-only truncated SVD.
- Waterbirds and Camelyon17 use frozen 512-dimensional vision features.
- Bias in Bios uses the frozen 768-dimensional author artifact.
- GaitPDB uses deterministic recording-level engineered time-series features,
  keeps every subject in one split, and is not an official challenge split.
- The release must preserve required notices for any upstream portion actually
  copied. Remote invocation and independently authored adapters do not justify
  bundling an upstream repository.

## Final Verification Gate

Before freezing either archive, a human author must verify from each official
source: license name and version, attribution text, research-use or commercial
restrictions, redistribution of raw and derived data, download procedure,
version, citation, and any notice requirement. The human author must also
approve the VERA-authored-material license and its exact copyright line. Record
the verification date and source URL in this ledger. No pending row may be
represented as cleared, and a missing license must remain no-redistribution
unless the copyright holder gives permission.
