# ALIVE-PI-02B-R2 — Independent Re-Review and Clause-Mutation Report

PR: https://github.com/ernanhughes/alive/pull/69
Reviewed head: `ab066db51d3992905980aa5a1122c6e540bd1335` (confirmed unchanged at the end of the review)
R1 reviewed commit: `b2d06caa59c411a87951afc76440a368717e8dfd`
Review date: 2026-10-30. Read-only: nothing in the PR, its branch, the owner checkout or production configuration was modified. No paid inference. Scratch worktrees and a disposable PostgreSQL 16 container only.

Note on PR state: at the end of the review `gh` reports the PR as **not a draft** (it was a draft at the start of R2). I did not change that.

Evidence classes: **VERIFIED** (executed and observed) · **SOURCE-CONFIRMED** (read in source) · **INFERRED** · **UNVERIFIED**.

Evidence folder: `C:\Projects\alive-pi02b-r2-evidence\` (raw JSON per probe and per mutant, `scripts/` holds every test file, campaign script and campaign log used here).

---

## A. Decision

| Decision | Verdict |
| --- | --- |
| Merge PR #69 as it stands | **REVISE** |
| Start PI-02C | **REVISE** — after the bounded R3 change below lands |

**No merge-gate failure was found.** There is no authorization bypass, no double-dispatch path reachable through a supported interface, no false completion after an ambiguous effect and no unreconciled Governor reservation.

Why REVISE and not GO:
1. One confirmed production defect: the stage-deadline classification regression (section C, D-01). It is a reporting defect only.
2. Several guards are load-bearing but no test pins them. The most important are the goal-status check and the one-invocation-per-stage check (section D). Removing either lets bad state through, and the 1,205-test suite does not notice.

Why not BLOCKED: every dispatch, cancellation, ambiguity and restart scenario I ran behaved correctly on the unmodified head, and the missing items are tests plus one one-line fix.

---

## B. What the head does well (R1 findings re-checked)

| R1 finding | R2 result | Evidence |
| --- | --- | --- |
| F-01 artifact served for a non-completed run | **Fixed by labelling.** The artifact now carries `run_status`, `terminal_reason`, `workflow_completed`, `stage_state`, `stage_uncertainty`. A `FAILED`, `CANCELLED` or `UNKNOWN` run still returns HTTP 200 but is labelled. | VERIFIED (R1 probes `c_finish_fault`, `c_cancel_before_finish` re-run; author's 4-way test) |
| F-02 context source not authenticated | **Fixed as policy.** The grant must carry a provenance record that exactly equals an allowlisted (source, event type) pair. Raw extension events without provenance are refused with `context_provenance_required_or_changed`. | VERIFIED (R1 probe `a2` now refused) |
| F-03 fence and integrity checks untested | **Largely fixed for the clauses I named.** 20 of 21 author mutants killed, one redundant (A10). I re-ran the author's replay independently: same result. | VERIFIED (`scripts.workflows_r2_mutations`) |
| F-04 opaque error category | **Mostly fixed.** Fence refusals report `authority_refused`; persistence failures `result_persistence_failure`. Provider failures still all report `adapter_execution_failure` (see D-03). | VERIFIED |
| F-05 `passed` read as validation | **Fixed.** Stage rows now carry a `validation` object (`contract_status`, `structural_status`, `reference_identity_status`, `semantic_status: unverified`, `independent_verification: false`, `uncited_claims_permitted: true`). One caveat in D-04. | VERIFIED |
| F-07 single-process dependence | **Evidenced.** On PostgreSQL a competing OS process is refused by the host lease (HTTP 503) and a successor process replays with zero effect-count change. | VERIFIED (`--process-probe`) |

Also VERIFIED on the unmodified head:
- All 31 original R1 probes run unchanged and pass.
- Full backend suite on the pristine tree: **1,205 passed, 12 skipped, 1 xfailed** (1,098 s).
- GitHub CI: both workflow runs on `ab066db` are green (backend ubuntu and windows, dashboard, first-contact-postgresql, notebook).
- Migrations: no change to migrations, `pi-runtime`, `alive/pi` or `alive/cognition.py` since R1. Single head `0010`; upgrade → downgrade 0009 → upgrade on PostgreSQL 16 passes.
- Real browser-event note (SOURCE-CONFIRMED and VERIFIED): a raw extension `browser.dom_changed` event with `{url, text}` cannot start a run (`context_scope_or_integrity`) because it lacks the approved-context shape. The provenance policy therefore blocks nothing new. PI-02C will need a context-preparation step to turn captured pages into admissible context.

---

## C. Confirmed production defect

### D-01 — Stage deadline expiry is reported as `adapter_execution_failure` instead of `timeout`
- Severity: **LOW** (label only). Evidence: **VERIFIED**. Merge-blocking: no, but required in R3.
- Location: `alive/workflows/runner.py`, `_stage`, the `try/except` around the adapter call (about line 452).
- Cause: `asyncio.timeout(stage.limits.timeout_seconds)` raises `TimeoutError` when it expires. The new `except Exception` turns it into `Refused("adapter_execution_failure")`, so the outer handler no longer sees a `TimeoutError` and cannot label it `timeout`.
- Is it only a label? **Yes.** `_abandon` chooses the terminal state from Pi and request state, never from the reason string, so terminal state, uncertainty, Governor settlement and dispatch are unaffected. I ran three cases on both commits; everything except the label is identical:

| Case | R1 label | R2 label | Run | Stage uncertainty | Pi / request | Provider calls | Replay |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Deterministic stage times out | `timeout` | `adapter_execution_failure` | `FAILED` | none | none | 0 | `FAILED`, 0 |
| Pi stage times out after dispatch | `timeout` | `adapter_execution_failure` | `UNKNOWN` | `unknown_outcome` | `UNKNOWN` / `ambiguous` | 1 | `UNKNOWN`, still 1 |
| Pi stage times out before dispatch | `timeout` | `adapter_execution_failure` | `FAILED` | none | `CANCELLED` / `rejected` | 0 | `FAILED`, 0 |

  Governor reservations were 0 in all six runs. The whole-run wall-deadline path still reports `timeout` on R2.
- Smallest correction (verified in a scratch worktree, saved as `proposed-timeout-fix.diff`):
  ```
  -        except Refused:
  +        except (Refused, TimeoutError):
               raise
  ```
  With it, all four cases report `timeout` with identical states, and the author's invariants file still passes (12 passed).
- Regression test: the three-case test in `scripts/test_review_timeout.py`, asserting label **and** uncertainty. A Pi timeout after dispatch must stay `UNKNOWN` with `unknown_outcome`; the fix must not turn it into a definite failure.

### Minor label notes (optional in R3)
- D-02: a goal cancelled mid-run ends with reason `authorized_inquiry_required`, because that check bundles goal and inquiry state. Misleading, not unsafe.
- D-03: provider failures (HTTP 500, timeout, malformed response) all report `adapter_execution_failure`. The Pi layer records the distinction, the workflow row does not.
- D-04: `reference_identity_status` reads `passed` on a model stage whose claim has an empty `evidence_refs` list. It is vacuously true and the same view says `semantic_status: unverified` and `uncited_claims_permitted: true`, so the object is honest as a whole. A reader of the single field could still be misled.

---

## D. Clause-mutation campaign

Method: every single-line `and <condition>` clause inside the authorization functions was replaced with `and True`, one at a time, in a scratch worktree, and the guard-relevant workflow tests were run (the four pre-existing authority suites plus the four new R2 files). Clauses on instance-id equality and size limits were skipped. Mutants that produced no failing test were then attacked with targeted probes to decide what they are.

Scope: `context.py` 25 clauses (`authorized`, `model_claim`), `runner.py` 21 clauses (`authorize_dispatch`, `_authority`, stage claim). **46 mutants: 10 caught, 36 survived.** The mutant list is a different, mostly unseen set from the 21 R1 mutants the author already replayed. Raw data: `scripts/r2-clause2.log`, `scripts/r2-clause-runner.log`, `clause-mutations-runner.json`.

### D1. Load-bearing guards with no pinning test — required in R3
For each of these a probe or controlled test showed that **removing the clause lets bad state through** while the full suite stays green.

| Site | Guard | What happens without it | Proof |
| --- | --- | --- | --- |
| `context.py:151` | `goal.status in ("active","accepted")` | A goal cancelled through the real API still lets the workflow dispatch and complete: 1 provider call, run `COMPLETED` | VERIFIED: `goalcancel-*`, all 3 real-route tests fail under the mutant |
| `context.py:245` | `stage.model_invocation_id is None` | One workflow stage reaches the provider **twice**: 2 upstream calls, run `COMPLETED` | VERIFIED: `negative-double_reservation-mut245` (baseline refuses the second reservation with `model_stage_claim_required`, 1 call) |
| `context.py:211` | `source_event_ids == [source.id]` | Out-of-contract context admitted | VERIFIED: `contract-source_ids-mut211` |
| `context.py:212` | `requested_action_kind == "record_analysis"` | A context requesting another action kind is admitted | VERIFIED: `contract-action_kind-mut212` |
| `runner.py:159` | `stage.run_id == run.id` (fence) | A stage belonging to another run is accepted | VERIFIED: `negative-stage_of_other_run-mut159` (1 call vs 0) |
| `runner.py:163` | `call.investigation_id == run.investigation_id` (fence) | An invocation from another inquiry is accepted | VERIFIED: `negative-invocation_of_other_inquiry-mut163` |
| `runner.py:296`, `297`, `298` | run row `definition_sha256`, `workflow_name`, `workflow_version` equal the grant and spec | Raw-SQL corruption of the run row crosses the fence | VERIFIED: `identity-*-mut296/297/298` (the ORM `ImmutableRecord` guard blocks ORM writes, so these need Core `UPDATE`) |
| `runner.py:300`, `301`, `308` | run `goal_id`, `authorization_ref`, `input_sha256` | Same, ORM-writable | VERIFIED: `identity-*-mut300/301/308` |

The goal-status and one-invocation-per-stage guards are the ones that matter in practice. The rest only fire on corrupted internal state, which no supported interface produces. They are still worth pinning, because that is what a fence is for.

### D2. Redundant guards, independently enforced
Not defects. Redundancy in security code is a feature; I do not recommend removing any of these.

| Site | Guard | Enforced independently by |
| --- | --- | --- |
| `context.py:127` | event type is `workflow.execution.authorized` | reserved source `workflow-owner` (caught, `:126`; public ingest returns 422), plus Grant schema validation (SOURCE-CONFIRMED) |
| `context.py:152`, `238`, `241` | object is not None | the next clause dereferences the object, so the mutant raises instead (equivalent mutants) |
| `context.py:237`, `runner.py:285` | `not cancel_requested` | an explicit `raise CancelledError` on the line before (`context.py:229`, `runner.py:277`) (equivalent) |
| `context.py:240` | run is `RUNNING` | `_authority` at every stage and persist boundary |
| `context.py:242`, `243` | stage belongs to run; stage is `RUNNING` | the dispatch fence repeats them later (`runner.py:159` / `160`). `160` is caught; `159` is in D1 |
| `context.py:254` | approved model | the dispatch fence (`runner.py:164`, caught) |
| `context.py:256` | context equals approved | the `model_input_changed` hash check and the fence (`runner.py:165`, caught) |
| `context.py:257` | inquiry matches run | the fence (`runner.py:163`, in D1) |
| `context.py:258` | deadline at reservation | the fence and `_authority` (`runner.py:286`, caught) |
| `context.py:259` | transport is `pi` | Pi egress is the only workflow path (SOURCE-CONFIRMED) |
| `runner.py:284` and `287` | slot and run status in `_authority` | each other (a finished run has its slot cleared and a terminal status). **Removing both at once was not tested.** |

### D3. Unreachable under supported interfaces
| Site | Reason |
| --- | --- |
| `context.py:154` `inquiry.goal_id == goal.id` | no API changes an inquiry's goal; grants are minted consistent. DB-level only |
| `context.py:244` operation is `cognition.role` | the adapter map is literal and only the role adapter calls the claim |
| `runner.py:283` `execution.owner == owner` | the dispatch fence passes `execution.owner` into `_authority` by design, so this clause only matters for a stale second runner. The host lease (VERIFIED on PostgreSQL) prevents a second runner. **Not executed.** |
| `runner.py:299` investigation identity | foreign keys plus unique constraints on `workflow_executions.investigation_id`; not probed |
| `runner.py:396`, `397` stage row type and attempt | derived from the immutable definition; not probed |

### D4. Unresolved
| Site | Question |
| --- | --- |
| `context.py:155` inquiry state is not terminal | It is the only guard if a workflow inquiry becomes terminal while its goal stays `active`. The real Governor stop and pause commands are stopped anyway, because they also move the goal out of `active` (so `:151` blocks them). I found no supported command that ends the inquiry alone. A direct-SQL flip of the inquiry state (unsupported) let one dispatch through with this clause removed. **Document the invariant and its owner, and ideally add a lifecycle-boundary test.** |
| `context.py:255` role contract equals `role_contract(role)` | Not probed. Likely covered by the stage input hash; unconfirmed. |

### D5. A probe artefact that is not a finding
A direct SQL flip of an inquiry to `CANCELLED` left the Governor reservation held (4 calls, 50,000 tokens, 3 tools). The real Governor stop and pause paths release the reservation (0 held). The leak came from bypassing the Governor with SQL, so I do not count it.

---

## E. Goal cancellation through the real API (requested priority)

`POST /api/v1/goals/{id}/transition {"status":"cancelled"}` — not direct SQL.

| Cancel point | Backend | Provider calls | Run | Invocation / Pi / request | Reservation |
| --- | --- | --- | --- | --- | --- |
| Before reservation | SQLite and PostgreSQL | 0 | `FAILED` (`authorized_inquiry_required`) | none | 0 |
| After reservation, before dispatch | SQLite and PostgreSQL | 0 | `FAILED` (`authority_refused`) | `failed` / `FAILED` / `rejected` | 0 |
| During the provider call | SQLite and PostgreSQL | 1 | `UNKNOWN` | `validated` / `SETTLED` / `settled` | 0 |
| Execute again, then `recover()` | all above | no further calls | unchanged | unchanged | 0 |

The third row is deliberate: the model operation finished and was accounted for, but the workflow cannot present a trusted completed result after losing authority mid-flight, so it stays `UNKNOWN`. Invocation, Pi and workflow states are intentionally separate.

PostgreSQL race (cancel concurrent with dispatch release, delays 0 to 50 ms, single process, separate pooled connections): at 0 and 2 ms dispatch won (1 call, `UNKNOWN`); at 5 ms and above the cancel won (0 calls, `FAILED`). Every outcome was coherent, reservation 0, no replay dispatch. This shows ordering behaviour in one process under the kernel lock; it does not show cross-process behaviour, which the host lease excludes.

Mutation proof: removing `context.py:151` makes all three real-route tests fail ("dispatch crossed an acknowledged goal cancellation"). Test file: `scripts/test_review_goal_cancel.py`.

---

## F. Required R3 change (bounded)

All items are tests plus one line. No change to Pi, Governor, database, dispatch or recovery behaviour is needed.

1. **D-01**: `except (Refused, TimeoutError): raise`, plus the three-case timeout test asserting label and uncertainty.
2. **Goal cancellation**: the three real-route tests (before reservation, after reservation, during provider call), each asserting provider calls, run state, reservation 0 and no redispatch on replay. Optional: the PostgreSQL race as an invariant test, not an outcome test.
3. **One stage, one invocation** (`context.py:245`): the double-reservation test.
4. **Scope contract** (`context.py:211`, `212`): negative tests for a wrong source-id list and a wrong action kind.
5. **Corrupted association at the fence** (`runner.py:159`, `163`): the two controlled negative tests.
6. **Run-identity at the fence** (`runner.py:296`–`301`, `308`): one parametrised raw-SQL test, six fields.
7. **Document or test** the inquiry-state invariant (`context.py:155`).
8. Optional, only if it does not widen the change: reason labels for D-02 and D-03.

Working versions of every test are in `scripts/` (`test_review_goal_cancel.py`, `test_review_negative.py`, `test_review_contract.py`, `test_review_identity.py`, `test_review_timeout.py`). They use the repo's existing fixtures and helpers and can be ported with minimal edits. Each one passes on the unmodified head and fails when its target clause is removed.

---

## G. Command log and limits

| Environment | What | Result |
| --- | --- | --- |
| Windows, pristine tree | full backend suite | 1,205 passed, 12 skipped, 1 xfailed |
| Windows | original R1 probes (31) | all pass |
| Windows | author's `workflows_r2_mutations` replay | 20 killed, 1 redundant |
| Windows | clause-mutation campaign | 46 mutants: 10 caught, 36 survived, classified in section D |
| Windows + PostgreSQL 16.15 | `workflows_execute_check` with `--process-probe` | PASS; competing process refused, successor replays with 0 effect delta |
| Windows + PostgreSQL 16.15 | migrations upgrade / downgrade 0009 / upgrade | PASS, head `0010` |
| Windows + PostgreSQL 16.15 | goal-cancel and race tests | PASS (section E) |
| Remote CI on `ab066db` | `gh pr checks 69` | both runs green on every job |
| Linux local, Docker image, container restart | none run by me | NOT RUN; covered by remote CI and the author's receipts, which I did not re-derive |
| Dashboard tests and build | none run by me | NOT RUN; remote CI `dashboard` job green |
| Real Pi | pinned Pi with a scripted local HTTP provider | VERIFIED; no commercial provider contacted |

Limits: the campaign tested one mutation operator (clause deletion) on authorization code only. I did not mutate the transaction, recovery or settlement code in R2. Competing terminal settlement across separate OS processes was not run, because the host lease excludes a second runner. The pairs `context.py:242`/`runner.py:159` and `context.py:257`/`runner.py:163` are each covered by the other layer, and removing both at once was not tested.

---

## H. Housekeeping

The worktrees `alive-review-pi02b-r2`, `-r2-scratch`, `-r2-probe` and `-r2-neg` (and the R1 ones) exist under `C:\Projects`, all at `ab066db` with clean tracked files and only my untracked probe files. The disposable PostgreSQL container `r2-pg` is removed at the end of this review. Nothing was committed, pushed or posted.
