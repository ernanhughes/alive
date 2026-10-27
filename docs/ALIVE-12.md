# ALIVE-12 - Personal Research Intelligence

Engineering: **PASS**. Native synthetic: **PASS**. Native Meta: **NOT RUN**.
Retrieval advantage: **NOT DEMONSTRATED**.

Baseline: `d58c30748a5ec9273a0be86dc769d8c1b7dc6b23` (ALIVE-11-R1 merge).
Branch: `codex/alive-12-research-intelligence`.
Source commit for the evidence: `cf7022cb168b4cbd65bbc0b98faafbb25b498c85`.
No paid inference was used.

## What was built

ALIVE-12 adds an explicitly saved, goal-scoped research memory over already reviewed
companion observations. A reviewed note is not automatically a research memory: the owner
chooses **Save current note for research**.

The authoritative record remains a `WebExperience` row of kind `research_memory`, linked to the
validated note, reviewed snapshot, goal, URL, excerpt SHA-256 and note interpretation. A bounded
projection is written into the existing `Memory` table and the existing `MemoryService` provides
retrieval (hybrid when embeddings are available, deterministic text fallback otherwise). No new
database, embedding system, vector store or learner was added.

## Research-memory contract

The record retains:

- goal ID, source URL and title;
- snapshot and note IDs;
- reviewed content SHA-256 and a bounded excerpt (up to 2,000 characters);
- exact note evidence quote, summary and limitations;
- source kind and review timestamp;
- owner usefulness at retrieval time, including revisions;
- model/policy provenance of the interpretation;
- active/withdrawn lifecycle and saved-at time;
- projection ID, index version, model and revision.

The source snapshot retains the full reviewed text under the existing companion policy. The research
row stores only the bounded excerpt and references; it is not a second copy of the web.

## Authorisation and lifecycle

- Saving requires an authenticated owner and an existing **validated** note.
- Saving is idempotent for the same note; duplicate saves return the existing row.
- Withdrawn memories cannot be resurrected through save, retrieval or reindex.
- Withdrawal deletes the `Memory` projection and its `MemoryVector` rows, marks the research row
  withdrawn and emits an audit event without retaining the excerpt in the event.
- Retrieval filters by instance, goal, active status, different source URL and current SHA.
- No browser-history permission, broad origin expansion or background collection was added.
- Retrieval itself performs no model call and sends no historical text externally.
- A connection is only an evidence-linked **candidate**, not proof that two sources corroborate.

## Cross-page retrieval

`POST /api/v1/browser-experience/research/retrieve` accepts the current reviewed snapshot and
returns up to three active memories for the same goal and a different URL. Each result contains the
historical source URL/title, reviewed timestamp, age, bounded excerpt, evidence quote, owner
usefulness, retrieval score/method and SHA-256. The current page and historical source are always
separate fields.

If no eligible memory exists, the response is an explicit abstention. There is no generated
connection for an empty result.

## Connections and feedback

`POST /research/connections` builds a deterministic candidate from lexical overlap between the
current reviewed excerpt and the historical excerpt:

- at least two shared content terms: `same_concept`, status `candidate`;
- one shared term: `complementary`, status `candidate`, weak;
- no shared term or missing exact quotation: `insufficient_evidence`, aborted connection.

Every candidate stores both source URLs and hashes, the current and historical quotations, exact
quote-validation flags, shared terms, relation type and explanation. It is never labelled factual
support. Connection feedback is persisted separately and never used to suppress a topic.

## Controlled evaluation

Protocol: `archives/ALIVE-12/protocol.json`
Evidence: `archives/ALIVE-12/evidence/retrieval-comparison.json`

Six controlled scenarios: related agent memory, competing retrieval policies, contradictory
results, false similarity, stale research and no relevant memory. Labels are source-adequacy
judgements prepared for this evaluation, not owner usefulness ratings. The evaluation used five
synthetic historical-note calls and no paid calls.

| Arm | Results | Relevant | Precision@3 | Targets retrieved | Recall@3 | False retrievals | Appropriate abstentions |
|---|---:|---:|---:|---:|---:|---:|---:|
| A current-page only | 0 | 0 | n/a | 0/4 | 0.0 | 0 | 2 |
| B exact-match only | 0 | 0 | n/a | 0/4 | 0.0 | 0 | 2 |
| C cross-page retrieval | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |
| D retrieval + connection | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |
| history-access control | 5 | 4 | 0.80 | 4/4 | 1.0 | 1 | 1 |

D produced four candidate connections with valid current and historical quotations and zero
unsupported/false connections. The false-similarity source was retrieved lexically but the
connection abstained because no shared evidence survived the deterministic check. The stale source
reported an age of approximately 30 days.

**No retrieval advantage is claimed.** The strong history-access control achieved the same
precision and recall as ranked cross-page retrieval on this small corpus. The comparison shows that
the capability works, not that ranking or connection synthesis improves research outcomes.

## Native synthetic qualification

`archives/ALIVE-12/evidence/native-synthetic.json` records the native journey:

1. real Chrome `155.0.8059.85` with a docked side-panel target;
2. source A reviewed and saved as research memory;
3. source B reviewed and searched;
4. source A returned with its historical URL and excerpt;
5. a `same_concept` candidate was shown with both exact quotations;
6. connection feedback was persisted;
7. the backend restarted and the memory remained active;
8. the panel withdrew it and retrieval returned no active memory;
9. wrong-origin grant returned 403.

The only provider call was one local synthetic call used to create the historical note. No Meta
call or paid spending occurred.

## Security and governance

- Owner-scoped rows; goal-scoped retrieval; different-source filtering.
- No broad history collection, cookies, profile import or new Chrome history permission.
- No external send during retrieval or connection generation.
- Withdrawn memories are not returned after restart or reindex.
- Historical text remains untrusted data; it is never an instruction or permission.
- Existing grants, Governor, budgets, cancellation and restart semantics are unchanged.

## Limitations

- One historical memory per goal in this corpus; the history-access control is therefore equal to
  ranked retrieval. A larger distractor corpus is needed for a ranking claim.
- Labels are predeclared source-adequacy labels, not independent task outcomes or owner ratings.
- Retrieval used the deterministic text fallback in the evaluation; the existing hybrid embedding
  path is available when the pinned local model is present.
- Connection relations are lexical candidates; contradiction and support are not semantically
  resolved.
- Controlled loopback sources only; no Hacker News, Hugging Face, GitHub or browser-history
  ingestion.
- No real Meta relationship analysis was run in this milestone.
- The native journey used a synthetic provider, not Meta.
- The false-similarity retrieval remains a measured false positive; it was not tuned away.

## Reproduction

```powershell
uv run pytest -q
uv run pytest -q tests/test_research_memory.py
node --test tests/extension-panel.test.cjs tests/extension-background.test.cjs
npm test --prefix dashboard
npm run build --prefix dashboard
uv run python -m scripts.alive12_evaluation
uv run python -m scripts.native12
```

## Next stage

The next qualification should add a distractor-rich corpus and an independently labelled
connection-usefulness task before considering automatic ranking adaptation. A small bounded Meta
relationship-analysis proposal can be prepared separately; it is not authorised here.
