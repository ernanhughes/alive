# ALIVE-14-R5-R1 - Durable campaign state and canonical approval integrity

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

R5-R1 is a correction to the already-merged R5 package. It does not change
protocol v3, the answer key, the task corpus, the rubric, the pinned model, the
stage budgets or the `$0.45` campaign ceiling.

## Repository state and PR reconciliation

The assignment described PR #26 as an open draft at `49a602b9` with main at
`8ae71b9`. That state was already stale when this correction started:

- `origin/main` was `7ecc4b77cf01fe4f1102bf34db3b4023107612b2`, the merge of
  PR #26;
- `49a602b9` is an ancestor of that merge and is already on main;
- PR #26 is `MERGED`.

The two original R5 commits were not rewritten or force-pushed. R5-R1 commits
continue on `codex/alive-14-r5-approval-integrity` and require a new PR because
GitHub does not permit new commits to a merged PR. Nothing was merged or
auto-merged during this correction.

## The controlling invariant

> The next experiment dispatch is permitted only when the server's durable
> campaign state, active approval, exact canonical content, next-call index and
> cumulative limits all permit it at the final dispatch barrier.

Local `state.json`, `approval.json`, output journals and local hash maps are
progress and display caches. They cannot authorize, reorder, retry or unblock a
campaign.

## REVIEW-12 blockers and corrections

### B1 - fatal-stop bypass

**Pre-fix reproduction.** A valid two-call stage-1 approval dispatched index 0
with a synthetic 401. The attempt recorded `campaign_fatal=true`, but the
authenticated backend still accepted index 1 and invoked the provider stub
again. A simulated process exit after the fatal settlement also allowed the
ordinary runner to recover the fatal attempt and dispatch the next cell.

Pre-fix evidence: `archives/ALIVE-14-R5-R1/evidence/review12-prefix.txt`.

**Correction.**

- The campaign row now carries a durable `blocked` object with reason,
  category, attempt identity and timestamp. The first block is never cleared.
- Fatal settlement writes the attempt outcome and the campaign block in the same
  transaction. A restart reads the server block.
- Reservation, authorization, the final dispatch marker, stage approval,
  recovery and the ordinary runner all refuse a blocked campaign.
- Superseding or revoking the stage approval cannot erase the campaign block.
- A fatal attempt always retains conservative liability when dispatch possibly
  started; a reservation that never dispatched settles at zero liability.

### B2 - cancellation recovery

**Pre-fix reproduction.** Cancellation was re-raised inside the settlement
transaction, so SQLAlchemy rolled the settlement back. The attempt remained
`reserved`; restart marked it `interrupted` with liability but no fatal flag;
stage-2 eligibility accepted the two non-reserved rows and a new stage-2
approval could dispatch index 2.

**Correction.**

- Cancellation is normalized as a campaign-fatal experiment outcome.
- The attempt settlement and the campaign block commit before
  `asyncio.CancelledError` is re-raised outside the transaction context.
- Restart recovery marks any reserved experiment attempt `interrupted`, records
  `campaign_fatal` when a possible dispatch occurred, retains the full
  reservation liability, and blocks the campaign.
- Stage-2 eligibility uses an explicit allowlist: exactly two distinct stage-1
  attempts at indices 0 and 1, both settled as `validated` or `rejected`, at
  least one `validated`, no fatal/ambiguous/interrupted/outstanding attempt, and
  no campaign block.
- A cancellation that rolls the settlement back still fails closed on restart:
  the reservation becomes an interrupted ambiguous attempt and the campaign is
  blocked. No ambiguous attempt is replayed.

### B3 - out-of-order execution

**Pre-fix reproduction.** With a valid stage-1 approval, an index-1/B request
was accepted before index 0 and reached the provider stub with historical
evidence.

**Correction.**

- The server derives the next eligible index from durable attempt history.
- A request must equal that index; all earlier indices must be settled; a later
  index may not overtake a missing or unresolved lower index; duplicate indices
  are rejected.
