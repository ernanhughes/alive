> **REVIEW-11 superseded R4 readiness.** The merged R4 package is **NOT READY** for owner approval. See `docs/ALIVE-14-R4-R1-SAFETY-CLOSURE.md` and `docs/ALIVE-14-R5.md`.

# ALIVE-14-R4 - Final pilot safety qualification

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**,
**OWNER_APPROVAL_FLOW_QUALIFIED**, **META_READY_FOR_OWNER_APPROVAL** (subject to
independent review and explicit owner approval), **NATIVE_META_NOT_RUN**,
**OWNER_USEFULNESS_NOT_MEASURED**.

Baseline: `ac11be81115f397a9bad9f5c630a74ee22bdc3d2` (ALIVE-14-R3 merge).
Branch: `codex/alive-14-r4-pilot-safety`.
Implementation commit: `4bdefea1bb0eb198d06db2b0518d6f13d1f7d6ad`.
PR: https://github.com/ernanhughes/alive/pull/25 (draft, review-only).
CI: all eight checks passed on `4bdefea`.
Protocol v3 is unchanged:
`85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b`.
Answer key: `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`.
No paid inference was performed. No merge or auto-merge was requested.

## REVIEW-10 defects reproduced

`archives/ALIVE-14-R4/evidence/review10-prefix.json` records the pre-fix
reproduction against `ac11be8`:

| Defect | Pre-fix result |
|---|---|
| Explicit owner revocation undone by runner | Grant remained `revoked_restart` after the owner revoke; the runner re-activated it and completed all 18 cells |
| All-401 provider did not stop the campaign | 18 attempted calls, 0 undispatched cells, all outputs failed |
| Approval was a self-asserted JSON file | `human_approval`, `approved_by` and `approved_at` were not bound to a server-side owner action |
| Rating revisions could break archive | Archive compared raw rating rows to output rows |
| Missing placeholders could count as success | Analysis applied the positive rubric to a missing output |
| Failed-cell metadata could reveal condition | Paired settled/authorized events exposed attempt IDs and status in fixed order |

## P0 corrections

### Irreversible owner revocation

- Restart suspension changes only `active -> revoked_restart`, records
  `suspended_at`, `suspension_reason`, `suspended_from` and a state history.
- Explicit owner revocation changes `active` or `revoked_restart` to permanent
  `revoked`, records `owner_revoked=true`, `revoked_by`, `revoked_at`,
  `revocation_reason` and state history. Repeated revocation is idempotent.
- Recovery accepts only `revoked_restart`, rejects any `owner_revoked` or
  `revoked_at` history, and never changes the original `expires_at`, scope or
  permission.
- Recovery is lock-protected and records `restored_from`, `restored_by`,
  `restored_for_run`, `approval_id` and state history.
- Final dispatch revalidates the grant. A revoked grant produces zero provider
  calls.
- Tests cover explicit revocation, normal recovery, concurrent revocation and
  recovery, two restarts, expiry, and final dispatch revalidation.

### Fail-fast provider policy

`ProviderError` now exposes a category, HTTP status, response-received flag and
`campaign_fatal` decision. HTTP status mapping is code-based, not substring
matching:

| Condition | Category | Campaign policy |
|---|---|---|
| 401 | authentication | fatal, stop |
| 403 | access_denied | fatal, stop |
| 402 / quota body | quota_exhausted | fatal, stop |
| 429 | rate_limit | fatal, stop for zero-retry campaign |
| 400/404/422 | invalid_request or unsupported_schema | fatal, stop |
| 5xx | server_error | fatal, conservatively stop |
| timeout/network | timeout/transient_network | fatal, conservatively stop |
| malformed provider JSON | invalid_response | fatal, stop |
| output truncated or local evidence invalid | cell-level | record rejection, continue |

The runner records the failed attempt, stops new dispatch immediately, preserves
remaining unexecuted cells, marks the run `blocked`, keeps cost liability and
never replays the attempt. All-401, unsupported-schema and quota tests each
dispatch exactly one call and leave 17 cells undispatched.

### Staged execution

`execute --limit N` counts attempted dispatches, not validated outputs. It:

- restricts new provider calls;
- preserves durable `outputs.jsonl` progress and attempt inventory;
- permits an explicitly approved continuation stage;
- never replays interrupted cells;
- honours the call, token and USD ceilings;
- preserves task order and the blind assignment;
- continues past per-cell failures but stops on campaign-fatal errors.

Stage 1 is two calls. After stage 1 the phase is `staged`; the owner must approve
stage 2 before the remaining 16 calls. The synthetic test executes 2 calls, then
16, with separate server-side approvals.

