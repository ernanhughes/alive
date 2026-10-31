# ALIVE-PI-02C-R1 — Independent Adversarial Review

PR: https://github.com/ernanhughes/alive/pull/72
Reviewed head: `58fd3cc21c67aa458ea7e0b723310a83aec0d3d7` (confirmed unchanged for the whole review)
Base: `b0b3e40ab51e2ea4f482a20767f9bad8b4491765`
Review date: 2026-10-31. Read-only: the PR, its branch, `main`, the owner checkout and production configuration were not modified. No paid inference, no PI-03 work. Fresh worktrees, disposable SQLite and PostgreSQL, scripted loopback providers, fake credentials only.

**PR state.** The request described #72 as an open draft. During the review GitHub changed it to **merged** (by `ernanhughes`, 2026-10-31 02:25Z, merge commit `e483d16bad57f7e1957bf73b043bce7e16f10d01`). `58fd3cc` is an ancestor of `main`, and `alive/`, `dashboard/src/`, `tests/`, `extension/` and `scripts/` on `main` are identical to the reviewed head. This is therefore a post-merge review of code already on `main`. The decision below is about that code.

Evidence classes: **VERIFIED** (executed and observed) · **SOURCE-CONFIRMED** (read in source) · **INFERRED** · **UNVERIFIED**.

