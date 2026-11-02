# ALIVE-FINISH-01 — Integrated Intelligence Qualification and Repair

**Status:** qualification complete; branch pushed for independent review.  
**Decision:** **QUALIFIED_WITH_CONDITIONS**.  
**Tested implementation SHA:** `3f30158a8597b226fb3c39e8ca1b58c7c1b80a94` (unchanged `main` baseline).  
**Qualification branch:** `alive-finish-01-qualification`.  
**Report date:** 2 November 2026.

No production Python or dashboard source was changed. The only tracked additions are this
report and its sanitized evidence file. The report commit is the tip of the qualification
branch; its exact SHA and the final branch HEAD are recorded in the draft PR description.

---

## Executive decision

ALIVE's integrated live path works on the tested baseline.

- Focused backend compatibility: **92 passed, 0 failed**.
- Dashboard live-admission tests: **14 passed, 0 failed**; production build passed.
- Real-model smoke: **7 actual provider dispatches**, all HTTP 200, all through production
  Pi/Meta, using the approved `muse-spark-1.3-contributor` model.
- Measured usage: **22,444 tokens**, **59.1 s** summed provider latency.
- The two AI-FIRST-04 blockers are resolved in the integrated code: foreign lesson metadata
  never enters the candidate record, model input or selection view, and forged or mismatched
  paired-feedback measurements cannot change lesson utility or create a demotion.
- AI-FIRST-05 task contracts work: the code-review response was schema-valid, all four named
  cases were addressed, uncertainty was explicitly typed, and the defect decision was correct.
- Completion repair is bounded and safe: one live repair was attempted, it tried to change an
  accepted citation, and the validator refused it while preserving the original. No second
  repair occurred.
- Live repair **success** was not demonstrated. The named-case predictions were typed
  `undetermined` because the test task did not supply the `item` argument, so named-case
  semantic correctness is **NOT_VERIFIED**.
- Production was left at its original schema version `0006` after a corrected environment
  isolation incident (see Stage 0). The disposable qualification database was at `0015`.
- Persistence and replay passed: after a backend restart, the retained exchange was returned
  unchanged and a repeated idempotency key produced **zero** new provider requests.

**Readiness:** the live foundation is established, but the conditions below must remain visible.
FINISH-02 may proceed; production migration and the repair/case-design follow-ups are separate
conditions, not evidence of a broken live path.

---

## Stage results

| Stage | Status | Key evidence | Blockers |
|---|---|---|---|
| 0 — Environment | PASS, with corrected incident | `main` = `3f30158`; PRs #96–#98 merged; Python 3.13.3; Pi 1.4.0; disposable DB at `0015`; dashboard build passed | Production schema remains `0006`; migration is an operator prerequisite |
| 1 — Regressions | PASS | 92 focused backend tests; 14 dashboard tests; production build | None |
| 2 — Integrity | PASS | Foreign metadata filtered before persistence/model input; historical view redacts; paired feedback rejects forged/stateless/mismatched baselines | None in tested boundaries |
| 3 — Live model | PASS_WITH_CONDITIONS | 7 real dispatches, 22,444 tokens, 0 failures; Test A semantic answer correct; Test B contract structurally valid but citation-incomplete; Test C repair safely refused; restart/replay zero calls | Live repair success NOT_DEMONSTRATED; named-case semantics NOT_VERIFIED |
| 4 — Corrections | PASS, none required | No production code defect found; no frozen data or tests changed | Repair usability and case design remain follow-ups |
| 5 — Decision | QUALIFIED_WITH_CONDITIONS | Core live path, privacy, feedback integrity, persistence and replay demonstrated | Conditions listed below |

---

## Stage 0 — Baseline and environment

### 0.1 Repository state

Verified before any qualification work:

- Local and remote `main`: `3f30158a8597b226fb3c39e8ca1b58c7c1b80a94`.
- Worktree for this milestone: `C:\Projects\alive-finish-01`.
- Branch: `alive-finish-01-qualification`, created directly from that baseline.
- Working tree initially clean.
- PR #96 (`AI-FIRST-04 selective adaptation`) merged at `06b4b714...`.
- PR #97 (`AI-FIRST-05 task contracts`) merged at `f5d7bda2...`.
- PR #98 (`AI-FIRST-04 owner-scope and paired-feedback guards`) merged at
  `b24418893fe26ad9d0218a85c2abd414e92534de`.