### Approval integrity

A local JSON file is no longer sufficient. The minimum authenticated flow is:

1. `prepare` registers a campaign with a stable content-only digest in the
   isolated experiment database.
2. `serve-approval` serves that database locally for the native side panel.
3. The owner opens **Experiment approval**, reviews the provider/model, task
   count, exact manifest, digest, stage caps, no-retry policy and total
   reservation, checks the attestation box for a real campaign, and clicks
   **Approve selected stage**.
4. The server creates an `research_experiment_approval` record bound to the
   campaign digest, call cap, token caps, USD cap, stage, no-retry flag and
   authenticated owner provenance. Prior active approvals for the campaign are
   marked `superseded`.
5. `approve` reads the server record; a file pointer without a server record is
   rejected.
6. `execute` re-fetches the server record and refuses if it is missing, revoked,
   superseded, or bound to another campaign digest.

The canonical campaign digest covers protocol/answer-key hashes, provider,
pinned model, instruction/schema hashes, and every task's goal, neutral
question, current/historical URL, SHA-256 and exact excerpt. It deliberately
excludes random database IDs. Equivalent fresh preparations produce the same
digest; changed content produces a different digest.

### Enforced budget

The effective cap is:

```
min(protocol ceiling, owner-approved max_usd, ALIVE_R4_RUNTIME_USD_CAP)
```

A higher owner request cannot override the runtime cap. An approval below the
stage's worst-case reservation is rejected. The runner uses the effective cap
when constructing Governor settings; it does not silently use the protocol
maximum.

## P1 corrections

### Accounting

- Archive compares distinct rated output identities, not raw rating rows, so
  append-only revisions no longer break archive.
- A missing/rejected output is forced to `supported_useful=false` regardless of
  its placeholder rating.
- Missingness is reported overall and by condition.
- Misleading counts are reported by A, B and C separately.
- Task-level outputs, ratings, attempt IDs and revisions are preserved.

### Blinding during failures

While collecting, paired-mode `outbound_authorized` and
`paired_analysis_settled` events contain only mode/settlement flags, not
attempt IDs, consent IDs, payload hashes or condition-correlatable status.
Blind cards use identical neutral placeholder text. Attempt metadata is retained
in the database and revealed only after rating closure. Content-based inference
from answer text is still possible and is documented rather than denied.

### Durable dispatch state

The attempt row commits `dispatch_possibly_started` before the provider call.
Settlement records `provider_response_received` when a response arrived and
`dispatch_possibly_started` when it did not. Restart settlement preserves the
marker:

- `reserved_never_dispatched` -> `interrupted`, zero cost liability;
- `dispatch_possibly_started` -> `interrupted`, full conservative reservation
  liability;
- missing provider response is never treated as proof of no charge;
- no automatic replay.

## Native Chrome

Chrome `155.0.8059.85`, genuine docked side panel, isolated backend, fresh
profile. The owner-facing flow now includes **Experiment approval**:

- register/list campaigns;
- select a campaign and see its digest and complete manifest;
- choose stage 1 (2 calls) or stage 2 (remaining calls);
- see provider/model, task count, call cap, reserved tokens and maximum spend;
- require the attestation checkbox for a real campaign;
- approve through the authenticated backend and see the active approval status.

The R4 native journey also repeats the R3 blind-rating/reveal/read-only/restart
checks. Evidence: `archives/ALIVE-14-R4/evidence/native-synthetic.json`,
`native-r4-approval.png`. Native ratings remain `synthetic_owner_endpoint`, not
human ratings. Synthetic note calls: 4. Paid calls: 0.

## Validation

- Full backend: **215 passed**
- R4 pilot-safety tests: **13 passed**
- Focused research memory: **52 passed**
- Extension: **11 passed**
- Frontend: **7 passed**
- Production build: passed
- Ruff check/format: passed
- R1/R2/R3 archives and protocol hashes: verified
- Native synthetic: `NATIVE_SYNTHETIC_PASS`

## Limits

No real Meta call, human owner usefulness rating or semantic truth verification.
The synthetic ratings are a task-hash null pattern and are not evidence about
memory value. Automated PII/secret redaction is not implemented. The approval
token proves an authenticated owner-channel action, not a human click. The
server-side approval is not a cryptographic signature by a separate owner
device. Content-based inference from published answer text remains possible.
Protocol v3 and its answer key are frozen and unchanged; this milestone changes
runner safety and approval integrity only. The historical R3 runner now refuses
real mode and is retained only for synthetic archive reproduction; the R4 runner
is the only real-execution path.
