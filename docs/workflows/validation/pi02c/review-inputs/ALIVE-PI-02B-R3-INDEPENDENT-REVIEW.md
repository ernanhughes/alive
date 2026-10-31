# ALIVE-PI-02B-H / R3 — Independent Review

PR: https://github.com/ernanhughes/alive/pull/71
Pinned head: `b56d3ccfc8cedc906289ad67e43125598e64e91c` (one commit on base `c4257e0`)
Base: `c4257e0393b98c3cd81453903e701de389185fcb` (merged PI-02B, #69; tree equals reviewed `ab066db`)
Review date: 2026-10-31. Read-only: the PR, its branch, `main`, the owner checkout and production configuration were not modified. No paid inference. Fresh worktrees only.

**PR state discrepancy.** The request described #71 as an open draft. GitHub reports it as **merged** (by `ernanhughes`, 2026-10-31 00:48Z, merge commit `b0b3e40ab51e2ea4f482a20767f9bad8b4491765`). The pinned head `b56d3cc` is an ancestor of `main`, and `alive/`, `tests/`, `migrations/` and `pi-runtime/` on `main` are identical to the pinned head. This is therefore a post-merge verification of code that is already on `main`. The decision below is stated for the code, not for a merge that has already happened.

Evidence classes: **VERIFIED** (executed and observed) · **SOURCE-CONFIRMED** (read in source) · **INFERRED** · **UNVERIFIED**.

---

## A. Decision

**GO.** The R3 change does what it claims, and the new tests protect what they advertise. No finding blocks the PI-02C start.

I found no authorization bypass, no double-dispatch path, no false completion after an ambiguous effect and no held Governor reservation. Two LOW test-strength gaps (R3-1, R3-2) and three notes are listed in section D. None changes the decision; R3-1 and R3-2 are cheap to close in the first PI-02C hardening commit.

---

## B. The ten review points

| # | Point | Result | Evidence |
| --- | --- | --- | --- |
| 1 | Only production change is the TimeoutError classification | **Confirmed.** `git diff c4257e0 b56d3cc -- alive` is one line in `alive/workflows/runner.py`: `except Refused:` → `except (Refused, TimeoutError):`. It is byte-identical to the diff I proposed in R2 (same blob `ce43037`). | VERIFIED |
| 10 | No Pi runtime, dispatch, migration or Governor change | **Confirmed.** No change to `migrations/`, `pi-runtime/`, `alive/pi/`, `alive/cognition.py`, `alive/app.py`, `alive/workflows/` other than that line, `uv.lock` or `pyproject.toml`. The only other file touched outside docs is `scripts/workflows_r2_mutations.py` (harness). | VERIFIED |
| 2 | All 19 new cases protect their advertised invariants | **Yes.** 1 + 2 + 3 + 4 + 3 + 6 = 19 cases in `tests/test_workflow_r3_guards.py`. Each asserts behaviour (provider call counts, run and stage state, uncertainty, Pi and request state, reservations, replay), not only an exit code. Full list and strength notes in section C. | VERIFIED / SOURCE-CONFIRMED |
| 3 | Second-reservation mutation caught by a behavioural assertion | **Yes.** Removing `stage.model_invocation_id is None` makes `test_stage_cannot_reserve_a_second_real_model_invocation` fail with `assert 2 == 1` ("one authorized stage dispatched twice"). Baseline: 1 call, run `UNKNOWN`, reason `model_stage_claim_required`, exactly 1 invocation / 1 Pi run / 1 request, all settled. | VERIFIED |
| 4 | Real-route goal cancellation prevents dispatch and leaves no reservation | **Yes**, and with the real HTTP route (`POST /api/v1/goals/{id}/transition`). Before and after reservation: 0 calls, `FAILED`. During the provider call: 1 call, `UNKNOWN`, invocation `validated`, Pi `SETTLED`, request `settled`. Reservations 0, execute-again and `recover()` add no call. Removing the goal-status clause fails all three (`assert 1 == 0`). | VERIFIED |
| 5 | Stage/run/invocation identity guards fail closed | **Yes.** Other run's stage and other inquiry's invocation: 0 calls. Six raw-SQL run-identity corruptions: 0 calls each, and I confirmed with an extra probe that each ends `FAILED` / `authority_refused` with one terminal invocation, Pi run and request, reservations 0, and no new call after replay (scripts/`test_review_identity_settlement.py`). Disabling the fence entirely fails all of them. | VERIFIED |
| 6 | Context source and action scope guards | **Yes, for the cases tested.** Wrong source ids and a wrong action kind are refused, and the in-contract control case is admitted. Two weakenings of the same checks are *not* detected (R3-2 and the contract test's lack of a refusal-reason assertion, section D). | VERIFIED |
| 7 | Timeouts before and after dispatch keep FAILED/UNKNOWN and uncertainty | **Yes.** Four cases: deterministic (`FAILED`, uncertainty none, 0 calls, no Pi rows); before dispatch (`FAILED`, Pi `CANCELLED`, request `rejected`, 0 calls); after dispatch (`UNKNOWN`, `unknown_outcome`, Pi `UNKNOWN`, request `ambiguous`, 1 call, no further call after replay and `recover()`); whole-run deadline (`timeout`, effect-free). All carry label `timeout`. | VERIFIED |
| 8 | All 13 R3 mutations killed by relevant assertions; the 20 earlier kills and one redundancy unchanged | **Yes.** I re-ran `scripts.workflows_r2_mutations` myself in a clean tree: **34 cases, 33 killed, 1 redundant (A10)**. I read the assertion excerpt of each R3 kill: all are behavioural (`'adapter_execution_failure' == 'timeout'`, `assert 1 == 0`, `assert 2 == 1`, `'admitted' == ...`, "corruption crossed the dispatch fence"). None is a setup, import, syntax or teardown error. | VERIFIED |
| 9 | Both exact-head CI runs passed, no hidden selection or skip regression | **Yes.** Runs `41148930999` and `41149093291` are both on `b56d3cc`. Each shows backend ubuntu and backend windows at **1224 passed, 12 skipped, 1 xfailed**, plus dashboard, first-contact-postgresql and notebook green. 1205 + 19 = 1224; skips and xfail are unchanged from R2. The CI command is `uv run pytest -q --durations=25 --durations-min=0.5` with no file selector, so full discovery applies (SOURCE-CONFIRMED in `.github/workflows`). The handoff's collection receipt reports 1237 tests (1224 + 12 + 1). | VERIFIED |

Other checks:
- Existing tests were not rewritten: the only test change is the new file `tests/test_workflow_r3_guards.py` (370 lines). VERIFIED by `git diff --stat`.
- Frozen review inputs are byte-identical: `ALIVE-PI-02B-R2-INDEPENDENT-REVIEW.md`, `ALIVE-PI-02B-R3-CORRECTION-BRIEF.md` and `clause-classification.json` under `docs/workflows/validation/pi02b-r3/review-inputs/` hash equal to my originals. The receipt manifest verifies with no mismatch. VERIFIED.
- The documented counts match my R2 classification: 46 clause mutants, 10 caught, 36 survivors split 12 load-bearing / 16 redundant / 6 unreachable / 2 unresolved. The R3 mutants cover exactly the 12 load-bearing sites (`context.py:151, 211, 212, 245`; `runner.py:159, 163, 296, 297, 298, 300, 301, 308`). VERIFIED against my list.
- Full suite on the pristine pinned tree: **1224 passed, 12 skipped, 1 xfailed** in 1213 s, exit 0 (matches CI and the 1205 + 19 arithmetic; skip and xfail counts unchanged from R2)

---

## C. Independent mutants (different operators from the author's)

The author's 13 R3 mutants are the clause deletions I specified, and the tests were written from my drafts. To check the tests are not merely tuned to those patterns, I applied nine mutants of my own to a scratch copy and ran the whole R3 file (19 tests) against each.

| Mutant | Result | Failed tests |
| --- | --- | --- |
| M1 goal check also allows `cancelled` | **KILLED** | all three goal-cancellation cases |
| M2 goal check also allows `completed` | **SURVIVED** | — (R3-1) |
| M3 source-id check weakened to "contains" | **SURVIVED** | — (R3-2) |
| M4 any string accepted as action kind | **KILLED** | `context_contract[action_kind]` |
| M5 `unknown_outcome` marker not recorded | **KILLED** | `timeout[after_dispatch]` only |
| M6 whole-run deadline label lost | **KILLED** | all four timeout cases |
| M7 dispatch fence disabled | **KILLED** | association x2, identity x6, goal `[after_reservation]` |
| M8 "Pi run not terminal" removed from the possible-effect test | **SURVIVED** | — (note N-1) |
| M9 `stage.model_invocation_id` check weakened | **KILLED** | `test_stage_cannot_reserve_a_second_real_model_invocation` |

Six of nine killed, by the intended test each time. M7 shows the association, identity and after-reservation tests exercise the real fence and cannot pass vacuously. Raw results: `independent-r3-mutants.json`, script in `scripts/scratch_r3_mutants.py`.

Test-by-test strength (SOURCE-CONFIRMED, plus the kills above):
- **One invocation per stage**: strong. Asserts call count, run state `UNKNOWN`, reason, exact row counts and no redispatch on replay.
- **Association (2)**: strong. Each builds a state where only the targeted clause is wrong, so a pass proves the fence caught it.
- **Goal cancellation (3)**: strong, with the `completed` gap below.
- **Timeouts (4)**: strong. Assert reason, stage category, uncertainty, Pi and request states, call count and replay.
- **Context contract (3)**: adequate. Asserts only admitted or refused, not the refusal reason (N-2).
- **Run identity (6)**: adequate for fence behaviour; the test itself asserts only the provider-call count, but my follow-up probe shows the post-state is clean.

---

## D. Findings

### R3-1 — Goal-status check is pinned for `cancelled` only
- Severity: **LOW**. Evidence: **VERIFIED**. Merge-blocking: no.
- Mutant M2 (the check also accepts a `completed` goal) survives all 19 tests. The real route allows `active → completed`, and I confirmed with a copy of the goal-cancellation test that on the pinned head a goal moved to `completed` through the route is handled identically to `cancelled` (before and after reservation 0 calls and `FAILED`; during the call 1 call and `UNKNOWN`). So the code is right; only the test does not pin it.
- Repair: parametrise the goal test over `["cancelled","completed"]`. Probe: `scripts/test_review_goal_completed.py`.

### R3-2 — Source-id contract is pinned against a disjoint list only
- Severity: **LOW**. Evidence: **VERIFIED**. Merge-blocking: no.
- Mutant M3 (`source.id in context["source_event_ids"]`) survives. The code correctly refuses `[event_id, extra_id]` (verified with a copy of the contract test), but the R3 test only tries a list that excludes the real id, which the weaker check also refuses.
- Repair: add an `extra_ids` case (`[event_id, uid()]`). Probe: `scripts/test_review_extra_ids.py`.

### Notes
- **N-1 — pre-existing unpinned disjunct.** M8 removes the "Pi run not terminal" part of `possible` in `_abandon` and survives. The remaining parts (dispatched, ambiguous or settled request; `pi_cleanup_unconfirmed`) cover every case R3 tests, and Pi recovery settles Pi runs before workflow recovery, so the edge may be unreachable at restart. It predates R3 and is out of its scope. Worth a test when the next lifecycle work touches `_abandon`.
- **N-2 — refusal reason not asserted** in the context-contract test. The control case and the kills show it works, but a violation case could in principle be refused for an unrelated reason. Assert `bounded_evidence_scope` for the two violation cases.
- **N-3 — unsupported-topology concurrency finding, disclosed by the author.** The R3 notes report that copied Cognition and kernel service views with independent pools and locks admitted two reservations for one stage, and that the final dispatch fence stopped one provider call. The row-lock proposal was removed (`superseded-proposal.diff`, preserved outside the branch in `C:\Projects\alive-pi02b-h-diagnostics`). I did not reproduce it. It is consistent with my R1 and R2 reading: the one-invocation-per-stage guard is a check-then-set that is safe under the in-process kernel lock and the host lease (the lease refusal of a second process is VERIFIED in R2), with the dispatch fence as the backstop. It must not become a supported worker topology without a separate concurrency review and the row lock.
- **N-4 — receipts built from files not in the PR.** `initial-timeout-reproduction.txt` and `postgresql-supplement.txt` were produced from `tests/test_workflow_h.py`, which is not in the repository (a copy is in the diagnostics folder). The committed tests cannot reproduce those two receipts directly. The PostgreSQL goal-cancellation and one-invocation behaviour is independently established by my R2 PostgreSQL runs, so I do not rely on them.
- **N-5 — declined items.** The optional reason labels (goal-specific reason; provider versus adapter failure category) were declined to keep the single-line boundary, and the inquiry-state guard (`context.py:155`) and role-contract clause (`context.py:255`) stay documented and unprobed. All three match what the brief allowed. The role-contract clause remains an open watch item for broader capabilities.

---

## E. Commands and limits

| Environment | What | Result |
| --- | --- | --- |
| Windows, pristine pinned tree | full backend suite | **1224 passed, 12 skipped, 1 xfailed** in 1213 s, exit 0 (matches CI and the 1205 + 19 arithmetic; skip and xfail counts unchanged from R2) |
| Windows, clean copy | `scripts.workflows_r2_mutations` | 34 cases, 33 killed, 1 redundant |
| Windows, scratch copy | nine independent mutants against the 19 R3 tests | 6 killed, 3 survived (R3-1, R3-2, N-1) |
| Windows | identity-corruption settlement probe (6 cases) | all clean |
| Windows | goal `completed` via real route; extra-source-ids context | baseline correct |
| Remote CI | `gh` / job logs for both runs on `b56d3cc` | all jobs green; 1224 passed, 12 skipped, 1 xfailed on ubuntu and windows, twice |
| PostgreSQL | not re-run for R3 | NOT RUN; R2 PostgreSQL results and the unchanged runtime cover it; the author's PostgreSQL supplement is not reproducible from the PR (N-4) |
| Local Linux, Docker image | not run | NOT RUN; covered by remote CI ubuntu |

Limits: I tested clause-deletion and a few other operators on the authorization code only. I did not mutate transaction, recovery or settlement code in R3. Cross-process behaviour is covered by the host lease, not by tests; see N-3.

---

## F. What happens next

PI-02C can start. Suggested carry-ins, none blocking:
1. Close R3-1 and R3-2 and N-2 with three small test additions.
2. Keep N-3's constraint in the PI-02C design: the observatory must not assume a multi-worker topology.
3. PI-02C must display arbitrary approved workflow structures; the context-preparation step it will need for captured pages (raw extension events cannot start a run, see R2) belongs in its design.

Nothing was modified, committed, pushed or posted.
