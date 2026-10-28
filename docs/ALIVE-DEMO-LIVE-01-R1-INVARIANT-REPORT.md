# ALIVE-DEMO-LIVE-01-R1 — display-invariant hardening

## Base and scope

Base: `91589605938f05903bc404e7dc7973ab0c7967e8` (merge of PR #38, the R1 repair),
verified by fetching `origin/main`. Branch: `fix/alive-demo-live-01-display-invariant`.
This is a **draft PR** follow-up; do not merge before independent review.

This change is deterministic and local. It makes no model calls, uses no paid
inference, adds no new feature, migration or browser permission, and does not
modify any historical result, fixture, oracle, scorer or frozen verifier rule.
The demonstration remains a deterministic local-fixture result; it does not
demonstrate independent reasoning or judgement.

## Why this follow-up

The owner added this acceptance requirement to R1:

> No interface may display "Evidence checked," "No validated change detected," or an
> equivalent result unless it can identify the exact source pair, investigation and
> completed analysis supporting that statement. A dismissed candidate must not cause an
> unrelated historical abstention to become the displayed result.

Reviewing the merged R1 repair against that requirement found two gaps.

1. **Persisted claim-comparison rows did not carry the fields the repaired
   renderer matched.** `renderContext` binds a recorded abstention to
   `goal_id`, `current_url`, `current_sha256` and `historical_memory_id`, but
   `ResearchRelationships.analyze` created claim-comparison attempt rows with
   only the snapshot/memory IDs and hashes. The filter therefore could not
   match a real persisted abstention. The native "stale abstention absent"
   assertion passed vacuously: nothing matched, so the stale message was absent
   for the wrong reason.
2. **The immediate post-authorisation path was unbound.** After
   `authorise-relationship` / `analyse-relationship`, `showPreview` displayed
   "Evidence checked · No validated change detected" for any analysis whose
   `status` was `validated`, without checking the goal, current source or
   historical memory. The Node fixture demonstrated the gap: its default
   analysis carried no identity fields and the abstention still rendered.

The refreshed renderer already fails closed with respect to *display*; the
second gap could display a validated result that did not belong to the checked
pair. Both are corrected here.

## Change

- Persist `goal_id` and `current_url` on every outbound analysis attempt, in
  addition to the existing snapshot ID, memory ID and SHA-256 fields. This is
  additive JSON metadata; no schema migration is required, and legacy rows
  without the fields fail closed (no abstention is displayed).
- In `showPreview`, display the abstention only when the returned analysis is
  `validated`, its validation relationship is `insufficient_evidence`, and its
  `goal_id`, `current_url`, `current_sha256` and `historical_memory_id` exactly
  equal the values in the authorised preview. Otherwise the existing
  conservative state is shown: "Check did not complete. No finding was stored."
- `renderContext` keeps its existing exact-pair filter; with the persisted
  fields it now binds real ledger rows instead of only synthetic test rows.
  A dismissed validated candidate still suppresses an older abstention for the
  same displayed memory; an unrelated pair still cannot display a recorded
  check; an unmatched source still falls back to the relevant-evidence or quiet
  state.
- No UI wording changed for the valid outcomes. The independent verifier,
  fixtures, oracle, scorer and Task B remain untouched.

## Permanent regression tests

`tests/extension-live-companion.test.cjs` — two new Node tests:

- The immediate abstention requires the exact recorded pair: each of
  `goal_id`, `current_url`, `current_sha256` and `historical_memory_id` is
  independently changed and then removed; none may display the abstention.
- A validated non-abstention without a stored connection is not displayed as
  an abstention.

The existing pair-binding, re-review, dismissal and quiet-state tests remain
and now exercise rows shaped like the real ledger.

`tests/test_demo_live_01.py` — the synthetic newer-source test now asserts that
the persisted attempt and the goal-scoped ledger listing carry the exact
`goal_id`, `current_url`, `current_sha256` and `historical_memory_id` used by
the authorised preview.

## Qualification

- Five extension Node suites: **35 passed, 0 failed** (two new cases).
- `tests/test_demo_live_01.py` + `tests/test_demo_live_01_r1.py`: **16 passed**.
- Scoped Ruff check and format: **PASS**.
- Six ALIVE-14 archive verifiers and three protocol verifiers: **PASS**.
- Full Python suite: **384 passed, 6 skipped** (recorded in
  `docs/validation/demo-live-01-r1-invariant/python.txt`).
- Real docked Chrome 156: **PASS** for both demos, retirement/restart, Goal
  isolation, 360 px width, the same-investigation stale-message assertion and
  the immediate abstention binding (recorded in
  `docs/validation/demo-live-01-r1-invariant/native/result.json`).

Windows ZeroMQ/Proactor warnings remain visible and unsuppressed. Linux and the
full pgvector first-contact context were not run locally. Hosted CI and a new
independent review are not claimed.

## Limits

- The display guard verifies identity; it does not independently re-verify the
  claim or grant new authority. Submissions remain untrusted until the frozen
  verifier accepts them.
- The immediate path associates the result with the authorised consent; the
  binding check is a display guard against a mismatched or stale response, not
  a second backend verification.
- Legacy claim-comparison rows created before this change have no `goal_id` or
  `current_url`; they fail closed and display no abstention. No backfill is
  attempted.
- One passing canary or one passing deterministic run does not establish a
  model capability ceiling, experience utility or comparison readiness.

## Review request

Please review the resulting draft PR head, confirm both display paths are
bound to the exact pair, and confirm that a dismissed candidate cannot expose an
unrelated abstention. Re-run the five Node suites, the two Python modules, the
full Python suite, the archive/protocol verifiers and the native harness.
