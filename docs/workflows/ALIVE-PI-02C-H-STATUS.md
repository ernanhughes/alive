# PI-02C-H — implementation intake (incomplete)

Base: integrated `main`, `e483d16bad57f7e1957bf73b043bce7e16f10d01`.
Branch: `codex/pi-02c-h`. Authentication recovery PR #73 remains separate.

## Confirmed replay correction

The saved `C:/Projects/alive-pi02c-evidence/ambiguous-timeline.json` recording
contains 13 events. `pi.run.unknown` is at sequence 101;
`workflow.execution.ended` with status `UNKNOWN` is at 102. The original
projection leaves Analyze `RUNNING` after both events.

The correction interprets recorded terminal workflow execution events. Any
previously claimed stage without an independently recorded result is shown as
`Ended — outcome not recorded`. Recorded completed stage results remain intact;
unclaimed stages remain absent. Pi terminal events alone do not establish a
workflow stage's terminal state. No final snapshot, synthetic event, event
reordering or cursor change is used.

Evidence outside the repository:
`C:/Projects/alive-pi02c-h-evidence/reproduce-unknown-replay.mjs`,
`unknown-replay-baseline.json`, and `unknown-replay-after.json`.
The captures include input and projection-source SHA-256 hashes.

Executed on Windows:

- Before correction, `npm test -- src/workflows/replay.test.ts`: 10 failed,
  3 passed, with behavioural assertion failures (the stale `RUNNING` state).
- After correction, `npm test`: 44 passed, including the 13 new replay cases.
- `npm run build`: passed.
- `node C:/Projects/alive-pi02c-h-evidence/reproduce-unknown-replay.mjs --fixed`:
  Analyze changes only at sequence 102 to the explicit unrecorded-outcome label.

## Required independent input is still missing

The final independent PI-02C-R1 report has not been located. The available raw
`C:/Projects/alive-pi02c-evidence/observatory-mutants.json` contains nine
survivors, three kills and six INVALID runs (O13–O18). Those invalid process
exits are not mutation kills or evidence of equivalence/redundancy.

The final O1–O18 classification, identity/ownership regression scope and final
qualification are pending the report required by the brief. No classification
is inferred from a survivor alone. No draft PR or final-head CI has been
submitted for this incomplete scope.

Browser replay qualification, SQLite/PostgreSQL restart and zero-effect checks,
Pi identity-corruption probes and relevant mutation replay have not been run
for PI-02C-H yet. No backend execution authority, Governor, Pi dispatch,
migration or Intelligence learning code has been changed. No paid inference.
