# ALIVE-14-R1 - Research Relationship Safety and Experiment Readiness

Engineering: **ENGINEERING_PASS**. Native synthetic: **NATIVE_SYNTHETIC_PASS**.
Meta readiness: **META_READY_FOR_APPROVAL**, subject to independent recheck.
Native Meta: **NATIVE_META_NOT_RUN**.
Owner usefulness: **OWNER_USEFULNESS_NOT_MEASURED**.
Paid calls: **0**.

Baseline: `777e4d99b6908d13875c9024dfb065cb3bfcaffa` (ALIVE-14 merge).
Branch: `codex/alive-14-r1-qualification`.
Source commit for the archived evidence: `9ff0e388cb7a874619e8acf3612beeb6260288c0`.
PR: https://github.com/ernanhughes/alive/pull/21 (draft, review-only).
CI: all eight PR checks passed (backend Ubuntu/Windows, dashboard, first-contact PostgreSQL).
Original ALIVE-14 archive: preserved unchanged.
R2 experiment protocol: committed before execution; **not run**.

## Corrected REVIEW-07 defects

### 1. Weak quotation validation

A versioned validator (`alive14r1-evidence-v1`) now rejects:

- quotations shorter than 16 characters;
- quotations with fewer than two meaningful non-goal terms;
- quotations with no shared meaningful terms across the pair;
- identical evidence spans;
- non-exact quotations;
- `insufficient_evidence` output with confidence above 0.2 or assertive language.

Valid quotations establish **quote provenance only**. The explanation is always stored as
`unverified_model_interpretation`; `semantic_verification` is false. A fabricated authority sentence
attached to valid quotations cannot become a fact-checked conclusion. Invalid raw output remains in
the attempt record with `rejected`/`failed` status and never creates a connection.

Evidence: `archives/ALIVE-14-R1/evidence/validator-cases.json`.

### 2. Interrupted USD accounting

`interrupted` and ambiguous attempts are now included in the conservative USD ledger. Validated
attempts use actual usage; failed, rejected, interrupted and unknown attempts use their reserved
liability. Restart cannot reset the liability. The Governor still reserves before dispatch.

The regression test sets the cap to 25,000 micro-USD, adds an interrupted 20,647 micro-USD
liability, rejects the next call before dispatch, restarts, and confirms the liability remains and
the consent cannot replay.

### 3. Provider kill switch and model pin

Immediately before dispatch the server now rechecks:

- provider enablement;
- provider identity;
- pinned model;
- exact request representation;
- the Governor reservation;
- the current cumulative USD ceiling.

Meta disabled after authorisation, or a changed model, produces a failed attempt with zero provider
calls. There is no fallback provider and no silent model substitution.

### 4. Connection reuse identity

Reuse now requires all of:

- current snapshot and source fingerprint;
- historical memory and source fingerprint;
- exact payload SHA-256;
- exact request SHA-256;
- provider identity;
- pinned model;
- analysis version and validator version.

A local-stub result cannot satisfy a Meta request. A cache hit is marked `cached`, does not dispatch,
and does not consume a paid-inference consent as if it had dispatched. Stub -> Meta dispatches once;
identical Meta -> Meta reuses the validated result without another call.

## Blind rating provenance

Added `alive/research_blind.py` and authenticated endpoints:

- `POST /research/blind/runs`
- `GET /research/blind/runs/{id}`
- `POST /research/blind/runs/{id}/ratings`
- `GET /research/blind/runs/{id}/reveal`

The rating view hides condition, provider, model, tokens, cost and attempt identity. The condition
assignment is stored in a separate protected record. Order is randomised per task with the recorded
seed. Output text and SHA-256 are immutable before rating. Owner ratings are server-labelled
`rater_type=owner`; scripted ratings use the internal test path and are reported separately. Ratings
are append-only revisions. Reveal is blocked until every output has an owner rating.

Connection feedback now records `rater_type`, `rating_id` and rubric version; scripted native
feedback is explicitly labelled.

## Meta outbound preview

The preview now includes:

- exact current and historical excerpts, URLs and fingerprints;
- provider, model and external/local operation identity;
- exact instructions, input payload and response schema;
- single-call reservation and estimated maximum micro-USD;
- remaining session/experiment calls, tokens and USD allowance;
- request SHA-256 and payload immutability marker.

The server-side consent contract remains authoritative; the panel display is not a permission check.

## Provenance reconciliation

The original ALIVE-14 archive is unchanged. Its recorded protocol hash
`56a85e...` is the CRLF working-tree representation; the committed Git blob is
`01165f...`. Both are documented in
`archives/ALIVE-14-R1/evidence/protocol-hash-reconciliation.json`.
`scripts/verify_alive14_protocol.py` verifies both representations and the original manifest.
Future R1 archive hashes use LF checked-in bytes via `scripts/canonical_sha256.py`; CI verifies the
R1 manifest and the ALIVE-14 reconciliation.

## Experiment preparation

`archives/ALIVE-14-R1/protocol/relationship-experiment-v1.json` freezes six paired tasks, three
conditions, a seed, budget planning estimates, rubric and stopping rules. Protocol canonical
SHA-256: `b0e255b2b0cf5325726cf1af652d307daeb56c1f227922e184c0235ac0cac349`.
No real experiment was run.

## Native synthetic qualification

Fresh isolated Chrome `155.0.8059.85`, genuine docked side panel, local synthetic provider:

- exact source and payload preview including instructions/schema and remaining allowance;
- explicit authorisation;
- valid local-stub analysis with quote provenance;
- malformed-output provider rejected with reasons and no connection;
- cache reuse for the same provider/model/payload without a second dispatch;
- scripted feedback marked `rater_type=scripted`;
- displayed-target withdrawal invalidating a previously authorised consent;
- restart persistence and zero external calls;
- 3 synthetic note calls, 0 paid calls.

## Validation

| Check | Result |
|---|---|
| Full backend suite | 187 passed |
| Focused research-memory suite | 41 passed |
| Extension tests | 11 passed |
| Frontend tests | 7 passed |
| Production dashboard build | passed |
| Ruff in CI scope | passed |
| Native synthetic Chrome | `NATIVE_SYNTHETIC_PASS` |
| ALIVE-14 protocol reconciliation | verified |
| Paid inference | 0 |

## Remaining limitations

- No real Meta call or human owner usefulness rating.
- The blind-rating API is prepared and tested with scripted plumbing; the R2 experiment is not run.
- The validator establishes quote provenance, not semantic truth.
- The R2 budget figures are planning estimates and require current pricing verification.
- Independent security recheck of the R1 provider boundary remains required before paid calls.
