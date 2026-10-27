# ALIVE-12 qualification archive

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**, **NATIVE_META_NOT_RUN**,
**NO_RETRIEVAL_ADVANTAGE_DEMONSTRATED**.

Baseline: `d58c30748a5ec9273a0be86dc769d8c1b7dc6b23` (ALIVE-11-R1 merge).
Product code: `cf7022cb168b4cbd65bbc0b98faafbb25b498c85`.
No paid inference was performed.

This archive preserves controlled cross-page retrieval evidence, native synthetic Chrome evidence,
protocols, validation transcripts and a SHA-256 manifest. It does not modify ALIVE-01 through
ALIVE-11-R1 archives.

## Evidence

| File | Meaning |
|---|---|
| `protocol.json` | predeclared six-scenario evaluation protocol |
| `evidence/retrieval-comparison.json` | raw per-scenario retrieval/connection results and summaries |
| `evidence/native-synthetic.json` | native Chrome two-page synthetic journey |
| `evidence/research-memory.png` | genuine docked side-panel capture from the journey |
| `validation/backend.txt` | 151 backend tests |
| `validation/research-memory.txt` | 5 focused research-memory tests |
| `validation/extension.txt` | 9 extension tests |
| `validation/frontend.txt` | 7 frontend tests |
| `validation/build.txt` | production dashboard build |
| `validation/ruff.txt` | Ruff check and format |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## Research-memory contract

A research row is a `WebExperience` record of kind `research_memory`, linked to a validated note,
reviewed snapshot, goal, URL, SHA-256, bounded excerpt, exact evidence quote, interpretation and
owner usefulness. The existing `Memory`/`MemoryVector` tables hold a rebuildable retrieval
projection. The authoritative record remains the companion observation and note.

Saving is explicit and idempotent. Retrieval is goal-scoped, excludes the current URL and SHA, and
returns only active rows. Withdrawal marks the row withdrawn, deletes the projection and vector, and
does not resurrect after restart or reindex.

## Evaluation result

| Arm | Results | Relevant | Precision@3 | Targets | Recall@3 | False retrievals | Correct abstentions |
|---|---:|---:|---:|---:|---:|---:|---:|
| Current-page only | 0 | 0 | n/a | 0/4 | 0.0 | 0 | 2 |
| Exact-match only | 0 | 0 | n/a | 0/4 | 0.0 | 0 | 2 |
| Cross-page retrieval | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |
| Retrieval + connection | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |
| History-access control | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |

The retrieval arm found all four relevant historical sources, but the strong history-access control
did the same. No ranking advantage is claimed. The false-similarity page was retrieved lexically but
the connection abstained because no shared evidence survived the deterministic check. Four
connection candidates had exact current and historical quotations; no unsupported or false
connections were recorded. The stale memory reported an age of approximately 30 days.

The evaluation used five synthetic historical-note calls and no paid calls. Retrieval and connection
generation made no model calls.

## Native synthetic journey

- Chrome `155.0.8059.85`, genuine docked side-panel target.
- Two controlled loopback research pages.
- Source A reviewed and saved; source B reviewed and searched.
- Source A returned as historical evidence; `same_concept` candidate displayed with both exact
  quotations.
- Connection feedback persisted.
- Backend restart retained the active memory.
- Panel withdrawal removed it; no active memory remained.
- Wrong-origin grant returned 403.
- One local synthetic provider call; no Meta inference.

## Boundaries

- Small controlled corpus, one memory per goal; ranking vs history-access advantage is not established.
- Labels are source-adequacy labels, not owner ratings or independent task outcomes.
- Retrieval used the deterministic text fallback; the hybrid embedding path exists but was not
  exercised because the pinned local model was disabled.
- Connections are lexical candidates, not semantic or factual validation.
- No Hacker News, Hugging Face, GitHub, browser-history or Docker search ingestion.
- No paid model calls, no native Meta journey and no ALIVE-13 work.