- The check runs before reservation, before authorization and again at the
  final dispatch marker.
- Experiment attempts receive a deterministic UUIDv5 primary key derived from
  campaign digest and call index. The database primary key rejects duplicate
  reservation even across independent backend instances that do not share the
  process-local kernel lock.
- Stage 1 starts at 0; stage 2 starts at 2 only after stage-1 eligibility.
  Cross-stage and out-of-order requests are refused.

### B4 - displayed versus dispatched content

**Pre-fix reproduction.** Registration accepted a canonical `content` object and
a separate `manifest` whose first question differed. The native panel rendered
`manifest`; dispatch used `content`.

**Correction.**

- Registration compares every overlapping substantive field of `manifest` with
  `content`: tasks, call order, cells, task order, provider/model, instructions
  and schema hashes, output cap and scalar identities. Unknown display fields are
  rejected.
- The server normalizes the durable display manifest from the canonical content;
  local payload hashes are not stored as approved research content.
- The server recomputes instruction and response-schema hashes from its own
  code. A client cannot supply a self-consistent but different instruction or
  schema hash.
- The native panel renders `content` and a server-derived `disclosure` containing
  the actual instruction text and response schema, alongside the digest,
  protocol/answer-key hashes, output cap, stage definitions and limits.
- The provider-bound payload is compared field-for-field with the registered
  cell before the dispatch marker. Captured synthetic provider input matches the
  approved canonical cell.

## Durable state machine

Campaign lifecycle:

```text
registered
  -> approval_active
  -> dispatch_authorized (reservation)
  -> dispatch_possibly_started (marker committed)
  -> provider_response_received / settled
  -> stage_complete_technical
  -> awaiting_owner_stage_approval
  -> ...
  -> campaign_blocked_fatal   (terminal for ordinary execution)
```

The following are durable and authoritative in the server database:

- campaign digest and canonical content;
- stage contracts and cumulative limits;
- active/revoked/superseded approval status;
- the deterministic per-cell attempt key;
- attempt dispatch state, settlement and conservative liability;
- the campaign block object;
- the next eligible index derived from attempts.

## Failure policy

Campaign-fatal for experiment dispatch:

- raw `TimeoutError` and actual `asyncio.timeout` expiry;
- cancellation before or after the dispatch marker;
- permission, approval, stage, source, manifest, provider or model mismatch;
- authentication, access denied, quota, rate limit, invalid request/schema;
- provider/server failure;
- transport ambiguity and malformed provider JSON with uncertain settlement;
- unexpected runtime exceptions;
- authorization/attempt-key consumption or duplicate reservation failures.

Continuation allowlist after a settled provider response:

- evidence quotation validation failure, recorded as a rejected cell;
- semantically insufficient evidence, recorded as an abstained/rejected cell;
- permitted structured-content rejection where settlement is known.

`reserved_never_dispatched` settles at zero liability. A possibly started or
ambiguous attempt retains the full conservative reservation and is never
replayed.

## Qualification

| Check | Result |
|---|---|
| Full backend suite | 274 passed, 6 skipped; `evidence/validation/backend.txt` |
| R5 approval/runner | 13 passed |
| R5-R1 regressions | 31 passed |
| REVIEW-11 corrected regressions | 21 passed |
| Research memory | 52 passed |
| Extension | 11 passed |
| Frontend | 7 passed |
| Production build | passed |
| Ruff check/format | passed |
| Protocol v3 hash | `85fe891c...b5a71b` verified |
| Answer-key hash | `255e706d...b43d` verified |
| R1/R2/R3/R4/R5 archives | 18/16/30/32/36 payloads verified |

The full backend transcript is generated at final head in
`archives/ALIVE-14-R5-R1/evidence/validation/backend.txt`. The six skips are the
historical R4 real/staged tests whose safe outcomes are replaced by R5 and R5-R1
coverage; no new test is skipped.

### Permanent R5-R1 regressions

`tests/test_alive14r5_r1.py` covers:

