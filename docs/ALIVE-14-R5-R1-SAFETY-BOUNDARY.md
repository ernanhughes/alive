# ALIVE-14-R5-R1 - Safety boundary

Status: **REAL_PILOT_BLOCKED**. This document defines the enforced boundary; it
is not an owner approval.

## One durable authority

The server database is the only authority for campaign progression. A dispatch
is allowed only when all of the following are true in the same final dispatch
transaction:

1. the campaign is registered with immutable canonical content;
2. no durable campaign block exists;
3. the active approval matches campaign, run, protocol, stage and cell;
4. the requested index is the single next eligible index;
5. every earlier index has a settled outcome;
6. the cell has no prior or concurrent durable attempt;
7. stage-1/stage-2 eligibility holds;
8. the actual payload matches the canonical cell;
9. source grants, snapshots and historical memory still match;
10. the governor and conservative budget permit the reservation.

Local JSON, output journals, previews and cached approval pointers cannot
override any of these conditions.

## Campaign block

The campaign row stores:

```json
{
  "blocked": {
    "reason": "durable human-readable reason",
    "category": "error category",
    "attempt_id": "fatal or ambiguous attempt",
    "blocked_at": "timestamp",
    "cleared": false
  }
}
```

The first block is never cleared by approval revocation, approval supersession,
local state edits, ordinary restart or a new stage approval. There is no
automatic recovery feature in this milestone.

## Dispatch linearisation

The linearisation point is the commit of the `dispatch_possibly_started` marker.
Revocation, supersession, campaign blocking and dispatch use the same backend
lock/transaction ordering.

- Revocation/supersession committed before the marker: dispatch is refused.
- Marker committed before revocation: the call is possibly in flight, cannot be
  retracted, retains conservative liability, and every later cell is refused.
- A marker committed before a crash is recovered as ambiguous, not as
  never-sent.

The backend is a single-process deployment. The process-local kernel lock
serialises normal callers. Experiment attempts additionally use a deterministic
UUIDv5 primary key derived from campaign digest and call index, so an independent
backend instance cannot reserve the same cell twice. The external provider call
itself is not a distributed transaction.

## Cancellation and recovery

Cancellation during experiment dispatch is campaign-fatal. Settlement and the
campaign block commit before cancellation is re-raised. If cancellation
interrupts the settlement transaction itself, the transaction rolls back; the
next startup recovers the reserved attempt as `interrupted`, charges the full
reservation if dispatch possibly started, marks it fatal/ambiguous and blocks the
campaign. No cancellation path permits a successor dispatch or replay.

## Ordered progression

The next eligible index is derived from durable attempts:

- stage 1: 0 then 1;
- stage 2: 2 through 17 only after stage-1 eligibility;
- a missing, reserved, interrupted, failed or fatal lower index blocks all
  successors;
- duplicate indices are refused;
- a later index cannot overtake an earlier missing index;
- the index check runs at preview, authorization, reservation and the final
  marker.

## Stage contracts

| Stage | Indices | Calls | Reserved tokens | Liability |
|---|---:|---:|---:|---:|
| 1 | 0-1 | 2 | 10,345 | $0.043967 |
| 2 | 2-17 | cumulative 18 | 92,148 | $0.391635 |
| Ceiling | 0-17 | 18 | - | $0.45 |

Stage 2 requires two distinct settled stage-1 attempts at indices 0 and 1, at
least one validated, no fatal/ambiguous/interrupted/outstanding attempt, no
campaign block, and a separate new owner action. `stage != settled` is not
enough.

## Canonical content and disclosure

The canonical campaign content contains:

- schema/protocol versions and frozen protocol/answer-key hashes;
- provider and pinned model;
- instruction and schema SHA-256;
- output-token cap;
- frozen task order;
- exact task records: goal, question, current/historical URL, SHA-256, excerpt;
- frozen A/B call order;
- one cell per call index with content hash, reserved tokens and conservative
  micro-USD reservation.

The server recomputes the digest and the instruction/schema hashes. The
owner-facing manifest is derived from this content; a divergent client manifest
is rejected. The panel renders the canonical content plus a server-derived
disclosure with the actual instruction text and response schema. The approval
digest is computed over the same content. Dispatch compares the actual payload
field-for-field with the same cell.

The approval/display surface exposes research content, not blinded A/B answers.
The blinded rating surface remains separate. If the same owner performs approval
and rating, that procedural overlap is documented as a limitation, not treated
as cryptographic separation.

## Failure and liability

| Outcome | Campaign | Liability |
|---|---|---|
| `reserved_never_dispatched` | may remain unblocked only if no cancellation/fatal event | zero |
| `dispatch_possibly_started` without confirmed settlement | blocked | full reservation |
| settled response, validated/rejected | may progress if allowlisted | recorded usage/conservative |
| timeout, cancellation, authorization, provider, transport, malformed response | blocked | full reservation once possibly started |
| evidence quotation rejection after settled response | rejected cell, allowlisted | settled |
| unexpected exception | blocked | full reservation once possibly started |

No ambiguous attempt is automatically replayed. Missing output is not success.

## Owner boundary

Real approval still requires the authenticated owner interface, explicit human
attestation and a separate stage action. No local approval file can manufacture
authority. This milestone creates no real approval, uses no live credential and
performs no Meta inference.