- No open pull requests at the time of baseline inspection.

AI-FIRST-05 is present in the baseline: `alive/task_review/`, code-review admission profiles,
the `code_reviewer` / `code_review_repairer` roles, completion validation, bounded repair and
the `LivePane` UI. The PR #98 guard paths are present in `alive/adaptation/selection.py`:
authorization filtering happens before candidate construction, the historical selection view
reprojects old records, and `record_application` checks baseline statelessness, source,
artifact, principal, model/destination and verifier identity.

### 0.2 Tools and model configuration

| Item | Observed |
|---|---|
| Python | 3.13.3 (existing shared `.venv`; no reinstall) |
| uv | 0.7.2 |
| Node | v25.8.2 |
| npm | 11.21.1 |
| Pi | 1.4.0, pinned bundle verified |
| Pinned bundle SHA-256 | `e79626f2dd6f94aa45d30f3fa63cd84319a6eefcd150b353cfaf274366926774` |
| Meta provider | configured; key present (not printed) |
| Approved model | `muse-spark-1.3-contributor` |
| Model discovery | `available`; the model is present in the authenticated catalogue |
| Model transport | `pi` for the disposable qualification |
| Disposable database | `alive_finish01`, PostgreSQL, migrated to `0015` |
| Disposable workspace | temp path outside the repository |

The isolated worktree initially lacked the installed Pi `node_modules` and dashboard
`node_modules`. Both were reused from the existing checkout through ignored directory
junctions; no dependency installation or lockfile change was made. `locate_pi` then verified
the exact pinned version and bundle digest.

The production checkout's default `ALIVE_MODEL_TRANSPORT` is `direct`; the qualification used
`pi` explicitly to exercise the production Pi/egress path. The configured model was
`muse-spark-1.3-contributor`, not the older `muse-spark-1.3` default.

### 0.3 Disposable runtime and authorization

The disposable runtime started successfully with:

- `ALIVE_MODEL_TRANSPORT=pi`
- `ALIVE_META_MODEL=muse-spark-1.3-contributor`
- `ALIVE_PI_PROVIDER=meta`
- `ALIVE_PI_MODEL=muse-spark-1.3-contributor`
- `ALIVE_EMBEDDING_ENABLED=false`
- `ALIVE_EXPERIMENTS_ENABLED=false`
- `ALIVE_DEMO_MODE=false`

A public, non-sensitive fixture was captured and approved through the existing owner-local
source CLI:

- capture `0c4ce683-00bb-480e-b9a2-1411770a1912`
- approval `7b761ebe-c76a-4609-b1da-90131246a4da`
- content SHA-256 `60df35836e07566da4a628175f781da2bfc19b8f83e265765f03a8318d6334f4`
- approved operations: `intent.interpret`, `repository.inspect`, `repository.analyze`,
  `context.reason`, `context.validate`
- approval scope: both files (`README.md`, `implementation.py`), 2-hour TTL.

The inspected, approved standing consent for the general/code-review smoke was
`5be8188b-bef3-40e4-beeb-a06e2b50bdba` (6 calls / 100,000 tokens). A second consent,
`71bb7a05-e673-4f00-a27f-36797f75b91c` (4 calls / 100,000 tokens), was approved only for the
separate repair attempt. Both were approved by the local owner CLI after inspecting the exact
hash. No credentials were sent to the dashboard or written to the repository.

### 0.4 Environment isolation incident (corrected)

During the first disposable-database setup, the shell inherited a global `ALIVE_DSN` variable
pointing at the production `alive` database. `Settings` accepts `ALIVE_DSN` as an alias for
`DATABASE_URL`; Alembic therefore used the inherited production DSN instead of the worktree
`.env` URL.

Effect:

- Production `alive` was temporarily moved from Alembic `0006` to `0015`.
- All 17 newly created tables were empty (`pi_runs`, `pi_provider_requests`,
  `workflow_*`, `intelligence_*`, `source_*`, `owner_admissions`,
  `intent_recommendations`, etc.).
- No existing rows were inserted, updated or deleted.

Correction:

- `alembic downgrade 0006` was run against production with an explicit production
  `DATABASE_URL` and the inherited `ALIVE_DSN` removed.
- Production returned to `0006` with its original 24 public tables.
- The restoration left the existing retained counts at `events=7666`, `goals=71`,
  `memories=57`, `web_experiences=39`, `living_journeys=1`. The intervening migrations
  are schema-only create-table/index operations; they contain no row inserts, updates or
  deletes for the pre-existing tables.
