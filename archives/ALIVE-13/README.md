# ALIVE-13 qualification archive

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**, **NATIVE_META_NOT_RUN**,
**RETRIEVAL_ADVANTAGE_DEMONSTRATED** on the frozen controlled lexical corpus.

Baseline: `af12bc88c91a85558873d01579dba93fdd6b1bbf` (ALIVE-12 merge).
Product and harness commit: `d963d267c219d49e4dfab23cf838946b64c4b190`.
Archive commit: `04adadb`.
PR: https://github.com/ernanhughes/alive/pull/19 (draft, review-only).
CI: all eight PR checks passed (backend Ubuntu/Windows, dashboard, first-contact PostgreSQL).
No paid inference was performed. No merge or auto-merge was requested.

This archive preserves the frozen protocol, reproduced pre-fix defects, corrected retrieval
comparison, native synthetic Chrome journey, validation transcripts and a SHA-256 manifest. It does
not modify ALIVE-01 through ALIVE-12 archives.

## Evidence

| File | Meaning |
|---|---|
| `protocol.json` | frozen 36-memory, 3-goal, 12-query, 60-distractor protocol with predeclared labels, arms, metrics and success criteria |
| `evidence/pre-fix-defects.json` | reproduced 60-distractor retrieval failure, general-cognition sentinel leakage and old relation labels |
| `evidence/withdrawal-target.json` | old worker withdrawing the last saved ID versus the corrected explicit displayed ID |
| `evidence/retrieval-comparison.json` | raw per-query results for recency, old ALIVE-12, corrected scoped lexical and full-history arms, with summaries and criteria |
| `evidence/native-synthetic.json` | native Chrome journey evidence |
| `evidence/research-memory.png` | genuine docked side-panel capture |
| `validation/backend.txt` | 164 backend tests |
| `validation/research-memory.txt` | 18 focused research-memory tests |
| `validation/extension.txt` | 11 extension tests |
| `validation/frontend.txt` | 7 frontend tests |
| `validation/build.txt` | production dashboard build |
| `validation/ruff.txt` | Ruff check and format in CI scope |
| `validation/native.txt` | native qualification command and result |
| `validation/whitespace.txt` | working-tree status at archive creation |
| `validation/archive.txt` | manifest verification result |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## Retrieval result

| Arm | P@3 | Recall@3 | MRR | Rank-1 | False positives | Correct abstentions | Missing failures | p50 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A recency | 0.3333 | 0.5185 | 0.4259 | 0.3333 | 27 | 0/3 | 4 | 1.323 ms |
| B old ALIVE-12 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 3/3* | 9 | 4.094 ms |
| C corrected scoped lexical | 0.6296 | 1.0000 | 1.0000 | 1.0000 | 9 | 3/3 | 0 | 5.314 ms |
| D full-history access | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 1.335 ms |

\* The old arm returned no post-filter research results on every query; its negative-query
abstentions are correct outcomes for the wrong reason. The full-history control contained a relevant
source for 9/9 positive queries (mean 12 eligible rows), showing that access to history was already
available and that selection is the changed capability.

All predeclared criteria passed. The result is a controlled lexical retrieval advantage, not a
general semantic or owner-usefulness claim.

## Boundaries

- Small frozen corpus with source-adequacy labels, not owner ratings or task outcomes.
- Lexical ranker only; no embedding/hybrid research retrieval.
- Old arm reconstructed with the new type allowlist disabled, not a bit-for-bit old process.
- Ordinary distractors deliberately share goal vocabulary to reproduce the crowding defect.
- Connections are review candidates, not semantic support or contradiction.
- No native Meta journey, paid relationship analysis or additional ingestion.
- Frozen ALIVE-11 archive contains one pre-existing Ruff line-length finding outside the CI scope;
  it was not modified.