Evidence folder: `C:\Projects\alive-pi02c-r1-review\` (probe JSON, screenshots, mutation matrices, `scripts/`). See the housekeeping note at the end about a shared folder name.

---

## A. Decision

**REVISE** (post-merge follow-up). Not BLOCKED.

The authority and identity design is sound. The observatory is read-only, every identity attack I mounted was refused by the server, and rendering of hostile data is safe. Two things need a follow-up before anyone relies on the observatory to answer "what remains uncertain":

1. **R1-F1 (MEDIUM, defect).** Replaying a run that ended `UNKNOWN` shows the interrupted stage as `RUNNING` at the end of the recorded history, although the same page lists the recorded events that ended it.
2. **R1-F2 (MEDIUM, test gap).** Seven server-side identity and scoping checks in the new projections are not pinned by any committed test. They are correct today, but their removal would let another run's or another instance's Pi data be served with HTTP 200.

The central question, answered directly: a human can trust the observatory to show what ALIVE did and what it recorded, with one exception. For a run that ended in doubt or failure, the replay graph presents a stale state for the stage that was in flight.

---

## B. Review points

| Area | Result |
| --- | --- |
| **A. Execution-authority isolation** | **SOUND.** All observatory routes are GET-only and authenticated. I polled 36 routes three times each over a completed Pi run, a second Pi run and a deterministic run: no table row count changed, the Governor reservation and spend were unchanged, no event other than the kernel's own heartbeat appeared, and the scripted provider saw 0 calls. POST, PUT, PATCH and DELETE return 405. Public ingest returns 422 for the `workflow` and `pi` sources, so those event sources cannot be forged from outside. `observatory.py` contains no insert, update, delete, add, begin, commit, flush or execute call, and imports only models, `store`, `digest` and `spec` helpers. |
| **B. Identity and ownership** | **SOUND in code, with a test gap (R1-F2).** Attack matrix in section C. |
| **C. Replay truthfulness** | **DEFECT FOUND (R1-F1)** in the UI projection. The server timeline is sound. |
| **D. Concurrency and stale UI** | **SOUND.** Late responses from a previously selected run never overwrote the current run (section D). |
| **E. Epistemic correctness** | **SOUND, one exception (R1-F1).** UNKNOWN stays UNKNOWN in the snapshot, cost and tokens read "Unknown" when null, `validation` separates contract, structure, reference identity and semantics, and partial artifacts are labelled as such. |
| **F. Security and rendering** | **SOUND.** Section E. |
| **G. End-to-end integration** | **SOUND.** Section F. |
| **H. Test and CI integrity** | **SOUND with gaps.** Section G. |
| **I. Architecture and Bespoke readiness** | **SOUND with notes.** Section H. |

---

## C. Identity and authorization attack matrix (all VERIFIED, two real Pi workflows in one database)

Corruption was applied directly in a disposable database, then `inspection`, `timeline` and the Pi receipt route were read for the corrupted run. "Refused" means HTTP 404 on all three.

| Attack | Result |
| --- | --- |
| Run B's stage attempt requested through run A's route | refused |
| Unknown attempt id | refused |
| Deterministic stage's attempt asked for a Pi receipt | refused |
| Stage's Pi pointer replaced with another run's Pi run | refused |
| Stage's invocation pointer replaced with another run's invocation | refused |
| Pi run moved to another ALIVE instance | refused |
| Pi run's operation changed | refused |
| Invocation names a different stage attempt | refused |
| Invocation names a different run | refused |
| Invocation belongs to a different investigation | refused |
| Run moved to another instance | refused (also the artifact route) |
| Run's stored definition hash altered | refused |
| Stored `definition_json` hand-edited (raw SQL) | refused (also affects every run on that definition) |
| Stage-result event payload altered | timeline refused; dashboard fails the whole recording |
| Stage `output_ref` swapped to another stage's event | timeline refused; dashboard fails the whole recording |
| Stage renamed to a stage the definition does not declare | refused |

Event correlation ids alone cannot establish Pi receipt ownership in the unmodified code: the timeline selects Pi events only for Pi runs that `attached_pi` has bound to this run through the invocation, the reservation and the instance (SOURCE-CONFIRMED, and VERIFIED: 19 events, 0 belonging to the other run's Pi run).

Note: a corruption that touches only an upstream stage's result event leaves the `record` artifact route at 200, because that route validates the `record` stage's own chain. The timeline, which the dashboard always fetches, catches it, and the dashboard shows "History unavailable ... integrity check failed" for the whole run.

---

## D. Timeline and replay integrity

Server (VERIFIED, 19-event Pi run in a database holding another Pi run):
- Sequence numbers strictly increasing; paging with limits 1, 2, 3 and 7 reproduces the full 500-limit list exactly, with no duplicates or gaps.
- `has_more` is false at limit = N and true at limit = N−1; `after` beyond the last event returns an empty page with `next_after` unchanged.
- `after=-1`, `limit=0`, `limit=501` and a non-numeric `after` return 422.
- No event from another run or another run's Pi run; only 13 event types appear; each event exposes only ids, type, timestamp, status and output reference, never payloads. `complete_transition_history` is `false` with an explicit note that some transitions were not retained.
- Minor: a `workflow.stage.claimed` event for a Pi stage carries `pi_run_id` equal to the stage's *final* Pi run, although no Pi run existed when that event was recorded. It is an identity field filled from the snapshot, not a state, and the dashboard never displays it (R1-N1).

### R1-F1 — Replay shows an interrupted stage as `RUNNING` after the history ends it
- Severity: **MEDIUM**. Evidence: **VERIFIED** in a real browser against real persisted records. Merge-blocking: n/a (already merged); required follow-up.
- Location: `dashboard/src/workflows/model.ts`, `replayStates` (maps only `workflow.stage.claimed` to `RUNNING` and `workflow.stage.result` to `COMPLETED`); rendered by `WorkflowGraph.tsx` and the stage list.
- Reproduction: seed with `scripts.workflow_observatory_demo --seed`, open the `ambiguous` run, Recorded events → Replay → move the position to the last event (13 / 13).
  - Snapshot: `Analyze UNKNOWN`, `Validate CANCELLED`, `Record CANCELLED`.
  - Replay at the end: `Analyze RUNNING`, `Validate Not recorded`, `Record Not recorded`.
  - The event list on the same page shows `#258 pi.run.unknown analyze` and `#259 workflow.execution.ended UNKNOWN` as already played.
  - Screenshot: `replay-end-ambiguous.png`. Data: `replay-real-unknown.json`, `replay-end-browser.json`.
- Expected: after the recorded `pi.run.unknown` and `workflow.execution.ended UNKNOWN` events the replay should not present the stage as still running; at minimum it should say that the stage was left without a recorded outcome and the run ended `UNKNOWN`.
- Observed: the projection ignores every recorded terminal event. For the `partial` (`FAILED`) run the final replay frame shows all four stages `COMPLETED` while `#316 workflow.execution.ended FAILED` is listed; that one is accurate for the stages but silent about the run failing.
- Impact: this is precisely the case a reviewer opens a replay for. "RUNNING" is not a fabricated state (a claim event was recorded) but it is stale, and for an `UNKNOWN` outcome it understates the uncertainty.
- Root cause: `replayStates` has two cases. The existing unit test ("never backfills final snapshot state into replay") uses a one-event fixture and so cannot see terminal handling; the Playwright scenario replays one event and returns.
- Minimal repair: in `replayStates`, apply recorded `pi.run.{unknown,failed,cancelled,settled}` to the event's stage, and apply `workflow.execution.ended` status to stages still `RUNNING` as a distinctly labelled run-level outcome (for example "Run ended UNKNOWN; stage outcome not recorded"). Keep "Not recorded" for stages with no event.
- Regression test: replay the real `ambiguous` timeline to the last event and assert the Analyze label is not `RUNNING`; add one for a cancelled and one for a failed run.

