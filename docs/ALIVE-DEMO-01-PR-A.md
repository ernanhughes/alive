# ALIVE-DEMO-01 PR-A — Evidence-integrity repair (draft)

**Status:** implemented as a reviewable draft, **not qualified**. No model inference, paid calls or extension modifications were performed.

## Source of this change

Claude's independent ALIVE-DEMO-01-R0 review (reported at main `acd9b05`) reproduced three defects: withdrawn historical evidence remained in served findings, page-grant revocation could race late inference settlement, and the non-bounded relationship path could recover a possibly-dispatched request at zero cost.

## Changes

1. `ResearchMemory.withdraw` invalidates dependent consent, attempts, connection and bounded analysis rows in the *same transaction* that retires the authoritative research row. It removes copied quotations, raw model output, explanations, excerpts and payloads from those dependent records while retaining IDs, lifecycle state and accounting. Repeated invalidation is idempotent. The pre-existing endpoint's subsequent invalidation call remains a redundant safety sweep.
2. `ResearchRelationships._settlement_source_valid` rechecks the current snapshot's grant, SHA and, where relevant, historical source status, SHA and goal *under the settlement lock*. If invalid, output cannot be marked validated or persisted as a new connection; the attempt is marked invalidated and evidence-bearing fields scrubbed.
3. The history-assisted relationship path now durably commits `dispatch_possibly_started` before invoking any provider. Restart recovery already recognizes this marker and conservatively charges the reservation, rather than treating ambiguous post-dispatch crashes as free.
4. Targeted unit tests cover content scrubbing and rejection of revoked grants/retired evidence.

## Engineering qualification gates (still required)

- Run `uv run pytest tests/test_demo01_evidence_integrity.py` and the complete backend suite.
- Re-run Claude's **three reproductions** in `test_zz_review_probe.py` (not supplied to this branch); transform each into a permanent integration regression.
- Verify atomic withdrawal with direct database queries and authenticated `research/relationships` list responses; no copied quote or raw output appears after withdrawal or restart.
- Simulate grant revocation while a local synthetic provider response is blocked; confirm no new validated finding, and confirm cost liability is settled.
- Terminate the process after durable dispatch-start and before response. Restart and verify `interrupted` attempt with reserved token liability, without replaying the external call.
- Verify exception and cancellation behaviour for both current-only/paired and history-assisted paths, including existing ALIVE-14 budget and campaign tests.
- Independently review the broad scrubbing set, residual provenance, source-pointer leakage and authorization semantics.
- Verify no current-page-only analysis is spuriously labelled invalid because it lacks a historical memory.

## Important limitations

This work does **not** make ALIVE-DEMO-01 hackathon-ready. It has no browser card, no real-source fixture, no Meta call and no conversational skill creation. The repository's existing source/grant policy remains unchanged. The patch has not been executed in the user's local environment; the claim is an engineering **candidate**, not a verified safety fix.

**Review request:** do not merge until the above gates pass. If the three Claude probes still reproduce, correct the implementation rather than weakening the probes.
