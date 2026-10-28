# Codex ALIVE-14-R5-R1 handoff

## Repository and branch

- Repository: `https://github.com/ernanhughes/alive`
- Worktree: `C:\Projects\alive-worktrees\alive-14-r5`
- Branch: `codex/alive-14-r5-approval-integrity`
- Correction base: `7ecc4b77cf01fe4f1102bf34db3b4023107612b2` (merged PR #26)
- Original R5 commits preserved:
  - `ef26935ab346c0e0e916a1d83c84c706f58d3be5`
  - `49a602b9eb9cc0a15cdc100ecd63e81d33a9e7b0`
- R5-R1 code commits:
  - `fe5376df59e83d4e00a27f2077bbd874a18bcd18` - durable campaign state
  - `f378ef4dfe07b7ed7fc650a39b1026a4d41aa782` - native harness async fix
  - `08f2ad11e383244058d4381e12892bfec6f133bc` - panel approval reload and native journey
- The final evidence/docs commit is the branch head after this file.

PR #26 was already merged when R5-R1 started. The assignment's reported
`main=8ae71b9` / open draft PR state was stale. A new PR is required because
GitHub cannot accept new commits on a merged PR. Nothing was force-pushed or
auto-merged.

## Status

- `ENGINEERING_PASS`
- `DURABLE_FATAL_STOP_PASS`
- `CANCELLATION_SETTLEMENT_PASS`
- `ORDERED_DISPATCH_PASS`
- `CANONICAL_MANIFEST_PASS`
- `STAGE_BOUNDARY_PASS`
- `NATIVE_SYNTHETIC_PASS`
- `META_READY_FOR_OWNER_APPROVAL=NOT_READY`
- `NATIVE_META_NOT_RUN`
- `OWNER_USEFULNESS_NOT_MEASURED`

## REVIEW-12 corrections

| Blocker | Correction |
|---|---|
| B1 fatal-stop bypass | Durable campaign `blocked` record written with fatal settlement; checked at preview, authorization, reservation, final marker, stage approval, recovery and runner restart |
| B2 cancellation recovery | Settlement and block commit before `CancelledError` propagation; restart turns reserved attempts into fatal/ambiguous blockers; stage 2 uses a strict settled-outcome allowlist |
| B3 out-of-order calls | Server derives the single next eligible index; checks at preview/authorize/reservation/final marker; deterministic per-cell UUID primary key prevents duplicate reservation |
| B4 display/dispatch divergence | Registration rejects any manifest/content difference and recomputes instruction/schema hashes from server code; panel renders canonical content plus server disclosure |

## Tests

- Full backend: **274 passed, 6 skipped**, recorded at final head in
  `archives/ALIVE-14-R5-R1/evidence/validation/backend.txt`; the six skips are
  historical R4 real/staged tests replaced by R5/R5-R1 coverage
- R5 approval/runner: **13 passed**
- R5-R1 regressions: **31 passed**
- REVIEW-11 corrected regressions: **21 passed**
- Research memory: **52 passed**
- Extension: **11 passed**
- Frontend: **7 passed**
- Production build: passed
- Ruff check/format: passed
- Protocol/answer-key hashes: verified
- R1-R5 archives: 18/16/30/32/36 payloads verified

The independent REVIEW-12 harness is preserved unmodified in
`evidence/test_review12.py`. Its pre-fix output is in
`evidence/review12-prefix.txt`; its post-fix run is in
`evidence/review12-postfix.txt`. Its four unsafe-outcome probes fail after the
fix by design; the corrected outcomes are permanent repository regressions.

## Native qualification

Fresh genuine docked Chrome 156.0.8078.73, isolated synthetic databases, local
deterministic stub only.

- Campaign A: canonical content/disclosure/digest review; stage-2 rejection
  before stage 1; panel stage-1 approval; one CLI dispatch; active approval
  reloaded and revoked in the panel after restart; HTTP and CLI successor paths
  refused; one attempt total.
- Campaign B: canonical content review; stage-2 rejection before stage 1; panel
  stage-1 approval; two CLI stage-1 calls; `stage_1_eligible=true` and
  `stage_2_eligible=true` displayed; separate panel stage-2 approval; sixteen
  CLI calls; rating, reveal, analysis and archive; read-only results after
  restart.

Evidence source commit: `08f2ad11e383244058d4381e12892bfec6f133bc`.
Source tree: `ca2192c8effc50df4e55cf627225c6d146ae409d`.
Git status at run: empty. Paid calls: 0. Real approvals: 0.

Browser-driven: campaign selection, canonical content/disclosure/digest review,
stage selection, stage approvals, revocation, active-approval reload and
read-only archived results.
CLI/backend-driven: one-call revoked campaign dispatch, 2+16 execution, rating,
reveal, analysis and archive.

## Budget

Isolated real preview, no approval and no inference:

| Scope | Calls | Reserved tokens | Liability |
|---|---:|---:|---:|
| Stage 1 | 2 | 10,345 | $0.043967 |
| Full | 18 | 92,148 | $0.391635 |
| Ceiling | 18 | - | $0.45 |

Real campaign digest:
`c11590b43c5b366618ca15153249555f949276e05abe65087295b55514c6b3ff`.

## Evidence

`archives/ALIVE-14-R5-R1/` contains:

- independent REVIEW-12 report and probe;
- pre-fix and post-fix harness transcripts;
- corrected campaign A and campaign B run journals;
- native evidence JSON, backend logs and five screenshots;
- real-mode preview budget and stage contracts;
- full/focused test transcripts, Ruff, protocol, archive and native summaries;
- SHA-256 manifest.

R5 archive remains unchanged. R1-R4 archives remain unchanged.

## Remaining gates

- Push the branch and open a new draft PR against main; PR #26 is merged.
- Run hosted CI on the correction head; add the R5-R1 archive check (done in
  this change).
- Independent reviewer must rerun REVIEW-11 and REVIEW-12, including fatal
  restart, cancellation settlement, ambiguous recovery, ordering/concurrency and
  native evidence.
- No owner approval may be offered until that review passes and the owner
  separately authorizes a stage.
- Real Meta connectivity, production structured-output compatibility, provider
  settlement reconciliation, human usefulness and cryptographic human presence
  remain unproven.

The paid pilot remains blocked.
