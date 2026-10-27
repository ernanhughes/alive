# Codex ALIVE-13 handoff

## 1. Repository baseline and branch

- Verified `origin/main`: `af12bc88c91a85558873d01579dba93fdd6b1bbf` (ALIVE-12 merge).
- Branch: `codex/alive-13-reliable-research`, based on that commit.
- Product and harness commits: `1b7d06f` (retrieval/isolation/withdrawal fix) and `d963d26`
  (regression, evaluation and native harnesses).
- Archive commit: `04adadb` (protocol, evidence, validation, manifest and reports).
- Archived evaluation and native evidence record source commit
  `d963d267c219d49e4dfab23cf838946b64c4b190`.
- PR: https://github.com/ernanhughes/alive/pull/19 (draft, review-only; no merge and no
  auto-merge).
- CI: all eight checks passed on the PR: backend Ubuntu, backend Windows, dashboard and
  first-contact PostgreSQL, across both workflow runs.

No paid inference was used. The owner's primary checkout and the frozen ALIVE-01 through ALIVE-12
archives were not modified.

## 2. Confirmed defects and fixes

| Defect | Reproduction | Fix |
|---|---|---|
| Retrieval was effectively unranked | 60 ordinary memories produced 15 ordinary candidates and 0 research candidates; the relevant research memory was absent (`evidence/pre-fix-defects.json`) | Scope by instance, kind, active status and goal in SQL before scoring; rank eligible research rows lexically; deduplicate; apply the result limit last |
| Research memory entered general cognition prompts | Old general retrieval returned `RESEARCH_SENTINEL_ALPHA`; new default returned only the ordinary experience row | Default `MemoryService.retrieve` allowlist excludes `research_memory`; general text search uses the same allowlist; `Cognition.world_state` regression asserts the sentinel is absent |
| Withdrawal targeted the last saved ID | Old background worker sent `research-B-last-saved` for a displayed `research-A-displayed` item | Panel sends explicit per-result `researchId`; background rejects an absent ID; server revalidates the exact row |
| Relation labels overstated semantics | Old labels were `same_concept`, `complementary`, `no_supported_connection` for lexical overlap | New labels are `topic_overlap_candidate`, `weak_lexical_overlap`, `insufficient_evidence`; exact source spans and a separate model quotation are stored |
| Interrupted indexing could strand an active record | Missing projection test | `/research/index/repair` recreates missing projections, refreshes stale content/version, removes stale vectors and deletes withdrawn leftovers without resurrection |

The pre-fix reproductions reconstruct the old query, top-k and post-filter from `af12bc8` against a
fresh database, with the ALIVE-13 allowlist deliberately disabled. They are faithful reproductions,
not a literal pre-change checkout run.

## 3. Memory scope and outbound consent

- General memory types: `experience`, `cognitive_analysis`, `authorised_history`.
- `research_memory` is excluded from general retrieval by default and from the general text-search
  endpoint.
- Research retrieval remains available locally through `/browser-experience/research/retrieve` for
  the same instance and goal, active rows only, excluding the current URL and SHA.
- Reading retained history does not require a live current-page grant. Creating a connection that
  involves the current page does require a live reviewed grant; a revoked grant returns 403.
- Research retrieval and connection generation make no model calls and perform no external
  transmission. Real Meta relationship analysis remains separately authorised ALIVE-14 work.

## 4. Retrieval algorithm and frozen result

Order: authorised instance/goal -> active research rows -> current-source exclusion -> lexical
scoring -> deterministic tie-break (recency, then ID) -> SHA-256 deduplication -> result limit.

Score: `2 * |current ∩ historical content terms| + |goal ∩ historical terms - current|`. At least
one current/historical overlap is required. The SQL candidate bound is 5,000 active rows for the
goal; the bound is applied after instance/kind/status/goal eligibility and is reported.

Final frozen evaluation: 36 research memories, 3 goals, 12 current queries (9 positive with 17
relevant labels, 3 negative), 60 ordinary-memory distractors, stale and contradictory sources.

| Arm | P@3 | Recall@3 | MRR | Rank-1 | False positives | Correct abstentions | Missing failures | p50 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| A recency | 0.3333 | 0.5185 | 0.4259 | 0.3333 | 27 | 0/3 | 4 | 1.323 ms |
| B old ALIVE-12 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0 | 3/3* | 9 | 4.094 ms |
| C corrected scoped lexical | 0.6296 | 1.0000 | 1.0000 | 1.0000 | 9 | 3/3 | 0 | 5.314 ms |
| D full-history access | n/a | n/a | n/a | n/a | n/a | n/a | n/a | 1.335 ms |

