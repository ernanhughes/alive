# ALIVE-14-R5-R1 - Durable campaign state and canonical approval integrity

Status: **ENGINEERING_PASS**, **DURABLE_FATAL_STOP_PASS**,
**CANCELLATION_SETTLEMENT_PASS**, **ORDERED_DISPATCH_PASS**,
**CANONICAL_MANIFEST_PASS**, **STAGE_BOUNDARY_PASS**,
**NATIVE_SYNTHETIC_PASS**, **META_READY_FOR_OWNER_APPROVAL=NOT_READY**,
**NATIVE_META_NOT_RUN**, **OWNER_USEFULNESS_NOT_MEASURED**.

Correction base: `7ecc4b77cf01fe4f1102bf34db3b4023107612b2` (merged PR #26).
The original R5 commits are preserved unchanged. R5-R1 is a separate correction
on `codex/alive-14-r5-approval-integrity`; PR #26 was already merged, so a new
PR is required.

No real campaign approval, Meta transport, live credential, paid inference,
merge or auto-merge occurred during this qualification.

## Contents

| Path | Meaning |
|---|---|
| `evidence/ALIVE-REVIEW-12.md` | independent controlling REVIEW-12 report |
| `evidence/test_review12.py` | independent pre-fix probe harness |
| `evidence/review12-prefix.txt` | reproduced pre-fix unsafe outcomes |
| `evidence/review12-postfix.txt` | same harness against R5-R1 (unsafe assertions fail) |
| `evidence/campaign-a-run/` | revoked-after-one-dispatch campaign journals |
| `evidence/campaign-b-run/` | complete 2+16 campaign state, outputs and analysis |
| `evidence/campaign-b-archive/` | archived blind run and result payloads |
| `evidence/native-synthetic.json` | fresh docked Chrome A/B journey |
| `evidence/native-campaign-a-stage1-approval.png` | panel stage-1 approval, campaign A |
| `evidence/native-campaign-a-revoked.png` | panel revocation, campaign A |
| `evidence/native-campaign-b-stage1-approval.png` | panel stage-1 approval, campaign B |
| `evidence/native-campaign-b-stage2-approval.png` | separate stage-2 approval after eligibility |
| `evidence/native-campaign-b-readonly.png` | read-only archived results after restart |
| `evidence/native-campaign-a-backend.log` | isolated campaign A backend log |
| `evidence/native-campaign-b-backend.log` | isolated campaign B backend log |
| `evidence/real-preview.json` | real-mode preview only; not an approval |
| `evidence/validation/backend.txt` | full backend suite |
| `evidence/validation/r5-r1.txt` | R5-R1 regressions |
| `evidence/validation/r5.txt` | R5 approval/runner tests |
| `evidence/validation/review11-corrected.txt` | REVIEW-11 corrected outcomes |
| `evidence/validation/research-memory.txt` | focused research-memory suite |
| `evidence/validation/extension.txt` | extension tests |
| `evidence/validation/frontend.txt` | frontend tests |
| `evidence/validation/build.txt` | production build |
| `evidence/validation/ruff.txt` | lint/format |
| `evidence/validation/protocol.txt` | protocol and answer-key hashes |
| `evidence/validation/archives.txt` | R1-R5 archive verification |
| `evidence/validation/native.txt` | native status, source identity and scope |
| `evidence/validation/real-preview.txt` | real budget and stage contracts |
| `manifest.json` | SHA-256 and byte length for every payload except itself |

## What is proven

- A durable campaign block written with a fatal settlement prevents all later
  backend, runner and restart dispatch, and survives approval revocation or
  supersession.
- Cancellation settlement and the campaign block commit before cancellation is
  re-raised; ambiguous/interrupted attempts cannot unlock stage 2.
- The server derives and enforces the single next eligible call index; a
  deterministic per-cell primary key prevents duplicate reservation across
  clients.
- Registration rejects display/manifest divergence and verifies instruction and
  schema hashes against server code. The panel renders the canonical content and
  a server-derived disclosure.
- Stage 1 is exactly two calls; stage 2 is a separate approval for the remaining
  sixteen cells after durable technical eligibility.
- The synthetic 2+16 lifecycle, rating revision, reveal, analysis and archive
  still work.
- No real approval or paid call was created.

## Budget

| Scope | Calls | Reserved tokens | Liability |
|---|---:|---:|---:|
| Stage 1 | 2 | 10,345 | $0.043967 |
| Full | 18 | 92,148 | $0.391635 |
| Ceiling | 18 | - | $0.45 |

Real campaign digest:
`c11590b43c5b366618ca15153249555f949276e05abe65087295b55514c6b3ff`.

## Native scope

Browser-driven: campaign selection, canonical content/disclosure/digest review,
stage selection, stage approvals, active-approval reload, revocation and
read-only archived results.

CLI/backend-driven: one-call revoked campaign dispatch, 2+16 execution, rating,
reveal, analysis and archive.

The native evidence records source commit
`08f2ad11e383244058d4381e12892bfec6f133bc`, source tree
`ca2192c8effc50df4e55cf627225c6d146ae409d`, a runtime source fingerprint and an
empty git status.

## Limits

No real provider connectivity, account balance, production structured-output
compatibility, provider settlement reconciliation, semantic truth, human
usefulness, cryptographic human presence, exhaustive cross-route unblinding
protection or retraction of already-transmitted data is claimed. The system is
not a distributed transaction with the external provider; a crash inside
transport remains ambiguously billable and is treated conservatively. The paid
pilot remains blocked pending a new independent review.
