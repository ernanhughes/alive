# ALIVE-10 closeout and integration checkpoint

Review date: 2026-10-27. Mainline: `5ee1031f36aa411e8675f208a794de13c478fea0`.
Reviewed PR #14 head: `f222a0613ccb1c338cfccd2d43a2cd864a0e5977`.
Additional panel correction: `8e1b65a` on `codex/alive-10-review`.

**Recommendation: merge PR #14 after its latest-head CI checks pass and the owner
accepts this checkpoint.** This is an engineering acceptance with explicit limits.
No merge, direct main push, paid Meta inference or ALIVE-12 implementation is part
of this closeout. Codex authored the preceding probe/migration refinements; this
closeout is not a new independent external audit of those changes.

## Findings and resolutions

| Area | Finding / review result |
| --- | --- |
| Probe authority | Previously, a due probe authorised old paused snapshots. Fixed by checking persisted snapshot eligibility. Regression rejects all three old snapshots, allows one designated probe and rejects its duplicate. |
| Migration | Creation-order backfill could undo an in-place rating revision. Fixed by effective policy revision order. Tests preserve v1, create v2 once, and handle known and unknown revision times without inventing timestamps. |
| Feedback targeting | An additional delayed-response race could re-enable feedback after Stop. Fixed by invalidating outstanding note responses when observation context changes. Five JavaScript tests cover Stop, changed preview/language, late errors and normal completion. CI now runs them. |
| Evidence independence | Support is one effective rating per excerpt hash within goal/URL/language. Repeated notes/snapshots do not add independent support; revisions replace evidence. |
| Recovery and correction | Three paused observations make a new snapshot probe-eligible. Explicit owner correction remains permission- and Governor-bound. Transaction rollback preserves policy/correction state on a rejected budget check. |
| Governor / persistence | Reviewed request reservation, pre-dispatch grant recheck, failed-call accounting, stop settlement, restart revocation and no paid replay. No new critical permission or persistence defect found in the qualified single-process scope. |
| Native harness | Isolated SQLite, migrated schema, free loopback ports, temporary extension copy, synthetic HTTP provider and fresh Chrome profile. No reliance on the primary development service. |
| Evidence | Original ALIVE-10 and refinement archives remain frozen. New closeout evidence is separate. No decision replay was passed off as a native outcome test. |

The entire PR diff against main was examined, including configuration, extension,
policy, tests, native/evidence builders and documentation. No new cognitive roles,
model provider, dependency lock changes or unrelated runtime redesign were added.

## Validation and evidence reuse

- Full backend suite: **137 passed** on the refined backend. Backend files are
  unchanged by the panel correction; the full suite was also rerun for closeout.
- Current companion/probe/migration suite: **27 passed**, rerun during closeout.
- Frontend suite: **7 passed**; extension response-race suite: **5 passed**.
- Ruff check and whole-project Python format check pass; production build and
  extension JavaScript syntax pass.
- Fresh headful Chrome journey on committed panel correction: **5 synthetic local
  calls, 750 synthetic tokens, $0 paid**. Price-formula estimate $0.0016875 is not
  a Meta charge. Restart retained policy v11 and five notes; stale grant rejected
  with 403, no duplicate inference. Duplicate analysis, wrong origin, changed hash
  and budget exhaustion were rejected.
- All **334 payloads across 15 existing manifests** matched before adding the
  closeout archive. Earlier frozen experiment files are unchanged in the diff.
- GitHub checks on `f222a06` were independently verified green; the final review
  commit also requires its own checks before merging.

Evidence: [original](../archives/ALIVE-10/README.md),
[post-review refinement](../archives/ALIVE-10-REFINEMENT/README.md), and
[closeout](../archives/ALIVE-10-CLOSEOUT/README.md).
Windows ZeroMQ selector-thread warnings remain; tests still pass.

## Limitations that remain

Chrome used the **extension-page fallback**, not a demonstrated docked side panel.
Real Meta inference was not run for ALIVE-10. Native tests exercise a controlled
page and goal, not arbitrary websites or browsing history. The policy is a small,
configured count-based mechanism, not demonstrated general learning superiority.

The frozen eight-observation replay gives adaptive v2 five calls, two labelled
useful analyses and two missed useful opportunities; constant analysis obtains all
four useful labels with eight calls. Counterfactual cost is estimated, not measured
savings. ALIVE-08 remains negative (0.0475 hierarchical versus 0.0723 flat); the
approximately 0.0747 always-retrieve diagnostic remains post hoc.

The evidence generators can overwrite their fixed archive destinations. Do not
rerun them over frozen directories; use the native harness's fresh local output
and create a separately named archive for future qualification. This operational
constraint is not a runtime permission defect.

## Primary-checkout transition

The primary checkout remains on `0809f37`, with **25 changed/untracked files**,
including **11 differing from or absent in the reviewed head** after line-ending
normalisation. They include unique material; they were not assumed disposable.
The local hash inventory is `.alive/transition-primary-inventory.json`. Its
unrelated file contents and credentials are not published.

Ports 8000 and 5173 still belong to services launched from that older checkout.
The read-only database inspection found PostgreSQL at migration 0006, with two
companion notes and no adaptive policy row. This is not the reviewed ALIVE-10
service. No primary running process, owner database row, checkout or uncommitted file was reset,
stashed, overwritten or stopped during this closeout.

After owner acceptance and merge, first preserve the inventoried files in an
audited local recovery snapshot. Keep ignored credentials/profiles local. Then
establish a clean integration worktree at the actual merged main commit and plan
the controlled service transition; do not start new code against the old running
backend merely because it occupies the familiar port.

## Next checkpoint

The single recommended owner operation is **accept and merge PR #14** after green
latest-head checks. Only then begin ALIVE-11 implementation from the actual merged
commit. [ALIVE-11](ALIVE-11.md) is a preparation-only protocol and cost proposal;
[ALIVE-12](ALIVE-12-PROPOSAL.md) is a deferred design proposal, not implementation.
