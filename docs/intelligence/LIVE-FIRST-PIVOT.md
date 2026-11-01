# ALIVE live-first reset — product contract (1 November 2026)

Status: **decision and implementation brief, NOT an implemented or qualified live-model feature**.
Applies immediately to PR #85 and subsequent ALIVE work. Replaces the assumption that every model call is an exceptional, separately approved research operation.

## Product principle

**ALIVE uses AI by default.** Inference is a routine computation, like search or database access. An owner should normally be able to ask a question, have ALIVE think with the configured real model, and inspect the result without an approval ceremony for every request.

**Thinking and acting have different authority.** Frequent model calls do not create tool permissions. A new external data recipient, broader data disclosure, code execution, file mutation, external publication, or irreversible action may require additional owner approval.

A deterministic selector, schema validator, policy, or script may *constrain* a model; none may masquerade as model reasoning. Existing Cognition/Living/Bespoke, governed ModelGateway/Pi, source custody, evidence provenance and persistence should be reused. Do not build a fourth intelligence orchestrator.

## Default product behavior to implement

1. **Configure once:** a clearly displayed *standing AI session/workspace authorization* selects the provider endpoint/model, trust scope (what source classifications/content may be sent), maximum calls/tokens and optional spend ceiling, expiry and revocation. Provider credentials stay server-side. This is explicit, bounded consent to a class of routine inference, not a blank cheque.
2. **Call as needed:** after that authorization, ordinary reasoning, intent interpretation, comparison, critique, and follow-up may use the approved model automatically. A new user goal does not imply a new OS CLI approval of the same destination and same approved data scope. Keep the existing Governor and the final outbound destination, token, cancellation and accounting checks.
3. **Never silently downgrade:** when live inference is unavailable, return a visible `model_unavailable`, `budget_exhausted` or `consent_required` state. Do not emit a deterministic or scripted recommendation as though the AI thought of it. An explicit, labelled offline or deterministic tool may still exist.
4. **Make model use unmistakable:** dashboard and receipts show `LIVE MODEL` or `NO MODEL CALL`, model identity, provider, call count, latency, actual usage and provenance per decision. No fabricated `live` flag: derive it from the invocation and provider response records and distinguish transport-scripted results.
5. **Keep safety as internal mechanics:** validate schemas and evidence/authorization boundaries in code, not through repetitive manual owner ceremonies. Avoid a chain of user approvals for each reasoning step.
6. **Action boundaries remain:** a model proposal never authorizes a new tool or write. Source approval for *new* sensitive data/destinations, changes to standing authority and consequential actions require explicit consent. Read-only actions inside an existing trusted scope can proceed without repeated review.
7. **Reuse learned experience:** persist actual model outputs, independently observed results and subsequent context. Learning or improvement claims require new live outcome evidence; fixture-only updates are not production learning.

## Immediate PR #85 redesign

The current PR implements `intent.interpret` with a one-call workflow but requires per-goal local approval and contains a scripted, author-constructed 9/9 interpretation evaluation. **This is integration evidence, not the desired product.** Keep the useful typed contracts, exact catalogue identities, source custody, invocation receipts, safe endpoint enforcement and replay protection. Revise the user journey and qualification contract.

### Required implementation tasks

- Build the smallest possible **standing model-use authorization** using existing owner/Governor/model settings and source operations, not an entirely new authorizer. A scope must bind effective endpoint, model, source classification, outbound content allowed, budgets, expiry/revocation and principal. Revalidate automatically at dispatch, not in a manual CLI prompt for each call.
- Wire ordinary goal entry to `intent.interpret` using this standing authorization. A previously trusted source/workspace must permit multiple successive goal interpretations in one bounded session without reapproving the model destination each time.
- Make the UI default to the live model-backed path when the owner has configured a model and scope. The choice to run a deterministic baseline should be deliberate and plainly marked.
- Preserve the distinction between **intent selected**, **procedure eligible**, **procedure executed** and **outcome verified**. The deterministic selector is a constraint/availability check, not evidence of intelligence.
- Integrate the selected read-only analysis procedure where already permitted, so the demonstration can go from goal to a real evidence-bearing report. Do not silently start consequential operations.
- Ensure denied external disclosure, revoked session, changed endpoint/model, exhausted budget, unsupported recipe, malformed response, cancellation and provider outage are visible and safe.

### Required live qualification

All acceptance evidence asserting AI quality must come from actual provider responses through the real ALIVE path, not an `httpx.MockTransport`, fixture provider, scripted upstream, synthetic text or model-generated answer key.

- Choose **one pinned, configured real model** and freeze instructions/schema/task labels before the evaluation; no invented provider or costs.
- Reuse the nine existing goal categories as a *starter*, add genuinely held-out goals independently labelled by the evaluator, and record raw outputs, exact model/provider identity, approvals, response provenance, usage, latency, failures and recommendations.
- Compare live hybrid interpretation with the existing fixed and deterministic baselines on the same goals. Deterministic baselines are legitimate *controls*, never substitutes for the live model.
- Measure correct recommendations, correct abstentions, unsupported suggestions, misses, malformed responses and uncertainty. Explicitly report when hybrid fails to outperform the deterministic baseline.
- Test the **three-goal routine**: within one authorized trusted scope, submit at least three successive user goals; observe actual live invocations and results without repeating a CLI or owner-review approval between them.
- Test one real, permitted goal-to-analysis-to-retained-report journey and a backend restart. Verify no replay makes a new model call.
- Demonstrate model outage and budget/consent refusal without a fake AI answer. Preserve destination/proxy/CA/redirect guards and the existing refusal tests.
- Report what the evaluation does **not** establish: task success is separate from citation validity, and continued learning must be shown independently.

**Acceptance requires executed live-model evidence.** If credentials, explicit standing consent or runtime are unavailable, report `LIVE_QUALIFICATION_NOT_RUN` and keep the PR in draft. Do not count the previous scripted 9/9 as product success. Do not dispatch paid calls without the owner's approved scope/budget.

## Test policy

Offline, scripted, fake-Pi and deterministic tests **remain appropriate for unit, safety, parsing, failure injection, and CI regression checks**; they cannot qualify intelligence quality. Running every CI test against a paid provider would be wasteful and unstable. Live calls are mandatory for empirical AI claims and the product acceptance journey, not for every pure function test.

Use focused tests during development. Keep full CI and independent review as release gates. No auto-merge.

## Feature freeze

Until the live-first journey is demonstrated, do not add L2-02 generated-DAG capabilities, new policy gate layers, novel evaluators, more approval screens or additional intelligence frameworks unless a demonstrated defect blocks the live journey. Optimize the user-facing experience: **ask → AI reasons → evidence/result → memory → next useful step**.

## Evidence status at the pivot

- PR #85 head before this reset: `13b78a9c1ecff7c752bc57e0149f5852125edf96`; no new live inference claimed.
- Previously demonstrated real Meta inference in ALIVE-02 / ALIVE-04 / ALIVE-11 does **not** qualify the new Bespoke intent path.
- The prior scripted 9/9 L2-01 comparison is retained only as a historical integration test, never an empirical result.

This document is a directive for implementation and qualification, not a claim that the software has already changed to satisfy it.