---

## E. Rendering and privacy (real Chrome, VERIFIED)

- Definition and stage titles are restricted server-side to letters, digits, spaces and `. , : ' & + / ? ! % -`. Registration with `<img onerror>` or `<script>` titles is refused.
- To test model-controlled fields I intercepted the artifact and Pi receipt responses of a real run and replaced result, claims, evidence references, assessment, provenance strings, `terminal_reason`, `requested_upstream_model` and request `error_category` with `<img src=x onerror=…>`, `<script>`, `"><svg onload=…>`, `javascript:` strings, a 30,000-character value, a 200-item list and a `C:\Users\…` path. Result: all shown as text; `window.__pwn` stayed undefined; no injected elements, no dialogs, no off-site navigation; truncation notices displayed; no horizontal overflow on desktop or at 390 px.
- No bearer token in any request URL, in `location`, in `localStorage` or in cookies. The token is kept in `sessionStorage` under `alive-token`; that is the existing dashboard behaviour (unchanged by the PR).
- Deep links: on a fresh load, five invalid links (bad name, path traversal run id, script stage, a `token=` parameter, a duplicated parameter) each show "Invalid workflow link. No action was taken." and select nothing. After load, an invalid hash change is ignored silently with no alert (R1-N2, harmless).
- Pi receipt: `approved_request` holds only the model, operation, output limit and two hashes; no prompt text, no keys, no paths appeared in any observatory response (searched for the API key, bearer token, `C:\`, `/tmp/`, `pytest-of`, `\Users\` and the observer prompt).
- External requests: only Google Fonts, from `style.css`, which predates the PR.
- Extension: `workflowURL` accepts only `http://127.0.0.1:8000` and `http://localhost:8000`, validates every identifier and carries no token or context. `node --test` on the two extension files: 8 of 8 pass.

---

## F. Races and end-to-end

Races (real Chrome, delayed responses; `race-ui.json`): run A's reads were delayed 4 seconds and the user switched to run B. B's heading and its 3-stage graph stayed; A's heading never appeared after its responses arrived. Starting a replay, switching to A (slow) and back to B left replay mode and showed B. With the tab hidden, a "Refresh records" click issued zero reads. The author's unit tests cover run switching, replay-page cancellation, unmount, terminal-state polling shutdown and five-attempt backoff; I did not re-run the backoff timing in a browser.

End to end (my own seeding, not the author's data):
- `scripts.workflow_observatory_demo --seed` on SQLite and on a disposable PostgreSQL 16 produced six runs with the pinned Pi and the scripted provider: a 4-stage Pi workflow (two versions), a 3-stage deterministic workflow, a goal cancellation (`FAILED`), an ambiguous post-dispatch run (`UNKNOWN`) and a settlement-failed run (`FAILED` with a retained artifact). Provider requests: 4. Restart replay: "unchanged invocation/Pi/request/run/artifact/learning counts" on both. Learning updates: 0. `paid_inference`: NOT_RUN.
- The author's Playwright scenario (`e2e/workflows.spec.ts`) passes against that history in Chrome (1 passed).
- My own probes added a Pi run with a custom timeout to confirm an `UNKNOWN` run with stage `uncertainty: unknown_outcome`, cost `null` and a Pi request `ambiguous`.
- Docker container restart: NOT RUN by me. The author's retained Docker receipts were not independently reproduced.

---

## G. Tests and CI

- Backend: full suite on the pristine pinned tree **1238 passed, 12 skipped, 1 xfailed** (1,098 s). The 14 new tests assert behaviour (counts, status codes, redaction, ordering, refusal), not just HTTP success. Dashboard: **31 passed**, build clean. Extension: 8 of 8 on the two relevant files (the author reports 38 across the suites).
- Receipt manifest (`docs/workflows/validation/pi02c/manifest.json`, 14 files): all hashes verify. The receipts record runtime head `2b5f1ad`; the two commits after it change only documentation and the manifest (VERIFIED by diff). The preserved PI-02B-R3 review input is byte-identical to mine.
- **Mutation testing of the new projections (my own, 18 mutants of `alive/workflows/observatory.py` against the new backend tests and the API test):** 7 killed, 11 survived. A first run of O13 to O18 was invalid (the process was killed when the host session ended; those return codes are Windows kill codes, not results) and was re-run.

| Mutant | Result | My probe with the mutant applied |
| --- | --- | --- |
| O1 Pi run must belong to this instance | survived | Pi run on another instance served with 200 |
| O2 Pi run reservation must equal the invocation | survived | Pi pointer swapped from another run served with 200 |
| O3 invocation must name this run | survived | served with 200 |
| O4 invocation must belong to the run's investigation | survived | served with 200 |
| O5 invocation must name this stage attempt | **killed** | — |
| O6 Pi operation must equal the stage operation | survived | served with 200 |
| O7 one Pi run per stage | survived | not probed |
| O8 timeline events scoped to the instance | survived | redundant (events also selected by run or Pi run id) |
| O9 Pi events scoped to attached Pi runs | survived | **8 events of another run's Pi run appear in this run's timeline** |
| O10 workflow event must name this run | survived | not probed; events are also selected by run correlation |
| O11 stage result event matches recorded hash | **killed** | — |
| O12 run must belong to this instance | **killed** | — |
| O13 stored definition hash recomputed | survived | hand-edited definition served with 200 |
| O14 stage must be declared by the definition | survived | still refused (redundant) |
| O15 cursor exclusive | **killed** | — |
| O16 page fetches one extra row | **killed** | — |
| O17 `has_more` reported | **killed** | — |
| O18 `complete_transition_history` honest | **killed** | — |

### R1-F2 — Seven identity and scoping checks are unpinned
- Severity: **MEDIUM** (test gap; production code is correct today). Evidence: **VERIFIED**. Follow-up, not an exploit.
- Sites (`observatory.py`): `attached_pi` clauses for instance, reservation, run, investigation and operation (O1, O2, O3, O4, O6); the `Event.correlation_id.in_(by_pi)` scoping in `timeline` (O9); the `hash_of_stored` recomputation in `records` (O13).
- The committed corruption test alters only the invocation's stage name, which is why O5 is the only Pi-binding clause killed.
- Repair: port the parametrised attack matrix from `scripts/test_review_obs.py` (`test_b_…` and `test_c_timeline_pagination_and_run_isolation`), which fails under each of these mutants and passes on the unmodified code.
- Not probed: O7 and O10. O8 and O14 are redundant.

### CI timeout
- CI ran twice on the head: `pull_request` run `41155746593` all green; `push` run `41155744161`: attempt 1 failed only the Windows backend job (1 failed, 1237 passed, 12 skipped, 1 xfailed); **attempt 2 on the same commit passed everything**, Windows included (1238 passed, 12 skipped, 1 xfailed in 21 minutes).
- The failure was `tests/test_pi_gateway.py::test_a_cognition_role_runs_through_pi_end_to_end`: `wait_for` in `tests/test_cognition.py` polls `/cognition/investigations` for a fixed **10 seconds** and gave up while the investigation was still in `INVESTIGATING`. That test starts the autonomous Cognition loop and four real Pi subprocesses in sequence.
- Classification: **fragile pre-existing test under CI load**, not a defect in #72 (INFERRED from: neither the test nor `alive/cognition.py`, `alive/pi/` or `pi-runtime/` is touched by the PR; the same commit passes on rerun; the PR-event run passed Windows at 26 minutes). I did not change any timeout. The right fix is a separate change that bounds the wait by Pi startup cost or waits on an event.
- Skips and xfail: 12 skipped and 1 xfailed identical to the previous review, so no hidden selection or skip regression. CI runs `pytest` with no file selector.

---

## H. Architecture and Bespoke readiness

- The UI is generic over the definition: the graph is built from `/inspection` (nodes and edges from the stored definition), the stage inspector reads the declared operation and the recorded attempt, and comparison works on stable stage ids. The only operation-name coupling in the dashboard is `stage.operation === "result.record"` for the "Open retained artifact" button; there is no `research-review`, `source-comparison`, `analyze` or `prepare` branch (grep). A GitHub, PDF, Hacker News or documentation workflow that ends in `result.record` needs no UI change.
- Three new read projections plus one reuse of the existing Pi receipt renderer; no second source of truth: the UI merges `pi_links` with the stage snapshot and throws on a mismatch.
- Notes for Bespoke readiness:
  - **R1-N3.** `ArtifactPanel` hard-codes "Independent feedback: Not recorded" and "Intelligence learning: No linked episode recorded" instead of reading `independent_feedback` and `intelligence_episode_id`. The backend contract currently fixes those to `false` and `null`, so the text is true today and would stay true if the contract later allowed an episode link. Bind them to the fields when the contract can vary.
  - **R1-N4.** A recording is three separate reads (inspection, stages, timeline), so a snapshot can straddle a state change between reads. Each read is individually consistent and the UI labels snapshot and events separately, so nothing is invented.
  - **R1-N5.** The timeline trusts event rows in the database; there is no signature or hash chain check. A database-level writer could inject workflow events into a replay. That is outside the stated attack surface but worth recording.
  - **R1-N6.** The UI loads the first 500 events and offers "Load next event page". Every real run I saw has under 20 events, so the long-history path in a browser is UNVERIFIED (the author's unit test covers pagination).

---

## I. Commands and limits

| Environment | What | Result |
| --- | --- | --- |
| Windows, pristine pinned tree | full backend suite | 1238 passed, 12 skipped, 1 xfailed |
| Windows | dashboard `npm test`, `npm run build`, extension tests | 31 passed, build OK, 8 of 8 passed |
| Windows, scratch | 16-attack identity matrix; timeline; disclosure; effect-free probes | section C, D, B |
| Windows, scratch | 18 observatory mutants (7 killed, 11 survived); 8 re-probed with the mutant applied | section G |
| Windows + Chrome | author's Playwright scenario; replay-to-end; hostile data; races; deep links | all as reported above |
| SQLite and PostgreSQL 16 (disposable) | real-Pi demo seed, restart replay | PASS both |
| Remote CI | both runs on the head, including attempt 2 of the push run | green |
| Docker container restart; Linux local | not run | NOT RUN |

Limits: the dashboard `node_modules` for my local runs were copied from the owner's checkout rather than installed with `npm ci`, so the local dashboard result depends on those versions (CI uses `npm ci`). Hostile model output was exercised by intercepting real API responses, not by a model that produced it. I mutated only the projection module, not the dashboard code.

---

## J. Minimal remediation plan

1. **R1-F1.** Extend `replayStates` to apply recorded Pi terminal events and the run-level `workflow.execution.ended` status; add replay-to-end tests for `UNKNOWN`, `FAILED` and `CANCELLED` runs using real persisted timelines.
2. **R1-F2.** Add the identity attack matrix and the cross-run timeline isolation test to the committed suite.
3. Bind the artifact panel's feedback and episode lines to their fields (R1-N3).
4. Separate change: stop the 10-second wait in `test_a_cognition_role_runs_through_pi_end_to_end` from depending on runner speed.

None of these changes the read-only design or needs a new endpoint.

---

## K. Housekeeping

The folder name `C:\Projects\alive-pi02c-evidence` already existed and holds the PI-02C implementation's own evidence (`sqlite-*`, `postgresql-*`, `docker-*`, `release-*`, `correction-*`, `collection.txt`, `extension-final.txt`). I wrote my files into it before noticing. I created no file with any of those names and removed none; I have now moved all of mine into `C:\Projects\alive-pi02c-r1-review\`. The implementation's files were not overwritten, because their timestamps are all earlier than my first write. If any of them look modified, that did not come from this review.

The demo servers on ports 8018 and 8019 are stopped (no listener remains). I issued `docker rm -f` for the disposable PostgreSQL container `r2c-pg`, but the Docker engine was not reachable when I last checked, so I could not confirm the container is gone; if it is still there, `docker rm -f r2c-pg` removes it. Review worktrees remain under `C:\Projects\alive-review-pi02c*`. Nothing was committed, pushed or posted.
