# ALIVE-14 - Evidence-Grounded Research Connections

Engineering: **ENGINEERING_PASS**. Native synthetic: **NATIVE_SYNTHETIC_PASS**.
Native Meta: **NATIVE_META_NOT_RUN**.
Retrieval: **RETRIEVAL_ADVANTAGE_DEMONSTRATED** on the frozen held-out lexical corpus.
Relationship usefulness: **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**.
Owner ratings: **SCRIPTED_ONLY** (no human ratings collected).

Baseline: `3d81ce9a435d375ff6652bde07582d22a1eafdd6` (ALIVE-13 merge, `origin/main`).
Branch: `codex/alive-14-research-connections`.
Protocol freeze commit: `bf0af924d75483fc1c06ea5f8621ab08c3950b98`.
Implementation commit for the archived evidence: `83852b2bdcccdef041c3e440dce3a2b22906ad0c`.
PR: https://github.com/ernanhughes/alive/pull/20 (draft, review-only).
CI: all eight PR checks passed (backend Ubuntu/Windows, dashboard, first-contact PostgreSQL).
No paid inference was used. No merge or auto-merge was requested.

## What changed

### 1. Memory-type filtering fails closed

ALIVE-13 treated an empty `memory_types` collection as "all types". ALIVE-14 replaces that
contract with:

- `memory_types=None` -> the restrictive general allowlist;
- `memory_types=ALL_MEMORY_TYPES` -> the explicit privileged all-types selector;
- `memory_types=[]` or `()` -> `ValueError`.

The old ALIVE-13 harnesses were updated to use the explicit selector. The regression suite proves
that an accidental empty allowlist cannot expose a research sentinel to a provider-bound prompt.

### 2. Length-aware, generic-resistant lexical ranking

Research retrieval retains the ALIVE-13 ranker as a frozen comparator and adds
`alive14-bm25-v1`:

- goal vocabulary is removed from the query before scoring;
- document frequency and inverse document frequency are computed over the eligible same-goal
  research rows;
- BM25 term saturation and document-length normalisation stop long prose from winning merely by
  containing more words;
- overlapping terms without a discriminating IDF are rejected once the corpus has at least three
  eligible documents;
- a conservative score floor preserves abstention;
- ties break by recency and stable row ID.

This remains lexical retrieval. It is not promoted to semantic retrieval.

### 3. Connection evidence is limited to displayed spans

Local lexical connections now:

- exclude goal vocabulary from substantive overlap;
- choose a pair of exact source sentences that actually share the displayed terms;
- report only terms present in both displayed spans;
- keep the historical model quotation separately labelled;
- abstain when no inspectable shared span exists.

New candidate labels remain `topic_overlap_candidate`, `weak_lexical_overlap` and
`insufficient_evidence`.

### 4. Outbound consent is a distinct permission

The owner can inspect retained research locally without any external request. Sending current and
historical excerpts to an external model requires a separate sequence:

1. **Preview** the exact bounded payload, current and historical source identities and hashes,
   goal, provider/model, estimated maximum tokens and estimated maximum micro-USD.
2. **Authorise** that exact payload hash with an explicit owner action.
3. **Analyse** only if the server revalidates the instance, live current-page grant, active
   historical memory, goal, source hashes, payload hash, provider enablement, Governor budget and
   availability of the selected model.

The consent is bound to the exact payload and source hashes. Changing the source, excerpt, grant or
memory invalidates it. Consents expire, can be revoked, and are consumed before dispatch. A second
analysis of the same current/historical pair reuses the existing connection rather than creating a
duplicate or dispatching again.

Meta is disabled by default via `ALIVE_RESEARCH_META_ENABLED=false`. The zero-cost path uses the
clearly labelled `local_stub` provider. No setting in this milestone authorises paid inference.

### 5. Structured relationship records

The model contract records:

- relationship hypothesis category;
- explanation and limitations;
- exact current and historical quotations;
- confidence;
- provider and model identity;
- payload/consent identity;
- quote-validation results;
- usage and estimated cost;
- analysis version.

Invalid raw output is retained in a separate `research_relationship_analysis` attempt with
`rejected` or `failed` status; it never becomes a validated connection. Valid model output is stored
as a `research_connection` with the hypothesis explicitly marked as not independently verified
truth.

### 6. Owner feedback rubric

Connection feedback now accepts distinct judgments: factual support, goal relevance, whether the
connection revealed something new, whether it was already obvious, whether the owner would act, and
whether it is misleading. Each submission is a revision with history. The legacy `useful` boolean
remains accepted for compatibility.

## Frozen held-out evaluation

