# Isolated Intelligence subsystem, v1

**INT-02 integration:** this document describes the preserved INT-01 pure/session API.
The separate durable fixture adapter, read-only authenticated API, migration and
restart/replay qualification are documented in
[`../../docs/validation/alive-int-02/ARCHITECTURE.md`](../../docs/validation/alive-int-02/ARCHITECTURE.md).
INT-02 does not enable model dispatch or automatic execution of proposals.

INT-02 adds a fixture-only durable integration with real workflow references and
authenticated read-only inspection. See
[`ARCHITECTURE.md`](../../docs/validation/alive-int-02/ARCHITECTURE.md) for the
canonical durable workflow, authority boundaries and production limitations.

The isolated engine coordinates authorized evidence, bounded structured interpretation,
empirical proposals, independently supplied outcomes and session-local learning.
Live reasoning and feedback are **not admitted by the durable adapter**. Nothing here executes an
action or grants permission. Importing `alive.intelligence` initializes no runtime,
provider, database, browser or predictive controller.

## Quick start

From the feature worktree, using the repository's existing Python 3.13 environment:

```powershell
$py = 'C:/Projects/alive/.venv/Scripts/python.exe'
& $py -B -m alive.intelligence.example
& $py -B -m pytest -q alive/intelligence/tests -p no:cacheprovider --confcutdir=alive/intelligence/tests
& $py -B -m ruff check --no-cache alive/intelligence
```

The example is a **controlled integration example**, not a live AI benchmark.
Its injected fixture returns a cited role response with zero tokens. Episode 1
proposes `monitor`; an independent fixture observer reports unresolved utility
`-0.5`. Only that observed feedback updates the policy. Episode 2 proposes
`retrieve`, while the frozen cold policy still proposes `monitor`. Dated history
remains historical evidence. The example records a fixture observer's reported
action, but performs no browser action or physical execution.

## Public surface

`IntelligenceEngine` is the single package-root export. Construct it with trusted
`EvidencePort`, `FeedbackVerifier` and immutable `EmpiricalPolicy` instances.
Import wire types from `contracts`, and the optional simulation adapter from
`policies.predictive`.

| API | Meaning |
| --- | --- |
| `await engine.analyze(observation, context, inference=capability)` | Admit exact evidence, validate a structured role response, then return an unexecuted masked proposal or explicit failure/abstention. |
| `engine.evaluate_feedback(proposal, feedback)` | Validate an issued proposal and independently verified completed training outcome, then atomically replace session-local policy state. |
| `await engine.revisit(observation, context, earlier_proposal=proposal, inference=capability)` | Analyze a related new episode and compare its decision with the earlier frozen policy under the new candidate mask/resources. |
| `engine.shadow_compare(adapter, simulation_state)` | Separate read-only shadow query. Its result cannot enter active ranking or feedback updates. |
| `engine.policy` | Immutable current state; caller may explicitly serialize `snapshot_json()`. No persistence occurs automatically. |

All contracts have version 1, reject extra fields, bound strings/collections and
reject nonfinite numbers. Nested values are frozen models and tuples. Use normal
validation when restoring serialized state. `model_construct` or arbitrary Python
monkeypatching is outside this in-process trust boundary.

## Authority and reasoning

No capability means **unavailable reasoning and abstention**, with no backend call.
A token string, provider name or reservation ID is insufficient. `ModelReasoner`
requires an injected `AuthorizedInvocation` object with an exact payload/scope
binding. This structural protocol is an integration contract, not authentication:
the trusted host must construct and protect the object. Never deserialize such
an object from observation text, model output or an API caller's permission flags.

The capability must enforce **the entire request**, one-use dispatch, a real
Governor reservation, owner consent, outbound-payload approval, model choice,
budget, timeout/cancellation settlement and receipts. The payload hash checks only
data identity; it is not a permission certificate. `approved_context` is an audit
label. The adapter uses the existing `StructuredRequest`, `RoleOutput` schema and
observer role instructions. It never calls `gateway_for`, a provider client or Pi.

The sole supported operation shape is `cognition.role`, because that is the only
operation registered in the inspected gateway. Existing role reservations do not
automatically authorize this workflow or payload. A separately reviewed caller
must explicitly approve the exact request (including instructions, schema, model,
1536 output-token ceiling and correlation). No production capability factory is
provided. Provider/model/invocation/receipt and usage metadata come from the trusted
capability; no model or transport is selected here.