- The disposable `alive_finish01` database was then migrated independently to `0015` and all
  qualification work used only that database.

This was an environment-isolation mistake, not a code-path failure. It is recorded here
because it changed production schema temporarily and must remain visible to the owner.

### 0.5 Stage 0 conclusion

PASS for the disposable qualification environment. Backend startup, disposable database
initialization, dashboard build, Pi presence, Meta configuration and standing authorization
were all established. The remaining production prerequisite is the operator-approved
migration of the production database from `0006` to `0015`; it was not performed as part of
this milestone.

---

## Stage 1 — Focused regression qualification

### 1.1 Backend

Command, run from the qualification worktree with the existing interpreter:

```powershell
C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q -o addopts="" `
  tests/test_selective_adaptation.py `
  tests/test_task_review.py `
  tests/test_contextual_continuity.py `
  tests/test_live_admission.py
```

Result:

```text
92 passed, 74 warnings in 461.21s
```

The warnings were the existing Windows Proactor/zmq event-loop warning, not test failures.
No live provider call was made by this suite; the tests use their controlled scripted
providers and disposable SQLite databases.

Established by the suite:

- General contextual conversation, context freeze, revision and replay remain intact.
- Code-review contracts validate required fields and named cases.
- Missing, duplicate, unexpected and malformed cases remain visible as errors.
- Typed `undetermined` values preserve uncertainty rather than guessing.
- Accepted predictions and explanations cannot be overwritten by completion repair.
- Repair is bounded to one additional attempt and cannot dispatch after a refusal.
- Task/source/context/artifact/model identities remain bound.
- Restart and idempotent replay do not redispatch.
- The selective-adaptation selector remains operational alongside the new contracts.

### 1.2 Dashboard

```powershell
npm --prefix dashboard test -- src/admission/live.test.tsx
npm --prefix dashboard run build
```

Result:

```text
14 passed (1 file)
production build passed
```

The build produced the same production asset shape as the baseline; no dashboard source
change was required.

### 1.3 Stage 1 conclusion

PASS on tested implementation `3f30158a8597b226fb3c39e8ca1b58c7c1b80a94`.

---

## Stage 2 — Authorization and feedback-integrity qualification

### 2.1 Foreign lesson metadata

The relevant implementations were inspected directly:

- `alive/adaptation/selection.py` filters by `authorized(body, principal, destination)`
  **before** any candidate dictionary, support reference or utility metadata is built.
- `support()` is called only for already-authorized lessons.
- `view()` reconstructs the visible set from currently authorized lessons and filters both
  `candidates` and `selected` in historical selection records.
- The evaluation override accepts only IDs that are both present and authorization-eligible;
  `override_lesson_not_authorized` is raised otherwise. The override cannot bypass owner or
  destination checks.

The focused suite includes:

- `test_authorization_scope_owner_destination_and_lesson_text_is_inert`
- `test_historical_selection_view_redacts_foreign_candidate_metadata`
- `test_evaluation_override_is_labelled_cannot_bypass_authorization_and_resets`

These assert that foreign candidate IDs, mechanisms, utility, support references and private
task metadata do not appear in the model input, the newly persisted selection candidate list
or the owner-facing view; an old record containing a foreign candidate is projected as an
empty, `none/no_lessons_available` selection.

### 2.2 Paired feedback integrity

The relevant implementation was inspected:

- `_validated_measurement` binds the measurement to the admission instance, the Oracle event
  source/type, the frozen artifact digest, the admission source digest, the frozen context
  snapshot digest, and one or more validated model invocations with a single
  provider/model/role identity.
- Baseline validation requires a distinct admission, the same task/split/family/verifier,
  corpus and oracle digests, the same principal, the same source and profile, matching model
  disclosure fields, and exactly matching model-invocation identities.
- The baseline snapshot must be `strategy_mode == "stateless"`, use
  `no-experience-control/v1`, have `decision == "none"` and have an empty `items` list.
- `record_application` writes application events only after every check; a rejected pairing
  leaves no application and no demotion event.

The focused suite includes:

- `test_paired_feedback_rejects_nonstateless_baseline_and_tampered_identity`
- `test_primary_measurement_must_match_source_and_artifact`
- `test_paired_feedback_rejects_changed_model_identity`
- `test_application_is_idempotent_and_conflicting_baselines_fail_closed`

