# ALIVE-DEMO-LIVE-01-R1 — post-merge repair report

## Delivery and scope

Reviewed main/base: `cf587c1af90bb605dd18e64162403bcade588e82`, verified by fetching
origin/main. Branch: `fix/alive-demo-live-01-r1`. Runtime/native-qualified checkpoint:
`fc9e75f1fca1b436edb372acb29f2251eafcd9b2`. Delivery commits after that checkpoint
contain documentation and qualification evidence only. This repair is delivered
as a **draft PR** for a new independent review of its resulting head. Do not merge.

This demonstration remains a **deterministic local-fixture result**: both the
comparison and the abstention are pre-registered outputs keyed by source-hash
pairs. It does not demonstrate independent reasoning or judgement. The real-page
path is demoted by design because only pinned mirrors have source identity.
No paid or external inference was made and no real provider was invoked.
No I1-B/Think work, new features, migrations or browser permissions were added.
Any authorization exercised by tests/native qualification was isolated local-fixture
API activity, not an owner approval for a real provider.

**Retired findings and saved sources are hidden from ordinary views; audit
originals are retained.** Complete deletion, source authenticity, human usefulness
and live-provider readiness are not claimed.

## Item 1 — stale recorded abstention

Reproduction supplied by the independent review: an abstention for pair X was
shown while viewing pair Y in the same investigation; an older abstention could
also appear after dismissing a real candidate. `renderContext` previously selected
any validated abstention from the entire investigation ledger.

The repaired renderer matches all of the attempt's actual stable fields:
`goal_id`, `current_url`, `current_sha256`, and `historical_memory_id` of a displayed
anchored memory. Snapshot IDs are deliberately not used: a re-review may create a
new snapshot of the same source. A validated non-abstention outcome for that pair
suppresses older abstentions, including after dismissal; the dismissal message is
retained. An unmatched source retains the relevant-evidence/no-authorisation state
or the quiet state. The existing wording is unchanged in both UI and harness.

Four permanent Node tests were added to `tests/extension-live-companion.test.cjs`:

- Mismatches of hash, URL, memory or investigation cannot display a recorded check.
- A matching pair displays its abstention despite a different snapshot ID.
- A dismissed validated candidate cannot inherit an older abstention (same or other pair).
- An unrelated abstention with no displayed memory preserves the quiet state.

Running those same new tests against the reviewed-main companion reproduces
three failures (mismatched pair, dismissed alert and quiet state); the repaired
companion passes all ten tests. See
[node-reviewed-main-reproduction.txt](validation/demo-live-01-r1/node-reviewed-main-reproduction.txt).

The existing six companion tests pass unchanged. The native harness now records
Demo B's abstention, anchors again in that same investigation, opens the 3.12 mirror
and asserts the **unauthorised** relevant-evidence state without a third dispatch.
`stale_abstention_absent: true` is recorded in the final native result.

## Item 2 — withdrawn note exposure

The legacy flow retained the full note at `/notes/{id}` after source withdrawal;
the ordinary events feed exposes its ID. The endpoint now checks for **any**
withdrawn `research_memory` row with `data.note_id` equal to the requested note ID.
It returns HTTP **410** with a generic message and no note output, context,
instructions or other source-derived fields. Unknown notes retain existing 404
handling. This is an endpoint exposure check; no stored note/snapshot/memory row is
deleted, and withdrawal/projection semantics and the leak-scanner audit allowance
are unchanged.

Two existing expectations were deliberately changed as explicitly requested:

- `test_D_all_tables_and_public_reads_after_withdrawal` in
  `tests/test_demo01_foundation_probes.py`: 200 plus marker becomes 410 without marker.
- `test_probe_D_full_database_scan_after_withdrawal` in
  `tests/test_zz_prc_probe.py`: the same deliberate change.

New `tests/test_demo_live_01_r1.py` has two permanent tests:

- Enumerate every `web.note` ID from the events feed after withdrawal and verify
  410/404 with no marker; scan every non-templated GET path in OpenAPI plus events;
  confirm the stored note still contains the audit original; shut down the original
  app, reopen the same database and verify 410 persists.
- An unsaved note is readable, and an active saved note remains readable when a
  different memory in the same investigation is withdrawn. The retired note is 410.

The new tests support the isolated PostgreSQL fixture as well as default SQLite.
Existing active-note expectations in `tests/test_research_memory.py` and
`tests/test_web_experience.py` were not modified.

## Item 3 — capture-version downgrade