- backend fatal 401 blocks the next cell and the ordinary restart;
- runner crash after fatal settlement does not dispatch the successor;
- cancellation settlement commits and blocks stage 2;
- interrupted/ambiguous reservations block stage 2 and retain conservative
  liability across all crash windows;
- index 1 before index 0 is refused with zero provider calls;
- concurrent same-index attempts produce at most one attempt and one dispatch;
- a later index cannot overtake a missing lower index;
- a separate client cannot replay a settled cell;
- stage 2 cannot dispatch index 3 before index 2;
- all tested manifest/content divergences are rejected at registration;
- the registered display equals the canonical content;
- the server disclosure matches the exact instruction and schema;
- client-recomputed instruction hashes are rejected;
- identical canonical re-registration is accepted;
- campaign state exposes technical stage eligibility without blinded outputs.

The independent REVIEW-12 harness is preserved unmodified. Against R5-R1 its
four unsafe-outcome probes fail because they assert the old behavior; the
corrected outcomes are asserted by the repository regressions.

### Native qualification

Fresh genuine docked Chrome 156.0.8078.73 side panels, isolated synthetic
databases, local deterministic stub only:

- Campaign A: canonical content/disclosure/digest review; stage-2 rejection
  before stage 1; panel stage-1 approval; one CLI dispatch; approval reload and
  revocation in the panel after restart; HTTP and CLI successor paths refused;
  attempt count remained one.
- Campaign B: canonical content review; stage-2 rejection before stage 1; panel
  stage-1 approval; two CLI stage-1 calls; technical state showed
  `stage_1_eligible=true` and `stage_2_eligible=true`; separate panel stage-2
  approval; sixteen CLI calls; synthetic rating, reveal, analysis and archive;
  read-only blind results after restart.

Browser-driven: campaign selection, content/disclosure/digest review, stage
selection, stage-1/stage-2 approval, active-approval reload, revocation, and
read-only archived results.

CLI/backend-driven: the 1-call revoked campaign dispatch, 2+16 execution,
rating, reveal, analysis and archive.

Native evidence records source commit
`08f2ad11e383244058d4381e12892bfec6f133bc`, source tree
`ca2192c8effc50df4e55cf627225c6d146ae409d`, the runtime source fingerprint and
an empty git status. The final evidence/docs commit does not change runtime code.

## Budget

Unchanged, recomputed from an isolated real-mode preview with no approval:

| Scope | Calls | Reserved tokens | Conservative liability |
|---|---:|---:|---:|
| Stage 1 | 2 | 10,345 | $0.043967 |
| Full campaign | 18 | 92,148 | $0.391635 |
| Protocol ceiling | 18 | - | $0.45 |

Real campaign digest:
`c11590b43c5b366618ca15153249555f949276e05abe65087295b55514c6b3ff`.

The `$5` project budget does not raise the `$0.45` campaign ceiling.

## Preservation

- Protocol v3 and answer-key files are byte-identical.
- R1-R5 archives verify at 18/16/30/32/36 payloads.
- No historical R5 archive file was rewritten.
- R5-R1 has a separate archive and SHA-256 manifest.
- No real campaign approval was created.
- No Meta transport or paid inference occurred.
- No merge, auto-merge or force-push occurred.

## Remaining limitations

No real provider connectivity, account balance, production structured-output
compatibility, provider-side settlement reconciliation, semantic truth, human
usefulness, cryptographic proof of human presence, exhaustive cross-route
unblinding protection or retraction of already-transmitted data is claimed. The
process-local kernel lock is supplemented by a deterministic database primary
key for cell uniqueness, but the system is not a distributed transaction with
the external provider. A crash inside provider transport remains an ambiguous
possibly-billed event and is treated conservatively.

The paid pilot remains blocked. A new independent review must reproduce
REVIEW-11 and REVIEW-12, including fatal/restart, cancellation, ordering,
manifest equality and native evidence, before any owner approval is offered.