The forged cases cover wrong artifact, source, verifier, corpus, oracle and family metadata,
a non-stateless baseline, a tampered model identity, and conflicting duplicate application.
All refusals leave the application and demotion stores empty.

### 2.3 Learning integrity

A rejected or forged pairing does not increase utility, decrease utility, trigger a
demotion, or create a verified learning claim. The tests assert that `APPLICATION` and
`DEMOTION` remain empty after refusal. Historical measurements are immutable event rows.

### 2.4 Stage 2 conclusion

PASS. Both inherited blockers are resolved in the integrated baseline, and the existing
adversarial tests exercise the boundaries. No new security framework or test inflation was
introduced.

---

## Stage 3 — Real-model production-path smoke test

### 3.1 Scope and hard budget

- Database: disposable `alive_finish01` only.
- Workspace: disposable temp path only.
- Source: public, non-sensitive `append_item` fixture (`README.md`, `implementation.py`).
- Path: Ask ALIVE → admission → Cognition → ModelGateway → PiGateway → Pi → ALIVE egress →
  Meta chat completions.
- Model requested: `muse-spark-1.3-contributor`.
- Transport: `pi`.
- Actual dispatches: **7** (ceiling: 8).
- No retry of an ambiguous attempt, no injected transport, no fixture provider substitution.

The fixture contract requires `append_item(items, item)` to append to the caller's list in
place and return that same list, including for an empty caller list; `None` creates a new
list. The supplied implementation uses `items = items or []`, so an empty caller list is
replaced by a new list. The defect is therefore independently known before model review.

### 3.2 Test A — Normal real-model reasoning

**Request:** explain whether `append_item` always appends to the caller list, using only the
approved README and implementation, with citations and explicit uncertainty.

- Exchange: `1946a58f-a60e-4c82-9ffc-82f30a4f0e75`
- Status: `LIVE MODEL`
- Model calls: `2` (intent interpretation + repository analysis)
- Model: `muse-spark-1.3-contributor`
- Usage: `3,171 + 1,827 = 4,998` tokens
- Provider latency: `10,449.99 + 6,177.61 = 16,627.60 ms`
- Report artifact: `8aa94c4a6327bd94c2f5a6fb250b40a8598681983057d8d6ee92fb47eb3c200a`
- Both provider receipts: HTTP 200, transport `network`, inference provenance
  `production_pi`.

The model answered:

> No, `append_item` does not always append to the caller list. README requires in-place
> append and same-object return when `items` is not `None`, but `items or []` replaces a
> falsy empty list with a new list, so empty-list callers are not mutated.

The finding cited the implementation line `items = items or []` and the README contract; the
citation validator reported `1 of 1` findings with matching references. **Independent
semantic check:** correct. For `xs = []`, `append_item(xs, "a")` rebinds the local name to a
new list and leaves `xs` empty, contrary to the contract; the model did not claim execution.

### 3.3 Test B — Code-review task contract

**Request:** review `append_item` against the README contract; for c1 (empty list), c2
(nonempty list), c3 (list containing `0`) and c4 (`None`), predict observed and required
behaviour as `[caller_list_after, returned_list]`; decide whether a defect is present.

- Exchange: `e42d980c-aab2-4018-b822-ff1a87c1da81`
- Status: `LIVE MODEL`
- Model calls: `2` (intent + code reviewer)
- Usage: `3,180 + 3,295 = 6,475` tokens
- Provider latency: `9,657.28 + 8,627.28 = 18,284.56 ms`
- Candidate: `676e1dbf79c299d516f0458c07de02b303a4c77be971ed79fdedbd247dc34c79`
- Both provider receipts: HTTP 200, transport `network`, inference provenance
  `production_pi`.

Structural result:

- `transport_completed`: true
- `response_schema_valid`: true
- `schema_valid`: true
- `all_cases_addressed`: true (c1, c2, c3, c4 each exactly once)
- `contains_undetermined`: true
- `task_complete`: **false**
- Error: one `unsupported_reference` — the model's README quote
  `If items is None, create a new list.` did not exactly match the captured line
  `1. If \`items is None\`, create a new list.`
- `defect`: `{"status":"determined","issue_present":true}` — correct
- All four case predictions: `observed` and `required` are typed `undetermined` with the
  reason that the task did not supply the `item` argument value.

Semantic assessment:

