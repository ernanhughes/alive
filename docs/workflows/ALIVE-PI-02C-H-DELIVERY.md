# PI-02C-H — historical replay and Pi identity integrity

Base: integrated main `e483d16bad57f7e1957bf73b043bce7e16f10d01`.
Branch: `codex/pi-02c-h`. Authentication recovery PR #73 remains separate.

## Production correction

Only three production files change, all in `dashboard/src/workflows/`:

- `model.ts` maps recorded Pi unknown/failed/cancelled events to distinct
  `UNKNOWN (Pi run)`, `FAILED (Pi run)` and `CANCELLED (Pi run)` labels. A terminal
  execution event changes a still-running stage to
  `Run ended S; stage outcome not recorded`. No snapshot, synthetic event,
  event reordering or cursor change is used.
- `RunTimeline.tsx` shows the recorded run outcome only after its event has
  been played. Rewinding or returning to the snapshot removes it.
- `StageInspector.tsx` reads feedback and learning facts from artifact fields.
  False/null responses retain their current text; a future true/episode-id
  response is tested without loosening today's backend contract.

The final R1 report, correction brief and O1–O18 classification are retained
byte-for-byte in `validation/pi02c-h/review-inputs/`. These supersede the stale
partial results found during intake. Independent O9/O13 probe results in that
input were transcribed by the reviewer from an earlier run, as disclosed there.
All seven new target kills below were executed afresh.

## Real-history qualification

Fresh `scripts.workflow_observatory_demo` seeds used the pinned Pi and a
loopback scripted provider. SQLite and disposable PostgreSQL 18 each produced
six runs, four provider calls and zero learning updates. Restart verification
preserved invocation/Pi/request/run/artifact/learning counts on both. SQLite
and PostgreSQL were verified again after browser reads, with counts unchanged.

`dashboard/src/workflows/fixtures/recorded-timelines.json` contains actual
captured demo histories, with generator/base provenance. The before/after
receipt compares the base and corrected projections on identical inputs:

| History | Before | After |
| --- | --- | --- |
| ambiguous, 13 events | Analyze RUNNING | UNKNOWN (Pi run); ended UNKNOWN |
| partial, 19 events | Four stages COMPLETED; no run outcome | Same stages; ended FAILED |
| goal_cancel, 3 events | No stage events | Stages Not recorded; ended FAILED |
| research, 19 events | Four stages COMPLETED | Same stages; completed |

Every cursor is checked for future-state leakage. Supplemental cases cover all
four terminal statuses with absent stage-result events. The original test
"never backfills final snapshot state into replay" is unchanged.

| Executed check | Result |
| --- | --- |
| Focused backend: observatory, workflow API, new identity file | 88 passed |
| New identity/scoping file against unchanged Python production | 15 passed |
| Dashboard `npm test` | 59 passed (31 baseline + 28 new) |
| Dashboard `npm run build` | TypeScript/Vite pass |
| Chrome `e2e/workflows.spec.ts`, fresh SQLite and PostgreSQL | 2 passed on each; end, rewind and original journey; no API writes |
| Six extension suites, `node --test` | 38 passed |
| Ruff check and format, alive/migrations/scripts/tests | pass |
| Full collection | 1266; expected 1253 pass, 12 skip, 1 xfail |
| Production Python, dependencies, migrations, timeouts | unchanged |

Final-head push and pull-request CI results and full-suite counts are recorded
in the draft PR after completion, without changing the tested commit. The full
backend suite is delegated to both Windows/Linux CI runs rather than duplicated
locally. Local dependencies use the existing locked installations; CI installs
from the lockfiles independently.

## Mutation proof

`python -m scripts.workflow_observatory_mutations --output <receipt.json>`
mutates temporary copies only. Each target first passes against unmodified
production. A kill requires a named behavioural assertion, never setup failure.

| Mutant | Assertion target | Result |
| --- | --- | --- |
| O1 | identity `[pi_other_instance]` | KILLED |
| O2 | identity `[pi_pointer_from_other_run]` | KILLED |
| O3 | identity `[invocation_wrong_run]` | KILLED |
| O4 | identity `[invocation_wrong_investigation]` | KILLED |
| O6 | identity `[pi_wrong_operation]` | KILLED |
| O9 | `test_c_timeline_pagination_and_run_isolation` | KILLED |
| O13 | identity `[definition_json_altered]`, raw SQL | KILLED |
| O5 | existing actual-Pi receipt/history | KILLED |
| O11 | existing corruption `[result_hash]` | KILLED |
| O12 | existing corruption `[owner]` | KILLED |
| O15–O18 | existing bounded ordered timeline | KILLED |

All 14 assertion receipts are retained. An initial parser expected the literal
`AssertionError` text, while pytest printed `E assert` for O15. The parser was
corrected and O15–O18 rerun; no invalid execution is counted as a kill.

Under O9, foreign Pi events are admitted and stamped with the selected run id:
false attribution and disclosure of foreign identity/timing/status metadata in
that projection. Payloads remain omitted. The unmodified server prevents it.

The independent 18-case matrix is imported, not replaced by our 14-case replay.
O7 stays unresolved/unprobed; O8 is additionally scoped by owned run/Pi ids;
O10 is correlated by run but not independently probed; O14 is still refused
through the later declaration lookup. No guard is removed or declared equivalent.

## Independent-review handoff

Inspect the production diff, actual timeline frames and per-cursor assertions.
Verify all three 404s for corrupted associations and O9's inclusion/ownership
assertions. The shared-definition JSON attack must not assume the other run is
unaffected. Read all mutation assertion excerpts and both final-head CI runs.

Evidence lives under `validation/pi02c-h/`: `mutations.json`,
`replay-before-after.json`, `ambiguous-replay-end.png`, SQLite/PostgreSQL restart
receipts and the hash manifest. Commands: seed with
`python -m scripts.workflow_observatory_demo --directory <empty> --seed`;
serve with `--directory <same> --serve 8022`; set ALIVE_BASE_URL,
ALIVE_OBSERVATORY_MANIFEST and the demo's fake ALIVE_API_TOKEN for Playwright.
The mutation script gives the exact named backend test selectors.

Per the final brief, Docker restart, hash-chain verification and long-history
browser qualification beyond 500 events are out of scope. No tests were added
solely for O7/O8/O10/O14. The pre-existing Windows 10-second Cognition/Pi wait is
unchanged, as is the single-active-host topology. No paid inference, PI-03,
Bespoke implementation, new endpoint or automatic merge.
