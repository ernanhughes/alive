# ALIVE-PI-02C — Complete Visual Workflow Observatory

Base: `b0b3e40ab51e2ea4f482a20767f9bad8b4491765`, verified merged #71.
Final head and exact-head CI links are recorded in the draft PR description to avoid
a documentation-only commit restarting qualification. No merge is authorized here.

## Delivered behavior

The existing dashboard has a first-class Workflows section with workflow filtering,
explicit version selection, immutable definition/hash inspection and bounded owned
run history. The native React/SVG graph uses the existing graph projection. Actual
dependency edges, stage IDs and states drive both the graph and keyboard-accessible
stage list. No renderer dependency, external CDN or executable graph syntax is used.

The owner's Stephanie example informed the run header, selectable stages and tabs:
Overview, Stage details, Evidence & result, Recorded events and Comparison. The
implementation uses ALIVE's React/auth/style stack and actual DAG dependencies.
There is no raw-HTML report rendering, prompt dump, script URL or unrelated record.

Stage inspection distinguishes stable stage ID from attempt UUID; displays exact
definition, operation, dependencies, timing, timeout, input/output references/hashes,
authorization reference, usage, error, uncertainty and validation. Unrestricted raw
inputs/prompts are not exposed by these contracts. That absence is not filled with
fabricated content. Stage output content is available only for the existing retained,
hash-checked result artifact; other outputs remain opaque references and hashes.

Actual Pi receipts show requested upstream model separately from the locally reported
Pi alias, reservation, request effects, settlement, cleanup, usage and unknown cost.
During execution, the stage's final Pi pointer may not yet exist: inspection derives
an attachment from the actual unique Pi reservation plus exact invocation/run/attempt/
inquiry and instance checks. This is a projection of existing records, not a synthetic
receipt. A genuine paused dispatch is covered by the backend integration test.

Retained results render bounded structured fields and escaped text, with a bounded
raw-record disclosure. Parent failure/cancellation/UNKNOWN remains visible above the
artifact. Execution completion, contract/structure, reference identity, semantic
verification and independent feedback stay separate. Current artifacts have no linked
Intelligence episode and explicitly no independent feedback; the viewer says so.

Run comparison uses each execution's own version/hash/edges and stable stage IDs.
It compares actual status, stage durations, invocation counts, nullable usage/cost,
validation, uncertainty and output references. There is no quality score.

## Read model and historical integrity

Three authenticated GET projections were added:

| Route suffix under workflow-runs/{run_id} | Read contract |
| --- | --- |
| inspection | Owned run, exact hash-checked definition and graph, validated Pi attachments |
| timeline?after=&limit= | Instance/run-scoped allow-listed workflow and attached Pi events; monotonic sequence cursor, max 500/page |
| stages/{attempt_id}/pi-receipt | Exact owned stage/invocation/Pi attachment, using existing Pi receipt formatter; at most 2,000 request rows |

Definition name/version/schema/hash, stage membership/type/operation and all receipt
associations are checked server-side. Result events must match their stored stage
output reference and hash. Opened events must match run definition identity. Corrupt
or foreign history refuses. Timeline payloads are never returned: only fixed event
identity/time/output-reference/status fields. App wiring supplies the existing pure
receipt formatter; workflow imports remain limited to Pi record models.

Recorded-event replay is local and effect-free. It binds run, definition and attempts,
uses persisted sequence order and advances only states justified by recorded events.
Some reservation and interrupted-stage transitions were never retained. The API marks
complete_transition_history=false; UI explicitly separates latest snapshot facts from
event-derived state and withholds later snapshot details while replaying. No new
event store, fabricated timestamps, inferred transition history or execution path exists.

Live observation polls only visible nonterminal selections, one cycle in flight,
initially two seconds, backing off to at most 30 seconds and stopping after five
consecutive failures. Terminal/replay/unmount stops polling. Token/run changes abort
and invalidate reads. A previous snapshot after a transient failure is marked stale.
Timeline pages are bounded and loaded explicitly; run history is explicitly latest
200, not a claim of unlimited pagination. Manual refresh reloads current standing.

