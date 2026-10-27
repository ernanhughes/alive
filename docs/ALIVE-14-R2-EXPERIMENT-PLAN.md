# ALIVE-14-R2 experiment plan - Relationship usefulness

Status: **PREPARED, NOT RUN**. No real Meta calls are authorised by this document.

Frozen protocol: `archives/ALIVE-14-R1/protocol/relationship-experiment-v1.json`
Canonical LF SHA-256: `b0e255b2b0cf5325726cf1af652d307daeb56c1f227922e184c0235ac0cac349`
Seed: `20261101`

## Question

Does an owner-reviewed historical source help produce a more useful relationship insight than
analysing the current page alone, after controlling for the direct presentation of the same history?

This is a three-condition comparison, not a single "history is better" claim.

## Six paired tasks

| Task | Goal | History expectation |
|---|---|---|
| T01 | Reference counting vs tracing collectors | may help: cycle leak |
| T02 | Reference counting vs tracing collectors | may help: root tracing |
| T03 | HTTP cache revalidation | may help: ETag / 304 |
| T04 | HTTP cache revalidation | may help: max-age freshness |
| T05 | Service-worker offline caching | may help: controlled-page condition |
| T06 | Service-worker offline caching | irrelevant or misleading: old appcache manifest |

Each task contains a neutral research question, current reviewed excerpt, historical reviewed excerpt,
source URLs and content hashes. Task wording does not reveal the expected answer.

## Conditions

- **A_current_only**: model analyses only the current excerpt.
- **B_current_plus_history**: model analyses the current excerpt plus the explicitly authorised
  historical excerpt.
- **C_history_without_synthesis**: the same historical excerpt is displayed directly, with no
  model-generated relationship explanation.

A and B use the same pinned model, instruction, schema, token cap and no-retry policy. C is a
transparent baseline, not a model call.

## Planned calls and budget

- 6 tasks x 2 model conditions = **12 calls**.
- No automatic retries.
- Input cap: 18,000 tokens per call; output cap: 1,536 tokens.
- Planning estimate: approximately **$0.02 expected**, **$0.25 worst-case reservation**,
  **$0.30 ceiling**.
- These are planning estimates only. Verify current provider pricing and the exact reservation
  before requesting owner approval.
- Any real call requires a separate owner approval naming endpoint, model, payload hashes, call
  count, token caps, spend cap, abort conditions and redaction plan.

## Blind rating procedure

1. Generate and persist all A/B/C outputs before showing any rating view.
2. Store each output with an immutable SHA-256 and attempt identity in a protected output record.
3. Create the blind run with `POST /research/blind/runs`; the server stores the condition assignment
   in a separate protected `research_blind_assignment` row.
4. Shuffle each task's three outputs with the recorded seed.
5. The rating view (`GET /research/blind/runs/{id}`) shows only:
   - task ID and question;
   - anonymous display order;
   - output text and output hash.
   It omits condition, provider, model, token usage, cost and attempt identity.
6. The owner submits ratings through the authenticated owner endpoint
   `POST /research/blind/runs/{id}/ratings`. The server records `rater_type=owner`; a caller cannot
   claim owner status with a supplied string.
7. Scripted test feedback is recorded with `rater_type=scripted` through the internal test path and
   is excluded from owner reveal metrics.
8. Ratings are append-only revisions. A repeated rating creates a new revision; the earlier rating
   remains in history.
9. `GET /research/blind/runs/{id}/reveal` is available only after every output has an owner rating.
   It returns conditions and ratings; it does not alter them.

The rubric captures, independently:

- `factually_supported`
- `relevant_to_goal`
- `revealed_new`
- `already_obvious`
- `would_act`
- `misleading`
- `uncertain`

No single usefulness score is preregistered. Report each dimension separately and any composite
only with an explicit, preregistered weighting.

## Analysis

Do not use the model as the sole judge. Do not let a model-generated explanation stand in for owner
judgment. Report paired differences by task and dimension, not just aggregate means. A null or
negative result is valid and must be preserved.

## Stop conditions

- Stop if any exact-payload consent check fails.
- Stop if the provider is disabled or the pinned model changes.
- Stop if the cumulative USD liability would exceed the approved ceiling.
- Stop if an invalid quotation or unsupported output is promoted to a validated connection.
- Stop if an interrupted/ambiguous attempt is not represented in the ledger.
- Do not retry an ambiguous call.
- Do not unblind early or reveal condition names in the rating view.

## Approval gate

No paid Meta inference is authorised. A separate proposal must verify:

- exact endpoint and model;
- exact six task payloads and hashes;
- 12-call count;
- input/output caps;
- maximum spend;
- no retries;
- abort rules;
- data-redaction plan;
- owner rating procedure and blinding.

Only after written owner approval may the experiment be run.
