# ALIVE-14-R5 - Approval and dispatch boundary

Status: **REAL_PILOT_BLOCKED**. This document defines the security invariants and
the implementation boundary. It is not an owner approval.

## Invariants

1. **Approval:** every paid dispatch corresponds to a currently active,
   unsuperseded and unrevoked server approval for the campaign, run and stage.
2. **Content:** the actual outbound request is the immutable server-approved
   content. Local JSON cannot change question, excerpts, URLs, hashes, goal,
   instructions, schema, provider, model, mode, output cap or call order.
3. **Stage:** stage 1 authorises exactly two calls; stage 2 is a separate
   approval for the remaining sixteen calls after durable stage-1 technical
   eligibility. Neither stage can be silently promoted.
4. **Failure:** a fatal provider, timeout, cancellation, authorization or
   unexpected error prevents new calls until a deliberate authorised recovery.
   Ambiguous attempts are never automatically replayed.
5. **Budget:** the effective limit is
   `min(frozen protocol ceiling, owner-approved USD, runtime USD cap)`.
   The wider $5 project budget does not relax the $0.45 campaign ceiling.

## Canonical campaign content

The server stores and validates:

```text
schema_version, protocol_version, protocol_sha256, answer_key_sha256,
provider, model, analysis_mode, instructions_sha256, schema_sha256,
max_output_tokens, task_order, tasks[], call_order[], cells[]
```

Each `cells[]` entry binds a stable `call_index`, task, condition, exact goal,
question, current/historical URL and SHA-256, exact excerpts, a cell content
hash, reserved tokens and conservative micro-USD reservation. The server
recomputes the campaign digest from this content; it does not trust a
client-supplied digest. Task/cell counts, ordering, cell hashes, stage ranges,
stage token/USD totals and campaign caps must agree.

Database UUIDs (snapshot, memory, goal, grant) are deliberately excluded from
the content digest because they do not change what the model sees; the server
still verifies that the actual snapshot/memory content matches the immutable
task record.

## Stage contracts

| Stage | Call indices | Calls | Reserved tokens | Max liability |
|---|---:|---:|---:|---:|
| 1 | 0-1 | 2 | 10,345 | $0.043967 |
| 2 | 2-17 | cumulative 18 | 92,148 | $0.391635 |
| Campaign ceiling | 0-17 | 18 | — | $0.45 |

Stage 2 approval is rejected unless both stage-1 cells have durable terminal
attempts, no campaign-fatal error occurred, no unresolved dispatch remains, and
at least one stage-1 result validated. Stage 2 cannot dispatch an index outside
2-17. Stage 1 cannot dispatch an index outside 0-1. A consumed cell cannot be
attempted again.

## Per-dispatch barrier

For every experiment cell the backend:

1. resolves the campaign and approval from its own database;
2. checks approval status exactly `active`, campaign/run/protocol identity,
   stage and call index;
3. checks the cell is the next frozen call-order entry and has not been
   attempted;
4. checks stage-2 eligibility when applicable;
5. compares the actual payload field-for-field with the immutable task record,
   including goal, question, excerpts, URLs, hashes, provider, model, analysis
   mode, instruction/schema hashes and output cap;
6. revalidates the source grant, snapshot and historical memory;
7. commits the dispatch-start marker in the same lock/transaction ordering
   used by revocation and supersession.

The linearisation point is the commit of the dispatch-start transaction. A
revocation or supersession committed before it prevents transmission. If the
marker commits first, the call is possibly in flight, cannot be recalled, and
retains settlement and conservative liability. Revocation prevents all later
cells.

## Failure policy

Campaign-fatal: raw `TimeoutError`, `asyncio.timeout` expiry, cancellation
during/after dispatch authorization, permission/manifest/stage/source mismatch,
authentication, access denied, invalid request/schema, quota, rate limit,
provider/server failure, transport error, malformed response with uncertain
settlement, ambiguous settlement and unexpected dispatch exceptions.

Continuation allowlist: evidence quotation validation failure, semantically
insufficient evidence, and permitted structured-content rejection after a
settled provider response. These are recorded as rejected/abstained cells; they
do not authorize a replay.

Liability: `reserved_never_dispatched` settles at zero; a possibly started or
ambiguous attempt retains the full conservative reservation; confirmed usage is
recorded conservatively; no ambiguous attempt is automatically replayed.

## Owner approval boundary

The native panel displays the immutable digest, complete manifest, provider/
model, stage definition, caps, no-retry policy and active/revoked/superseded
status. Real approval requires explicit human attestation and an authenticated
owner-channel action. A local file cannot manufacture authority. This
implementation does not create a real approval, use a live API key or dispatch
Meta traffic.
