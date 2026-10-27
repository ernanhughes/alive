# OpenCode interim handoff - ALIVE-04 Living Experience

## Starting state

| Item | Value |
|---|---|
| Repository | `https://github.com/ernanhughes/alive` |
| Isolated worktree | `C:\Users\ernan\.local\share\opencode\worktree\f94c9e\nimble-sailor` |
| Starting branch | Detached `HEAD` at `0809f3788b521328e37d0bb41e87a6aefde76ef3` |
| Same commit as | `codex/alive-05-browser-experience` |
| ALIVE-04 branch then | `codex/alive-04-living-experience` at `a2aa64d` |
| Isolated worktree status | Clean |
| Primary worktree | `C:\Projects\alive`, branch `codex/alive-05-browser-experience`, dirty with uncommitted ALIVE-05 work |

The primary worktree had 11 modified files and 9 untracked paths, including an unrelated
`models.txt` and uncommitted ALIVE-05 files. **It was not modified, cleaned, reset or stashed.**
This work used a separate clean worktree. No branch other than `opencode/alive-04-interim` was
created or changed.

I branched from the committed tip `0809f37` rather than from the older ALIVE-04 branch
`a2aa64d`, because `0809f37` already contains the qualified ALIVE-04 implementation and archive
(`c8c9feb`, `62be48a`, `bdefbc4`) plus the follow-up optional-Critic test commit. The primary
worktree's uncommitted ALIVE-05 changes were deliberately not imported.

## Scope selected

Bounded ALIVE-04 reliability, provenance and dashboard observability only:

- Verify model claims against the source they cite, not only against end-of-episode feedback.
- Recheck the persisted controlled-read grant immediately before paid inference.
- Revoke the grant and record an event when a running journey is interrupted by restart.
- Make the existing feedback loop legible in the dashboard: reason, recalled outcome, executed
  operations, source/feedback separation, factual support, conclusion contract, Governor envelope.
- Add focused backend and frontend tests. No new learner, cognitive role, provider, migration,
  budget increase, deployment or architecture change.

## Files changed

| File | Change |
|---|---|
| `alive/living_evaluation.py` | Claim/source support, feedback corroboration, source value in outcome |
| `alive/living_policy.py` | `numeric_equal` handles malformed non-numeric values |
| `alive/living.py` | Grant recheck before inference; restart grants revoked and audited; sources persisted |
| `tests/test_living.py` | Three new tests; malformed-number assertions |
| `dashboard/src/Living.tsx` | Reason, recall, Governor operations, provenance, Governor envelope |
| `dashboard/src/style.css` | Styling for recall and provenance blocks |
| `dashboard/src/Living.test.tsx` | New component test for provenance rendering |
| `docs/ALIVE-04.md` | Protocol updated for source/feedback distinction and restart revocation |
| `docs/OPENCODE-ALIVE04-HANDOFF.md` | This handoff |
| `archives/ALIVE-04-INTERIM/` | New controlled regression evidence archive |

## Problems fixed

1. **Factual support was checked against the wrong evidence.**
   `assess()` compared the model claim with the end-of-episode feedback. A claim could therefore
   match feedback while contradicting the current instrument source it cited. The claim is now
   checked against `sources[0]["value"]`; goal resolution additionally requires the independent
   feedback to corroborate that source. `outcome.source_value` and
   `outcome.feedback_confirms_source` are persisted.
2. **Permission could be revoked between action execution and inference.**
   `Living.reason()` checked journey status and Governor budgets but not the persisted `allow`
   grant. It now raises `PermissionError` before reserving tokens. A test revokes the grant after
   the action phase and verifies that no ledger entry or transition is created.
3. **A restart-interrupted journey retained an active grant.**
   `Living.initialize()` marked running journeys interrupted and settled reservations but left
   `allow` true and emitted no audit event. It now sets `allow=false`, records
   `living.interrupted`, and still refuses replay. A test simulates a reserved in-flight call,
   restarts the app and verifies conservative charging, zero reserved calls, no transitions and a
   rejected advance.
4. **The dashboard did not expose the evidence chain.**
   It now shows the deterministic reason, the recalled prior outcome (not just a count),
   Governor-permitted operations, the source value and feedback value separately, factual
   support vs conclusion-contract status, and the Governor envelope. It labels missing legacy
   fields rather than guessing.
5. **Malformed numeric values could raise instead of failing closed.**
   `numeric_equal` now catches `TypeError` as well as `ValueError`.

## Tests executed

