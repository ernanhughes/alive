# ALIVE-14-R4 pilot-safety archive

Status: **ENGINEERING_PASS**, **NATIVE_SYNTHETIC_PASS**,
**OWNER_APPROVAL_FLOW_QUALIFIED**, **META_READY_FOR_OWNER_APPROVAL** (subject to
independent review and explicit owner approval), **NATIVE_META_NOT_RUN**,
**OWNER_USEFULNESS_NOT_MEASURED**.

Baseline: `ac11be81115f397a9bad9f5c630a74ee22bdc3d2` (ALIVE-14-R3 merge).
Protocol v3 and its answer key are unchanged. All earlier archives are preserved.
No paid inference was performed. No merge or auto-merge was requested.

## Frozen protocol

- Path: `archives/ALIVE-14-R3/protocol/relationship-experiment-v3.json`
- SHA-256: `85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b`
- Answer key SHA-256: `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`

## Contents

| Path | Meaning |
|---|---|
| `protocol-reference.json` | frozen R3 protocol identity used by R4 |
| `evidence/review10-prefix.json` | pre-fix reproduction of both REVIEW-10 blockers |
| `evidence/runs/...` | complete R4 synthetic run: campaign, approval records, outputs, results, analysis, archive |
| `evidence/native-synthetic.json` | native Chrome campaign approval and blind journey |
| `evidence/native-r4-approval.png` | genuine docked-panel capture |
| `evidence/real-run-preview-manifest.json` | exact real-run payload/request hashes and reservations |
| `evidence/real-campaign.json` | server-side campaign registration for the real run |
| `evidence/pilot-approval-request.json` | non-approval request summary; server approval required |
| `validation/backend.txt` | full backend transcript |
| `validation/alive14r4.txt` | R4 pilot-safety regression transcript |
| `validation/research-memory.txt` | focused research-memory transcript |
| `validation/extension.txt` | extension transcript |
| `validation/frontend.txt` | frontend transcript |
| `validation/build.txt` | production build transcript |
| `validation/ruff.txt` | lint/format transcript |
| `validation/native.txt` | native result summary |
| `validation/preflight.txt` | synthetic full-run summary |
| `validation/prefix-repro.txt` | pre-fix reproduction summary |
| `validation/real-preview.txt` | real prepare summary |
| `validation/protocol.txt` | protocol/answer-key hash verification |
| `validation/archive.txt` | archive verification statement |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## What is proven

- Explicit owner revocation of a restart-suspended grant is permanent; recovery
  cannot restore it, and final dispatch dispatches zero calls.
- Normal restart recovery preserves the original expiry and cannot broaden scope.
- A campaign-fatal provider error stops after exactly one attempted call and
  leaves the remaining cells undispatched.
- Stage 1 (2 calls) and stage 2 (remaining 16) execute only with separate
  server-side owner approvals.
- Approval files alone are rejected; the server record is authoritative and
  digest-bound.
- Missing/rejected outputs cannot count as research successes; rating revisions
  no longer break archive; misleading counts are reported by condition.
- Failed-cell events and blind cards do not expose attempt IDs or condition labels
  during collecting.
- Dispatch-start is committed before provider transmission; ambiguous attempts
  keep conservative cost liability and are never replayed.
- The native panel can review the digest/manifest and approve a stage without raw
  HTTP commands.

## What is not proven

No real Meta call, human usefulness rating, semantic truth verification or
population-level inference. The synthetic ratings are a task-hash null pattern
and are not evidence about memory value. Automated PII/secret redaction is not
implemented. The owner approval proves an authenticated owner-channel action,
not a human click or a cryptographic signature from a separate device.
Content-based inference from answer text remains possible. A paid pilot still
requires the separate approval in `docs/ALIVE-14-R4-PILOT-APPROVAL.md`.
