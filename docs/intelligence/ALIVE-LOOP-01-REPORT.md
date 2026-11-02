# ALIVE-LOOP-01 - First Production Decision Loop

**Status:** implemented, focused-tested, and exercised with the real approved model; branch pushed
for independent review.  
**Decision:** **PASS for LOOP-01's bounded claim** - a real model chose search/read/answer actions
through the existing Ask ALIVE, Cognition, Governor, source-custody and Pi paths, observed the
results, and retained an outcome-labelled episode. A later related task received that episode and
changed its first action.  
**Baseline:** `8478c6a420fa33da4fc2af56db591e11308c7f6b` (`main`, including FINISH-01 and
FINISH-01R).  
**Branch:** `alive-loop-01-research`.  
**Report date:** 2 November 2026.

No production database was contacted or modified. The live campaign used a disposable SQLite
database under `ALIVE_DB_TARGET=disposable:...`; the FINISH-01R resolver ran before schema use.
The campaign used 11 of its 12-dispatch ceiling. The exact report commit is the branch HEAD
recorded in the draft PR.

---

## 1. Executive decision

LOOP-01 now has a working, model-directed, bounded research loop in the product path.

The model, not configuration, chose each action:

- Task 1: `search` -> `read(refunds.md)` -> `answer`.
- Task 2: `search` -> `answer`.
- Task 3: `search` -> `read(policy.md)` -> `answer`.
- Reuse probe: `read(policy.md)` -> `answer`.
- One-call baseline: `search` (no tool round-trip; did not answer).

The host validated and executed every chosen action against the exact owner-approved capture. The
model never received a shell, browser, URL, file path, write or arbitrary-tool capability. The
observations from earlier actions appeared in later model situations.

The durable record contains the full decision trace, model invocation receipts, token/latency
usage, verification and final outcome. LOOP-01 does **not** claim that the model learned a better
policy. It demonstrates decision, action, observation, independent verification and bounded
experience reuse.

Focused results:

- **15 LOOP-01 tests passed** (`tests/test_research_loop.py`).
- **11 real model dispatches** were made, within the 12-dispatch campaign ceiling.
- **3 of 4 controlled tasks were VERIFIED_SUCCESS.** Task 1 was semantically correct but failed
  the frozen exact-answer match; this is reported as a verifier limitation, not hidden.
- The one-call full-corpus baseline did not answer; it chose a search action in its only call.
- Ruff check and format check passed for all changed Python files.
- Existing live-admission and repository-analysis tests passed; one unrelated test also fails on
  `main` and is identified below.

---

## 2. Baseline and integration seam

### Existing architecture verified

The implementation reuses, rather than replaces:

- Ask ALIVE standing consent: `alive/admission/live.py`.
- Typed admission contracts: `alive/admission/contracts.py`.
- Governor reservation and settlement: `alive/cognition.py`.
- Exact source custody and source operations: `alive/sources/custody.py`.
- Model dispatch through the approved Pi transport: `alive/model_gateway.py`, `alive/pi/`.
- Investigation, `CognitiveMessage`, `ModelInvocation`, event log and `Experience` storage.
- Workflow dispatch fence: `alive/workflows/runner.py`.

### Chosen seam

A bounded `research` mode was added to the existing Ask ALIVE request:

- `LiveSetup.research: bool` opts a standing consent into the loop.
- `LiveGoal.task_mode: "research"` selects it.
- `POST /api/v1/admissions/live/ask` reaches the same admission path as ordinary questions.
- `GET /api/v1/admissions/live/research/{task_id}` returns the retained task view.
- `Cognition.call_role(..., research_claim=...)` validates the existing consent, source, model,
  role contract and budget at reservation time.
- `WorkflowRunner.authorize_dispatch` revalidates the same terms at Pi's actual dispatch fence.
- `alive/cognitive_schema.py` accepts the `researcher` message sender.

The research consent is one revocable owner authorization, not a per-inference approval. It
pins the principal, goal, approved paths, source resources, model destination, role contract,
maximum four model calls and the existing token budget. It cannot be widened by model output or
document content.

### Why no new Episode framework

`Investigation`, `CognitiveMessage`, `ModelInvocation`, the event log and `Experience` already
provide identity, provenance, usage and terminal settlement. A new episode store would duplicate
those writers. The one-action-per-investigation constraint on `ActionProposal` is real, so the
loop does not insert one proposal per step. It stores:

- ordered decisions and observations in `Investigation.snapshot["decision_trace"]`;
- each decision and tool observation as a `CognitiveMessage`;
- the final chosen action in the `Experience` record;
- model receipts in `ModelInvocation` and `PiRun`.

No schema migration was required.

---

## 3. Model-directed action implementation

The model receives a bounded situation containing:

