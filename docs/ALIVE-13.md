# ALIVE-13 - Reliable Research Retrieval and Evidence-Grounded Connections

Engineering: **ENGINEERING_PASS**. Native synthetic: **NATIVE_SYNTHETIC_PASS**.
Native Meta: **NATIVE_META_NOT_RUN**.
Controlled lexical retrieval: **RETRIEVAL_ADVANTAGE_DEMONSTRATED** on the frozen corpus.
General semantic or owner-usefulness superiority: **NOT DEMONSTRATED**.

Baseline: `af12bc88c91a85558873d01579dba93fdd6b1bbf` (ALIVE-12 merge, `origin/main`).
Branch: `codex/alive-13-reliable-research`.
Product and harness commit for the archived evidence: `d963d267c219d49e4dfab23cf838946b64c4b190`.
No paid inference was used. No merge or auto-merge was requested.

## What was wrong

ALIVE-12 established the research-memory lifecycle, but its retrieval path was:

`goal + current text -> unscoped MemoryService top-k -> post-filter by research metadata`

The rank and limit were therefore decided before goal and record-type eligibility. Sixty
older ordinary memories could fill the candidate window before the relevant research row was
considered. The same shared `MemoryService` path was also used by general cognition, so a saved
research excerpt could enter an ordinary investigation prompt. The panel's withdrawal command used
the last saved research ID rather than the displayed result. Lexical overlap was labelled
`same_concept` or `complementary`, which overstated what shared words establish.

The frozen pre-fix evidence is in `archives/ALIVE-13/evidence/pre-fix-defects.json`:

- With 60 ordinary memories, the old path returned 15 ordinary candidates and **zero** research
  candidates; the relevant research memory was absent.
- The old general retrieval path returned the research sentinel; the corrected default returned
  the ordinary experience memory and excluded the sentinel.
- The old background worker withdrew `research-B-last-saved` when the displayed item was
  `research-A-displayed`; the corrected worker withdrew the displayed ID and rejected a request
  with no explicit ID.
- Contradictory, unrelated and weakly related fixtures were labelled `same_concept`,
  `complementary` or `no_supported_connection`; the corrected labels are
  `topic_overlap_candidate`, `weak_lexical_overlap` and `insufficient_evidence`.

## Retrieval contract

Research retrieval now operates in this order:

**authorised instance and goal -> active research rows -> current-source exclusion -> lexical
scoring -> deterministic ranking -> SHA-256 deduplication -> result limit**

The candidate query is bounded in SQL to at most 5,000 active rows for the exact instance and
goal, ordered by recency. That cap is applied after instance, kind, status and goal filtering. A
single goal with more than 5,000 active rows is outside the personal-memory product envelope; the
cap is reported as `candidate_limit`, and the number of eligible rows loaded is reported as
`scoped_count`.

The baseline ranker is deliberately simple and explainable:

- Normalise lower-case content terms of at least three characters.
- Exclude the reviewed stopword list.
- Score `2 * |current ∩ historical| + |goal ∩ historical - current|`.
- Require at least one current/historical content-term overlap; goal words alone are not evidence.
- Break ties by recency (newest first), then by stable research-row ID.
- Deduplicate by source SHA-256.
- Return `scoped_lexical_v1` with the matched terms and ranking version. No model or embedding call
  is made.

The 60-ordinary-memory regression now returns the relevant research memory at rank 1
(`tests/test_research_memory.py::test_scoped_ranking_survives_sixty_general_memory_distractors`).
The current implementation does not use embeddings for research retrieval, so a requested
`hybrid` or `vector` mode is recorded as requested but the response truthfully reports
`mode: scoped_lexical_v1` and `embedding: null`.

## Memory isolation and outbound consent

`MemoryService.retrieve` now defaults to the explicit general-memory allowlist:

`experience`, `cognitive_analysis`, `authorised_history`

`research_memory` is excluded unless a caller passes `memory_types` explicitly. The general text
search endpoint applies the same allowlist. The general investigation snapshot builder therefore
cannot receive a research projection through its default memory path. The regression test creates
a research sentinel, builds `Cognition.world_state`, and asserts that the sentinel is absent from
`snapshot["memories"]` while an ordinary experience memory remains present. The old unscoped path
returns the sentinel in the same controlled database, demonstrating that the test is not vacuous.

