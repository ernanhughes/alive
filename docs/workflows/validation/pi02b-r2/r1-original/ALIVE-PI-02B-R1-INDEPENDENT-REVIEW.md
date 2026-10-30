# ALIVE-PI-02B-R1 — Independent Adversarial Review

PR: https://github.com/ernanhughes/alive/pull/69 (draft) — "ALIVE-PI-02B: execute governed workflows through Pi"
Reviewed commit: `b2d06caa59c411a87951afc76440a368717e8dfd` (tree `64d5011f660eee3f1d624627c344845d85024091`)
Implementation baseline: `4fed829aa57245b93796e98808818fcb0aa58e8f` (merged INT-02)
Review date: 2026-10-30. Reviewer: independent, read-only. Nothing in the PR, the branch, the owner checkout or any production configuration was modified. No paid or commercial inference was run. No external network operations were performed beyond reading the PR metadata and CI status with `gh`.

Evidence class legend: **VERIFIED** (I executed it and observed it) · **SOURCE-CONFIRMED** (read in the pinned source, not executed) · **INFERRED** · **UNVERIFIED** · **SPECULATIVE**.

Workspaces (all outside the PR):
- Pristine pinned worktree `C:\Projects\alive-review-pi02b-r1` — never edited; `git status` clean, HEAD and tree hash as above.
- Scratch copy `C:\Projects\alive-review-pi02b-r1-scratch` — same SHA; holds the untracked probes and the mutation harness. Every production-file mutation was applied with a `.bak` and restored in `finally`; `git status` of the scratch tree shows only untracked review files.
- Evidence `C:\Projects\alive-pi02b-r1-evidence\` — probe JSON, mutation matrices, copies of the probe file and mutation scripts (`scripts/`). This report lives there and is not committed.
- Databases: disposable SQLite files and one disposable `pgvector` PostgreSQL 16.15 container (`r1-pg`, now removed). Fake credentials only; scripted local providers only.

---

## A. Executive verdict

| Decision | Verdict | Basis |
| --- | --- | --- |
| Merge PR #69 | **REVISE** (no blocker found; two MEDIUM items should be repaired first) | No confirmed authorization bypass, no double-dispatch path, no false completion after an ambiguous effect, no unreconciled Governor reservation. The two MEDIUM findings are F-01 (artifact served for a non-completed run) and F-03 (the dispatch fence's binding clauses and several integrity checks are untested by the author's suites). |
| Start PI-02C | **REVISE** — proceed only after #69 lands with F-01 and F-03 repaired, and F-02 decided | PI-02C will lean on exactly the surfaces F-01 and F-03 describe. |
| Build the Bespoke Intelligence router | **BLOCKED on sequencing, not on a defect** | It depends on PI-02C. Before it starts, multi-process claim safety (F-07) should be shown rather than assumed. |

What the merge gate asked for, answered directly:

- **Authorization bypass:** none confirmed. A forged owner event cannot be minted through the public ingest path (VERIFIED, probe A1). The owner-minted grant is the only trust anchor and the grant is re-validated, including hash, revocation, expiry, goal, inquiry, definition hash, context hash, withdrawal and Governor configuration, at the dispatch fence.
- **Double dispatch:** none found. Duplicate starts, concurrent runner claims, retries after failure and a crash image all produced exactly one provider call or zero (VERIFIED).
- **False completion after an ambiguous effect:** none found. Timeout, malformed response, process interruption and a database fault after a real Pi success all end in `UNKNOWN` or a settled record, never `COMPLETED` on an unreconciled effect (VERIFIED).
- **Unreconciled Governor reservation:** none found. Every probe ended with `reserved = {calls: 0, tokens: 0, tools: 0}` (VERIFIED).

---

## B. Coverage per lens

| Lens | Rating | Notes |
| --- | --- | --- |
| A Authority boundary | SOUND WITH CAVEATS | Forged owner events refused (A1). Context event source is not authenticated (F-02). |
| B Provider dispatch and budget | SOUND | Four authority changes between reservation and dispatch each produced 0 upstream calls. Fence clauses individually load-bearing but untested (F-03). |
| C Transactional integrity | SOUND WITH CAVEATS | All injected faults ended consistent. Artifact exposure for non-completed runs (F-01). |
| D Concurrency / multi-process | SOUND WITH CAVEATS | Run-claim race reproduced on PostgreSQL by the author's harness, which is single-process (F-07). Stage-level compare-and-set is untested (A1). I did not run a multi-process stage race. |
| E Cancellation / timeout / recovery | SOUND | Matrix in section E. |
| F Operation adapter boundary | SOUND | Literal map, no name-based branching, two structurally different workflows run by the same runner. |
| G Dataflow, evidence, artifact integrity | DEFECT FOUND (LOW/MEDIUM) | Tamper detection is sound (experiment F). Misleading `validation_status="passed"` (F-05); F-01. |
| H API / information disclosure | SOUND | No secrets, paths or prompt text in responses; 401/404/405/422 as expected. |
| I INT-02 integration | COULD NOT ASSESS beyond the author's harness and the pristine suite | Zero learning writes observed in the harness on PostgreSQL. I did not probe the receipts resolver for stage-versus-receipt confusion. |
| J Migration 0010 | SOUND | Single head, parent 0009, full cycle on PostgreSQL 16 and SQLite (repo tests). Dangling-reference refusal path SOURCE-CONFIRMED only. |
| K Test integrity | DEFECT FOUND (MEDIUM) | F-03. |

---

## C. Confirmed findings

### F-01 — Artifact endpoint serves the result of a FAILED or CANCELLED run with no run status
- Severity: **MEDIUM**. Evidence: **VERIFIED**. Merge-blocking: no (repair before merge recommended).
- Location: `alive/workflows/runner.py:647-727` (`artifact_view`); route in `alive/workflows/api.py:111`.
- Repro: `probe-c_finish_fault.json` (cognition settlement faults after all stages completed) and `probe-c_cancel_before_finish.json` (cancel requested just before terminal settlement).
- Expected: an artifact whose run did not complete should not be presentable as a finished result, or should carry the run status.
- Observed: run `FAILED` (respectively `CANCELLED`) while `GET /api/v1/workflow-runs/{run}/artifacts/{stage}` returned HTTP 200 and a body with no `status` or terminal reason (keys: `artifact_id, assessment, classification, created_at, definition_sha256, evidence_refs, independent_feedback, input_sha256, intelligence_episode_id, kind, result, run_id, schema, sha256, source_status, stage_id`). The check only requires the `result.record` stage to be `COMPLETED`.
- Impact: a consumer that follows the artifact link sees a complete-looking result for a run the system itself recorded as failed or cancelled. No provider effect is involved in these cases (deterministic workflow), so this is a presentation and trust defect, not an effect-accounting defect. It matters for PI-02C and for any INT-02 reader.
- Root cause: `artifact_view` validates the record stage and the hash chain but never reads `run.status`.
- Minimal repair: add `run_status` and `terminal_reason` to `ArtifactView`, or return 409 unless `run.status == COMPLETED`; pick one and document it.
- Regression test: run the two fault cases above and assert the chosen behaviour.

### F-02 — The context event's source is not authenticated
- Severity: **LOW–MEDIUM** (design gap, not a bypass). Evidence: **VERIFIED**. Merge-blocking: no.
- Location: `alive/workflows/context.py` (`authorized`, Grant fields `context_event_id`, `context_sha256`); probe A2.
- Repro: `probe-a2_context_source.json` — an observation ingested with `source="extension"`, `type="browser.dom_changed"` was admitted as workflow context and the run reached `COMPLETED`.
- Expected: either an owner-approved source class or an explicit statement that the owner's grant over a named event and hash is the whole trust decision.
- Observed: the grant binds the event id and payload hash, which stops substitution after the grant, but nothing checks that the source class is one the owner meant to trust. The owner must still mint the grant, so no one can inject context unprompted.
- Impact: an owner who grants over an extension-originated event approves arbitrary page-derived content as run context. Prompt-injection material in that content reaches the model stage.
- Minimal repair: record the source class in the grant and refuse when it differs, or add an allowlist of admissible source classes; at minimum document that the grant is the only control.
- Regression test: grant over a `source="extension"` event with and without the source class in the grant.

### F-03 — The author's suites do not pin the dispatch fence's binding clauses or several integrity checks
- Severity: **MEDIUM**. Evidence: **VERIFIED**. Merge-blocking: no (repair before PI-02C).
- Location: `alive/workflows/runner.py:150-170` (`authorize_dispatch`, `dispatch_stage_binding`), `:95-110` (`result_event`), `:672` (artifact hash), `:521` (slot release), the deadline check, and `alive/workflows/context.py` (Governor configuration check).
- Method: I applied 20 mutants of my own to the scratch copy and ran the author's four workflow suites (`test_workflow_authority`, `test_workflow_cancellation`, `test_workflow_execution`, `test_workflow_transactions`; 39 tests). The author's suites killed 5 of 20. Survivors, and whether my own probes kill them:

| Mutant | Author suites | My probe |
| --- | --- | --- |
| A1 stage claim not a compare-and-set | survived | not killed — run-level ownership makes it unreachable in a single process (see F-07) |
| A4 Governor configuration change ignored | survived | **killed** (`b_configuration`: the run completed instead of stopping) |
| A7 stored stage-result hash not checked on read | survived | **killed** (`f_matrix-A7v`: `artifact_hash_rebuilt` returned 200 instead of 404) |
| A8 stored artifact hash not checked on read | survived | **killed** (`f_matrix-A8v`: `artifact_content` returned 200 instead of 404) |
| A9 egress guard fails open when no guard is installed | survived | not killed; `create_app` always installs the guard, so this needs a host that builds `PiEgress` without it |
| A10 model comparison removed in `context.py:220` | survived | redundant with the fence check (B1) — not independently exploitable |
| A12 dependency completion not required before a stage starts | survived | UNVERIFIED — stages run in declared order |
| A13 unclaimed-inquiry requirement dropped | survived | UNVERIFIED |
| A14 slot not released on success | survived | **killed** (`h_sequential_runs`: the second run in the same instance is refused with `execution_identity_or_instance_slot_conflict`) |
| A15 execution deadline not enforced | survived | **killed** (`b_expire_deadline`: the run completed) |
| B1 fence: model not compared | survived | **killed** (`j-matrix-B1`: substituted model reached the provider, 1 upstream call) |
| B2 fence: context not compared | survived | **killed** (`j-matrix-B2`: 1 upstream call) |
| B3 fence: reservation status not required | survived | **killed** (`j-matrix-B3`: 1 upstream call) |
| B4 fence: stage must be RUNNING | survived | inconclusive (`j-matrix-B4`: probe errored with no upstream call) |
| B5 fence: invocation-stage link dropped | survived | **killed** (`j-matrix-B5`: 1 upstream call) |

  Caught by the author's suites: A2 (revocation), A3 (withdrawal), A5 (UNKNOWN preservation), A6 (cancel request), A11 (Pi response linkage).
  A7 as first written produced a syntax error (pytest exit code 4) and was replaced by A7v; both A7 and A8 are in `additional-mutations.json` and `f-matrix-*.json`.
- Why the author's own mutation set missed this: its `dispatch_fence` mutant disables the whole guard, so the five clauses inside `dispatch_stage_binding` are never separated. The eleven author mutants (`docs/workflows/validation/pi02b/mutations.json`) all report KILLED with assertions that match the intended behaviour (SOURCE-CONFIRMED).
- Impact: the binding clauses stop a substituted reservation (wrong model, wrong context, wrong status, wrong stage link) from reaching the provider. That protects against database-level substitution only, so it is defence in depth, but it is the PR's central fence and nothing pins it.
- Minimal repair: add one test per clause using the `gated_pi_run` pattern in my `probe_j` (tamper after reservation, before dispatch, assert 0 upstream calls); add the A4, A7, A8, A14 and A15 tests above.

### F-04 — One opaque error category for distinct failure causes
- Severity: **LOW**. Evidence: **VERIFIED**. Merge-blocking: no.
- Observed: `adapter_or_persistence_failure` is the stage and run category for revocation at the fence (`b_revoke`, `b_withdraw`, `b_configuration`, `b_expire_deadline`), provider HTTP 500, timeout, malformed responses, an injected reservation fault and an injected cognition fault. Only the revoked-after-response case reports `authorization_expired_or_revoked`. The Pi layer does record `workflow_authority_revoked` on the request, so the distinction exists one layer down.
- Impact: operators and INT-02 readers cannot tell a revoked authority from a persistence fault from the run row.
- Minimal repair: surface the fence's rejection reason on the stage; keep the opaque category only as the fallback.

### F-05 — `validation_status="passed"` on a stage whose claim is uncited and whose semantic status is `unverified`
- Severity: **LOW–MEDIUM** (labelling). Evidence: **VERIFIED** for the observed fixture, **UNVERIFIED** for the intended contract.
- Repro: `probe-i_api.json`. Stage rows show `analyze: passed`, `validate: passed`, `record: passed`. The retained artifact holds one claim with `evidence_refs: []`, `recommendation: "proceed"`, `confidence: 0.9`, and `assessment.semantic_status: "unverified"`.
- Impact: the artifact is honest about `unverified`. The stage-level `passed` is not, and it is the field a dashboard is likely to show. `independent_feedback` is correctly `false`.
- Minimal repair: rename the stage field value (for example `contract_checked`) or add `semantic_status` to the stage row. Decide whether an uncited claim should pass `evidence.validate_references` at all.

### F-06 — Receipt provenance notes
- Severity: **NOTE**. Evidence: **VERIFIED**.
- The retained receipts name `implementation_commit 4de4f86`. `b2d06ca` differs from it only in `docs/` and one docstring line in `scripts/workflows_execution_mutations.py` (VERIFIED by diff). The manifest hashes of all listed receipt files match (VERIFIED).
- `image-parity.json`: 9 of 12 file hashes equal the git blob only after converting to CRLF, the other 3 equal the LF blob. The image was built from a Windows working tree. Python is indifferent to this, but "image equals source" holds modulo line endings, not byte-for-byte against the blob.
- `linux-initial.txt` records 2 failures (`test_ratchet_no_new_direct_meta_construction`, `test_persistent_benchmark_budget_and_paid_opt_in`) caused by `scripts/benchmark.py` missing from the container; `linux-supplement.txt` is 4 tests. The Linux full-suite evidence is therefore the remote CI run, which I confirmed green on the head SHA (section G).

### F-07 — Single-process dependence of the concurrency claims
- Severity: **NOTE**. Evidence: **SOURCE-CONFIRMED** and **VERIFIED** for what the harness does; multi-process correctness is **UNVERIFIED**.
- `scripts/workflows_execute_check.py` (~lines 112–150) builds two extra `Database(settings.database_url)` engines wrapped in `WorkflowRunner(SimpleNamespace(...))` inside one process and races `execute(run_id)` with `asyncio.gather`. I ran it against my PostgreSQL 16.15: one `workflow.execution.claimed` event, one upstream call, three claim workers, replay with zero dispatch, zero learning writes. This proves the atomic run claim on separate connections. It does not prove several OS processes, and it uses a stubbed kernel.
- The design is conservative: `workflow_executions.slot` is unique per instance, the run needs an owner claim, and the kernel's exclusive per-database lock implies one active ALIVE process. Correctness therefore currently depends on that single-process kernel lease. The compare-and-set on stage rows (A1) is not exercised by any test.

### F-08 — Two baseline tests were modified
- Severity: **NOTE**. Evidence: **VERIFIED** by diff.
- `test_migrations.py`, `test_intelligence_migration.py`: version `0009` → `0010` and the new table added to the list. Expected.
- `test_workflows_api.py`: route count 8 → 9 with an explicit GET-only assertion for the artifact route. Expected.
- `test_workflows_store.py`: the Pi-run reference test was strengthened (now requires an existing receipt, FK enforced). The package-boundary test was loosened: the regex now permits `alive.pi.models` only (`alive.pi\b(?!\.models\b)`); `alive/workflows/runner.py:12` imports `PiProviderRequest, PiRun` from it. `from alive.pi import …` and `alive.providers` stay forbidden. Acceptable, and narrow.

---

## D. Successful falsification resistance

Each item is something I tried to break and could not.

| Attack | Result |
| --- | --- |
| Mint or impersonate an owner authorization through the public ingest route | Refused: `owner_authorization_required` (`a1_forged_authorization`) |
| Revoke the grant between reservation and dispatch | 0 upstream calls; Pi request `rejected`; reservation released (`b_revoke`) |
| Withdraw the context between reservation and dispatch | 0 upstream calls (`b_withdraw`) |
| Change the Governor configuration between reservation and dispatch | 0 upstream calls (`b_configuration`) |
| Expire the execution deadline between reservation and dispatch | 0 upstream calls (`b_expire_deadline`) |
| Provider HTTP 500 | one call, run `FAILED`, retry stays `FAILED`, no second dispatch (`b_failure_http_500`) |
| Provider timeout | one call, run `UNKNOWN`, Pi request `ambiguous`, retry stays `UNKNOWN` (`b_failure_timeout`) |
| Malformed provider response | one call, run `UNKNOWN`, `ambiguous`, no replay (`b_failure_malformed`) |
| Duplicate `start` and duplicate `execute` | one run, one upstream call; second grant refused `unclaimed_governor_inquiry_required`; second `execute` returned `RUNNING` without dispatching (`b_duplicates`) |
| Fault inside the reservation transaction | no invocation, no Pi run, reservation 0 (`c_fault_before_reservation_commit`) |
| Cancel immediately after the reservation commit | invocation `cancelled`, 0 upstream calls, reservation 0 (`c_cancel_after_reservation_commit`) |
| Randomised cancel races, with and without a model stage | every trial ended `CANCELLED` or `COMPLETED` with invocation, Pi run and request in matching terminal states (`g_cancel_race_model_*`) |
| Revoke after the provider responded, before the stage commit | stage committed as `COMPLETED` (effect already happened and reconciled), later stages `CANCELLED`, Pi `SETTLED`, run `FAILED` with `authorization_expired_or_revoked` (`c_revoke_after_response`) |
| Real Pi success, then a database fault while committing the stage result | run `UNKNOWN`, Pi `SETTLED`, request `settled`, invocation `validated`, reservation 0; `execute` again and `recover()` did not redispatch (1 upstream call total) (`k_pi_ok_then_db_fault`) |
| Fault while settling the inquiry after all stages completed | run `FAILED`, reservation 0 (but see F-01) |
| Crash image taken mid-provider call, restarted on a new app | run `UNKNOWN` (`interrupted_requires_review`), replay stays `UNKNOWN`, no redispatch (`e_crash_image`) |
| Evidence substitution: edit the stored stage-result event, edit the artifact content, rebuild the hash inside the event, swap `output_ref` to another stage's event | all four return 404 "Result unavailable or integrity check failed" on the baseline (`f-matrix-baseline`); each integrity check is individually load-bearing (mutants A7v and A8v flip exactly the expected rows to 200) |
| Substituted reservation (wrong model, context, status, stage state, stage link) reaching the provider | all five: 0 upstream calls on the baseline (`j-matrix-baseline`) |
| Information disclosure in API responses | no API key, token, host path or prompt marker in artifact, run or stage bodies; unknown run 404; non-record stage artifact 404; oversize id 422; unauthenticated 401; POST/PUT/DELETE/PATCH 405 (`i_api`) |
| Adapter boundary: forged operation | unknown operations are not in the literal `ADAPTERS` map; no name-based branching in `runner.py` or `adapters.py` (grep: only `run.workflow_name == spec.name` at `runner.py:297` and operation equality at `:397`, `:662`) (SOURCE-CONFIRMED) |
| Same runner, structurally different workflows | the four-stage Pi workflow (`prepare, analyze, validate, record`) and the three-stage deterministic workflow (`prepare, compare, record`) both run to completion in the same runner (`c_finish_fault`, `i_api`) |

---

## E. Concurrency and interruption matrix

| Point of interruption | Cancel | Revoke | Provider failure | Process stop | DB fault |
| --- | --- | --- | --- | --- | --- |
| Before reservation | `CANCELLED`, 0 dispatch | `FAILED`, 0 dispatch | n/a | recoverable, never resumed | `FAILED`, no invocation |
| Reservation committed, before dispatch | `CANCELLED`, invocation cancelled | `FAILED`, request rejected | n/a | `UNKNOWN` only if a request was dispatched or ambiguous; otherwise cancelled | n/a |
| Dispatch marker written, provider in flight | not interruptible | n/a (already past the fence) | timeout/malformed → `UNKNOWN`; 500 → `FAILED` | crash image → `UNKNOWN`, no redispatch | n/a |
| Provider responded, stage not committed | stage still commits (effect reconciled) | stage commits, later stages cancelled | n/a | — | `UNKNOWN`, Pi settled, no redispatch |
| All stages complete, before terminal settlement | `CANCELLED` with artifact retained (F-01) | n/a | n/a | recoverable | `FAILED` with artifact retained (F-01) |

Evidence classes for the matrix: the cells that cite a probe above are VERIFIED. The cells "not interruptible", "n/a (already past the fence)" and the "process stop" cells before the dispatch marker are SOURCE-CONFIRMED or INFERRED from `_abandon` and `recover()`, not executed.

PostgreSQL: the run-claim race on separate connections is VERIFIED by the author's harness running in my environment (F-07). Competing terminal settlement on PostgreSQL with independent connections was NOT RUN; on SQLite the cancel/settle race is covered by `g_cancel_race_*` and `c_cancel_before_finish`.

---

## F. Mutation assessment

- Author set: 11 mutants, all KILLED, assertions match the intended behaviour (SOURCE-CONFIRMED from `mutations.json`). I did not re-run the author's mutation script.
- My set: 20 mutants (A1–A15, B1–B5). Author's four workflow suites killed 5 (A2, A3, A5, A6, A11). 15 survived; 9 of those are killed by my own probes and show a real test gap (A4, A7v, A8v, A14, A15, B1, B2, B3, B5); 1 is inconclusive (B4); 5 remain unkilled (A1, A9, A10, A12, A13), of which A10 is redundant with B1 and A1 is unreachable in one process.
- Equivalent-mutant judgement for A9, A12 and A13 is UNVERIFIED; I did not write a probe for them.
- Raw data: `additional-mutations.json`, `dispatch-fence-mutations.json`, `f-matrix-*.json`, `j-matrix-*.json`.

---

## G. Command log

| Environment | What | Result |
| --- | --- | --- |
| Windows, pristine tree | `CI=true uv run pytest -q -p no:cacheprovider -W ignore -rs` (full suite) | **1163 passed, 12 skipped, 1 xfailed**, 946 s, exit 0 |
| Windows, scratch tree | author's four workflow suites (39 tests) | 39 passed |
| Windows, scratch tree | my probe file `tests/test_review_r1.py` | probes pass; several are observation-only and write JSON |
| Windows + PostgreSQL 16.15 (disposable container) | `scripts.workflows_execute_check` | PASS: 1 provider request, restart PASS, replay PASS (zero dispatch, artifacts or learning writes), learning delta 0, 3 claim workers, 1 owner, `paid_inference` NOT_RUN |
| Windows + PostgreSQL 16.15 | alembic `upgrade head` → `downgrade 0009` → `upgrade head` → `downgrade 0008` → `upgrade head` → `downgrade base` → `upgrade head` | all steps succeeded, final `0010`, single head |
| SQLite | migration tests inside the full suite (`test_migrations.py`, `test_intelligence_migration.py`, `test_workflow_execution_migration.py`) | passed |
| Remote CI on head `b2d06ca` | `gh pr checks 69` | backend ubuntu and windows, dashboard, first-contact-postgresql, notebook — all pass on both workflow runs listed |
| Linux (local) | none run by me | NOT RUN; covered by remote CI ubuntu |
| Docker image / container restart | none run by me | NOT RUN; I read the retained receipts (`image-parity.json`, `container-replay.json`, `docker-postgresql.json`) and verified the manifest hashes and the commit relationship (F-06) |
| Real Pi, local scripted HTTP provider | all provider probes use the real pinned Pi gateway path with a scripted local upstream (`Upstream`) | VERIFIED; no commercial provider contacted |
| Dashboard `npm test` / `npm run build` | none run by me | NOT RUN; remote CI `dashboard` job passed |
| Author's `workflows_execution_mutations.py` | not run | NOT RUN |
| Competing terminal settlement on PostgreSQL | not run | NOT RUN |
| Multi-process stage race | not run | NOT RUN |

---

## H. Unverified claims

- Whether `evidence.validate_references` is meant to accept a claim with no evidence (F-05).
- Whether the INT-02 receipts resolver can confuse a workflow stage with a receipt, and whether it reads stage artifacts of non-completed runs (lens I).
- The behaviour of A9, A12 and A13 mutants against any realistic exploit.
- Multi-process correctness of the stage compare-and-set and of the run claim without the kernel lease (F-07).
- The migration's refusal path for historical dangling Pi references (read, not exercised).
- Distributed-worker safety generally; the stubbed-kernel harness does not establish it.

---

## I. Architectural assessment

The structure is sound where it matters. Authority is a single owner-minted event, hashed, re-validated at the one place a provider call can happen, inside the transaction that writes the dispatch marker, and it fails closed. Retained results are written in the same transaction as stage completion, chained by two hashes, and re-verified on read. Recovery never resumes and preserves doubt as `UNKNOWN`. The adapter map is literal and the runner has no workflow-specific branches.

Weak points are around the edges, not the core:
1. The presentation layer (F-01, F-04, F-05) says more than the state supports.
2. The test suite proves the fence as a whole but not its parts (F-03).
3. Concurrency safety rests on a single-process kernel (F-07).
4. The context trust decision lives entirely in the owner's grant (F-02); that is acceptable if it is documented and the source class is recorded.

---

## J. Remediation plan (not started; for the owner to approve)

1. F-01: add `run_status`/`terminal_reason` to `ArtifactView`, or 409 unless COMPLETED. Test with the two repro cases.
2. F-03: add the clause-level fence tests (wrong model, context, status, stage state, stage link), plus configuration change, deadline expiry, sequential runs (slot release), artifact-hash tamper and stage-result-hash tamper. My probe file and `scripts/` already contain working versions to port.
3. F-05: relabel stage `validation_status` or expose `semantic_status` on stage rows.
4. F-04: carry the fence rejection reason onto the stage.
5. F-02: decide and document the source-class policy for context events.
6. F-07: before the Bespoke router, add a genuine multi-process stage-claim race on PostgreSQL and a competing-terminal-settlement test with independent connections.
7. F-06: rebuild the Docker parity receipt from an LF checkout, or document the CRLF basis.

None of these needs a design change.

---

## K. Final decision

- **Merge #69:** REVISE. No merge blocker was found; the gate conditions are met. Repair F-01 and F-03 first because they are small and they pin the fence the PR is about. If the owner prefers to merge now, record F-01 and F-03 as the first PI-02C tasks.
- **Start PI-02C:** REVISE — after #69 lands with F-01 and F-03 repaired and the F-02 policy decided.
- **Build the Bespoke Intelligence router:** BLOCKED on sequencing (depends on PI-02C) and on showing multi-process safety (F-07).

I did not proceed to code remediation, did not merge or comment on #69, did not start PI-02C or router work, did not upgrade Pi dependencies, and did not alter frozen evidence.
