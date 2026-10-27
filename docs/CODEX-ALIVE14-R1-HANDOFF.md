# Codex ALIVE-14-R1 handoff

## 1. Starting point and branch

- Verified main: `777e4d99b6908d13875c9024dfb065cb3bfcaffa`.
- Branch: `codex/alive-14-r1-qualification`.
- Review basis: ALIVE-REVIEW-07.
- Original ALIVE-14 archive preserved unchanged.
- No paid inference, merge or auto-merge.

PR/CI: to be recorded after push.

## 2. Confirmed corrections

| REVIEW-07 finding | Correction |
|---|---|
| One-character or generic quotes could validate | Versioned validator with minimum quote length, meaningful non-goal term floor, shared-term requirement, identical-span rejection, abstention language/confidence guard |
| Interrupted attempts escaped USD accounting | Interrupted/ambiguous attempts included in conservative liability; restart preserves it; no double charge |
| Meta kill switch not rechecked at dispatch | Provider enablement, provider identity, pinned model, request hash, reservation and USD cap rechecked immediately before dispatch |
| Reuse ignored provider/payload | Reuse requires source fingerprints, exact payload hash, request hash, provider, model, analysis version and validator version |
| Protocol hash not reproducible | Original CRLF/evidence and LF Git blob reconciled; R1 uses LF hashes; CI verifier added |
| Blind rating provenance absent | Owner/scripted rating separation, protected assignment, seeded order, hidden metadata, immutable output hashes, append-only revisions, reveal gate |
| Meta preview incomplete | Exact instructions/input/schema, reservation, remaining allowance, provider operation and request hash exposed server-side |
| Missing race/recovery tests | Added same-consent race, stub/Meta identity, timeout, interruption, kill switch, model switch, cache reuse and budget tests |

## 3. Consent and Governor guarantees

- Preview binds exact current/historical excerpts, source hashes, goal, provider, model and request
  representation.
- Authorisation binds the payload SHA-256.
- Dispatch revalidates live grant, active memory, source hashes, payload hash, request hash, provider
  enablement, model pin, reservation and USD cap.
- Withdrawal/revocation invalidate outstanding consent; withdrawal is blocked during in-flight
  dispatch.
- Consumed consent cannot replay. Cache hits use `cached`, not a provider-dispatch consumption.
- Interrupted attempts are charged conservatively and cannot be retried automatically.

## 4. Output validation

`validate_relationship_output` version `alive14r1-evidence-v1` returns quote provenance separately
from semantic verification. It rejects short/generic/unsupported quote pairs and assertive or
overconfident abstentions. Valid quote provenance does not make the explanation fact-checked; the
connection records `semantic_verification=false` and `unverified_model_interpretation`.

## 5. Blind rating readiness

Owner route: authenticated `POST /research/blind/runs/{id}/ratings`; server sets
`rater_type=owner`. Scripted ratings use the internal test path and are excluded from owner reveal.
The rating view hides condition/provider/model/token/cost; assignment is a separate protected row;
seeded order and output hashes are persisted; ratings are append-only revisions; reveal requires all
owner ratings.

## 6. Experiment protocol

- `archives/ALIVE-14-R1/protocol/relationship-experiment-v1.json`.
- Six paired tasks, conditions A/B/C, seed `20261101`.
- Canonical LF SHA-256 `b0e255b2b0cf5325726cf1af652d307daeb56c1f227922e184c0235ac0cac349`.
- Budget planning only: 12 calls, ~$0.02 expected, ~$0.25 worst-case reserve, $0.30 ceiling.
- No real calls; no re-use of ALIVE-11 approval.

## 7. Native qualification

Fresh isolated Chrome `155.0.8059.85`, genuine docked side panel, local synthetic provider:

- exact owner-visible payload preview including request/schema/allowance;
- explicit authorisation;
- valid local-stub analysis with validated quotations;
- malformed-output provider rejected with reasons and no connection;
- same provider/model/payload cache reuse without second dispatch;
- scripted feedback marked `rater_type=scripted`;
- display-target withdrawal invalidated a previously authorised consent;
- restart persistence and zero external calls;
- 3 synthetic note calls, 0 paid calls.

## 8. Testing

- Full backend: 187 passed.
- Focused research-memory: 41 passed.
- Extension: 11 passed.
- Frontend: 7 passed.
- Production build: passed.
- Ruff in CI scope: passed.
- ALIVE-14 reconciliation: verified.
- ALIVE-14-R1 native: `NATIVE_SYNTHETIC_PASS`.

## 9. Archive and provenance

- `archives/ALIVE-14-R1/` contains R1 protocol, validator cases, pre-fix defects, hash reconciliation,
  native evidence/screenshot, validation transcripts and manifest.
- Original ALIVE-14 archive is untouched.
- `scripts/verify_alive14_protocol.py` verifies both protocol representations.
- `scripts/verify_archive.py` verifies R1 from LF checked-in bytes.
- CI runs both checks.

## 10. Status

- **ENGINEERING_PASS**
- **NATIVE_SYNTHETIC_PASS**
- **NATIVE_META_NOT_RUN**
- **META_READY_FOR_APPROVAL** subject to independent recheck
- **OWNER_USEFULNESS_NOT_MEASURED**

## 11. Remaining limitations

The validator proves quotation provenance, not semantic truth. No real Meta call or human owner
rating has occurred. The R2 budget is a planning estimate and must be revalidated against current
pricing. Independent recheck of the corrected provider boundary is required before paid inference.

## 12. Recommended next step

Independently re-run the R1 provider-boundary tests and review the diff. If confirmed, request owner
approval for the frozen six-task/12-call R2 experiment with exact payload hashes, token caps, spend
ceiling, no retries and blinded owner ratings.
