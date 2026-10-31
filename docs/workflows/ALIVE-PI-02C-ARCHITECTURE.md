# PI-02C architecture and contract inventory

Baseline: `b0b3e40ab51e2ea4f482a20767f9bad8b4491765`, verified from origin/main
on 2026-10-31. PR #71 is merged; merge is not independent approval. R3 audit
qualification remains a merge dependency. No execution-security correction belongs
in this branch. The owner authorizes concurrent observatory implementation.

The preparation document was read in `C:/Projects/alive-pi02c-prep`; its old closed
implementation gate is superseded by this assignment. That worktree is unchanged.

## Reuse and read contracts

Reuse React/TypeScript, existing navigation, shared bearer request helper, styles,
Vitest and Playwright. No new application, auth scheme, event bus or dependency.
Definitions are global; run, artifact and Pi history belong to the current instance.

| Existing GET | Contract / use |
| --- | --- |
| workflow-operations | Registry availability and executable binding, not authority |
| workflows; workflows/{name} | Catalogue and version metadata |
| workflows/{name}/versions/{version} | Exact immutable content and rederived integrity |
| workflows/{name}/versions/{version}/graph | Actual declared nodes/dependencies |
| workflow-runs?workflow=&limit= | Bounded owned history, latest 50, at most 200 |
| workflow-runs/{id}; .../stages | Parent state and stable stage + attempt UUIDs |
| .../artifacts/{stable-stage-id} | Hash-checked result with parent state, provenance and separate validation |
| pi/runs/{id} | Existing owned receipt; requested upstream differs from observed alias |

Read-model gaps: add an owned, bounded, cursor-based durable event projection and
an owned stage-to-receipt attachment projection. Validate definition ID/name/version/
hash, stage membership, invocation inquiry and Pi reservation binding server-side.
Never project raw workflow.stage.result payloads or prompts into the event timeline.
Existing artifact integrity checks remain the output-content authority.

## Historical truth

Event.sequence_number supplies durable ordering, not wall-clock sort. Workflow run
opened, execution claimed, stage claimed/result and execution ended/completed events
exist. Pi events exist under their own correlation IDs. Some stage abandonment and
reservation transitions are not separate workflow events. A safe projection can
include real linked Pi events, but cannot recover transitions never recorded.

The viewer must call this **Recorded events**, explicitly incomplete, and keep the
latest stage snapshot separate. Event replay derives only states justified by events
up to the selected cursor; absent transitions say Not recorded. It must never
back-project final row values into earlier times. Reads and replay add no writes,
reservations, provider requests, artifacts or learning updates. Restart reloads the
same durable rows. No migration or duplicate event store is needed.

## Rendering and state ownership

Choose native React/SVG: maximum 32 nodes and eight dependencies each, no editing.
Topological columns with deterministic row placement are sufficient. React text
escaping avoids graph-language directives and raw SVG/HTML injection. An accessible
button/list view shares selection with the SVG. No rendering dependency is needed.

Use cohesive catalogue, graph, stage inspector, receipt, artifact, timeline/replay
and comparison components. Typed calls use the shared authenticated helper with
AbortSignal. Selection/token changes abort requests and invalidate old generations.
Poll only the visible active run, one cycle at a time, bounded backoff; stop for
terminal/replay/unmount. Exact run definition is loaded, never silently latest.

Comparison loads each run's own graph/hash and compares stable stage IDs. Costs and
usage aggregate conservatively; null remains unknown. No quality score. Execution,
contract, reference identity, semantic verification and feedback remain separate.

Bounded deep links carry workflow/version/run/stage identifiers only, never token,
context or action. Extension navigation reuses existing dashboard origin settings.
All observatory network traffic is GET. No Run/Approve/Cancel controls are added.

## Qualification

Targeted backend tests validate authentication, ownership, linked identity, corrupt
records, chronology, bounds and SELECT-only effects. Frontend tests cover distinct
graphs, escaping, replay, comparison, missing facts and cancellation/stale responses.
Real Pi/scripted provider and deterministic executions feed browser demonstrations;
restart replay compares durable counts before/after. Full backend Windows/Linux CI
is the release gate, not a per-UI-edit loop. Docker/PostgreSQL and existing extension,
Pi and Intelligence regressions remain required. Final results and limitations are
recorded separately from this initial contract inventory.
