# ALIVE-14 qualification archive

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**, **NATIVE_META_NOT_RUN**,
**RETRIEVAL_ADVANTAGE_DEMONSTRATED** on the frozen held-out lexical corpus,
**RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**, **OWNER_RATINGS_COLLECTED: SCRIPTED_ONLY**.

Baseline: `3d81ce9a435d375ff6652bde07582d22a1eafdd6` (ALIVE-13 merge).
Protocol commit: `bf0af924d75483fc1c06ea5f8621ab08c3950b98`.
Implementation commit: `83852b2bdcccdef041c3e440dce3a2b22906ad0c`.
Archive evidence commit: `a1b1040`; transcript normalization: `df5f91b`.
PR: https://github.com/ernanhughes/alive/pull/20 (draft, review-only).
CI: all eight PR checks passed (backend Ubuntu/Windows, dashboard, first-contact PostgreSQL).
No paid inference was performed. No merge or auto-merge was requested.

This archive preserves the frozen held-out protocol, retrieval comparison, ranker diagnostics,
consent/relationship dry-run, native synthetic Chrome evidence, validation transcripts and a SHA-256
manifest. It does not modify ALIVE-01 through ALIVE-13 archives.

## Evidence

| File | Meaning |
|---|---|
| `protocol.json` | frozen 18-memory, 3-goal, 9-query held-out protocol with development cases, labels, arms, metrics, seed and stopping rules |
| `evidence/retrieval-comparison-held_out.json` | raw held-out retrieval results and relationship dry-run |
| `evidence/ranker-diagnostics.json` | long-excerpt and generic-overlap diagnostics |
| `evidence/native-synthetic.json` | native Chrome consent, relationship and withdrawal journey |
| `evidence/research-relationship.png` | genuine docked side-panel capture |
| `validation/backend.txt` | 177 backend tests |
| `validation/research-memory.txt` | 31 focused research-memory tests |
| `validation/extension.txt` | 11 extension tests |
| `validation/frontend.txt` | 7 frontend tests |
| `validation/build.txt` | production dashboard build |
| `validation/ruff.txt` | Ruff check and format in CI scope |
| `validation/native.txt` | native qualification command and result |
| `validation/whitespace.txt` | working-tree status at archive creation |
| `validation/archive.txt` | manifest verification result |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## Held-out retrieval result

| Arm | P@3 | Recall@3 | MRR | Rank-1 | False positives | Correct abstentions | Missing failures | p50 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A recency | 0.1667 | 0.3333 | 0.2222 | 0.0000 | 24 | 0/3 | 3 | 1.085 ms |
| B ALIVE-13 lexical | 0.4444 | 1.0000 | 0.7500 | 0.5000 | 9 | 3/3 | 0 | 5.331 ms |
| C ALIVE-14 BM25 | 0.4444 | 1.0000 | 1.0000 | 1.0000 | 9 | 3/3 | 0 | 4.964 ms |
| D full history | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

D found a relevant source for 6/6 positive queries (mean 6 rows) but does not rank. The ALIVE-14
gain over ALIVE-13 is rank-1/MRR on long-excerpt competition; recall and precision are unchanged.
This is a controlled lexical result, not semantic superiority.

All predeclared criteria passed: long-excerpt regression, generic-overlap abstention, recall not
worse than ALIVE-13, MRR not worse than ALIVE-13, deterministic replay and no retrieval provider call.

## Consent and relationship dry-run

The local deterministic stub exercised the full preview -> exact payload authorisation -> server
revalidation -> structured analysis -> exact quotation validation -> persistence -> duplicate reuse
path for Q1, Q4 and Q7. External calls: 0.

The three usefulness conditions (current only, current plus history, history without synthesis) are
prepared in the protocol but not scored. No human owner ratings were collected. The correct result is
**RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**, not an engineering failure and not a usefulness claim.

## Native synthetic journey

Chrome `155.0.8059.85`, genuine docked side panel, isolated backend, local synthetic note provider:

- target ranked 1 of 2 competing research results;
- truthful local connection with exact spans;
- exact outbound preview and explicit authorisation;
- local-stub relationship analysis with exact quotations;
- scripted feedback saved;
- displayed-target withdrawal; stale authorised consent returned 409 with no external call;
- restart preserved withdrawal and validated relationship;
- revoked-grant connection 403; local retrieval remained 200;
- wrong-origin grant 403;
- 3 synthetic note calls, 0 paid calls.

## Boundaries

- Lexical corpus and lexical ranker; no semantic paraphrase claim.
- Source-adequacy labels, not owner ratings.
- No human relationship-usefulness rating.
- Local stub only; no native Meta or paid inference.
- Research vectors remain a backlog architecture item and are not used by retrieval.
- The Meta approval gate remains closed pending a separate proposal.