The contract is:

| Operation | Permission |
|---|---|
| Read retained research history for the same instance and goal | Local owner-scoped history; no live page grant required |
| Use the current reviewed page | A live, reviewed snapshot grant is required |
| Create a new connection involving the current page | A live reviewed grant is required; revoked grants return 403 |
| Send current or historical evidence to an external model | Not performed by research retrieval or connection generation; a future workflow must authorise it separately |

Reading retained history after grant expiry is intentional and remains owner-scoped. It is not the
same permission as observing or transmitting the current page.

## Withdrawal

Each displayed research result carries its own `memory_id`. The panel creates a per-result
**Withdraw this memory** action that sends that explicit `researchId` to the background worker.
The background worker rejects a request without an explicit ID. The server revalidates instance,
kind and status, withdraws the exact row, deletes its projection and vectors, and records the
withdrawal event. Repeated and concurrent withdrawals are idempotent.

The native journey saves a target, then two distractors, retrieves the target, restarts the backend,
withdraws the displayed target, and confirms the two distractors remain and the target is absent
after a second restart. The pre-fix reproduction shows the old worker targeting the last saved ID.

## Connection evidence semantics

New connection records use only lexical claim labels:

- `topic_overlap_candidate` - at least two shared content terms and exact sentence spans in both
  sources.
- `weak_lexical_overlap` - exactly one shared content term and exact sentence spans.
- `insufficient_evidence` - no inspectable shared span; the connection abstains.

The record carries the current URL/SHA-256, historical URL/SHA-256, exact current and historical
source sentences, separately labelled model evidence quotation, shared terms, an explicit
`evidence_policy`, and quote-validation booleans. The explanation states that lexical overlap does
not establish agreement, support, contradiction or corroboration. The panel labels source spans and
the historical model quotation separately. Legacy persisted rows are not rewritten.

## Frozen distractor-rich evaluation

`archives/ALIVE-13/protocol.json` was frozen before the final run. It contains:

- 36 research memories across 3 goals (Python memory, JavaScript asynchronous runtime, browser
  storage/caching).
- 60 ordinary-memory distractors inserted before any research projection.
- 12 current observations: 9 positive queries with 17 predeclared relevant sources and 3 negative
  queries that require abstention.
- Multiple relevant candidates, same-goal lexical decoys, contradictory/competing explanations,
  stale sources (45 and 30 days), and unrelated queries.
- Four predeclared arms: recency, old ALIVE-12, corrected scoped lexical, and full-history access.
- Predeclared success criteria in the protocol.

Final result (`archives/ALIVE-13/evidence/retrieval-comparison.json`):

| Arm | P@3 | Recall@3 | MRR | Rank-1 relevant | False positives | Correct abstentions | Decoy rate | Missing failures | p50 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A recency | 0.3333 | 0.5185 | 0.4259 | 0.3333 | 27 | 0/3 | 0.7500 | 4 | 1.323 ms |
| B old ALIVE-12 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 3/3* | n/a | 9 | 4.094 ms |
| C corrected scoped lexical | 0.6296 | 1.0000 | 1.0000 | 1.0000 | 9 | 3/3 | 0.3462 | 0 | 5.314 ms |
| D full-history access | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 1.335 ms |

\* The old arm returned no post-filter research results on every query, including the negative
queries. Its three "abstentions" are therefore correct outcomes for the wrong reason; the
nine positive queries all failed to retrieve a relevant source.

The full-history control contained the relevant source for 9/9 positive queries (mean 12 eligible
same-goal rows), but it has no ranking. That control shows that access to history existed in
ALIVE-12; the changed result is the ability to select the right rows from the eligible history.

All predeclared criteria passed:

- Crowding regression: 0 missing-memory failures for the corrected arm.
- Recall@3 improvement over recency: +0.4815 (predeclared threshold +0.20).
- MRR improvement over recency: +0.5741 (predeclared threshold +0.20).
- Missing failures not worse than recency: 0 vs 4.
- Negative queries: 3/3 correct abstentions.