Extension navigation uses existing allowed loopback backends and validates the same
workflow/version/run/stage grammar as the API. It carries no token/context/action and
adds no permission. Dashboard authentication is still required. Contradictory run and
version links refuse. The Workflows page has no runtime/action controls.

## Reproducible demonstrations

The trusted CLI harness is scripts/workflow_observatory_demo.py. It is never imported
by app startup or exposed as an execution route. It uses real pinned Pi 1.4.0 and a
throwaway loopback HTTP provider, with synthetic lab evidence and explicit owner grants.

Six persisted runs: completed research v2; completed v3 with a different declared edge;
completed three-stage deterministic comparison; goal cancelled through the real route
before execution (FAILED, zero requests); post-dispatch interruption (UNKNOWN, one
request); and finalization interrupted after the retained artifact (FAILED, artifact
preserved). The finalization hook exists only in this CLI fixture and is restored.

Expected seed facts: four scripted requests, four invocations, four Pi runs, six
workflow runs, four workflow-result artifacts, seven total CognitiveMessages and zero
Intelligence learning updates. Deterministic/cancel-before-execution runs add no model
invocation. Restart/read/replay verification checks every retained artifact hash and
all these counts. Background heartbeat/runtime bookkeeping is not claimed absent.

```powershell
python -m scripts.workflow_observatory_demo --directory C:\temp\pi02c-new --seed
python -m scripts.workflow_observatory_demo --directory C:\temp\pi02c-new --serve 8018
# In dashboard/, using only the disposable harness credential:
$env:ALIVE_BASE_URL='http://127.0.0.1:8018'
$env:ALIVE_API_TOKEN='integration-token-0123456789-0123456789'
$env:ALIVE_OBSERVATORY_MANIFEST='C:\temp\pi02c-new\manifest.json'
npx playwright test e2e/workflows.spec.ts --reporter=line
```

For an explicitly disposable PostgreSQL database, add --database-url to seeding and
verification. Migrations run through existing head 0010. --verify-url accepts only a
plain loopback HTTP origin and compares SELECT-only DB counts around actual GET reads,
without starting a second host or acquiring another runtime lease. The Docker image
uses the unchanged production Dockerfile, LF Git-exported source, standard entrypoint,
PostgreSQL and no paid credential. The seed harness is mounted only for qualification.

## Qualification and limits

Focused new backend tests: 14 passing cases. Broader workflow contract suite initially
found two integration failures: the previous nine-route count and a forbidden direct
Pi API import. Route coverage now explicitly includes all 12 GET routes; formatter
injection preserves the import boundary. Both fixes passed targeted regression tests.
No assertion was weakened to admit a write route or provider dependency.

Dashboard: 31 unit tests pass and production build passes. Browser E2E passes against
the real persisted SQLite and Docker/PostgreSQL history, covering authentication,
stage/Pi/artifact navigation, replay, comparison, distinct graphs, failure/UNKNOWN,
reload, zero non-GET feature requests and 390-pixel mobile overflow. Screenshots and
hash manifests are in validation/pi02c; large logs and disposable DBs stay outside Git.
Existing extension checks pass. Docker build/smoke and PostgreSQL restart/read evidence
are recorded in the bounded qualification receipt. Full backend Windows/Linux results
come from exact-head CI, not from collection or a subset. No duplicate local full run.

R3 independent audit: GO, no PI-02C blocker. Preserved audit input is included for
provenance; its full-suite placeholder is not a pass receipt. Its LOW completed-goal
and extra-source-ID test-strength findings are separate follow-ups, with no production
defect established. Role-contract and unsupported-worker watch items remain deferred.

PI-02C requires its own independent review. No authorization/Governor/Pi dispatch/
recovery/provider-routing change, migration, dependency, paid inference, automatic
merge, PI-03 or Bespoke selector is included. See the independent-review handoff and
Bespoke readiness report for the next qualification boundaries.

A final frontend concurrency audit added immediate cancellation of timeline pages on
run/hash/replay/refresh changes and an explicit selected-run identity check. A delayed
replay-page regression pins this boundary. The corrected Docker source was rebuilt,
restarted against the same persisted database and passed browser/count verification
again, with no new provider request. Earlier superseded CI runs were cancelled; final
qualification is pinned to the corrected head reported in the PR.
