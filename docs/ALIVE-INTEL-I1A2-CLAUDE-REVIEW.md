# ALIVE-INTEL-I1A2-CLAUDE-REVIEW

**Date:** 28 October 2026 · **Reviewer:** Claude (local runs and scratch patches only; nothing pushed)
**State reviewed:** `main` @ `767596cde22bdc6d5c896415fb83e0e9604a61c8` (2026-10-28 14:16 UTC)
- PR #34 (I1-A validator) is **merged** at `5a750c4` and includes the reviewer's boundary/subject fixes (`edf8861`, `6adcaa9`, `30e4541`).
- PR #35 (I1-A2 claim mode) is **merged** at `767596c`, even though its own doc says "must remain draft… do not merge".

## Verdict: **STOP: `main` is broken. Apply the hotfix (or revert #35) before anything else.**

| # | Severity | Finding | Evidence |
|---|---|---|---|
| H1 | **BLOCKER** | **`main` does not import; the app cannot start and zero tests run.** `research_relationships.py` L44 contains a literal `\n` in source: `CONSENT_TTL_MINUTES = 10\nCLAIM_INSTRUCTIONS = (…`. That is a `SyntaxError`, and `alive.app` imports this module. | `python -m py_compile` fails; `pytest` aborts loading `conftest.py` (`ImportError`). |
| H2 | **BLOCKER** | A second syntax error: a `local_fixture_claim` branch with an unindented body, inserted **inside `_analyze_bounded`** (the paired/ALIVE-14 path), nested under `if provider["id"] in ("local_stub", …)`, where it would be unreachable anyway. | Revealed after fixing H1 (L1001–1005). |
| H3 | **BLOCKER (ALIVE-14 boundary violated)** | Two edits in `_analyze_bounded` reference the undefined name `analysis_mode` (that function's parameter is `mode`): the attempt's `analysis_version` (L903) and a claim-Meta guard (L951). With the syntax fixed, **24 tests fail**: every paired/current-only analysis and every ALIVE-14 campaign dispatch. It fails closed (no call is made), but it breaks paths I1-A2 was forbidden to touch. Claim mode never reaches `_analyze_bounded`, so both edits are simply reverted. | After H1/H2 repair: 24 failed, 255 passed. Reverting one edit: 21 failed. Reverting both: 279 passed. |
| H4 | **BLOCKER (egress)** | **The "zero-cost" fixture provider dispatches to `MetaProvider`.** The ordinary `analyze()` path, which claim mode uses, has no `local_fixture_claim` branch, so it falls to `else:` and calls `MetaProvider.structured(model="deterministic-claim-fixture-v1")`. This **bypasses both** `alive_research_meta_enabled` and `alive_claim_meta_enabled`, because the provider ID is not `meta`. It is gated only by `alive_relationship_allow_test_providers`. On a machine with a Meta key configured and test providers enabled, source excerpts would be sent to Meta. | Probe 1: `meta calls: ['deterministic-claim-fixture-v1']`, attempt `failed`. |
| H5 | **MAJOR** | **The withdrawn anchor quote survives in invalidated claim connections.** `_scrub_withdrawn_data` does not cover the new `reliance` field (`{quote, start, end, revision, source_sha256}`). The list endpoint hides these rows, but this is a derived-row leak (an I1-A stop condition). | Probe 4: invalidated connection keys holding withdrawn text = `['reliance']`. |
| H6 | Process | Two PRs that declared themselves unqualified ("NO", "do not merge") were merged. #35 was merged without running Python once. | Commit log; PR docs. |

## What works, verified after the hotfix

Claim-mode lifecycle, run end to end with the real fixture branch (`test_zz_claim_mode_probe.py`):

1. **Anchor:** 200.
2. **Preview:** binds `reliance` (revision 1), and the request hash uses the **claim** schema.
3. **Authorise, then analyse:** attempt `validated`; candidate `explicit_supersession`; validator `accepted`; `historical_quote_retained_in_current = true`.
4. **Listing:** goal-scoped and shows the candidate.
5. **Re-anchor:** 200; candidates drop to 0 (`anchor_revised` invalidation works).
6. **Fresh run, withdraw, restart:** 0 active; the listing holds no withdrawn text.
7. **Derived rows:** no withdrawn text. Only authoritative originals remain (both snapshots, the note, the withdrawn memory row), per the retention decision.
8. **Gates:** `claim_comparison` + `meta` with research-Meta on and claim-Meta off returns **403** (preview gate). After the hotfix, the dispatch path is also gated.

## Hotfix (`i1a2-hotfix.patch`: 1 file, +20/−11; applies cleanly to `767596c`)

1. Split L44 into two lines (H1).
2. Remove the misplaced fixture branch from `_analyze_bounded` and restore the original `local_stub` branch (H2).
3. Revert both `analysis_mode` edits in `_analyze_bounded` (H3).
4. In `analyze()`: add an explicit `local_fixture_claim` branch (claim mode only). In the external `else`, **refuse any provider ID other than `meta`** (defence in depth), and re-check `alive_claim_meta_enabled` at dispatch (H4).
5. `_scrub_withdrawn_data` drops `reliance.quote` while keeping revision, offsets and SHA (H5).

**Results with the hotfix:** `uv run pytest -q` → **279 passed, 6 skipped, 0 failed** (208 s, Linux/SQLite/Python 3.13.18); `node --test` → 5/5 and 6/6; probes 1–4 clean (zero Meta calls).

**Not run:** PostgreSQL, Windows, native Chrome.

## Still open before I1-B (unchanged obligations)

- Commit probes 1–4 as permanent tests, together with C-real/D/E/F and the leak scanner.
- Add a test asserting that **no non-`meta` provider ever reaches `MetaProvider`**; this would have caught H4.
- The `_claim_fixture_map` is only an attribute (`getattr(self, "_claim_fixture_map", {})`); nothing populates it. Commit the pinned SHA → output map with the fixtures (I1-C).
- Anchor 409/422 status mapping.
- Owner-revoked current grant invalidates claim candidates.
- Timeout and accounting tests for claim mode.
- The `utcnow`/`utcfromtimestamp` structural binding remains interim until capture-v2.

## Process recommendation

Protect `main`: require a green `uv run pytest -q` before merge (CI or a local pre-merge check). Two consecutive merges declared unqualified by their own authors, one of which left `main` unimportable, show that the "draft until tested" rule is not being enforced by anything.

**I1-A2 ready for I1-B: NO** until the hotfix lands and the probes become permanent tests.