- The defect decision is correct.
- The model did not fabricate case outputs; it used the declared typed-uncertainty mechanism.
- Named-case semantic correctness is **NOT_VERIFIED** because the task did not provide the
  `item` values required to compute `[caller_list_after, returned_list]`. This is a fixture
  design gap, not a code path failure.
- The citation error is real and correctly blocked adoption of the response as complete.

### 3.4 Test C — Bounded completion repair

A second standing consent with `completion_repair=true` was approved
(`71bb7a05-e673-4f00-a27f-36797f75b91c`, 4-call ceiling) for one separate repair attempt.
The same fixture and task were submitted with `repair_incomplete=true`.

- Exchange: `5588bf5b-f3a5-4536-9c8a-c9bba2c70e4d`
- Status: `LIVE MODEL`
- Model calls: `3` (intent + code reviewer + repair)
- Usage: `3,240 + 3,183 + 4,548 = 10,971` tokens
- Provider latency: `10,902.25 + 6,631.58 + 6,698.88 = 24,232.71 ms`
- Original candidate: `d26e52348fd76aa7cd5536efd61a7ef8d08cd813ab36b6e6f7f4100f91e9c74f`
- Repair candidate: `1e3d0bbfcd8d3312aa930b12c8de41ef182bd13efe0ec1c5278f0b9b92dd9849`
- All three provider receipts: HTTP 200, transport `network`, inference provenance
  `production_pi`.

Result:

- `repair_requested`: true
- `repair_attempted`: true
- `additional_model_calls`: 1
- `repair_successful`: false
- `repair_rejection`: `repair_refused_identity_or_accepted_content_changed`
- The original candidate remains the effective candidate.
- No second repair was dispatched.
- The original incomplete state remains visible.

Cause: the repair response returned a replacement citations list. It corrected the README
quote, but also changed the already-accepted implementation citation's line range
(`line_end` 4 → 3). The accepted-content preservation gate correctly refused the patch.
The model identity `original_sha256` itself matched; the rejection is about accepted content,
not a stale parent identity.

This is a **safe failure**. It does not demonstrate successful live repair.

### 3.5 Test D — Restart and replay

Before restart, the disposable database contained:

```text
pi_provider_requests = 7
pi_runs = 7
model_invocations = 7
```

The backend was stopped and restarted against the same disposable database and workspace.
A read-only `GET /api/v1/admissions/live/5588bf5b-f3a5-4536-9c8a-c9bba2c70e4d` returned:

- same exchange ID
- `status=LIVE MODEL`
- `model_calls=3`
- original and repair artifacts present
- repair rejection still visible

A repeated `POST /api/v1/admissions/live/ask` with the same conversation and idempotency key
returned the same exchange ID and `model_calls=3`. The provider-request, Pi-run and
model-invocation counts remained exactly `7 / 7 / 7`. No new provider request was made.

### 3.6 Dispatch accounting

| Test | Calls | Tokens | Latency (ms) |
|---|---:|---:|---:|
| A — general analysis | 2 | 4,998 | 16,627.60 |
| B — code review | 2 | 6,475 | 18,284.56 |
| C — review + repair | 3 | 10,971 | 24,232.71 |
| **Total** | **7** | **22,444** | **59,144.88** |

All 7 requests:

- used the approved endpoint `https://api.meta.ai/v1/chat/completions`;
- used transport `network` through production Pi;
- returned HTTP 200;
- requested `muse-spark-1.3-contributor`;
- reported `model_observed = null` (the provider did not attest an observed model identity).

Currency cost is unknown and was not estimated.

### 3.7 Stage 3 conclusion

PASS_WITH_CONDITIONS. A genuine, useful live-model result was produced and retained through
ALIVE's existing interfaces, with source, model identity, usage, receipts and history. The
code-review contract is structurally reliable and honestly exposes incompleteness. Successful
live completion repair and named-case semantic correctness remain unproven.

---

## Stage 4 — Findings, focused corrections and retesting

### 4.1 Production code changes

**None.** No confirmed production-code defect required correction. The live path, privacy
guards, feedback binding, task contracts, persistence and replay all behaved as designed on
the tested baseline. No frozen dataset, ledger, oracle, corpus or historical lesson was
modified.

### 4.2 Findings that remain conditions

**F-01 — Production schema is behind the tested code.**  
Production is at Alembic `0006`; the tested code expects `0015`. This is an operational
prerequisite, not a qualification result. The production upgrade must be separately approved,
backed up and verified by the owner.