Protocol: `archives/ALIVE-14/protocol.json`.
Protocol commit: `bf0af924d75483fc1c06ea5f8621ab08c3950b98`.
Protocol SHA-256: `56a85e66219425387ca42465ad2f3435be0b9af1652ba484fd7e5836cf54baf5`.

Corpus: 18 research memories, 3 goals, 9 current queries (6 positive, 3 negative), 8 predeclared
relevant labels, long generic excerpts, stale sources, competing methods and abstention cases.
The protocol was committed before the final held-out results were generated.

| Arm | P@3 | Recall@3 | MRR | Rank-1 | False positives | Correct abstentions | Decoy rate | Missing failures | p50 latency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A recency | 0.1667 | 0.3333 | 0.2222 | 0.0000 | 24 | 0/3 | 0.8889 | 3 | 1.085 ms |
| B ALIVE-13 lexical | 0.4444 | 1.0000 | 0.7500 | 0.5000 | 9 | 3/3 | 0.5294 | 0 | 5.331 ms |
| C ALIVE-14 BM25 | 0.4444 | 1.0000 | 1.0000 | 1.0000 | 9 | 3/3 | 0.5294 | 0 | 4.964 ms |
| D full history | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

D contained a relevant source for 6/6 positive queries (mean 6 eligible same-goal rows), but it
does not rank.

The predeclared criteria all passed. The ALIVE-14 gain over ALIVE-13 is **rank-1 ordering and MRR**
on the long-excerpt cases; recall and precision are unchanged. The gain over the recency baseline is
larger but still controlled and lexical. This is not evidence of semantic superiority.

Long-excerpt diagnostics:

| Query | Target | Long distractor | ALIVE-13 rank 1 | ALIVE-14 rank 1 |
|---|---|---|---|---|
| Q1 | H01 | H04 | H04 | H01 |
| Q4 | H07 | H10 | H10 | H07 |
| Q7 | H13 | H16 | H16 | H13 |

Negative queries Q3, Q6 and Q9 abstain in both lexical arms.

## Relationship dry-run

The frozen protocol prepares three conditions:

- A: current page only;
- B: current page plus retrieved history;
- C: history available without relationship synthesis.

Only condition B's **local deterministic stub** path was exercised, on Q1, Q4 and Q7. It validated
consent binding, exact payload display, server revalidation, structured output, exact quotations,
persistence, duplicate reuse and scripted feedback revisions. It made zero external calls. No human
owner ratings were collected, so no usefulness comparison is reported.

Classification: **RELATIONSHIP_USEFULNESS_NOT_DEMONSTRATED**, **OWNER_RATINGS_COLLECTED:
SCRIPTED_ONLY**.

## Native synthetic qualification

Chrome `155.0.8059.85`, genuine docked side panel, isolated backend, local synthetic note provider:

- saved a target and two competing research memories;
- retrieved the target at rank 1;
- displayed a truthful `topic_overlap_candidate` with exact source spans;
- displayed the exact outbound preview and authorisation action;
- ran the local deterministic relationship stub with exact quotations;
- saved a scripted feedback assessment;
- withdrew the displayed target, then confirmed a previously authorised consent could not be used
  after withdrawal and made zero external calls;
- restarted and confirmed the withdrawal and validated relationship persisted;
- confirmed a revoked-grant connection returned 403 while local retrieval remained available;
- confirmed wrong-origin grant returned 403.

Evidence: `archives/ALIVE-14/evidence/native-synthetic.json`,
`archives/ALIVE-14/evidence/research-relationship.png`.

## Validation

| Check | Result |
|---|---|
| Full backend suite | 177 passed |
| Focused research-memory suite | 31 passed |
| Extension tests | 11 passed |
| Frontend tests | 7 passed |
| Production dashboard build | passed |
| Ruff in CI scope | passed |
| Held-out protocol frozen before results | yes, commit `bf0af92` |
| Native synthetic Chrome | `NATIVE_SYNTHETIC_PASS` |
| Paid inference | 0 |

## Limitations

- The corpus is lexical and controlled; no semantic paraphrase claim.
- Retrieval labels are source-adequacy labels, not owner usefulness ratings.
- ALIVE-14 improves MRR and rank-1 on the held-out corpus but not recall or precision over ALIVE-13.
- The local stub is not Meta and cannot establish relationship usefulness.
- No owner ratings or paid Meta calls were collected.
- Real Meta requires a separate approval naming the exact model, payloads, call count, token caps,
  spend cap, abort conditions and data-redaction plan.
- Additional relationship feedback revisions are stored as revisions, not independent ratings.

## Recommended next step

Submit a separate Meta approval proposal for up to 12 fixed calls over the frozen condition A/B/C
tasks, with a spend cap, no automatic retries, exact payload hashes and the owner rating rubric.
Only that approved experiment can test whether historical research reveals something useful that
the current page alone did not.