\* The old arm returned no post-filter research results on all queries. Its negative-query
abstentions are correct outcomes for the wrong reason.

All predeclared criteria passed. Classification: **RETRIEVAL_ADVANTAGE_DEMONSTRATED** on the frozen
controlled lexical corpus; **NOT DEMONSTRATED** for general semantic retrieval or owner usefulness.
The full-history control found the relevant source in 9/9 positive queries (mean 12 rows), proving
that access alone is not the same as ranking.

## 5. Withdrawal

- Each displayed result has its own `Withdraw this memory` action carrying `item.memory_id`.
- The background worker never reads a last-saved ID for withdrawal.
- The server checks instance, kind and status; repeated and concurrent withdrawal is idempotent.
- Withdrawal removes the projection and vectors and records an event.
- Tests cover saved-A/saved-B/displayed-A, restart, repeated withdrawal, wrong instance, unknown ID
  and concurrent double withdrawal.
- The native journey withdraws the displayed target after restart, leaves the two distractors, then
  restarts again and confirms the target remains withdrawn.

## 6. Relationship evidence semantics

- `topic_overlap_candidate`: at least two shared content terms, with exact source sentences.
- `weak_lexical_overlap`: exactly one shared content term, with exact source sentences.
- `insufficient_evidence`: no inspectable shared source span; abstain.
- Records include current/historical URL and SHA-256, exact source spans, `model_evidence_quote`
  separately labelled, shared terms, quote-validation booleans, and an explicit evidence policy.
- The UI displays source spans and the model quotation separately.
- Legacy persisted connection rows are not rewritten.

## 7. Index consistency

`POST /api/v1/browser-experience/research/index/repair`:

- recreates missing projections;
- refreshes stale content, wrong research identity or stale `index_version`;
- deletes vectors for refreshed projections;
- deletes projections/vectors for withdrawn rows without resurrection;
- reports `active`, `projection_created`, `projection_refreshed`, `withdrawn_skipped`, index
  availability and `index_version`;
- is idempotent and handles unavailable embeddings without claiming success.

## 8. Native Chrome

Chrome `155.0.8059.85`, genuine docked side panel, isolated current-branch backend, local synthetic
HTTP provider. Three synthetic note calls; zero paid calls.

Journey result: target ranked 1 of 3 competing research memories; `topic_overlap_candidate` with
exact source spans; feedback persisted; revoked-grant connection 403 while local retrieval stayed
available; backend restart retained memories; displayed-target withdrawal left the distractors;
second restart confirmed withdrawal. `NATIVE_SYNTHETIC_PASS`.

Evidence: `archives/ALIVE-13/evidence/native-synthetic.json`,
`archives/ALIVE-13/evidence/research-memory.png`.

## 9. Evaluation and limitations

- Frozen protocol: `archives/ALIVE-13/protocol.json`.
- Raw results: `archives/ALIVE-13/evidence/retrieval-comparison.json`.
- Pre-fix defects: `archives/ALIVE-13/evidence/pre-fix-defects.json`.
- Withdrawal reproduction: `archives/ALIVE-13/evidence/withdrawal-target.json`.

Limitations: lexical corpus and lexical ranker; source-adequacy labels rather than owner ratings;
old arm reconstructed with the new allowlist disabled; ordinary distractors deliberately share
goal vocabulary; no embedding/hybrid research retrieval; no semantic relationship analysis; no
native Meta journey. The controlled retrieval advantage is not a general research-intelligence
claim.

## 10. Archive integrity

- `archives/ALIVE-13/` contains the frozen protocol, pre-fix defects, evaluation, native evidence,
  screenshot, validation transcripts, README and SHA-256 manifest.
- Frozen ALIVE-01 through ALIVE-12 archives are unchanged.
- Verify with:

```powershell
uv run python scripts/verify_archive.py archives/ALIVE-13
```

(If the repository's generic verifier is not available for this archive layout, the manifest can be
checked with the command recorded in `archives/ALIVE-13/validation/archive.txt`.)

## 11. Recommended next milestone

ALIVE-14 - Research Connection Usefulness. Separately authorise Meta relationship analysis over a
frozen pair set, then have the owner rate whether each proposed relationship is genuinely useful.
Keep retrieval ranking, permissions and semantic relationship judgement as separate claims.
