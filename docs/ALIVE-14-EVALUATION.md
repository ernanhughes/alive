# ALIVE-14 - Evaluation report

## Status

- Retrieval: **RETRIEVAL_ADVANTAGE_DEMONSTRATED** on the frozen held-out lexical corpus.
- Relationship usefulness: **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**.
- Owner ratings: **SCRIPTED_ONLY** (no human ratings).
- Native Meta: **NATIVE_META_NOT_RUN**.
- Paid calls: **0**.

## Provenance

- Verified baseline: `3d81ce9a435d375ff6652bde07582d22a1eafdd6`.
- Protocol: `archives/ALIVE-14/protocol.json`.
- Protocol commit: `bf0af924d75483fc1c06ea5f8621ab08c3950b98`.
- Protocol SHA-256: `56a85e66219425387ca42465ad2f3435be0b9af1652ba484fd7e5836cf54baf5`.
- Evidence source commit: `83852b2bdcccdef041c3e440dce3a2b22906ad0c`.

The protocol was committed before the final held-out results were generated. The evidence records
both the protocol commit and the source commit.

## Retrieval corpus

- 18 research memories across three goals:
  - reference counting versus tracing garbage collectors;
  - HTTP cache revalidation;
  - service-worker offline caching.
- 9 current queries: 6 positive and 3 negative.
- 8 predeclared relevant labels from source content, independent of the retrieval scorer.
- Long generic excerpts H04, H10 and H16; stale/superseded H06, H12 and H18; competing methods H03,
  H05, H11 and H15.
- No ordinary-memory crowding condition is needed here: the ALIVE-13 scoping fix remains in force
  and the comparator ranks the same eligible research rows.

## Metrics

| Arm | P@3 | Recall@3 | MRR | Rank-1 | False positives | Correct abstentions | Decoy rate | Missing failures | p50 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A recency | 0.1667 | 0.3333 | 0.2222 | 0.0000 | 24 | 0/3 | 0.8889 | 3 | 1.085 ms |
| B ALIVE-13 lexical | 0.4444 | 1.0000 | 0.7500 | 0.5000 | 9 | 3/3 | 0.5294 | 0 | 5.331 ms |
| C ALIVE-14 BM25 | 0.4444 | 1.0000 | 1.0000 | 1.0000 | 9 | 3/3 | 0.5294 | 0 | 4.964 ms |
| D full history | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

D contained a relevant source for 6/6 positive queries (mean 6 eligible same-goal rows) but has no
ranking or result limit. It is an access control, not a retrieval product mode.

### Interpretation

- The corrected ranker preserves ALIVE-13's recall and precision on this corpus.
- It improves MRR from 0.75 to 1.00 and rank-1 relevant results from 0.50 to 1.00 by moving the
  short specific source ahead of newer long generic prose.
- All three predeclared long-excerpt cases pass.
- All three negative queries abstain.
- The result is lexical and controlled. It does not establish semantic paraphrase, cross-lingual
  retrieval, owner usefulness or a general research advantage.

## Ranker diagnostics

Source: `archives/ALIVE-14/evidence/ranker-diagnostics.json`.

| Query | Target | Long distractor | ALIVE-13 top 3 | ALIVE-14 top 3 |
|---|---|---|---|---|
| Q1 | H01 | H04 | H04, H01, H03 | H01, H04, H03 |
| Q4 | H07 | H10 | H10, H07, H09 | H07, H09, H10 |
| Q7 | H13 | H16 | H16, H13, H17 | H13, H16, H17 |

Generic-only negative queries Q3, Q6 and Q9 return no result in either lexical arm.

## Predeclared criteria

| Criterion | Result |
|---|---|
| Long-excerpt regression | pass |
| Generic-overlap abstention | pass |
| Recall@3 not worse than ALIVE-13 | pass (1.0 = 1.0) |
| MRR not worse than ALIVE-13 | pass (1.0 > 0.75) |
| Deterministic replay | pass |
| No provider call for retrieval | pass |

## Relationship dry-run

The protocol prepares three matched conditions:

- **A_current_only** - current source only;
- **B_current_plus_retrieved_history** - current source plus selected historical evidence;
- **C_history_without_synthesis** - historical evidence visible without a model-generated
  relationship.

Only condition B's consent and structured-output plumbing was exercised with the local deterministic
stub for Q1, Q4 and Q7. It is not a model and cannot establish usefulness.

| Check | Result |
|---|---|
| Exact outbound payload preview | pass |
| Owner authorisation bound to payload SHA-256 | pass |
| Server revalidation of grant, memory, source hashes and payload | pass |
| Structured schema validation | pass |
| Exact current and historical quotations | pass |
| Duplicate analysis reuse | pass |
| Consent invalidation after withdrawal | pass, 409 |
| Consumed consent replay | pass, 409 |
| Revoked grant | pass, 403 |
| Budget exhaustion | pass, 409 |
| Concurrent withdrawal during dispatch | blocked with 409 while in flight; succeeds after settlement |
| External calls in dry run | 0 |

Owner ratings: **SCRIPTED_ONLY**. Scripted test feedback validates the revision path but is not a
human rating and must not be presented as evidence of usefulness.

## Why no relationship-usefulness claim

A usefulness comparison requires:

1. a real model;
2. matched current-only, current-plus-history and history-only tasks;
3. randomised presentation order;
4. blinded owner ratings;
5. separate judgments for factual support, relevance, novelty, obviousness, action intent and
   misleadingness.

None of these real conditions were run. The zero-cost work establishes that the consent boundary,
Governor checks, structured contract, quotation validation, persistence and duplicate controls are
ready for a separately approved experiment.

## Reproduction

```powershell
# Development mechanics only; not a held-out claim.
uv run python -m scripts.alive14_evaluation --dataset development

# Frozen held-out comparison; requires the committed protocol.
uv run python -m scripts.alive14_evaluation --dataset held_out
```

The held-out evidence is written to
`archives/ALIVE-14/evidence/retrieval-comparison-held_out.json`.

## Stopping and approval rules

- Do not run paid Meta inference without a separate owner approval naming the exact model, source
  material, task count, condition count, call count, token caps, spend cap, retry policy, abort
  conditions, redaction plan and assessment procedure.
- Do not reuse the ALIVE-11 campaign approval.
- Do not tune the ranker against the held-out results.
- Do not treat scripted feedback as owner ratings.
- No automatic retries and no duplicate dispatch.
