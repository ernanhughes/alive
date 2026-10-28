# Main consolidation — 28 October 2026

The owner explicitly requested consolidation of all recent branches and PRs into
`main`, with old branches retained. This supersedes draft/no-merge recommendations
in the attached historical reviews for this engineering integration. It does not
authorize a paid experiment or establish feature/demo readiness.

## Included work

- Starting local main: `767596c` (PR #35).
- Existing claim qualification history: `fc56df4`, plus local repairs, reference
  documents, fixtures, probes and historical evidence preserved in `e00fae5`.
- Browser branch `codex/alive-05-browser-experience`, through `7ac8563`.
- R5-R1 durable campaign/approval safety branch, through `e70af92` (PR #36).
- Upstream main merge `36207cf`, which appeared during consolidation.
- All other local and fetched remote branch tips were already ancestors and
  remain included. No branch was deleted and no history was force-pushed.

The browser branch was based on an older version of the companion. Its conflicting
features were already implemented in newer form on main. The merge retains the
current configurable backend, provenance checks, selected-note/rating protections,
research/blind/campaign UI and extension version. Other browser-branch changes
merged without a content delta.

The R5-R1 recovery conflict preserves both durable campaign blocking and zero-cost
local claim-fixture recovery. R5-R1 tests and archives were preserved, not weakened.

## Integration repairs

The all-table F probe previously failed because withdrawn evidence survived in
`validation.evidence[].quote`. Scrubbing now traverses nested dictionaries and
lists, removes evidence/output copies, and preserves lifecycle/accounting metadata.
The original failing test is unchanged and now passes on SQLite and PostgreSQL.

Inherited Python lint and formatting failures were corrected. The only additional
validator edit removes an unused local variable; this is not new semantic or
entity-binding qualification. Frozen protocol/corpus and archive payloads were not
modified.

## Validation

- Focused claim, foundation and R5-R1 backend suite: **61 passed**.
- PostgreSQL 18 claim/foundation suite: **30 passed**, isolated per-test databases.
- Extension suites: **11 passed**.
- Dashboard: **7 passed**; production TypeScript/Vite build passed.
- Ruff lint: passed; Ruff format: **157 files already formatted**.
- R1/R2/R3/R4/R5/R5-R1 archives: **18/16/30/32/36/52 payloads verified**.
- ALIVE-14/R2/R3 protocol and R3 answer-key identity checks: passed.
- Full Windows/SQLite backend suite: **356 passed, 6 skipped** in 335.23 seconds.
  [Full output](validation/consolidation-2026-10-28/backend.txt).
  All six skips are existing R4 paths superseded by R5, not new skips.
- [PostgreSQL output](validation/consolidation-2026-10-28/postgres.txt).

The PostgreSQL server was created solely for these tests and shut down when
complete. Automatic approval review blocked deletion of its temporary data
directory; the stopped test files remain under the user's Temp directory. No
existing database service was changed. No external model call, paid experiment,
actual owner consent, new browser permission, or intelligence cycle was introduced.
Native Chrome and Linux were not rerun in this session.

The older [claim qualification report](ALIVE-INTEL-I1A2-LOCAL-QUALIFICATION.md)
records an earlier stopped state. Its F storage-leak blocker is resolved by this
consolidation. Its remaining real-source/capture-v2 identity and independent review
gates remain; a green engineering suite is not a declaration of I1-B readiness.