- objective and success criteria;
- approved source identities and hashes;
- the corpus catalogue (document IDs, paths, headings);
- current evidence and the last observation;
- previous actions and, when relevant, one prior outcome-labelled episode;
- the closed action catalogue;
- remaining calls, tokens and steps;
- the role contract hash.

It must return exactly one `ResearchAction`:

- `search(query)`
- `read(document_id, section)`
- `answer(text, citations)`
- `abstain(reason)`

There is no configuration-selected action kind. The host parses the strict schema, validates the
action parameters, charges the tool budget, executes only the chosen bounded operation and
returns the observation to the next situation.

The loop stops at a terminal `answer`/`abstain`, at the four-step ceiling, at the model-call
budget, or on a visible decision/tool error. An ambiguous provider outcome is never retried; the
existing Cognition/Pi settlement rules apply.

The one-call baseline (`research.run(..., baseline=True)`) is a qualification-only path. It
supplies the full approved corpus in the situation, permits exactly one model call and never
executes a tool. It is not reachable through the public API.

---

## 4. Actual decision and observation traces

The sanitized evidence is in
[`loop-01-live-evidence.json`](loop-01-live-evidence.json). The live traces were:

### Task 1 - multi-document return/refund question

Question: "What is the return request window and the refund issue time? Answer exactly as
'<window>; <refund time>'."

1. `search("return request window refund issue time")`
   - Results: `refunds.md` (lines 2-4), `policy.md` (lines 4-6).
2. `read("refunds.md", section=0)`
   - Returned the full refund document with line numbers.
3. `answer("30 days from delivery; within 10 business days after inspection")`
   - Cited `policy.md` ("The request window is 30 days from delivery.") and `refunds.md`
     ("Refunds are issued within 10 business days after inspection.").

The answer was factually correct and both required quotes were present and grounded
(`citations_present=2`, `required_present=2`). The frozen expected answer was
`"30 days; 10 business days"`; the wording differed. The independent verifier therefore returned
`VERIFIED_FAILURE`. This is recorded as a strict-verifier finding, not a missing answer.

### Task 2 - single-document shipping question

1. `search("express shipping duration")` -> `shipping.md`.
2. `answer("2 business days")` with the exact `shipping.md` quote.

Result: `VERIFIED_SUCCESS`.

### Task 3 - return window reuse probe (pre-fix)

1. `search("return request duration how long")` -> `policy.md`, `refunds.md`.
2. `read("policy.md", section=0)`.
3. `answer("30 days")` with the exact `policy.md` quote.

Result: `VERIFIED_SUCCESS`. The supplied prior episode was the less-relevant shipping episode
because the lexical relevance matcher did not normalize punctuation and common words. This was a
real defect, not a simulated one.

### Reuse probe after the relevance fix

1. `read("policy.md", section=0)` - no search first.
2. `answer("30 days")` with the exact `policy.md` quote.

Result: `VERIFIED_SUCCESS`. The supplied prior episode was the preceding return-window task, which
was `VERIFIED_SUCCESS`; the first action changed from `search` to `read`.

### One-call baseline

The baseline received the full corpus but chose
`search("return request window refund issue time")` in its only dispatch. The tool was not
executed (one-call mode), so it did not answer; result `INCONCLUSIVE`. Under the same action
schema, the model did not treat the full corpus as sufficient to answer without a search action.
That is evidence for the value of the tool round-trip, not proof of improved research quality.

No document content, URL, shell command or external web request was executed by the model. The
host executed only `search` and `read` over the approved captured files.

---

## 5. Episode persistence and provenance

For every task:

- `CognitiveObservation` identifies the owner question and source.
- `Investigation` retains the ordered decision trace, evidence and verification.
- `CognitiveMessage` retains each `researcher` decision and each `investigator` evidence
  observation.
- `ModelInvocation` retains the role, provider, model, input context hash, output JSON, usage,
  latency and settlement status.
- `Experience` retains the state snapshot, final chosen action, outcome state, usage, evaluation
  and episode identity.

The `Experience.investigation_id` unique constraint remains intact: one episode per investigation.
The full multi-step trace is in `Experience.data["state_snapshot"]["decision_trace"]`, not
duplicated into multiple `ActionProposal` rows.

Replay is idempotent. The investigation is located through the unique
`CognitiveObservation.fingerprint` built from the consent and request key. A replay with the same
question and reference returns the retained view without another model or tool action. Reusing
the key with a different question or reference is refused. A restart test reopens the application,
reads the retained task and verifies the same episode.

---

## 6. Verification results

Verification is deterministic and independent of the model:

