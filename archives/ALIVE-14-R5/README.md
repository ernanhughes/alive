# ALIVE-14-R5 / R4-R1 safety-closure archive

Status: **ENGINEERING_SAFETY_CORRECTIONS_IMPLEMENTED**,
**LOCAL_SYNTHETIC_QUALIFICATION_PASS**, **READY_FOR_INDEPENDENT_REVIEW**,
**REAL_PILOT_BLOCKED**, **NATIVE_META_NOT_RUN**, **OWNER_USEFULNESS_NOT_MEASURED**.

Baseline: `ac11be81115f397a9bad9f5c630a74ee22bdc3d2`.
Protocol v3 and its answer key are unchanged. No real approval, Meta transport,
paid call, push or merge was performed.

## Contents

| Path | Meaning |
|---|---|
| `evidence/ALIVE-REVIEW-11.md` | independent controlling safety assessment |
| `evidence/review11_probe.py` | independent pre-fix probe source |
| `evidence/review11-prefix.txt` | reproduced pre-fix unsafe outcomes |
| `evidence/runs/...` | corrected synthetic 2+16 campaign with server approvals, outputs, ratings, reveal and archive |
| `evidence/native-synthetic.json` | fresh docked Chrome approval/revocation/read-only journey |
| `evidence/native-r5-stage1-approval.png` | native stage-1 approval |
| `evidence/native-r5-stage2-approval.png` | native stage-2 approval after eligibility |
| `evidence/native-r5-readonly.png` | native archived read-only retrieval |
| `evidence/real-run-preview-manifest.json` | unapproved real preview manifest |
| `evidence/real-campaign.json` | unapproved server campaign registration |
| `evidence/pilot-approval-request.json` | not an approval; stage-1 request only |
| `validation/backend.txt` | full backend suite |
| `validation/alive14r5.txt` | R5 approval/runner tests |
| `validation/review11-corrected.txt` | corrected REVIEW-11 safety regressions |
| `validation/research-memory.txt` | focused research-memory suite |
| `validation/extension.txt` | extension tests |
| `validation/frontend.txt` | frontend tests |
| `validation/build.txt` | production build |
| `validation/ruff.txt` | lint/format |
| `validation/native.txt` | native actions and limitations |
| `validation/preflight.txt` | corrected 2+16 synthetic run summary |
| `validation/prefix-repro.txt` | pre-fix reproduction |
| `validation/real-preview.txt` | real preview only |
| `validation/protocol.txt` | protocol/answer-key hashes |
| `validation/archive.txt` | archive verification |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## What is proven

- Campaign approval is revalidated at every experiment dispatch under the same
  lock ordering as revocation and supersession.
- The server campaign content is authoritative; local question, excerpt, URL,
  hash, provider/model, instruction/schema, output-cap and call-order edits are
  refused before provider transport.
- Stage 1 is exactly two calls; stage 2 requires a separate approval after
  durable stage-1 technical eligibility and only covers the remaining sixteen.
- Raw and actual wall-clock timeouts, cancellation and unexpected dispatch
  errors block later calls; no ambiguous attempt is replayed.
- Missing outputs are not successes; rating revisions and archive still work.
- No real approval, paid call or Meta transport occurred.

## Limits

No real provider connectivity, account balance, production structured-output
compatibility, provider settlement reconciliation, semantic truth, human
usefulness, cryptographic human presence, exhaustive cross-route unblinding or
retraction of already-sent data is claimed. The broader $5 budget does not
increase the frozen $0.45 campaign ceiling. The paid pilot remains blocked
pending independent review and separate owner approval.