| Command | Result |
|---|---|
| `uv run pytest -q` | **86 passed** (83 before; three new tests) |
| `uv run pytest -q tests/test_living.py` | **10 passed** |
| `uv run ruff check alive migrations scripts tests` | Passed |
| `uv run ruff format --check alive migrations scripts tests` | 79 files already formatted |
| `npm test --prefix dashboard` | **5 passed** in 2 files |
| `npm run build --prefix dashboard` | TypeScript and Vite production build passed |
| Frozen ALIVE-04 replay with the new `assess()` | Both episodes match original classifications |

The only repeated warning is the pre-existing Windows ZeroMQ Proactor selector-thread warning.

## Evidence generated

`archives/ALIVE-04-INTERIM/` contains:

- `README.md` - provenance, results, reproduction and limits.
- `evidence/controlled-fixture-journey.json` - complete two-encounter journey from an isolated
  SQLite database and synthetic in-process browser adapter.
- `evidence/frozen-archive-replay.json` - proof that the new assessment preserves the frozen
  ALIVE-04 classifications.
- `validation/` - actual backend, living-focused, frontend, build, Ruff and whitespace transcripts.
- `manifest.json` - SHA-256 and byte count for every other payload.

**This is simulated controlled-fixture evidence, not live Chrome or Meta evidence.** It records
zero model tokens, zero paid calls and provider `mock`. It is useful for regression and dashboard
provenance, not for claims about native browser behaviour or model reasoning.

A native Chrome/Meta requalification was not attempted because ports `8000` and `5173` were
occupied by the owner's primary worktree, and no paid inference was authorised. I did not stop or
interfere with those processes.

## Security and budget status

- No Meta call was made. No paid inference was run.
- No provider key, token or credential was written to the archive.
- No browser contents beyond the controlled synthetic fixture were captured.
- No unrestricted URL, selector or tool permission was added.
- No budget, model pin or Governor limit was changed.
- No migration was added or altered.
- No frozen ALIVE-01/02/03/04 evidence was modified. All prior archive manifests verify.
- Nothing was pushed, merged, rebased or deployed. `main` was not changed.
- The primary worktree and its `models.txt` were not touched.

## Known limitations

- No native Chrome or Meta requalification on this branch. The archive is a test-harness fixture.
- The new dashboard fields have a React component test and production build, but no new native
  browser screenshot or Playwright run.
- Legacy ALIVE-04 archive rows do not contain `source_value`, `feedback_confirms_source` or
  `conclusion_contract_correct`; the dashboard labels these as not recorded for legacy journeys.
- The policy is still a tiny exact-context empirical outcome mean with a zero prior. Two outcomes
  do not establish generalisation.
- `Living.initialize()` still scans all `running` journeys rather than filtering by instance. The
  runtime is single-instance in current use; note this if multi-instance deployment is considered.
- The live demo remains sensitive to a warm policy: it reuses existing action values and may not
  show a new action change. The UI now says this before a journey starts.
- The existing `archives/ALIVE-04` remains frozen at `62be48a`; its source hashes describe the
  original implementation, not this branch. Do not regenerate it in place.

## Incomplete work / recommended next steps for Codex

1. Review `opencode/alive-04-interim` as a candidate; do not auto-merge. The branch is based on
   `0809f37`, not on the primary worktree's uncommitted ALIVE-05 changes.
2. Reconcile the one-line `alive/living.py` concurrency guard when integrating ALIVE-05
   (`self.app.state.web.active`).
3. Run a native Chrome/Meta requalification on free ports with a cold qualification database and
   explicit owner authorisation. Preserve it as a new archive; never overwrite `archives/ALIVE-04`.
4. Add a native browser E2E assertion for the new provenance text if a paid live journey is
   available; the current component test covers the rendering path without inference.
5. Consider a read-only preflight indicator of whether the live context is cold or warm, so a
   presenter knows before starting whether a new action change is possible.
6. Keep the new source-vs-feedback distinction in any future archive replay. Do not backfill or
   rewrite the old archive.

## Exact local commits

| Commit | Purpose |
|---|---|
| `6ebbfa1` | Harden living evaluation and revoked-permission restart paths |
| `b6aad7d` | Expose living provenance, recall and Governor outcome in dashboard |

The evidence archive and this handoff document are committed in the final local commit on
`opencode/alive-04-interim`. The final branch tip hash is reported in the completion message and
can be confirmed with:

```powershell
git log -1 --format=%H
git log --oneline 0809f37..HEAD
```

No remote branch was created. Nothing was pushed.