- The answer must match a frozen reference answer (or a predeclared accepted variant).
- Every cited quote must exist verbatim in the cited approved document.
- Every required reference quote must appear in the model's own citation list.
- A fabricated quote is a grounding failure, not a successful citation.
- An unlabelled ordinary question remains `INCONCLUSIVE` even when its citations are grounded;
  citation existence is not promoted to semantic truth.
- `VERIFIED_FAILURE` means the answer or its grounding failed the frozen check.
- `ABSTAINED` and `ERROR` remain distinct states.
- Frozen references are accepted only when the host is in qualification mode
  (`ALIVE_QUALIFICATION=1`). An ordinary owner request carrying a reference is refused, so a
  caller cannot assert their own "verified" claim through the product API.

| Task | State | Verification | Basis |
|---|---|---|---|
| Task 1 return/refund | `COMPLETED` | `VERIFIED_FAILURE` | Correct facts and 2/2 grounded required quotes; wording did not match the frozen answer set |
| Task 2 express shipping | `COMPLETED` | `VERIFIED_SUCCESS` | Frozen answer and required quote matched |
| Task 3 return window | `COMPLETED` | `VERIFIED_SUCCESS` | Frozen answer and required quote matched |
| Reuse probe after fix | `COMPLETED` | `VERIFIED_SUCCESS` | Frozen answer and required quote matched; prior episode supplied |
| One-call baseline | `ABSTAINED` | `INCONCLUSIVE` | Baseline chose `search`; no tool round-trip and no answer |

Task 1 is the important limitation. The live model produced a correct, grounded answer, but the
exact-match reference set was too narrow. LOOP-01 deliberately does not loosen the verifier after
seeing the model output. A separate semantic verifier is future work.

---

## 7. Experience reuse

The reuse mechanism is intentionally narrow:

- only experiences with the same approved source reference are considered;
- lexical term overlap selects at most one prior episode;
- context is bounded to the last three decisions and truncated observations;
- the prior episode carries its verification, `verified_success` flag and outcome state;
- an unverified episode is never labelled as a successful strategy;
- the situation records whether an episode was supplied, its outcome and whether the first action
  changed.

The first reuse probe exposed a real relevance defect: punctuation and common words made an
unrelated shipping episode outrank the return-window episode. The matcher was corrected to strip
punctuation and exclude common request words. The second probe then supplied the verified
return-window episode and changed the first action from `search` to `read`.

This demonstrates that a prior trajectory can influence a later decision. It **does not** show
that the decision became better. LOOP-01 records `first_action_changed=true`; it does not claim a
performance gain. That requires a separate controlled comparison with matched tasks and a
no-experience control, which is LOOP-LEARN-01.

---

## 8. Focused tests

`tests/test_research_loop.py` - **15 passed**:

- model chooses search -> read -> answer;
- chosen action determines actual execution;
- observations inform later decisions;
- invalid action schema is refused with no tool execution;
- unapproved document ID is refused;
- prompt injection in approved content cannot widen authority;
- model-call budget is enforced;
- step budget is enforced;
- wrong answers fail independent verification;
- ungrounded citations fail independent verification;
- unlabelled answers remain `INCONCLUSIVE`;
- abstention remains distinct;
- replay performs no duplicate dispatch;
- prior verified episode is supplied and the first action changes;
- unverified episode is not presented as a success;
- one-call baseline sees the full corpus and never executes a tool;
- restart preserves the episode;
- research mode without its own consent is refused;
- a frozen reference is refused outside qualification mode;
- dispatch revalidation refuses revoked consent.

Additional checks:

- `uv run ruff check` and `ruff format --check` passed for every changed Python file.
- `tests/test_live_admission.py` and `tests/test_repository_analysis.py` were exercised through the
  existing admission/workflow path.
- One test, `test_the_governor_must_be_explicitly_started_for_a_model_admission`, also fails on
  untouched `main` at `C:\Projects\alive` (the workflow start returns 200 where the test expects
  409). It is recorded as pre-existing, not caused by LOOP-01.

No dashboard code was changed; the dashboard build is therefore not part of this milestone's
verification.

---

## 9. Real-model evidence and costs

Campaign conditions:

- transport: `pi`, the approved production path;
- model: `muse-spark-1.3`;
- provider: `meta`;
- database: disposable SQLite under `ALIVE_DB_TARGET=disposable:...`;
- source: a disposable four-document owner corpus;
- campaign ceiling: 12 dispatches; used: **11**.

| Run | Calls | Tokens | Latency | Verification |
|---|---:|---:|---:|---|
| Task 1 return/refund | 3 | 4,014 | 6.23 s | `VERIFIED_FAILURE` (strict wording) |
| Task 2 express shipping | 2 | 2,791 | 3.64 s | `VERIFIED_SUCCESS` |
| Task 3 return window | 3 | 5,546 | 7.78 s | `VERIFIED_SUCCESS` |
| Reuse probe after fix | 2 | 4,167 | 5.75 s | `VERIFIED_SUCCESS` |
| One-call baseline | 1 | 2,789 | 5.15 s | `INCONCLUSIVE` |
| **Total** | **11** | **19,307** | **28.56 s** | |

