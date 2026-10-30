# PI-02B execution architecture

Baseline: `4fed829aa57245b93796e98808818fcb0aa58e8f`, including merged INT-02.
The engine executes stored, active, hash-verified definitions in deterministic
topological order. It runs one stage at a time. Definition selection, owner
authorization, Governor admission and provider dispatch remain separate operations.

## Operation and authority matrix

Registry bindings remain descriptive metadata. No binding string is imported or
invoked dynamically. `ADAPTERS` is the literal server-owned execution map; the
operation inspection API distinguishes `available` metadata from `executable`.

| Operation | Actual existing interface and constraints | PI-02B adapter |
| --- | --- | --- |
| `context.prepare` | `Cognition.world_state(run_id)` charges a tool, indexes memory, retrieves context, reads goals/lab state and persists a snapshot. It is not a pure independent context function. | Narrow read-only preparation of the exact bounded context event approved by the owner. No ambient memory, broad goal read or indexing. New procedure uses version 2 rather than changing version 1. |
| `memory.retrieve` | `MemoryService.retrieve(query, mode="text", top_k=5, exclude_event=None, memory_types=None)` requires existing provenance/access/type selection and may emit retrieval events. | Not executable. A future adapter must bind explicit memory scope and consent. |
| `cognition.role` | `Cognition.call_role(run_id, role, context)` owns reservation, accounting, `ModelGateway`, Pi transport, output/reference validation and cancellation settlement. | Same service with optional stage ceiling, caller ledger and workflow claim. Stage/invocation linkage commits with the existing reservation, before Pi can start. No gateway is constructed by a workflow adapter. |
| `evidence.validate_references` | `society.validate_references(RoleOutput, context)` is a pure admitted-reference identity check. | Typed role/context check over exactly submitted evidence; retained interpretation stays semantically unverified. |
| `evidence.evaluate` | `society.evaluate(observed, proposed, sources)` performs deterministic exact controlled-source comparisons. | Scope-bound comparison of approved claims/sources. Its result explicitly says controlled sources only, not general-world truth. |
| `evidence.qualify` | `EvidenceQualifier.qualify(QualificationRequest)` depends on research/web goals, current grants, retained captures, withdrawal and history permissions. | Not executable. A callable signature is not independent authorization. |
| `evidence.record` | No safe standalone implementation; `Cognition.finish()` settles an investigation and its reservation/experience. | Remains unavailable. No model opinion is inserted as independently observed evidence. |
| `approval.request` | Existing `ExperimentApprovals` is experiment-specific. | Remains unavailable; no automatic approval and no public write/start API. |
| `result.record` | Reuses existing `CognitiveMessage` result persistence and `Kernel.add_event` in an existing database transaction. | New narrow operation. Requires the exact result of a declared, completed validation dependency. Retains a bounded owner-internal artifact, never independent feedback. Artifact, result event and stage completion commit together. |

## Ownership and data flow

The trusted host starts cognition under existing ALIVE conventions and reserves
an inquiry through `Cognition.workflow_inquiry()`. This uses the unchanged auction
admission and budgets, transfers the inquiry to INVESTIGATING while holding the
existing command lock, and settles unused reservations on every host exit. The
runner accepts a fresh caller-owned inquiry; it refuses a live legacy cognition
worker or an inquiry that already contains model calls/context. No second admission
algorithm was copied. Existing cognition behavior retains its original call path.

The owner separately supplies an existing protected event with source
`workflow-owner` and type `workflow.execution.authorized`. `Grant` binds principal,
goal, inquiry, definition ID/hash, context event/hash, workflow inputs, permitted
operations, configuration hash, role/model/prompt/schema contract, outbound consent,
budgets, expiry and idempotency identity. Principal strings/hashes are audit data,
not authentication. Authority comes from the trusted host custody boundary; the
public observation schema cannot mint these source/type combinations. There is no
HTTP authorization factory or execution initiation endpoint.

`WorkflowRunner.start(grant_id)` validates the exact grant and creates the PI-02A
run/stage rows plus one execution record in a caller-owned transaction. The grant
and inquiry each have a durable unique consumer. A unique instance slot permits
one nonterminal executable run per instance. `execute(run_id)` takes an atomic
database PENDING-to-RUNNING claim with a fresh private owner identity; each stage
also takes a conditional claim. Independent connection pools and locks cannot
produce two owners or repeat a single-call Pi stage. No lock or database transaction
spans the model wait.

