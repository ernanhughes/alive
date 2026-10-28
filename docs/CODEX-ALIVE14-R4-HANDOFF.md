# Codex ALIVE-14-R4 handoff

## 1. Repository

- Verified baseline: `ac11be81115f397a9bad9f5c630a74ee22bdc3d2` (ALIVE-14-R3
  merge).
- Branch: `codex/alive-14-r4-pilot-safety`.
- Worktree: `C:\Projects\alive-worktrees\alive-14-r4`.
- Protocol v3 and answer key remain frozen at
  `85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b` and
  `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`.
- Final implementation commit, PR and CI: to be recorded after push.
- The R3 runner refuses real mode; the R4 runner is the only real-execution path.
- No paid Meta inference. No automatic merge or auto-merge.

## 2. Statuses

- **ENGINEERING_PASS**
- **NATIVE_SYNTHETIC_PASS**
- **OWNER_APPROVAL_FLOW_QUALIFIED**
- **META_READY_FOR_OWNER_APPROVAL** (subject to independent review and explicit
  owner approval)
- **NATIVE_META_NOT_RUN**
- **OWNER_USEFULNESS_NOT_MEASURED**

## 3. REVIEW-10 corrections

| Finding | Correction | Evidence |
|---|---|---|
| Explicit owner revocation undone | Permanent `revoked` state, `owner_revoked` history, recovery only from `revoked_restart`, original expiry preserved, final dispatch revalidation | `test_explicit_revocation...`, concurrent/two-restart/expiry tests |
| Systematic provider failure attempts all calls | Code-based error categories and campaign-fatal policy; stop after first fatal attempt | all-401, unsupported-schema, quota tests: exactly 1 call |
| Approval was self-asserted | Campaign registered server-side; owner approves through authenticated native UI; runner re-fetches active approval and rejects files/revoked/superseded records | `test_file_only...`, native campaign approval |
| Rating revisions broke archive | Archive compares distinct output identities | revised-rating test |
| Missing outputs could count as success | Missing/rejected output forced to `supported_useful=false` | missing-output test |
| Misleading results pooled | A/B/C-specific misleading counts | analysis output |
| Failed-cell events revealed condition | Paired events contain only mode/settlement; neutral placeholder text | mixed-failure event test |
| Dispatch start not durable | `dispatch_possibly_started` committed before provider call; no-dispatch zero liability, ambiguous full liability | dispatch-marker test |

## 4. Approval design

The campaign digest is content-only and stable across fresh database
preparations. It excludes random IDs and covers protocol/answer hashes,
provider/model, instruction/schema hashes and every task's goal, question, URLs,
SHA-256s and exact excerpts.

A server-side `research_experiment_approval` record binds:

- campaign digest, run ID and protocol identity;
- provider and pinned model;
- stage, call cap, reserved-token cap, output-token cap and USD cap;
- zero-retry policy;
- owner provenance and human attestation;
- creation/status/revocation timestamps.

A local file is only a pointer. `approve` and `execute` reject a missing,
revoked, superseded or digest-mismatched server record. New stage approvals
supersede prior active approvals for the same campaign.

The effective cap is:

```
min(protocol ceiling, owner-approved max_usd, ALIVE_R4_RUNTIME_USD_CAP)
```

The native panel displays the digest and complete manifest and requires the
attestation checkbox for a real campaign.

## 5. Staged execution

`execute --limit N` counts attempted dispatches, not validated outputs. Stage 1
uses 2 calls; stage 2 uses the remaining 16 after explicit approval. Progress is
durable in `outputs.jsonl` and the attempt inventory. Interrupted attempts are
never replayed. Campaign-fatal errors stop immediately; per-cell evidence
failures are recorded and the next cell continues.

## 6. Provider policy

Fatal: authentication, access denied, invalid request, unsupported schema,
rate limit, quota exhaustion, credentials missing, server error, transient
network, timeout, invalid provider response, ambiguous settlement, cancelled,
unknown.

Cell-level: invalid structured output and output truncation. These are retained
as rejected attempts and do not trigger campaign abort.

## 7. Accounting and blinding

- Missing outputs are not success even if a placeholder receives positive
  ratings; missingness is reported by condition.
- Misleading counts are separated for A, B and C.
- Archive accepts append-only rating revisions and preserves task-level records.
- Pairwise settled/authorized events expose no attempt ID, consent ID, payload
  hash or status during collecting.
- Content-based inference remains possible and is documented.

## 8. Native Chrome

Chrome `155.0.8059.85`, genuine docked side panel:

- campaign list and digest/manifest display;
- stage selector and owner attestation;
- authenticated approval created server-side and shown as active;
- R3 blind-rating/reveal/read-only/restart journey repeated;
- 4 synthetic note calls, 0 paid calls.

Evidence: `archives/ALIVE-14-R4/evidence/native-synthetic.json`,
`native-r4-approval.png`.

## 9. Validation

- Full backend: **215 passed**
- R4 pilot-safety: **13 passed**
- Focused research memory: **52 passed**
- Extension: **11 passed**
- Frontend: **7 passed**
- Build: passed
- Ruff: passed
- R1/R2/R3 archives and protocol hashes: verified
- Native synthetic: `NATIVE_SYNTHETIC_PASS`

## 10. Remaining approvals

1. Independent review of revocation, provider fail-fast, staged execution,
   approval provenance, accounting and blinding.
2. Verify current Meta pricing against the prepared 18-call manifest.
3. Approve stage 1 (2 calls, 10,345 reserved tokens, $0.043967 worst case)
   through the native owner approval flow.
4. After stage 1 technical success, approve stage 2 (cumulative 18 calls,
   92,148 reserved tokens, $0.391635 worst case) within the $0.45 ceiling.
5. Provide `ALIVE_META_API_KEY` only at execution time.

The correct claim remains: the pilot is now gated and locally qualified;
whether historical memory improves usefulness has not been measured.
