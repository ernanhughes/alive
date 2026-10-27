# ALIVE cognitive protocol v1

`CognitiveEnvelope` is a Pydantic contract with schema version, message ID, investigation ID, sender/recipient role, type, content, timestamp and optional model invocation ID. Types are observation, hypothesis, proposal, critique, evidence, decision, result, evaluation and abstention. Significant envelopes are persisted in `cognitive_messages`; their events preserve the investigation correlation ID.

Model output uses `RoleOutput` with forbidden extra fields and explicit bounds:

- Summary: at most 1,500 characters.
- At most four claims, each with exact subject, predicate, value and evidence reference IDs.
- At most two action proposals: `record_analysis`, `lab_draft`, `external_message`.
- At most six criticisms and six uncertainties.
- Recommendation: proceed, investigate, revise or abstain.
- Confidence: 0–1.

All native Meta structured responses are revalidated locally. Citations must resolve to supplied source IDs, memory IDs or triggering event IDs. An unknown reference or malformed schema fails the investigation; it never becomes a Governor decision. Invalid visible outputs are retained in redacted form where available. Zero automatic correction/retry attempts is the current policy. Failures, partial evidence and charged usage remain inspectable.

Role specification version **2** is distinct from protocol schema version **1**. Versioned prompts and actual model inputs/outputs are stored per runtime invocation. The benchmark also records prompts, inputs, outputs, dataset hash, usage and latency. Private model reasoning is neither requested nor exposed; reported reasoning-token counts are usage metadata only.

The API's authenticated `GET /api/v1/cognition/investigations/{id}` returns the snapshot, transition history, messages, invocations, actions and experiences. The event stream reports real state transitions and references; the dashboard fetches the persisted trace. This protocol is purpose-built for ALIVE and is not claimed to implement another project's language architecture.