All `ModelInvocation` rows were `validated`. The individual invocation receipts, token splits,
latency and sanitized decisions are in the evidence JSON. Provider currency cost is not known;
the existing configuration does not estimate it, so none is claimed here. The token and latency
figures are the actual provider usage returned through Pi.

The live campaign was run in three phases on the same disposable database and source: an initial
multi-document task plus baseline, the two remaining tasks, and the corrected reuse probe. The
evidence file merges the three phases and labels each task's phase and consent.

---

## 10. Existing product regressions

The existing Ask ALIVE analysis, contextual-reasoning and repository-analysis paths were not
rewritten. The research branch is entered only when `task_mode="research"` and the consent carries
the research block.

The focused live-admission and repository-analysis runs passed 90 tests with one pre-existing
failure (`test_the_governor_must_be_explicitly_started_for_a_model_admission`), reproduced on
untouched `main`. The typed-role refusal message was restored to its original wording after a
temporary message change; that test passes again.

The dashboard was not changed. The existing Ask ALIVE API remains the product path for this
milestone. A dashboard trace view is the main practical gap for LOOP-02.

---

## 11. Architectural limitations

1. **Exact-match verification is brittle.** Task 1 is the proof: a correct, grounded answer failed
   because its wording differed from the frozen set. A future milestone needs an independent
   semantic verifier, not a relaxed arbitrary check.
2. **Ordinary questions stay `INCONCLUSIVE`.** This is intentional. Citation grounding is not
   semantic truth.
3. **Reuse is lexical, not embedded.** The first probe found a real relevance defect; the fix is
   small and deterministic. It is not a learned retrieval policy.
4. **No policy learning.** LOOP-01 does not update weights, thresholds, skills or strategies. It
   records a trajectory and supplies it to a later task.
5. **One `ActionProposal` per investigation.** The loop does not insert per-step proposals because
   the existing unique constraint permits only one. The ordered trace lives in the investigation
   snapshot and messages. A future UI that needs to query individual steps relationally may
   justify the smallest schema extension then.
6. **No dashboard integration yet.** The API returns the trace, but the existing LivePane still
   renders only admission exchanges. This is a product-integration gap, not an intelligence
   claim.
7. **The one-call baseline is not a free-text baseline.** It uses the same `ResearchAction`
   schema and full corpus. It chose `search`, so it did not answer. A future comparison should
   include a free-text one-shot baseline with its own frozen verifier.
8. **Live qualification used SQLite.** The restart/replay tests use the same durable model, but
   the live campaign did not run against PostgreSQL or a mid-campaign process restart.
9. **The live model was `muse-spark-1.3`.** A different approved model may behave differently;
   the consent pins the model and refuses a destination change.
10. **Research consent requires `contextual=True`.** The contextual profile supplies the exact
    source approval and destination. This is a deliberate reuse of the existing source custody,
    but it couples research setup to the contextual profile.
11. **No external web, shell, browser or writes.** The only tools are corpus search and read.
    Prompt injection in a document cannot grant authority because the host executes only the
    closed action schema over the exact approved capture.

---

## 12. Next milestone recommendation

Proceed to **ALIVE-LOOP-02**, connecting the same bounded decision mechanism to the existing
analysis and code-review capabilities. The highest-value next increments are:

1. Add a dashboard trace view in the existing Ask ALIVE pane: question, chosen actions,
   observations, answer/abstention, citations, verification, calls and episode identity.
2. Let the model choose among existing product actions (`analyze`, `review`, `read`, `answer`,
   `abstain`) without adding a second orchestration engine. Reuse the workflow runner and the
   same dispatch fence.
3. Add an independent semantic verification tier for controlled tasks and keep unlabelled
   questions `INCONCLUSIVE` unless a frozen reference exists.
4. Then run **ALIVE-LEARN-01**: a matched controlled comparison of decisions with and without a
   verified prior trajectory. Do not claim learning before that comparison.

LOOP-01 is complete as a production-path, model-directed research loop with durable traces and
real-model evidence. It does not yet prove learning, and it does not yet replace the existing
analysis and code-review product paths.

---

## Evidence index

- [`loop-01-live-evidence.json`](loop-01-live-evidence.json) - sanitized live traces, receipts,
  token/latency totals, verification and reuse records.
- `tests/test_research_loop.py` - offline regression and authority tests.
- `scripts/loop01_campaign.py` - guarded live campaign harness (requires
  `ALIVE_LOOP01_LIVE=1`, a disposable database target and the approved Pi transport).
