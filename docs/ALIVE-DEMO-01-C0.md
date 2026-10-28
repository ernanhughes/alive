# ALIVE-DEMO-01-C0 — Evidence integrity repair (independent-review handoff)

**Status:** Implementation candidate on isolated branch; not independently qualified. Do not merge until gates below have been demonstrated.

## Basis
Claude PR-C review on merged `main` at `65fc0f0` found: paired output still exposing withdrawn source through missing `historical_memory_id`; a revocation/dispatch gap; 254 pass / 1 fail in full tests; and cross-goal findings in the side panel. See owner-provided `ALIVE-DEMO-01-PR-C-CLAUDE-REVIEW.md` and `test_zz_prc_probe.py`.

## Changes in this branch
1. The research-memory withdrawal transaction computes dependent consent IDs and invalidates all derived rows matching direct `historical_memory_id` or consent lineage, including paired analysis records. No new persistence or schema changes.
2. The optional bounded analysis `shared` fields include a historical-memory ID for future direct dependency tracing.
3. The ordinary history-assisted provider path performs its final source checks and commits the durable dispatch-possible marker under the same database transaction and lock hold, removing the separate unguarded marker transaction.
4. The pre-dispatch failure status remains `failed` when the request was never sent; post-dispatch loss may be `invalidated`.
5. The relationship-list route accepts an optional `goal_id`. Derived outputs are screened against the current authoritative active-memory set through their consent lineage. The Chrome background bridge requires a selected goal.
6. Targeted paired-withdrawal and goal-scope tests were added to `tests/test_demo01_c0.py`.

## Qualification required / possible limitations
- Run the existing test `test_grant_revocation_between_reservation_and_dispatch_blocks_call` **unchanged**, the new tests, and the full suite.
- Integrate reviewer probes E, F, D and C-real into permanent exhaustive tests, particularly a deterministic synchronization test for revocation immediately before provider egress. The new tests do **not** yet cover all four probes.
- Verify the non-bounded path on SQLite and PostgreSQL with cancellation/restart.
- Prove no copied withdrawn text remains in any derived storage row. Authoritative snapshot/note retention remains a separate owner policy decision.
- Confirm the read-time filtering logic includes all existing output shapes and does not leak cross-goal records.
- Confirm the source-grant revocation semantics when a provider call begins just as revocation executes. Atomic final check + marker reduces the old race but cannot alone eliminate the scheduling interval between marker commit and an external network call.
- Confirm existing ALIVE-14 experiment gates and budgets are not weakened. This branch intentionally does not modify experiment code.
- `node --check extension/background.js`, extension tests and native Chrome journey.
- No real Meta calls, expenditure, campaign approvals, or merges were performed in this work session.

## Independent reviewer instructions
Review C0 as a potential safety fix, not a complete or certified guarantee. Reject it if the provider can receive bytes after a completed revocation, a derived row retains withdrawn content, or a mainline regression remains. If these fail, retain draft status, correct in a further commit, and re-run probes; do not weaken tests.

**Next after qualified C0:** design and implement C1 claim-comparison with explicit reliance anchor, fixtures and deterministic validators.