Classification: **RETRIEVAL_ADVANTAGE_DEMONSTRATED** for this frozen controlled lexical corpus.
This is not evidence of semantic paraphrase, cross-lingual retrieval, owner-perceived usefulness, or
a general research advantage.

## Index repair

`POST /api/v1/browser-experience/research/index/repair` incrementally:

- recreates missing projections for active research rows;
- refreshes projections whose content, research identity or `index_version` is stale;
- deletes vectors for refreshed projections so the next index pass cannot use stale embeddings;
- deletes projections and vectors for withdrawn rows, never recreating them;
- reports `active`, `projection_created`, `projection_refreshed`, `withdrawn_skipped`, index
  availability and `index_version`.

The repair is bounded and idempotent. With embeddings unavailable it still repairs projections and
reports the index as unavailable. Repeated repair after a successful repair reports zero created and
zero refreshed. A withdrawn leftover projection is removed rather than resurrected.

## Native Chrome

`scripts/native13.py` ran an isolated, zero-cost native Chrome journey with the real docked side
panel (Chrome `155.0.8059.85`):

1. Saved a reviewed historical target.
2. Saved two competing distractor research memories.
3. Opened a different current page.
4. Ranked the target at position 1 of 3 among the competing research memories.
5. Displayed a `topic_overlap_candidate` with exact current and historical source spans.
6. Persisted owner connection feedback.
7. Revoked the current grant; a new connection returned 403 while local history retrieval remained
   available.
8. Restarted the backend and confirmed all three research memories persisted.
9. Withdrew the displayed target through its per-result button, leaving the two distractors.
10. Restarted again and confirmed the withdrawal remained effective.

Three local synthetic note calls were made; paid calls were zero. The evidence is in
`archives/ALIVE-13/evidence/native-synthetic.json` and the genuine docked-panel capture is
`archives/ALIVE-13/evidence/research-memory.png`.

## Validation

| Check | Result |
|---|---|
| Full backend suite | 164 passed |
| Focused research-memory suite | 18 passed |
| Extension tests | 11 passed |
| Frontend tests | 7 passed |
| Production dashboard build | passed |
| Ruff check/format (`alive migrations scripts tests`, the CI scope) | passed |
| Native synthetic Chrome | `NATIVE_SYNTHETIC_PASS` |
| Paid inference | 0 |

## Known limitations

- The evaluation is controlled and lexical. Relevance labels are source-adequacy labels, not owner
  ratings, independent human annotations, or task outcomes.
- The corrected ranker is deterministic lexical overlap. It does not understand paraphrase,
  negation, entailment, contradiction or complementarity semantically.
- The old-ALIVE-12 arm is a faithful reconstruction against the current database using the old
  query, top-k and post-filter, with the new type allowlist explicitly disabled. It is not a
  bit-for-bit checkout of the old process.
- The evaluation seeds 60 ordinary memories that deliberately share goal vocabulary. That reproduces
  the crowding defect; it is not a claim about typical owner databases.
- Research retrieval does not use the pinned embedding model. Vector/hybrid mode is reported
  truthfully as lexical, and no embedding advantage is claimed.
- The connection mechanism is not a semantic reasoner. It produces review candidates only.
- No native Meta journey, Hacker News/Hugging Face/GitHub/Docker ingestion, or paid relationship
  analysis was performed. Real Meta connection usefulness remains ALIVE-14 work.
- The repository-wide Ruff invocation still finds one pre-existing line-length issue in the frozen
  `archives/ALIVE-11/qualification-v1/recall-runner-executed.py`; the CI scope excludes archives and
  passes. The ALIVE-11 archive was not modified.

## Next milestone

ALIVE-14 - Research Connection Usefulness. Use a separately authorised Meta relationship analysis
over a frozen set of source pairs, then have the owner rate whether the proposed relationship
reveals something genuinely useful. ALIVE-13 has made the retrieval and evidence plumbing
dependable enough for that question to be separable from ranking and permission defects.