**F-02 — Live repair was safely refused, not successfully demonstrated.**  
The repair model replaced an accepted citation instead of preserving it exactly. The
accepted-content gate rejected the patch. The guard is correct; the repair prompt/schema
usability is not yet proven live. A future repair attempt should explicitly require accepted
citations to be repeated byte-for-byte, or the patch contract should allow an additive
citation repair without replacing accepted entries. Any prompt/contract change invalidates the
current live smoke and requires a fresh authorized run.

**F-03 — Named-case task was underspecified.**  
The code-review goal did not provide the `item` argument values for c1–c4, so the model
correctly returned typed `undetermined` for those predictions. A future test should provide
explicit inputs and independently computed expected outputs. This is a fixture design gap,
not a code defect.

**F-04 — Provider model identity is requested, not attested.**  
All provider receipts show `model_requested=muse-spark-1.3-contributor` and
`model_observed=null`. ALIVE's status is derived from the approved/requested identity and the
production Pi dispatch receipt. Do not describe this as independently attested provider model
identity.

**F-05 — Qualification used one small fixture.**  
This milestone does not establish general code-review quality, improvement over a stateless
baseline, or production-scale reliability. It establishes a working integrated path and the
specific boundaries above.

### 4.3 Retesting

No production code changed after the live smoke, so the tested implementation SHA remains
`3f30158a8597b226fb3c39e8ca1b58c7c1b80a94`. The report and evidence additions are
documentation-only and do not invalidate the runtime results.

---

## Stage 5 — Final decision and next-milestone handoff

### 5.1 Gate assessment

| Gate | Status | Evidence |
|---|---|---|
| Backend startup | PASS | Disposable runtime started; health OK; migrations at `0015` |
| Existing AI-FIRST compatibility | PASS | 92 focused backend tests; 14 dashboard tests; build |
| Selector privacy | PASS | Auth filtering before candidates; historical view redaction; override refusal |
| Feedback integrity | PASS | Forged/mismatched/non-stateless baselines refused; no utility or demotion |
| Real inference | PASS | 7 dispatches through production Pi/Meta; HTTP 200; `LIVE MODEL` |
| Contract completion | PARTIAL | Schema valid, all cases addressed, but citation error made `task_complete=false` |
| Semantic assessment | PARTIAL | Test A correct; named-case semantics not verified because predictions were typed unknown |
| Repair boundaries | PASS | One attempt, accepted content preserved, original retained, no second call |
| Repair success | NOT_DEMONSTRATED | Live repair refused safely; offline repair tests pass |
| Persistence | PASS | Restart retained original, repair and receipts |
| Replay | PASS | Same key returned retained result; 7→7 provider requests |
| Failure transparency | PASS | No fallback answer; incomplete and rejected repair visible; API status truthful |
| Product integration | PARTIAL | API projection and dashboard unit tests pass; no browser E2E |

### 5.2 Decision

**QUALIFIED_WITH_CONDITIONS.**

The principal claims are supported:

- ALIVE can perform a genuine live-model task through its existing production path.
- The result is retained with model, usage and provider receipts.
- The system distinguishes structural validity, task completeness and semantic verification.
- Foreign lesson metadata and forged paired feedback cannot cross the tested boundaries.
- Incomplete output is not silently repaired or hidden.
- Restart and replay do not redispatch.

The qualification is not unconditional because live repair success, named-case semantic
correctness and production schema readiness were not established.

### 5.3 Recommendation

**Proceed to FINISH-02**, with the following conditions tracked:

1. **Production migration:** back up and migrate the production database from `0006` to
   `0015` in a separately approved operator window; verify the existing data and application
   before normal use.
2. **Repair usability:** make one authorized follow-up attempt that preserves accepted
   citations exactly and successfully completes a genuinely incomplete response; acceptance
   requires one additional recorded call, no accepted-field changes, no second repair, and
   `task_complete=true` after repair.
3. **Named-case semantics:** run a fresh code-review fixture with explicit inputs and
   independently computed expected outputs; acceptance requires correct predictions or
   justified typed uncertainty for each named case, with semantic verification recorded
   separately from schema validity.
4. **Preserve the distinctions:** requested provider model is not attested model identity;
   a schema-valid answer is not semantically verified; a successful repair is not proof that
   the underlying review is correct.

