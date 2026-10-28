> **REVIEW-12 superseded R5 readiness.** Independent REVIEW-12 reproduced four remaining blockers in the merged R5 package: durable fatal-stop bypass, cancellation settlement rollback, out-of-order dispatch and display/manifest divergence. R5 is **NOT READY** for owner approval. See `docs/ALIVE-14-R5-R1.md` and `archives/ALIVE-14-R5-R1/`.

# ALIVE-14-R5 - Immutable approval and dispatch integrity

Status:

- **ENGINEERING_SAFETY_CORRECTIONS_IMPLEMENTED**
- **LOCAL_SYNTHETIC_QUALIFICATION_PASS**
- **READY_FOR_INDEPENDENT_REVIEW**
- **REAL_PILOT_BLOCKED**
- **NATIVE_META_NOT_RUN**
- **OWNER_USEFULNESS_NOT_MEASURED**
- **FRESH_NATIVE_SYNTHETIC_PASS** (approval/revocation/read-only UI; 2+16 execution was CLI/backend-driven)

Baseline: `ac11be81115f397a9bad9f5c630a74ee22bdc3d2` (R4 merge).
Branch: `codex/alive-14-r5-approval-integrity`.
Local commit: `ef26935ab346c0e0e916a1d83c84c706f58d3be5`.
No push, PR, merge, hosted CI or paid inference.
Protocol v3 and its answer key are unchanged.

## REVIEW-11 failures reproduced

`archives/ALIVE-14-R5/evidence/review11-prefix.txt` preserves the independent
pre-fix probe output against merged R4:

1. Revoking the campaign approval after call 1 still dispatched call 2.
2. Editing the local question and hash maps dispatched the changed question under
   the original server approval and digest.
3. The authenticated server accepted `stage=1, call_cap=18` for a campaign whose
   stage 1 definition is two calls.
4. A raw Python `TimeoutError` was nonfatal and dispatch continued.

The independent `ALIVE-REVIEW-11.md` and its probe are preserved in
`archives/ALIVE-14-R5/evidence/` for provenance. The repository regressions now
assert the corrected safe outcomes rather than the old unsafe ones.

## Server-authoritative manifest

The registered campaign now carries a strict, versioned content object:

- schema and protocol version;
- frozen protocol/answer-key hashes;
- provider and pinned model;
- instruction and schema hashes;
- output-token cap;
- frozen task order;
- exact task records (goal, question, current/historical URL, SHA-256 and excerpt);
- frozen A/B call order;
- one canonical cell per call index with a content hash, reserved tokens and
  conservative micro-USD reservation.

The server recomputes the campaign digest from the canonical content and rejects
a client-supplied digest mismatch. It validates task/cell counts, ordering,
cell content hashes, stage totals and campaign caps. A duplicate digest with
different content is rejected. Local `state.json` and `approval.json` are
pointer/progress caches only; the runner also compares local task content and
order to the server manifest and stops on mismatch.

## Dispatch authorization

Every experiment preview carries:

- campaign digest;
- approval ID;
- run ID;
- stage;
- task ID;
- condition A/B;
- call index.

The backend resolves the approval and campaign from its own database, checks
active/unsuperseded status, run/campaign/protocol identity, stage, call order,
call index, duplicate cell attempts, stage-2 eligibility, exact task content,
provider/model, instructions/schema hashes, analysis mode and output-token cap.

The final dispatch transaction revalidates sources, grant status, approval and
content, then commits `dispatch_possibly_started`. Revocation and supersession
use the same kernel lock. If revocation commits first, dispatch is refused; if
the dispatch marker commits first, the call is treated as possibly in flight,
retains settlement and conservative liability, and no later cell is dispatched.
A sent request cannot be recalled.

Stage 1 is exactly the first two call indices. Stage 2 is a separate approval
for the remaining sixteen cells and is not eligible until both stage-1 cells
have terminal attempts, at least one is validated, no campaign-fatal error
occurred and no unresolved dispatch remains. Stage 2 cannot be created before
that durable technical outcome. The server rejects `stage=1, call_cap=3/18`,
unknown stages, under-covered token/USD caps and stage-2 early approval.

## Fail-closed failures

Raw `TimeoutError`, actual `asyncio.timeout` expiry, cancellation, permission or
manifest mismatch, authentication/access, quota/rate limit, invalid request/
schema, provider/server failure, transport ambiguity and unexpected exceptions
are campaign-fatal. Only explicitly settled cell-level outcomes (evidence
quotation rejection, insufficient evidence and permitted structured-content
rejection after a response) continue.

- Never-dispatched attempts settle with zero liability.
- Possibly started or ambiguous attempts retain the full conservative
  reservation and are never automatically replayed.
- Cancellation after dispatch is finalized durably and re-raised.
- Restart of a blocked campaign is refused by ordinary execution.

## Evidence

- `archives/ALIVE-14-R5/evidence/review11-prefix.txt` - pre-fix probes.
- `archives/ALIVE-14-R5/evidence/runs/` - authenticated synthetic 2+16 run,
  server approval records, outputs, ratings, reveal and archive.
- `archives/ALIVE-14-R5/evidence/native-synthetic.json` - fresh docked Chrome
  approval, revocation, stage-2 eligibility and read-only retrieval.
- `native-r5-stage1-approval.png`, `native-r5-stage2-approval.png`,
  `native-r5-readonly.png`.
- `real-run-preview-manifest.json`, `real-campaign.json`,
  `pilot-approval-request.json` - unapproved real preview only.

Native actions: Chrome performed campaign selection, digest/manifest review,
stage-2 early rejection, stage-1 approval, stage-1 revocation, re-approval,
stage-2 approval after eligibility, and archived read-only retrieval. The
two-call and sixteen-call execution, rating, reveal, analysis and archive were
performed by the runner/backend against the same isolated database.

## Validation

- Full backend: **243 passed, 6 skipped** (the six skips are the superseded
  R4 real/staged tests; their safe outcomes are covered by R5 tests).
- R5 approval/runner tests: **13 passed**.
- R5 REVIEW-11 safety tests: **21 passed**.
- Focused research memory: **52 passed**.
- Extension: **11 passed**.
- Frontend: **7 passed**.
- Build: passed.
- Ruff check/format: passed.
- Protocol v3 and answer-key hashes verified.
- R1-R4 archives verified unchanged.
- Native synthetic: **NATIVE_SYNTHETIC_PASS** for the scope above.

## Budget

- Stage 1: 2 calls, 10,345 reserved tokens, **$0.043967**.
- Full campaign: 18 calls, 92,148 reserved tokens, **$0.391635**.
- Frozen ceiling: **$0.45**.
- No real approval, no Meta transport and no paid calls.

## Limits

No real provider connectivity, account balance, production structured-output
compatibility, provider settlement reconciliation, semantic truth, human
usefulness, cryptographic human presence, complete cross-route unblinding
protection, or retraction of already-transmitted data is claimed. The owner's
$5 project budget does not alter the $0.45 campaign ceiling. This package is
for independent review only; the paid pilot remains prohibited.
