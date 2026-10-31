# ALIVE-PI-02C-H — Bounded correction brief

Base: `main` at or after merge commit `e483d16bad57f7e1957bf73b043bce7e16f10d01` (PR #72, reviewed head `58fd3cc21c67aa458ea7e0b723310a83aec0d3d7`). Work on a new branch; PR #72 is merged.

Acceptance contract (read first):
- `C:\Projects\alive-pi02c-r1-review\ALIVE-PI-02C-R1-INDEPENDENT-REVIEW.md` — the final R1 report (supersedes any earlier partial files).
- `C:\Projects\alive-pi02c-r1-review\observatory-mutants-final.json` — the **complete O1–O18 classification** (18 valid results: 7 killed, 11 survived, 0 invalid). The older `observatory-mutants-run1.json` marks O13–O18 INVALID because the host process was killed mid-run; do not use it. `observatory-mutants.json` in the same folder holds only the O13–O18 re-run. Any copy of these files under `C:\Projects\alive-pi02c-evidence\` is stale: that folder belongs to the PI-02C implementation and my files were moved out of it.
- Working test drafts: `C:\Projects\alive-pi02c-r1-review\scripts\` (`test_review_obs.py`, `review_replay.test.ts`, `scratch_obs_mutants.py`, `scratch_obs_probe_mutants.py`) and the browser scripts in the same folder.

## Goal
Make the replay truthful about stages that ended in doubt, and pin the server-side identity and scoping checks that the new projections rely on. No new endpoint, no backend behaviour change.

## Hard constraints
- `alive/workflows/observatory.py` and every other production Python file stay unchanged. The only production edits allowed are in `dashboard/src/workflows/` (items 1 and 3).
- Do not weaken, delete or loosen any existing test. Add tests only.
- Do not change any timeout or polling threshold to make a test pass.
- No paid inference, no PI-03, no new dependency, no migration.
- If a new test fails on the unmodified head for a reason other than the item it targets, stop and report it.

## Item 1 — R1-F1: replay of interrupted and failed runs (dashboard)
Current behaviour (VERIFIED): `replayStates` in `dashboard/src/workflows/model.ts` maps only `workflow.stage.claimed` → `RUNNING` and `workflow.stage.result` → `COMPLETED`. Replaying the real `UNKNOWN` run to its last event (13 / 13) shows `Analyze RUNNING`, although `#258 pi.run.unknown analyze` and `#259 workflow.execution.ended UNKNOWN` are listed as played.

Required behaviour (recorded events only, never the snapshot):

| Recorded event (with `stage_id`) | Replayed label for that stage |
| --- | --- |
| `workflow.stage.claimed` | `RUNNING` |
| `workflow.stage.result` | `COMPLETED` |
| `pi.run.unknown` / `pi.run.failed` / `pi.run.cancelled` | `UNKNOWN (Pi run)` / `FAILED (Pi run)` / `CANCELLED (Pi run)` — a recorded Pi outcome, worded so it is not mistaken for the final stage state |
| `workflow.execution.ended` with status S, for a stage still `RUNNING` | `Run ended S; stage outcome not recorded` |
| no event for the stage | `Not recorded` (unchanged) |

Also show, in the replay panel, the recorded run-level outcome at the cursor when a `workflow.execution.ended` event has been played (for example "Recorded run outcome: ended FAILED").

Expected frames from the real timelines the demo script seeds (`python -m scripts.workflow_observatory_demo --directory <empty> --seed`):
- `ambiguous` at the last event: Prepare `COMPLETED`; Analyze `UNKNOWN (Pi run)`; Validate and Record `Not recorded`; run outcome "ended UNKNOWN".
- `partial` at the last event: all four stages `COMPLETED`; run outcome "ended FAILED".
- `goal_cancel` at the last event: all three stages `Not recorded`; run outcome "ended FAILED".
- At earlier cursors nothing may appear that a later event would introduce.

Tests required:
- Vitest: feed `replayStates` the **real captured timelines** for those three runs (take them from the demo seed, not hand-written fixtures) and assert the frames above, plus one assertion per cursor position that no state appears before its event. The existing test "never backfills final snapshot state into replay" must keep passing unchanged.
- Playwright (extend `e2e/workflows.spec.ts` or add a case): replay `ambiguous` to the end and assert the Analyze entry is not `RUNNING` and the page shows the recorded run outcome.

## Item 2 — R1-F2: pin the server-side identity and scoping checks (backend tests only)
Port the committed-test form of these two probes from `scripts\test_review_obs.py`; remove the evidence-folder writes and prints, and use the existing fixtures and helpers (`pi_environment`, `lifecycle`, `observation`, `call`):
- `test_b_identity_attacks_are_refused_server_side` — build two complete Pi workflows in one database, then for each attack assert HTTP 404 from `inspection`, `timeline` and the Pi receipt route of the corrupted run. Attacks: Pi pointer swapped from the other run; invocation pointer swapped; Pi run moved to another instance; Pi run operation changed; invocation naming another stage attempt; invocation naming another run; invocation in another investigation; run moved to another instance; run definition hash altered; stored `definition_json` hand-edited (raw `UPDATE`; the ORM `ImmutableRecord` guard blocks ORM writes); stage renamed to an undeclared stage. For `definition_json`, do not assert that the other run is unaffected (they share the definition). Keep the three trivial cases (foreign attempt through another run's route, unknown attempt, deterministic stage asked for a Pi receipt).
- `test_c_timeline_pagination_and_run_isolation` — paging with limits 1, 2, 3, 7 reproduces the full list exactly; `has_more` true at limit N−1 and false at N; `after` beyond the end returns an empty page with `next_after` unchanged; invalid parameters return 422; **no event of the other run's Pi run appears in this run's timeline**.

Mutation proof (extend `scripts/workflows_r2_mutations.py` or add a sibling script; mutate a temporary copy only). Each mutant below must be KILLED by a named new test with an assertion failure, never a setup error. The patterns are in `scratch_obs_mutants.py`; the observatory-module lines are:

| Mutant | Line removed or replaced in `alive/workflows/observatory.py` | Killed by |
| --- | --- | --- |
| O1 | `and pi.instance_id == kernel.instance_id` | Pi run moved to another instance |
| O2 | `and pi.reservation_ref == call.id` | Pi pointer swapped from the other run |
| O3 | `and call.input_json.get("workflow_run_id") == run.id` | invocation naming another run |
| O4 | `and call.investigation_id == run.investigation_id` | invocation in another investigation |
| O6 | `and pi.operation == stage.operation` | Pi run operation changed |
| O9 | `Event.correlation_id.in_(by_pi),` → `Event.correlation_id.is_not(None),` | timeline isolation test |
| O13 | `and hash_of_stored(definition.definition_json) == run.definition_sha256` | hand-edited `definition_json` |

The existing kills must stay killed: O5, O11, O12, O15, O16, O17, O18. O7, O8, O10 and O14 are redundant or unprobed; do not add tests for them unless you can show a path where removal changes behaviour.

## Item 3 — R1-N3: do not hard-code the feedback and learning lines (dashboard, small)
In `ArtifactPanel` (`StageInspector.tsx`), render "Independent feedback" and "Intelligence learning" from the artifact's `independent_feedback` and `intelligence_episode_id` fields instead of fixed text. With the current backend (`false`, `null`) the visible text must be unchanged. Add a unit test that feeds a value the contract does not allow today (an episode id, `independent_feedback: true`) and asserts the panel shows it.

## Out of scope (separate changes)
- The Windows CI timeout in `tests/test_pi_gateway.py::test_a_cognition_role_runs_through_pi_end_to_end` (a fixed 10-second wait; the same commit passed on re-run). Fix it separately; do not touch timeouts here.
- Event hash-chain verification of the timeline, long-history browsing beyond 500 events, Docker restart re-qualification.

## Acceptance
- Full backend suite passes on Windows and Linux CI with the new tests included (report the new total; baseline is 1238 passed, 12 skipped, 1 xfailed). Dashboard tests, build and extension tests pass.
- `git diff` against the base shows no change to any Python file under `alive/`, and dashboard changes only in `dashboard/src/workflows/` plus the e2e spec.
- Mutation replay: all seven new mutants KILLED, the seven existing kills unchanged, and receipts include the assertion excerpts.
- Replay-to-end Playwright case passes against a history seeded by `scripts.workflow_observatory_demo`.
- CI green on the exact final head, both workflow runs.

## Report back
New head SHA, the production diff (dashboard only), new test counts, the mutation table, a screenshot of the `ambiguous` run replayed to its last event, CI status for the head, and anything you declined to do with the reason.
