# ALIVE-INTEL I1-A2 — authorized claim mode (draft engineering branch)

## Scope introduced
- Strict preview API accepts `analysis_mode=claim_comparison` and `provider=local_fixture_claim`.
- Source/anchor inclusion in payload and exact preview hash; mode-specific claim instructions and schema.
- Existing `authorize`, durable guard, one-call reservation, and settlement routes reused, with anchor revalidation.
- Claim-specific validation, candidate-only storage for accepted conflicts / qualifications / explicit supersessions, claim-version listing and cache key.
- Strict code-level `alive_claim_meta_enabled=False` default: claim-mode Meta is denied even when ordinary Meta relationships are permitted.
- Test-gated fixture provider keyed by exact source SHA pair. Unregistered pairs fail closed. No model calls made.

## STOP: this PR is **not qualified**
This session edited GitHub source through connector operations and **did not run Python, tests, the app, or the validator attacks**. No claim of green tests, functional real fixtures or end-to-end readiness.

### Remaining engineering obligations
1. Run `uv run pytest -q` and all existing extension tests. Fix any syntax, response-shape or existing-mode regressions.
2. Add the actual pinned SHA fixture map, complete `save → anchor → preview → authorize → analyze → list → re-anchor → withdraw → restart` integration tests.
3. Add permanent C-real/D/E/F probes, leak scanner, I-E1/I-E2, timeout and accounting tests.
4. Fix strict HTTP 409 versus 422 anchor mapping and record owner-revoked current source-grant invalidation.
5. Verify quote identity `utcnow` versus `utcfromtimestamp` using real capture-v2 later; current validator only has an interim signature heuristic.
6. Audit cache use, consent expiry, settlement and dispatch-status handling for claim-mode specifically. Validate data scrub for withdrawn lineage.
7. Independently inspect all changed code and run PostgreSQL / Windows tests (report unrun contexts truthfully).
8. Keep all ALIVE-14, bounded experiment and blind test code untouched.

## Readiness
**I1-A2 ready for I1-B: NO** pending tests, fixtures, safety probe qualification and independent review. This PR must remain draft. Do not merge simply because the new mode is exposed.

## Non-actions
Zero Meta calls, no actual owner consent, zero paid spend, no ALIVE-14 changes, no migrations, no new browser permissions, no Think cycle.
