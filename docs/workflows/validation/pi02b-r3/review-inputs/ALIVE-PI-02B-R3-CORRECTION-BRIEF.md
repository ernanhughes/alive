# ALIVE-PI-02B-R3 — Bounded correction brief

Base: PR #69, head `ab066db51d3992905980aa5a1122c6e540bd1335` (reviewed; CI green on both runs).
Source of truth: `ALIVE-PI-02B-R2-INDEPENDENT-REVIEW.md` and `clause-classification.json` in `C:\Projects\alive-pi02b-r2-evidence\`.
Working test drafts: `C:\Projects\alive-pi02b-r2-evidence\scripts\`.

## Goal
Fix one label-only defect and pin the load-bearing authorization guards the R2 clause campaign found unprotected. This is a tests-plus-one-line change.

## Hard constraints
- Do not change Pi, Governor, database, dispatch, cancellation or recovery behaviour. The only production edit is item 1.
- Do not touch migrations, `alive/pi/`, `alive/cognition.py`, `pi-runtime`, dependencies or frozen evidence.
- No paid inference. Use the existing scripted local provider fixtures.
- Do not rewrite or loosen any existing test. Add new tests only.
- Stay on the PR #69 branch. Do not merge. Do not start PI-02C.
- If a new test fails on the unmodified head for a reason other than the item it targets, stop and report it; do not adjust production code to make it pass.

## Production change (one line)
1. `alive/workflows/runner.py`, `_stage`, the adapter `try/except` (about line 452):
   `except Refused:` becomes `except (Refused, TimeoutError):`.
   Reason: a stage deadline expiry is currently relabelled `adapter_execution_failure`. Terminal state and uncertainty are already correct and must not change.

## New tests (each must pass on the fixed head and fail with its target removed)

| # | Test | Asserts | Target clause (mutation) | Draft |
| --- | --- | --- | --- | --- |
| 1 | Stage deadline, three cases: deterministic stage; Pi stage after dispatch (block the upstream); Pi stage before dispatch (hold `_dispatch`) | label is `timeout` in all three. Deterministic: `FAILED`, uncertainty none, 0 calls. After dispatch: `UNKNOWN`, `unknown_outcome`, Pi `UNKNOWN`, request `ambiguous`, 1 call, no further call after replay and `recover()`. Before dispatch: `FAILED`, request `rejected`, 0 calls. Reservations 0. The wall-deadline path still reports `timeout` | `except (Refused, TimeoutError)` reverted | `test_review_timeout.py` |
| 2 | Goal cancelled through `POST /api/v1/goals/{id}/transition` (real route, no SQL): before reservation; after reservation, before dispatch; during the provider call | before and after reservation: 0 provider calls, run `FAILED`, reservation 0. During the call: 1 call, run `UNKNOWN`, invocation `validated`, Pi `SETTLED`. All: no further call after execute-again and `recover()` | `context.py:151` `goal.status in ("active","accepted")` | `test_review_goal_cancel.py` (`real_route`) |
| 3 | One stage cannot reserve two invocations: wrap the `cognition.role` adapter to call the original twice | exactly 1 provider call; the second reservation is refused with `model_stage_claim_required`; reservation 0 | `context.py:245` `stage.model_invocation_id is None` | `test_review_negative.py` (`double_reservation`) |
| 4 | Scope contract: an owner-approved context with (a) a wrong `source_event_ids`, (b) `requested_action_kind` other than `record_analysis` | `start` refuses with `bounded_evidence_scope`; the in-contract control case is admitted | `context.py:211`, `212` | `test_review_contract.py` |
| 5 | Corrupted association at the dispatch fence (disposable DB): reassign the invocation's stage to a `RUNNING` stage of another finished run; point the invocation at another inquiry | 0 provider calls in both; reservation 0 | `runner.py:159`, `163` | `test_review_negative.py` (`corrupted_association`) |
| 6 | Run-identity corruption at the fence: parametrise over `definition_sha256`, `workflow_name`, `workflow_version` (Core `UPDATE`, because ORM `ImmutableRecord` blocks ORM writes), and `input_sha256`, `authorization_ref`, `goal_id` | 0 provider calls for each field | `runner.py:296`, `297`, `298`, `300`, `301`, `308` | `test_review_identity.py` |

Porting notes for the drafts:
- Remove the JSON evidence writes, the `OUT` path, the `TAG`/`REVIEW_TAG` and `REVIEW_DB` environment switches, and the `print` lines.
- The goal-cancel draft has a PostgreSQL fixture that shells out to Docker. Port the SQLite variant only. If you want a PostgreSQL race test, make it an opt-in marked test that asserts invariants, not which side wins.
- Replace `tests.test_review_r1.record` imports. Use the existing `tests/workflow_execution_helpers.py` and `tests/workflow_r2_helpers.py`.
- Put the tests in the existing `tests/test_workflow_r2_*.py` files or one new `tests/test_workflow_r3_*.py`. Keep them fast; the stage-deadline tests take about 1 to 2 seconds each because the minimum stage timeout is 1 second.

## Mutation proof (required)
Extend `scripts/workflows_r2_mutations.py` with the targets above (clause replaced by `and True`, except item 1, which is the revert of the one-line fix). For each, record baseline PASS, mutant KILLED by the named test with an assertion error, and no setup error. Report any mutant that survives its own test.

## Decide or document (no behaviour change)
- `context.py:155` (inquiry state is not terminal): add a short comment or doc note stating that this is the sole guard for a workflow inquiry that becomes terminal while its goal stays `active`, and that no supported command produces that state. Add a lifecycle-boundary test only if you can reach the state through a supported command.
- Optional, only if it does not widen the diff: report a goal cancellation with a goal-specific reason instead of `authorized_inquiry_required`, and distinguish provider failures from adapter failures in the workflow error category. If either needs more than a few lines, leave it and say so.

## Acceptance
- Full backend suite passes on Windows, with the new tests included; report the new total.
- CI green on the new head SHA for both workflow runs.
- `git diff` against `ab066db` shows exactly one production line changed (plus the optional comment or labels, if done).
- Mutation replay: every R3 mutant KILLED, plus the existing 20 killed and 1 redundant unchanged.
- Report the new head SHA so the final focused review can pin it.

## Report back
New head SHA, the one-line production diff, the new test count, the mutation replay result, CI status for that SHA, and anything you declined to do with the reason.
