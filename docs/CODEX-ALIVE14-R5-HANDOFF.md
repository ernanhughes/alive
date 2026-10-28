# Codex ALIVE-14-R5 handoff

## Repository

- Baseline: `ac11be81115f397a9bad9f5c630a74ee22bdc3d2`
- Branch: `codex/alive-14-r5-approval-integrity`
- Worktree: `C:\Projects\alive-worktrees\alive-14-r5`
- Local commit: `ef26935ab346c0e0e916a1d83c84c706f58d3be5`.
- No push, PR, merge, auto-merge, hosted CI, real approval or paid inference.
- Protocol v3 and answer key unchanged.

## Status

- **ENGINEERING_SAFETY_CORRECTIONS_IMPLEMENTED**
- **LOCAL_SYNTHETIC_QUALIFICATION_PASS**
- **READY_FOR_INDEPENDENT_REVIEW**
- **REAL_PILOT_BLOCKED**
- **NATIVE_META_NOT_RUN**
- **OWNER_USEFULNESS_NOT_MEASURED**
- **FRESH_NATIVE_SYNTHETIC_PASS** (approval/revocation/read-only Chrome; 2+16
  execution via the local runner)

## REVIEW-11 corrections

| Finding | Correction |
|---|---|
| Revocation after call 1 allowed call 2 | Every experiment preview and final dispatch rechecks the active server approval under the same lock as revocation/supersession; cancellation/supersession blocks all later cells |
| Local question/hash edits bypassed approval | Immutable server content is authoritative; runner compares local content/order to it and the backend compares the actual payload field-for-field, instructions/schema and call order |
| Stage 1 accepted 18 calls | Server stage contracts require exactly 2 calls for stage 1; stage 2 requires cumulative 18, remaining indices 2-17 and durable stage-1 eligibility |
| Raw TimeoutError continued | Timeout, asyncio timeout, cancellation, permission, manifest, provider and unexpected dispatch errors are campaign-fatal; only settled cell-level evidence failures continue |

## Tests

- Full backend: **243 passed, 6 skipped** (R4 real/staged tests superseded by R5; safe outcomes covered in R5).
- R5 approval/runner: **13 passed**.
- R5 safety: **21 passed**.
- Research memory: **52 passed**.
- Extension: **11 passed**.
- Frontend: **7 passed**.
- Build and Ruff: passed.
- R1-R4 archives and protocol hashes: verified.
- Native: fresh docked Chrome approval/revocation/stage-2/read-only journey passed.

## Evidence

`archives/ALIVE-14-R5/` contains the pre-fix probe, independent REVIEW-11 record,
corrected synthetic 2+16 run, server approval records, native evidence and
screenshots, real preview manifest/campaign (no approval) and validation logs.

## Remaining gates

A new independent review must rerun the four failed scenarios, inspect the
server-authoritative manifest/approval barrier, confirm stage eligibility,
timeout/cancellation behavior and archive preservation. No real approval may be
created until that review passes and the owner separately authorises a stage.
