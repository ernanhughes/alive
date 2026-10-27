# ALIVE-04 — The Living Experience

ALIVE-04 makes a bounded feedback loop visible: observe a controlled Chrome page, retrieve prior
experience, predict action utility, choose, act within the Governor, synthesize evidence through
Meta, receive browser-observed feedback, and update a durable empirical decision policy.

## Qualified integration baseline

P2 (`f257cbc`) and P3 (`930fb23`) were published with their histories and evidence preserved.
The owner's simulator/diagnostic acceptance was PASS_WITH_LIMITATIONS. Before integration,
76 backend tests, four frontend tests, five browser tests and the production build passed;
all prior archive checksums verified. Local integration `3719cf461e839c6af8aee3681725f43bd265d74d`
combines origin/main `a060a6c` with those qualified branches. Its file contents match the tested
P3 branch. No main merge or forced history rewrite was performed. ALIVE-04 is a separate branch.

## Two predetermined encounters

The local research habitat displays `Aster endurance_hours 32`, plus a visible source-replacement
history event. A permitted `#retrieve` click reveals a synthetic current instrument reading of
20 hours. An end-of-episode `#feedback-button` click publishes the fixture's measurement and
task feedback independently of the model conclusion. Hidden DOM text is excluded from safe
browser observations until the relevant click. The fixture is inspectable by its authors;
this is a live integration demonstration, not a blinded generalization benchmark.

The second encounter has the same claim/history feature projection. Episode/session identifiers
are excluded from that projection. The policy cannot use the episode number to change its action.

The decision policy stores outcome counts and sums for each action and exact context. It chooses
the action with the largest observed mean; untried actions have a declared zero prior, and ties
prefer lower-resource monitoring. A cold policy therefore monitors. If feedback reports that
the goal remained unresolved, monitoring receives -0.5 synthetic utility. The next action favors
the still-untried retrieval option. Resolving the goal with current evidence yields +1, less
0.15 retrieval resource cost. These are designed utility units, not money or provider costs.

Meta does **not** choose the action. The policy choice and original-policy counterfactual are
persisted before the Meta call. The existing Proposer role, pinned to `muse-spark-1.3`, summarizes
only the observed evidence. Without current instrument evidence it should safely abstain; after
retrieval it can report the supported current measurement and compare it with the page claim.
Factual abstention and unresolved task utility are separate: the first encounter need not
contain a wrong factual answer for its action to have been unproductive.
Factual support and conclusion-contract acceptance are also measured separately: a supported
measurement with an unnecessary `investigate` recommendation is not labeled a wrong fact.
Factual support compares the model's claim with the value of the source it cites. Goal
resolution additionally requires the published end-of-episode feedback to corroborate that
source; feedback cannot make a claim factual when it contradicts the cited instrument reading.

## Persistence and causal evidence

`living_policies`, `living_journeys` and `living_transitions` are explicit migration-0005 tables.
Relevant past transitions are retrieved by exact instance/context and included as historical
context, never as current verification. Controlled-fixture and live-Meta contexts are separated,
so mock feedback cannot train the live action values. A normal Memory record preserves the observed
experience. The transition, feedback, policy update, memory and journey advancement commit in
one transaction. Before/after hashes and policy versions identify the actual update.

A fresh journey snapshots the existing policy; it never resets learning to create a favorable
demo. A warm instance may already retrieve in both encounters. The UI reports that honestly.
For the cold qualification, restart the backend after encounter one and verify identity, policy
hash, prior transition and ready state before explicitly advancing encounter two. No model call
or browser action auto-resumes after a restart. Interrupted calls retain conservative charges;
interrupted episodes cannot be replayed through the advance endpoint.

The causal check compares the original snapshot and the updated policy on the **same** second
state. If the original still chooses monitor and the learned policy chooses retrieve, with
the first feedback transition as provenance, the action difference is not model sampling noise.
A stronger frozen visible-history rule would retrieve from the first encounter. The learner
demonstrates feedback-driven change and can catch up to that rule; it does not outperform it.

## Permissions and limits

The owner grants only observation and public-evidence clicks in the exact local controlled
habitat. No arbitrary URL, selector, external message or model-proposed tool is accepted. The
Browser's origin and DOM operation checks apply. The deterministic Governor checks per-episode
tool limits, request/investigation tokens, session/experiment budgets and persisted reservations.
A journey is capped at two model calls, 40,000 charged tokens, six browser operations and a
$0.15 conservative application rate-card ceiling. No automatic model retries. Each episode has
the configured wall deadline. Paid usage is recorded even if validation or execution fails.

Living work and autonomous cognition/experiments cannot run concurrently. Budget/session resets
are rejected while a journey is active. Stop & revoke cancels the worker and prohibits further
advance; global Stop also stops living work. An idle explicitly authorized next step survives
restart but requires a new advance request. The inference path rechecks the persisted grant
before reserving tokens. A journey interrupted by a backend restart has its grant revoked,
outstanding reservations settled conservatively, and cannot be replayed. Browser sessions are
closed after each episode.

## Use and qualification

Open the **Living** tab in the dashboard. Choose Live Meta or a clearly labeled controlled
fixture, grant the local-habitat scope and begin. Inspect the first consequence, then select
**Face the related situation**. The loop, observed DOM, recalled experience and its prior
outcome, pre-action values, Governor-permitted operations, Meta summary, independent feedback,
factual support, feedback corroboration and policy update are shown together. Audit details
expose the actual model ledger and matching state/policy hashes.

```powershell
./scripts/dev.ps1
uv run python -m scripts.living04 first
./scripts/stop.ps1
./scripts/dev.ps1
uv run python -m scripts.living04 second
```

The live qualifier refuses to overwrite its plan or manufacture a cold policy. It records the
first result before restart and verifies persistence before the second. It never clears prior
experience or automatically repeats a failed paid run. Tests use isolated database fixtures and
explicitly empty provider credentials; native Chrome/Meta qualification is separate. Interim
controlled regression evidence for the OpenCode handoff is archived in
`archives/ALIVE-04-INTERIM`; it is not a native requalification and does not replace the original
archive.

This milestone uses controlled synthetic facts and rewards, exact-context memory and a tiny
empirical policy. It is not a learned semantic history extractor, open-web autonomous agent,
MR.Q result or proof of broad self-improvement. Predictive representation learners remain
experimental and are not a runtime dependency. Published rates are estimates, not confirmed
billing: [Meta pricing](https://dev.meta.ai/docs/pricing-rate-limits), checked 27 October 2026.