Do not infer general intelligence improvement from this milestone. FINISH-01 establishes a
live, inspectable foundation; it does not rerun or revise the AI-FIRST-04 comparison.

---

## Evidence index

| Evidence | Location / identity |
|---|---|
| Sanitized live evidence | `docs/intelligence/evidence/ALIVE-FINISH-01-live.json` |
| Test A exchange | `1946a58f-a60e-4c82-9ffc-82f30a4f0e75` |
| Test A report artifact | `8aa94c4a6327bd94c2f5a6fb250b40a8598681983057d8d6ee92fb47eb3c200a` |
| Test B exchange | `e42d980c-aab2-4018-b822-ff1a87c1da81` |
| Test B candidate | `676e1dbf79c299d516f0458c07de02b303a4c77be971ed79fdedbd247dc34c79` |
| Test C exchange | `5588bf5b-f3a5-4536-9c8a-c9bba2c70e4d` |
| Test C original candidate | `d26e52348fd76aa7cd5536efd61a7ef8d08cd813ab36b6e6f7f4100f91e9c74f` |
| Test C repair candidate | `1e3d0bbfcd8d3312aa930b12c8de41ef182bd13efe0ec1c5278f0b9b92dd9849` |
| Source capture | `0c4ce683-00bb-480e-b9a2-1411770a1912` |
| Source approval | `7b761ebe-c76a-4609-b1da-90131246a4da` |
| Main consent | `5be8188b-bef3-40e4-beeb-a06e2b50bdba` |
| Repair consent | `71bb7a05-e673-4f00-a27f-36797f75b91c` |
| Owner goal | `2d60081f-caf4-4075-82bc-dc1b7a71399d` |
| Focused test command | 92 tests, `-m` not used, `-o addopts=""`; exit 0 |
| Dashboard test command | 14 tests; exit 0 |
| Dashboard build | exit 0 |
| Local server logs | temp `alive-finish01-server.log`, `alive-finish01-server-restart.log` |
| Local live JSON | temp `alive-finish01-test-a.json`, `-test-b.json`, `-test-c.json` |

The sanitized evidence file contains IDs, statuses, model/usage/receipt fields, task
completion and rejection state. It contains no API token, provider credential, private
repository content or private prompt.

---

## Changed files and commit identities

| Path | Change | Reason |
|---|---|---|
| `docs/intelligence/ALIVE-FINISH-01-REPORT.md` | Added | Required qualification report |
| `docs/intelligence/evidence/ALIVE-FINISH-01-live.json` | Added | Sanitized evidence index for independent review |

- **Baseline / tested implementation:** `3f30158a8597b226fb3c39e8ca1b58c7c1b80a94`
- **Branch:** `alive-finish-01-qualification`
- **Production code changes:** none
- **Test changes:** none
- **Frozen data changes:** none
- **Report commit / final branch HEAD:** the tip of the qualification branch; exact SHA is
  recorded in the draft PR description.

---

## Unresolved risks and limitations

1. **Production is not schema-ready.** Production remains at `0006`; the tested code expects
   `0015`. The disposable runtime is qualified; production deployment is not.
2. **Live repair success is not demonstrated.** The one real repair attempt was safely
   refused; only the offline repair tests establish successful repair mechanics.
3. **Named-case semantic correctness is not established.** The code-review task omitted the
   `item` argument values, so the model used typed `undetermined`. Test A supplies the
   substantive semantic check; the named cases do not.
4. **One small public fixture.** The smoke is not a benchmark and does not establish general
   review quality, improvement over a stateless baseline, or absence of model errors.
5. **Provider model identity is requested, not attested.** `model_observed` is null in all
   receipts. Preserve this limitation in product language.
6. **No browser E2E or full CI/Docker qualification.** The dashboard unit suite and build
   passed; the live API projection is the primary integration evidence.
7. **Environment incident.** The production schema was temporarily forward-migrated and
   restored during setup. Existing data was unchanged, but the incident demonstrates that
   `ALIVE_DSN` can override a worktree `.env`; future runs must explicitly remove or override
   inherited DSN variables.
8. **Currency cost unknown.** Only measured token usage is reported; no billing rates are
   configured.
9. **Repair prompt usability.** The repair model changed an accepted citation's line range.
   The guard worked; the prompt/contract should make exact preservation easier before live
   repair success is claimed.
10. **No claim of learning improvement.** This milestone did not rerun AI-FIRST-04, change
    lesson policy, or modify frozen evidence.