Model actions are discarded. A model may recommend abstention, but cannot expand
the caller's candidate mask or resources. All retained model claims are explicitly
`model_opinion`; citation matching certifies neither entailment, quotation fidelity
nor independent truth. Source/document text is untrusted data. The caller must
provide bounded, nonsecret, outbound-approved excerpts and safe observation text;
this package is not a secret detector or replacement for ALIVE memory consent.

## Supported policy and feedback

The empirical bridge reuses actual `alive.living_policy.choose` and `update`.
It supports only the explicit Aster `endurance_hours` / `source_replaced` /
`resolve-current-claim` state. `monitor` and `retrieve` retain their original
observed-mean ranking, zero prior for unseen actions, and monitor-first tie order.
Candidate masking and reported affordability restrict that ranking. An unsupported
empirical action produces a typed `not_supported` error, rather than an invented
score. Risk/benefit estimates remain caller-reported metadata, not permissions or
a new reward function. Missing history is explicitly the empty tuple.

Live and controlled-fixture policies have separate origins and existing context
keys. Simulator data is unsupported by this empirical adapter. An update requires
the exact issued proposal, matching episode/goal/action, reported execution,
completed outcome, current independent measurements and a trusted verifier's exact
acceptance. Model confidence, model predictions and evaluation/development data
cannot train it. Outcomes and proposals are consumed once per engine session;
changing the outcome ID does not permit a second update. Stale policy proposals
must be analyzed again. Earlier unsupported predictions remain unknown (`None`),
while observed-mean prediction errors use the estimate saved before feedback.

The synchronous feedback preparation/commit has no await or external write. A
verifier/update failure leaves policy and deduplication state unchanged. This is
**session-local**, single-event-loop state, bounded to 256 issued episodes. It is
not thread-safe, durable or exactly-once across process restart. A new engine
starts a new idempotency domain. Production persistence must commit policy,
outcome identities and transitions together in a caller-owned transaction; it is
intentionally absent here.

Analysis has a configurable `(0, 60]` second wall deadline, no retries and no owned
background tasks. Adapters must cooperate with cancellation. The API returns a
typed `cancelled` result when cancellation is received; it does not propagate
`CancelledError`. A trusted inference capability still owns settlement when a
request times out or is cancelled. Errors expose bounded categories rather than
exception text that could contain private information.

## Predictive shadow: research only

`PredictiveShadow` accepts an explicitly supplied existing `Controller`, a canonical
parameter SHA-256 and a trusted checkpoint-qualification verifier. It deep-copies
the controller only after exact class, parameter-key, dimension, finite-value,
identity and qualification checks. It performs no checkpoint file reads, random
initialization, update, training or save. `controller_hash()` hashes ordered float64
online and target parameters under the ordering version; it is **not an NPZ file
hash**. A host must independently verify artifact provenance and bind that artifact
to this parameter hash. Qualification is checked again on every comparison.

Inputs require `alive.learning.environment/18x6/v1`, exact `FEATURES` and `ACTIONS`
ordering from `alive.learning.environment`, 18 finite numeric values and six strict
boolean mask values. No DOM/document-to-vector conversion exists. Results contain
six action-ordered Q values, the mask, chosen simulation action, predicted reward
and next observable state, checkpoint hash and `simulation_only=True`.

No qualified saved checkpoint was supplied for this milestone. The default is
`unavailable`; positive checkpoint-backed behavior remains unqualified. Tests do
not label random weights as trained. Matching/conflicting shadow fixtures test
separation from active proposals, not predictive accuracy. The historical learner
is MR.Q-inspired, not MR.Q, a semantic encoder or a planning controller. ALIVE-03-P2
did not establish a statistically conclusive predictive advantage; ALIVE-08 also
reported no advantage against its strongest empirical baseline. This subsystem
claims no live transfer, learned browser embedding, predictive superiority or
generalization benefit.

## Explicit limits

No production registration, service persistence, action execution, arbitrary-web
access, unrestricted Pi skills, model reservation creation, autonomous scheduling,
code execution, self-modification or autonomous self-improvement. No permission,
semantic truth or independent source-authenticity certificate is created by a hash
or model response. Governor, existing memory access/consent controls, dispatch ledger
and existing execution services retain their authority. See `DESIGN.md`,
`IMPLEMENTATION-REPORT.md` and `INTEGRATION-BACKLOG.md` for review and future seams.