[Validator reproduction](validation/demo-live-01-r1/validator-reproduction.json)
executes the reviewed main validator and the repair directly on the real mirror
text. Both declared-v1 and absent-version payloads were **accepted** on reviewed
main and are **demoted** by the repair, independently of provider dispatch.

The validator now computes excerpt hashes itself. If either excerpt matches any
registered mirror capture hash, it executes the existing v2 identity and entry
binding checks regardless of declared version. This is stricter than a URL-only
gate: changing the URL cannot bypass it. Caller-supplied SHA fields cannot enable
the bypass either. Missing/v1 versions fail identity verification and demote.
Existing demotions and legacy unregistered-v1 behavior are not weakened.

A two-case parametrized regression was added to `tests/test_demo_live_01.py` for
v1 and missing version keys. Both require demotion and both identity-failure reasons.
`test_legacy_named_other_method_is_not_a_supersession` and all of
`tests/test_claim_runtime.py` remain unchanged.

## Optional hygiene, narrowly scoped

The native harness writes a failed run to the next available
`attempt-N-result.json` and leaves an existing successful `result.json` untouched.
R1 artifacts use a separate directory, preserving the original qualification
artifacts. Native runs were executed from the short worktree `C:\r1`.

The public mirror route was intentionally left unchanged. Gating app startup is
not necessary for these three repairs and was optional. It serves only the
existing allowlisted static attributed fixture pages with pinned-byte verification
and the existing restrictive CSP; it does not serve user research. No claim that
this route is authenticated is made.

## Qualification

Baseline from the independent review on the exact merged commit: **380 passed,
6 skipped** Python and **29 passed** Node. A separate full baseline rerun was not
performed in this repair. Final commands and transcripts are in
`docs/validation/demo-live-01-r1/` and [commands.txt](validation/demo-live-01-r1/commands.txt).

- Full Python: **384 passed, 6 skipped, 546 warnings in 386.72s (0:06:26)**. Four new cases; two explicitly changed
  existing expectations, as listed above.
- Five extension Node suites: **33 passed, 0 failed** (four new cases).
- PostgreSQL 18: **46 passed, 49 warnings in 50.39s**, on a new isolated local
  server and fresh per-test databases. This includes the original 42-test subset,
  two downgrade cases and both PostgreSQL-backed note exposure tests.
- Scoped Ruff: **PASS**, **166 files already formatted**.
- All six ALIVE-14 archive verifiers and three protocol verifiers: **PASS**.
- `_analyze_bounded` AST: **identical** to main; SHA-256
  `7ad4e965db6d97176545cc63174ba435b37f0e87014b3e5fca60c96438e35e0a`.
- No protected paths changed: archives, research_blind, scripts/alive14*,
  scripts/verify*, migrations, shipped manifest and campaign approvals unchanged.
  [Proof and changed paths](validation/demo-live-01-r1/protected-boundaries.json).
- Real docked Chrome 156 from `C:\r1`: **PASS** for both demos, retirement/restart,
  Goal isolation, 360 px width, and the additional same-investigation stale-message
  assertion. Two local-fixture attempts, zero external calls, zero paid spend.
  [Native result](validation/demo-live-01-r1/native/result.json),
  [new-page screenshot](validation/demo-live-01-r1/native/06-unchecked-source-after-abstention.png).

The final native checkpoint matches the runtime implementation above. Its initial
working-tree status lists only untracked R1 artifacts from an earlier successful
run; no runtime edits were present. The earlier run at `f6056ca` also passed.

During test authoring, the first new enumeration test used the wrong events field
(`data` instead of actual `payload.id`); this was corrected. A subsequent targeted
run exposed a mistake in the new restart test: it opened a second app before
closing the first, correctly yielding 503 for an already-owned runtime. The test
now shuts down the original app first and passes on SQLite and PostgreSQL. These
were new-test errors, not changes to existing product expectations. An earlier
full run with that outdated collected test was interrupted and replaced by the
final full run. Failed targeted output remains in `targeted.txt`; the corrected
notes-only run is in `notes-targeted.txt`.

Windows ZeroMQ/Proactor warnings remain visible and unsuppressed. Linux and the
full pgvector first-contact context were not run locally. Hosted CI and a new
independent review are not claimed by these local results.

## Review handoff

Please independently review the **resulting draft PR head**, reproduce the three
regressions, inspect the deliberate note expectation changes and rerun the
qualification commands. Confirm that the pair-matching fallback and dismissal
behavior remain conservative with multiple related memories, and that the endpoint
checks any withdrawn lineage without altering audit originals. Independent review
is outstanding. **Do not merge this repair before that review.**
