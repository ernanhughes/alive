# PI-02B independent review handoff

Implementation commit: `4de4f86c77fee7567b320965cb1c3b532ba4fa24`.
Base: `4fed829aa57245b93796e98808818fcb0aa58e8f` (merged INT-02).
Read the architecture and report alongside the diff. This document requests independent
review; it is not a claim that a separate reviewer has approved the implementation.

## Reconstruct the result

1. Install locked Python dependencies and `npm ci --ignore-scripts` in `pi-runtime`.
2. Run `python -B -m scripts.workflows_execute_check` against disposable SQLite.
3. Repeat with `--database-url postgresql+asyncpg://...` on a disposable database.
   Never aim this fixture writer at production. It starts the actual pinned Pi and
   existing metered egress against a local scripted HTTP provider, using fake credentials.
4. Inspect the two retained definitions, 4/3 stage graphs, single Pi receipt,
   reservation/invocation/request linkage, cleanup and restart/replay assertions.
5. Run `python -B -m scripts.workflows_execution_mutations`. Every baseline must pass;
   every mutation must fail a relevant assertion, not setup or collection.
6. Run the workflow, cognition, Pi, gateway, recovery and migration tests, then the
   full backend suite. Saved qualification receipts are under `validation/pi02b`.

## Review the trust boundaries

| Question | Source and concrete adversarial probe |
| --- | --- |
| Can a definition, bearer or model authorize execution? | `context.Grant`, `authorized`, `runner.start`; admission tests reject forged source/owner/operation/budget/definition. Public routes are GET only. |
| Can arbitrary Python execute? | `adapters.ADAPTERS` literal map and `runner.executable`; operation mutation, foundation invalid binding/DAG tests. Registry metadata is never imported. |
| Can a worker double dispatch? | `runner.execute` SQL conditional claim precedes reads; unique grant/inquiry/slot, stage claim; real fixture races three independent connection pools. |
| Can stale authority survive reservation? | `cognition._invoke_role`, `context.model_claim`, `PiEgress._dispatch`, `runner.authorize_dispatch`; actual Pi revocation-after-reservation test proves zero upstream dispatch. PostgreSQL custody writers must use the locking revoke/withdraw helpers. |
| Can one stage borrow another receipt? | Stage/invocation linkage commits at reservation; `_complete` checks Pi owner, state, cleanup, request/response/usage linkage. Synthetic receipt rejection tests are explicitly synthetic; qualification success uses real Pi. |
| Can model text become truth? | `adapters.references`, `record`, `runner.artifact_view`; record rejects model-supplied validation booleans and undeclared dependencies. Reference validity remains semantic unverified. |
| Is F-002 preserved at every exit? | `workflow_inquiry`, shared `finish_in_session`, `_finish`, `_abandon`; cancellation before/after admission/claims/model dispatch, transaction rollback and ambiguous recovery probes. |
| Can restart repeat an effect? | Recovery classifies possible effects UNKNOWN and never resumes; replay is read-only. Mutation removes a replay guard and is killed. Actual container restart counts remain unchanged. |
| Is this a second provider client or learning loop? | Adapter calls existing Cognition only; ratchet tests reject new Meta construction. No intelligence/learning source changed. Existing INT-02 receipt resolver reads the genuine workflow stage. |

Prioritize inspecting atomicity manually: final artifact + result event + stage success,
workflow terminal + cognition settlement + instance slot release, and reservation + stage
invocation ownership. `test_workflow_transactions.py` injects rollback before artifact
commit and after a real settled Pi effect. The latter must remain UNKNOWN, charged and
unrepeated. Green tests alone cannot establish all interruption interleavings.

For any confirmed finding, provide a concrete failing scenario and exact file/line;
do not infer correctness from test counts. Check nullable cost, raw-vs-parsed receipt
limitations, quiescent host recovery and cancellation-cooperative adapter assumptions.

## Explicit limits

Only trusted-host initiation, approved finite context, sequential stop-on-failure
procedures and the literal adapters are qualified. No live memory/evidence capture
adapter, general gates/skip/retry, automatic resumption, worker framework, Bespoke
router, PI-02C UI, paid inference, independent feedback or policy promotion is added.
The active Intelligence policy and frozen research remain untouched. Model semantics
and learning performance are not demonstrated by a scripted provider.