At model reservation the existing cognition service verifies the exact claimed
stage, current grant/configuration, context, model, operation and ceiling. It stores
the new ModelInvocation reference on the stage in that same transaction. Its
existing gateway then selects Pi and retains PI-01B's reservation, egress, request
identity, process cleanup, conservative charging and settlement behavior.

The host installs a workflow guard on the **existing Pi dispatch fence**. Only
workflow-tagged reservations require it; missing guard fails closed. Immediately
before an admitted request becomes `dispatched`, the guard revalidates current
authority, expiry, data scope and stage/invocation binding in that transaction.
Owner grant/context rows are locked on PostgreSQL. `context.revoke()` locks the
same grant row before recording owner revocation, so acknowledged revocation before
the dispatch marker prevents a provider request. A request already marked dispatched
can have an unknown outcome and cannot be unsent; call `runner.cancel()` to interrupt
its owner and preserve the authoritative Pi receipt. Trusted custody writers must
use this coordination protocol rather than bypassing it with raw SQL.

## Persistence, recovery and reads

Migration `0010` follows actual head `0009`. It adds only `workflow_executions`
(grant/inquiry/owner/instance-slot/deadline metadata) and the deferred stage-to-Pi
foreign key. Results reuse existing events and CognitiveMessages, not a new general
artifact service. Old dangling PI-02A Pi references require explicit reconciliation;
the migration refuses before DDL and never rewrites them into real receipts.

Each result event has exact run/stage identity and an output hash. The final artifact
also retains producer, definition/input hashes, assessment, schema, owner-internal
classification, time and evidence references. Record IDs are deterministic per
stage; message, event and success are one transaction. Artifact reads verify their
linkage/hash and expose an explicit allow-list, without raw context, prompts or
credentials. Historical output remains historical, with source withdrawal visible.

Workflow completion and failure settle cognition in the **same transaction** as
the terminal workflow state and released instance slot. `Cognition.finish_in_session`
is extracted from the existing `finish` implementation, which still wraps it for
old callers. F-002 invocation settlement remains under its original outer handler.

App startup first recovers cognition, then Pi, then executable workflows. Only runs
with execution records are reconciled; INT-02's pending reference-only workflows
are untouched. Recovery never resumes a stage. Completed stages/artifacts remain;
unfinished model effects become UNKNOWN when receipts show possible dispatch or
unsettled completion. Never-sent attempts cancel/fail without fictional success.
No unknown request is retried. Replay is GET/read only; rerun needs a new owner grant,
run identity, admitted inquiry and provider reservation.

## Bounds and limitations

PI-02A bounds definition bytes, stage count, references and one attempt per stage.
The owner may narrow its model-call, total output-token and wall ceilings; it cannot
widen the immutable definition. Cognition separately enforces request/inquiry/session
budgets and conservatively charges unknown usage. Stage timeouts and the absolute
run deadline cover execution. Retained context, output and artifacts are capped at
64 KiB; workflow model text is rejected before the cognition ledger can retain an
oversized response. Stage outputs must satisfy the declared strict field/type schema.
Workflow events have fixed server-controlled counts per bounded stage; PI-01B
separately caps model event count/bytes. No model-directed stages, automatic retries,
fallback models or unbounded event loops exist. Cost remains nullable, not assumed zero.

Only stop-on-failure procedures execute in this slice. Optional skip policies,
general approval gates, independent memory retrieval and live capture qualification
are explicitly refused rather than partially interpreted. Host adapters must
cooperate with cancellation; database availability and inherited Pi process containment
limitations still apply. PostgreSQL claims support independent workers, while the
existing kernel lease remains the owner of application startup/recovery. Recovery
must run quiescently under that host lease, not as a competing live worker.

## INT-02 and future Bespoke procedures

Artifacts expose stable workflow/stage/message/evidence identities and a nullable
Intelligence episode reference. This demonstration has no Intelligence episode,
trusted feedback or learning success to attach, so those fields remain explicitly
None/False. A future separately admitted adapter can reference the retained artifact
in a proposal, then preserve authorized decision, independent observed outcome,
feedback and revisit. Model text never becomes that outcome. Active policies and
the INT-02 learning algorithm are unchanged.

A future Bespoke selector supplies a selected immutable workflow identity and
bounded approved context reference to the **host authorization boundary**. Selection
does not authorize execution. Recipes reference/compile to this existing workflow
DSL; no ContextEnvelope, TaskOpportunity, router, planner or competing recipe language
is implemented. The same runner executes `research-review` v2 (four stages, real Pi,
citation validation) and `source-comparison` v1 (three stages, controlled comparison,
zero model calls) with different graphs/operations/contracts and no workflow-name branch.
