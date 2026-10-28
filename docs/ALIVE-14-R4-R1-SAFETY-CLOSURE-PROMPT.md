# ALIVE-14-R4-R1 — Paid-Pilot Safety Closure

## Copy-ready implementation prompt

### 1. Your role

You are the lead safety engineer, backend architect, adversarial test engineer, and evidence author for ALIVE-14-R4-R1.

Your task is to correct four independently reproduced safety failures in the merged R4 paid-pilot implementation. Produce working code, strict server-side enforcement, deterministic synthetic evidence, regression tests, a fresh synthetic native-panel qualification where the environment permits it, and an auditable handoff.

Do not stop at a proposal. Inspect the actual repository, reproduce the four failures against the baseline, implement the smallest coherent correction, run the complete local qualification, and report limitations honestly.

This is a paid-execution safety milestone. Fail closed. Do not optimize for reaching the pilot. Optimize for making an unauthorized, mutated, over-cap, revoked, superseded, or uncertain dispatch impossible.

### 2. Repository and starting point

Repository:

```text
https://github.com/ernanhughes/alive
```

Expected merged baseline:

```text
main = 8ae71b967fe92ae43ca8baa24d382b74d5435044
PR #25 = merged
R4 source head = 689f192621709a925bba0c3e44f399c99e629b0e
R4 implementation commit = 4bdefea1bb0eb198d06db2b0518d6f13d1f7d6ad
```

Before editing:

1. Fetch the repository and verify the actual remote `main` commit and tree.
2. If `main` has advanced, inspect every intervening commit and report whether it changes `alive/`, `scripts/`, `tests/`, `extension/`, the protocol, or the R1–R4 archives.
3. Read all applicable repository-local instructions completely.
4. Inspect the working tree. Preserve unrelated user changes.
5. Do not reuse a dirty shared checkout.
6. Create an isolated worktree and branch:

```text
branch: codex/alive-14-r4-r1-safety-closure
suggested worktree: C:\Projects\alive-r4-r1
```

Do not work directly on `main`.

### 3. Authoritative failed gate

Treat ALIVE-REVIEW-11 as the controlling safety assessment.

Its disposition is:

```text
A. Engineering integrity: FAIL
B. Stage 1 approval readiness: NOT READY
C. Two-stage 18-call campaign: NOT READY
```

Four blockers were independently reproduced using synthetic campaigns:

1. revoking campaign approval after call 1 still permitted call 2;
2. edited local question/hash state bypassed the approved server content binding;
3. the authenticated server accepted `stage=1` with an 18-call cap;
4. an unwrapped Python `TimeoutError` allowed later dispatch.

The existing 215-test backend pass is baseline evidence, not a safety pass. Preserve all passing behavior while closing these failures.

### 4. Frozen protocol and protected evidence

The protocol and answer key are frozen:

```text
protocol v3 SHA-256:
85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b

sealed answer-key SHA-256:
255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d
```

Do not change:

- the scientific questions;
- answer-key contents;
- task order;
- A/B condition assignment or blinding design;
- pinned provider/model unless a separate owner-approved protocol revision is created;
- zero-retry policy;
- the full 18-call protocol ceiling;
- archived R1–R4 evidence in place.

Verify R1–R4 archives before and after implementation. Earlier archive trees must remain byte-identical unless the repository already has an explicit append-only correction mechanism. Prefer a new R4-R1 evidence record rather than rewriting historical evidence.

### 5. Absolute safety restrictions

During this milestone:

- do not create a real pilot approval;
- do not execute Meta inference;
- do not use live provider credentials;
- do not inspect, print, copy, or repurpose a real API key;
- do not make paid calls;
- do not approve Stage 1 or Stage 2 for the real campaign;
- do not claim owner approval readiness;
- do not claim native qualification unless a fresh genuine docked-panel synthetic journey actually completes;
- do not change billing, GitHub Actions, repository settings, branch protection, secrets, or spending limits;
- do not push, open a PR, merge, enable auto-merge, or trigger hosted CI without explicit subsequent authorization.

Run with `ALIVE_META_API_KEY` absent. Tests may inject a clearly fake value only while the actual provider transport is replaced by a deterministic stub and network egress is impossible.

### 6. Scope discipline

Implement only the four targeted corrections and the tests/evidence needed to qualify them:

1. server-authoritative immutable content binding;
2. per-dispatch campaign-approval revalidation with race-safe revocation/supersession;
3. server-enforced stage contracts and durable stage progression;
4. fail-closed timeout, cancellation, unexpected-exception, and ambiguous-dispatch handling.

Do not redesign the entire experiment platform. Do not change the research hypothesis, scoring rubric, provider, model, or frozen protocol.

The first three blockers share one trust boundary and should be corrected through one coherent **server-authoritative dispatch authorization** design. Do not implement three local runner checks that can disagree or race.

### 7. Required architecture: server-authoritative campaign manifest

The immutable server campaign record must be the source of truth for every dispatchable cell.

Local `state.json`, `approval.json`, preview files, and hash maps are not approval authorities. They may contain pointers, caches, progress, and display data only.

#### 7.1 Strict manifest contract

Replace loose trust in arbitrary `dict` manifest content with strict, versioned models or an equivalently fail-closed schema.

The canonical registered campaign must bind at least:

- schema/protocol version;
- campaign digest;
- run identity;
- protocol and answer-key hashes;
- provider and exact model;
- instruction text or instruction SHA-256;
- response schema and schema SHA-256;
- validator version;
- task order;
- condition/cell order without exposing blind labels to the rating interface;
- each task ID and stable cell ID;
- goal identity and goal text/hash as applicable;
- research question text and hash;
- current/historical source URLs;
- exact approved excerpts;
- source SHA-256 values;
- current snapshot and historical-memory identities where applicable;
- expected payload and request identities;
- reserved input/output/total tokens by cell;
- conservative cost reservation by cell;
- no-retry policy;
- registered stage definitions;
- full campaign caps;
- synthetic versus real mode;
- provenance and registration time.

Reject unknown fields where practical. Reject malformed, missing, duplicate, out-of-order, or inconsistent cells.

#### 7.2 Server recomputation

The server must recompute the canonical campaign digest from the received immutable manifest. It must reject a client-supplied digest that does not match.

Registration must reject:

- an existing digest with different manifest content;
- the same run ID bound to conflicting content;
- a protocol/answer hash mismatch;
- invalid provider/model identity;
- stage definitions inconsistent with the manifest totals;
- task/cell counts inconsistent with the call cap;
- payload/request hashes inconsistent with canonical content.

Do not trust the client merely because it supplies matching hash strings.

#### 7.3 Actual dispatch reconstruction

Immediately before dispatch, construct or validate the actual provider request against the immutable server manifest.

The binding must cover the actual:

- question;
- current and historical excerpts;
- source identities and hashes;
- goal/task identity;
- instructions;
- output schema;
- provider;
- model;
- mode/condition semantics;
- protocol and run identities.

A digest-generation helper alone is insufficient. The final provider input must either be reconstructed from server-authoritative data or compared field-for-field and canonically hashed against the registered cell.

Edited local state must never be able to redefine what was approved.

### 8. Server-authoritative dispatch authorization

Introduce a server-side dispatch authorization/lease or equivalent durable record that binds one approved campaign cell to one provider attempt.

The exact API shape may follow the existing architecture, but every dispatch must bind:

- approval ID;
- approval database row identity;
- campaign digest and campaign row identity;
- run ID;
- stage;
- stable cell ID and ordinal;
- consent/preview ID;
- canonical payload SHA-256;
- canonical request SHA-256;
- provider/model;
- token and cost reservation;
- no-retry policy;
- issue/consumption timestamps;
- dispatch state;
- attempt ID once created.

The authorization must be single-use. Reusing it, changing its consent, changing its hashes, or binding it to another attempt must fail.

Local files may store the authorization ID as a pointer. They must not be able to manufacture its authority.

### 9. Atomic per-dispatch approval barrier

The runner's one-time approval fetch before the loop is insufficient. Revalidate the campaign approval for every new dispatch.

Immediately before committing `dispatch_possibly_started`, under the same lock/transaction ordering used by revocation and supersession, verify:

- approval exists;
- approval identity matches the dispatch authorization;
- status is exactly `active`;
- it is not revoked;
- it is not superseded;
- it is not expired if expiry is supported;
- campaign digest and row identity match;
- run ID and protocol identity match;
- stage matches;
- cell belongs to that stage;
- cell has not previously been attempted or consumed;
- stage/campaign call cap remains available;
- token cap remains available;
- USD cap remains available;
- durable ledger and governor permit the reservation;
- source snapshots/grants are still valid;
- actual request identity matches the immutable manifest;
- no-retry policy remains true.

Only after this check may the attempt cross the durable dispatch boundary.

#### 9.1 Race semantics

Define and test a precise ordering rule:

- if revocation/supersession commits before the dispatch-start transaction, dispatch is refused;
- if the dispatch-start marker commits first, the call is treated as possibly in flight and later revocation cannot retract it;
- a sent or possibly sent call retains settlement and conservative liability;
- revocation prevents every later cell.

Use deterministic concurrency tests with barriers/events to force both orderings. Do not rely on timing sleeps.

#### 9.2 Durable state

Record the approval and dispatch-authorization identities on the attempt row. They must remain auditable through settlement, restart, analysis, and archive.

The final dispatch guard must live in the backend path that commits the dispatch marker. A runner-only check is not sufficient.

### 10. Stage contract enforcement

The server must validate approval requests against the immutable registered stage definitions, not only campaign-wide ceilings.

#### 10.1 Strict stage schema

Replace or validate the loose `stages: dict` with a strict stage contract containing at least:

- stage number and stable stage ID;
- cumulative or incremental semantics, stated explicitly;
- allowed cell ordinals;
- call cap;
- input/output/total token limits;
- maximum USD liability;
- prior-stage prerequisites;
- technical eligibility criteria;
- no-retry requirement;
- whether human attestation is required.

For the frozen campaign, preserve the intended lifecycle:

```text
Stage 1: first 2 calls only
Stage 2: remaining 16 calls after a separate approval
Full cumulative ceiling: 18 calls
```

If the existing protocol expresses Stage 2 as cumulative cap 18, preserve that representation but enforce that only the remaining 16 cells are dispatchable after two valid Stage 1 attempts. Document incremental versus cumulative accounting unambiguously.

#### 10.2 Approval-time enforcement

The authenticated server must reject:

- `stage=1, call_cap=18`;
- unknown stages;
- stage/cap combinations not present in the registered campaign;
- token or dollar caps beyond the registered stage;
- caps too low to cover the approved cells if the policy requires complete-stage approval;
- Stage 2 approval before Stage 1 eligibility;
- a stage approval bound to another run/campaign/protocol;
- a stale or superseded stage definition.

Do not rely on selector UI values.

#### 10.3 Stage 2 eligibility

Define a strict durable technical gate. At minimum Stage 2 must not be approvable unless:

- the two registered Stage 1 cells were attempted in frozen order;
- their attempt identities are distinct;
- both have durable settlement records;
- no campaign-fatal error occurred;
- no ambiguous/unresolved dispatch remains;
- the campaign is not blocked;
- the ledger is settled conservatively;
- Stage 1 used the correct approval and manifest;
- protocol/run/campaign identities still match;
- a Stage 1 technical-outcome record has been committed;
- the owner performs a new explicit Stage 2 approval action after that outcome exists.

Human usefulness or scientific success is not automatically implied by technical eligibility. Preserve that distinction.

#### 10.4 Dispatch-time enforcement

Recheck stage identity and remaining stage capacity at the atomic dispatch barrier. Approval-time validation alone is insufficient.

### 11. Fail-closed exception policy

The current fallback `campaign_fatal = bool(getattr(exc, "campaign_fatal", False))` is unsafe. Unknown exceptions must not default to continuation.

Create one explicit exception-normalization policy used by the backend and runner.

#### 11.1 Default policy

Default unexpected exceptions to campaign-fatal.

Campaign-fatal categories must include at least:

- Python `TimeoutError`;
- `asyncio.TimeoutError`/expired `asyncio.timeout(...)` context;
- cancellation during or after dispatch authorization;
- authentication/access failures;
- quota and rate limits under zero-retry policy;
- unsupported or invalid request/schema;
- provider/server failures;
- malformed provider response where settlement is uncertain;
- network/transport errors;
- ambiguous settlement;
- unexpected exceptions;
- approval, stage, manifest, source, provider, or model mismatch;
- authorization/lease consumption failure.

#### 11.2 Explicit continuation allowlist

Continuation may occur only for explicitly enumerated, documented cell-level outcomes that are safe after a settled provider response, such as:

- evidence quotation validation failure;
- semantically insufficient evidence;
- permitted structured-output content rejection where settlement is known and the protocol explicitly allows recording a rejected cell.

Do not infer nonfatal status merely because an exception lacks metadata.

Keep invalid provider JSON, uncertain transport, timeouts, cancellation, and unexpected exceptions fatal unless the protocol explicitly proves otherwise.

#### 11.3 Cancellation handling

`asyncio.CancelledError` may require special handling because it is a `BaseException` in supported Python versions.

On cancellation:

1. durably settle or mark the attempt according to the dispatch marker;
2. mark the campaign blocked/fatal;
3. retain full conservative liability if dispatch possibly started;
4. prevent later dispatch and ordinary restart continuation;
5. re-raise cancellation after durable finalization so task cancellation semantics are preserved.

Use shielding only for the minimal durable finalization block. Do not swallow process cancellation indefinitely.

#### 11.4 Liability

Preserve the established distinction:

- `reserved_never_dispatched` → zero liability;
- `dispatch_possibly_started` without confirmed settlement → full conservative reservation liability;
- confirmed usage → recorded usage subject to conservative rules;
- never automatically replay an ambiguous attempt.

### 12. Runner behavior

Update `scripts/alive14r4_experiment.py` so it:

- treats local state as cache/pointers, not authority;
- obtains server-authoritative cell/dispatch data;
- requests or consumes one server dispatch authorization per cell;
- stops immediately when approval is revoked/superseded or stage capacity is exhausted;
- records blocked state durably;
- does not continue after fatal timeout/cancellation/unexpected errors;
- cannot use local hash-map edits to legitimize changed content;
- never replays prior or ambiguous attempts;
- accurately counts attempted, settled, blocked, remaining, and undispatched cells;
- preserves already completed output and progress records;
- refuses ordinary restart of a campaign blocked by a fatal safety event.

Do not merely refetch approval once per outer task if two conditions/calls can occur inside it. Revalidate every dispatchable cell.

### 13. API and panel behavior

The authenticated API is the enforcement boundary. The panel is a presentation and owner-action surface, not a security boundary.

Update the panel only as required to display server-authoritative information:

- immutable campaign digest;
- exact stage definition;
- stage eligibility;
- call/token/USD limits;
- provider/model;
- technical outcome from Stage 1;
- active/revoked/superseded status;
- attestation requirement;
- explicit explanation that Stage 2 requires a separate action.

Even a manually forged HTTP request or modified panel state must be rejected by the backend.

Do not add a real approval or live-run button path beyond the existing frozen design. The real pilot remains blocked pending independent review.

### 14. Required reproduction-first workflow

Before implementing each correction, add or import a focused test that reproduces the unsafe baseline behavior.

Preserve the original ALIVE-REVIEW-11 probe outputs externally as historical evidence. In the repository, convert the unsafe observations into regression assertions for the corrected behavior.

The four primary tests must demonstrate:

1. **revocation:** after call 1 settles and campaign approval is revoked through the authenticated endpoint, the runner requests no call 2;
2. **content binding:** changing local question, excerpt, instructions, schema, provider, model, or hash maps cannot change the server-approved request;
3. **stage cap:** authenticated `stage=1, call_cap=18` is rejected before approval creation;
4. **timeout:** an actually expiring `asyncio.timeout(...)` around an awaiting stub produces one fatal attempt at most and no later dispatch.

Do not write tests that merely call the classifier directly. Exercise the real server/runner boundary.

### 15. Adversarial regression matrix

Add tests covering at least the following.

#### 15.1 Approval lifecycle

- approval revoked before first dispatch → zero calls;
- approval revoked after call 1, before call 2 authorization → one call total;
- revocation wins deterministic dispatch race → no new dispatch;
- dispatch marker wins race → one possibly-in-flight call retained, no later calls;
- superseded approval before next dispatch → no next call;
- expired approval if supported → no dispatch;
- approval from another campaign → rejected;
- approval from another run → rejected;
- approval from another protocol → rejected;
- stale approval pointer → rejected;
- forged local approval → rejected;
- capability reuse or dispatch-authorization reuse → rejected;
- repeated revocation → idempotent.

#### 15.2 Manifest and request binding

- local question edit;
- current excerpt edit;
- historical excerpt edit;
- source URL edit;
- source SHA edit;
- goal/task edit;
- instructions edit;
- output schema edit;
- provider edit;
- model edit;
- condition/research-memory edit;
- task-order edit;
- cell-order edit;
- local payload-hash edit;
- local request-hash edit;
- registered manifest mutation attempt;
- same digest with different manifest;
- same run ID with conflicting content;
- server recomputation mismatch.

Every case must fail before provider transport or use the immutable approved content. No local edit may silently redefine the approved request.

#### 15.3 Stage enforcement

- Stage 1 cap 18 rejected;
- Stage 1 token/USD cap beyond registered limit rejected;
- unknown stage rejected;
- Stage 2 before Stage 1 rejected;
- Stage 2 after only one Stage 1 attempt rejected;
- Stage 2 after fatal Stage 1 error rejected;
- Stage 2 with unresolved ambiguous settlement rejected;
- Stage 2 after valid two-call technical completion allowed synthetically;
- stage identity changed between approval and dispatch rejected;
- cumulative call cap cannot exceed 18;
- separate Stage 2 approval dispatches only the remaining 16;
- repeated execution under the same consumed stage approval adds no calls;
- cell order remains frozen.

#### 15.4 Fatal errors

- wrapped provider timeout;
- built-in `TimeoutError`;
- actual `asyncio.timeout(...)` expiry while awaiting stub provider;
- `asyncio.CancelledError` before dispatch marker;
- cancellation after dispatch marker;
- unexpected runtime exception before dispatch;
- unexpected runtime exception after dispatch marker;
- network/transport ambiguity;
- malformed provider response;
- 400/401/402/403/404/422/429/5xx categories;
- explicit allowed evidence-validation rejection continues only where documented;
- blocked campaign cannot resume through ordinary execution;
- no automatic retry or replay.

#### 15.5 Accounting and preservation

- never-dispatched zero liability;
- ambiguous full-reservation liability;
- settled usage preserved;
- effective cap remains `min(protocol, owner approval, runtime cap)`;
- local state cannot raise caps;
- output journals remain append-only;
- revision-aware ratings/archive still pass;
- missing output never becomes supported/useful;
- misleading counts remain separated by A/B/C;
- collecting view remains blind under failures;
- archive retrieval and verification still pass.

### 16. Concurrency and transaction requirements

Use deterministic concurrency primitives in tests. Avoid flaky sleeps.

Verify transaction ordering for:

- approval revocation versus dispatch authorization;
- approval supersession versus dispatch authorization;
- two runners attempting the same cell;
- two approval requests for the same campaign;
- Stage 2 approval concurrent with Stage 1 settlement;
- source/grant withdrawal versus dispatch;
- restart recovery versus revocation.

The invariants must hold after process restart, not only in memory.

Where the current architecture uses a process-local kernel lock, inspect whether database-level row locking or unique constraints are needed to preserve the invariant across multiple sessions/processes. Implement the smallest durable mechanism justified by the deployment model and document its boundary.

### 17. Database and migration discipline

If new durable fields or record kinds are required:

- use additive schema/data changes;
- preserve existing R4 rows and archive readability;
- add uniqueness constraints where they enforce single-use authorization or cell attempts;
- provide migration/default behavior for old synthetic records;
- fail closed for legacy records missing required real-execution bindings;
- do not silently upgrade a historical local approval into a valid server approval;
- record schema/version identifiers in new campaign, stage, approval, dispatch, and outcome records.

### 18. Evidence and status taxonomy

Use explicit statuses such as:

- `registered`;
- `approval_active`;
- `approval_revoked`;
- `approval_superseded`;
- `dispatch_authorized`;
- `dispatch_possibly_started`;
- `provider_response_received`;
- `settled`;
- `rejected_cell_output`;
- `campaign_blocked_fatal`;
- `stage_complete_technical`;
- `stage_ineligible`;
- `awaiting_owner_stage_approval`;
- `real_pilot_not_authorized`.

Do not overload `failed`, `approved`, or `complete` across different layers.

At milestone completion, the maximum allowed project status before independent review is:

```text
ENGINEERING_SAFETY_CORRECTIONS_IMPLEMENTED
LOCAL_SYNTHETIC_QUALIFICATION_PASS   # only if actually passed
READY_FOR_INDEPENDENT_REVIEW
REAL_PILOT_BLOCKED
NATIVE_META_NOT_RUN
OWNER_USEFULNESS_NOT_MEASURED
```

Do not restore `META_READY_FOR_OWNER_APPROVAL` yourself. That decision belongs to a new independent safety review after all evidence is complete.

### 19. Local qualification commands

Run from the isolated checkout with the project-managed environment. Adapt paths only after inspecting the repository.

At minimum run:

```powershell
$env:PYTHONPATH='C:\Projects\alive-r4-r1'
Remove-Item Env:ALIVE_META_API_KEY -ErrorAction SilentlyContinue

& C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q
& C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q tests\test_alive14r4.py
& C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q tests\test_alive14r4_r1.py
& C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q tests\test_research_memory.py

& C:\Projects\alive\.venv\Scripts\python.exe -m ruff check .
& C:\Projects\alive\.venv\Scripts\python.exe -m ruff format --check .

& C:\Projects\alive\.venv\Scripts\python.exe scripts\verify_alive14r3_protocol.py
& C:\Projects\alive\.venv\Scripts\python.exe -c "from scripts.verify_archive import verify; [verify('archives/'+x) for x in ['ALIVE-14-R1','ALIVE-14-R2','ALIVE-14-R3','ALIVE-14-R4']]"
```

Also run the extension tests, frontend tests, production build, database/backend variants, and PostgreSQL first-contact checks defined by the repository.

Use fresh temporary databases and `--basetemp` directories for adversarial probes. Do not share approval or state files between tests unless the test explicitly examines restart behavior.

Record exact Python, dependency, browser/extension, database, and OS versions.

### 20. Synthetic end-to-end campaigns

After focused tests pass, run at least these synthetic campaigns from clean databases:

#### Campaign A — revoked Stage 1

1. register campaign;
2. create synthetic Stage 1 approval for exactly two calls;
3. settle call 1;
4. revoke approval through authenticated server endpoint;
5. attempt continuation;
6. confirm exactly one provider-stub invocation;
7. confirm call 2 remains undispatched;
8. confirm campaign is blocked or awaiting new valid approval according to policy;
9. confirm no restart bypass.

#### Campaign B — mutated local state

For separate clean runs, mutate:

- question;
- current excerpt;
- historical excerpt;
- instruction;
- schema;
- provider/model;
- local payload/request hashes.

Confirm transport receives no mutated request. Prefer rejection before provider transport. If server reconstruction is used, prove the dispatched stub input is the immutable approved content.

#### Campaign C — stage enforcement

1. attempt Stage 1 approval with cap 18 → reject;
2. attempt Stage 2 before Stage 1 → reject;
3. complete valid synthetic Stage 1 with two calls;
4. persist technical outcome;
5. create separate synthetic Stage 2 approval;
6. execute remaining 16 once;
7. verify 18 unique attempts, frozen order, budgets, restart durability, ratings, reveal, analysis, and archive.

#### Campaign D — timeout/cancellation

1. expire an actual `asyncio.timeout(...)` while awaiting the stub;
2. confirm at most one attempt;
3. confirm fatal blocked state;
4. confirm conservative liability based on dispatch marker;
5. confirm no later dispatch or ordinary restart continuation;
6. repeat with cancellation before and after the dispatch boundary.

### 21. Native docked-panel qualification

Only after backend and runner qualification passes, perform a fresh genuine docked Chrome side-panel journey against an isolated synthetic backend.

The journey must demonstrate:

- immutable server manifest display;
- correct digest;
- provider/model;
- Stage 1 exact limits;
- Stage 2 ineligible before Stage 1;
- authenticated synthetic Stage 1 approval;
- server rejection of a forged over-cap request;
- revocation status reflected before another dispatch;
- Stage 1 technical outcome display;
- separate Stage 2 approval becoming available only when eligible;
- blind rating, reveal, analysis, restart/read-only, and archive behavior;
- zero paid calls;
- no real attestation or real approval.

Capture evidence only if the journey actually runs. If Chrome/extension access is unavailable, report `FRESH_NATIVE_SYNTHETIC_NOT_RUN`; do not reuse old screenshots as a fresh pass.

### 22. Documentation and evidence

Add a new correction record rather than rewriting the independent failure assessment.

Suggested files:

```text
docs/ALIVE-14-R4-R1-SAFETY-CLOSURE.md
docs/CODEX-ALIVE14-R4-R1-HANDOFF.md
```

Add a clearly versioned R4-R1 evidence/archive directory only after the repository's archive conventions are understood. Do not overwrite R4 evidence.

Update current status documentation so it no longer presents the merged R4 implementation as ready for owner approval without noting that REVIEW-11 superseded that readiness claim.

Document:

- all four reproduced failures;
- root causes;
- exact corrections;
- trust boundaries;
- transaction/race semantics;
- strict stage definitions;
- exception allowlist/fatal policy;
- liability treatment;
- tests and synthetic campaigns;
- native qualification status;
- protocol/archive preservation;
- remaining limitations;
- explicit prohibition on real pilot execution.

### 23. Required preservation checks

Verify and record:

- protocol v3 hash unchanged;
- answer-key hash unchanged;
- R1 archive payload count and manifest validity;
- R2 archive payload count and manifest validity;
- R3 archive payload count and manifest validity;
- R4 archive payload count and manifest validity;
- no unexpected changes to earlier archive trees;
- frozen task order unchanged;
- reported Stage 1/full budgets unchanged unless a discovered arithmetic defect is separately documented;
- no real approval record created;
- no paid provider transport invoked;
- no live credential accessed.

Expected existing budget evidence:

| Scope | Calls | Reserved tokens | Conservative liability |
|---|---:|---:|---:|
| Stage 1 | 2 | 10,345 | $0.043967 |
| Full campaign | 18 | 92,148 | $0.391635 |
| Protocol ceiling | 18 | — | $0.45 |

Do not silently recalculate these from editable local state. Recompute them from the immutable registered manifest and compare with the frozen protocol.

### 24. Acceptance criteria

R4-R1 is ready for independent review only when all of the following are true:

1. all four REVIEW-11 unsafe outcomes are reproduced on the baseline or preserved in historical evidence;
2. all four corrected regression tests fail closed;
3. the actual backend, not the UI, enforces immutable content and stage limits;
4. every dispatch revalidates active approval atomically;
5. deterministic race tests pass for revocation and supersession;
6. local state mutation cannot change approved content;
7. Stage 1 cannot exceed two calls;
8. Stage 2 cannot be approved without durable Stage 1 technical eligibility;
9. timeout, cancellation, unexpected and ambiguous errors block later dispatch;
10. continuation uses an explicit nonfatal allowlist;
11. liability remains conservative and no ambiguous attempt is replayed;
12. full backend and affected regression suites pass;
13. extension/frontend/build tests pass;
14. archive and protocol verification passes;
15. a clean two-stage synthetic campaign completes correctly;
16. a revoked synthetic campaign stops after the authorized boundary;
17. a fresh native synthetic journey passes, or its absence is explicitly reported as an open gate;
18. zero real approvals and zero paid calls occurred;
19. evidence is complete and reproducible;
20. status remains `READY_FOR_INDEPENDENT_REVIEW`, not owner-approval-ready.

Failure of any item keeps the paid pilot blocked.

### 25. Remaining limitations that must stay explicit

Even after R4-R1 passes, do not claim:

- real provider connectivity;
- current account balance or credit;
- production provider structured-output compatibility;
- provider-side settlement reconciliation;
- semantic truth of model answers;
- improved usefulness from historical memory;
- cryptographic proof of human presence;
- complete protection against all cross-route or timing inference;
- retraction of data already dispatched;
- exhaustive crash-window safety beyond tested boundaries.

These require separate evidence.

### 26. Commit and external-action policy

Use focused local commits. A reasonable structure is:

```text
ALIVE-14-R4-R1: bind dispatch to server campaign manifest
ALIVE-14-R4-R1: enforce approval and stage barriers
ALIVE-14-R4-R1: fail closed on timeout and cancellation
ALIVE-14-R4-R1: add safety qualification evidence
```

Do not push, open a PR, merge, enable auto-merge, trigger hosted CI, create a real approval, or execute Meta inference without explicit subsequent authorization.

The account currently has hosted-job billing/spending-limit problems. Local qualification is not hosted qualification. Do not generate repeated failed workflow runs.

### 27. Final handoff format

Return a comprehensive report containing:

1. actual starting commit/tree, branch, and worktree;
2. dirty/clean state and unrelated changes preserved;
3. baseline reproduction of each REVIEW-11 blocker;
4. files changed and architectural decisions;
5. immutable manifest schema and canonical digest rules;
6. dispatch-authorization and atomic revocation semantics;
7. stage schema, caps, and Stage 2 eligibility rules;
8. exception classification and explicit continuation allowlist;
9. liability and replay behavior;
10. exact tests added and which blocker each closes;
11. full and focused test commands/counts/durations;
12. synthetic campaign results and provider-stub call counts;
13. concurrency/race-test results;
14. archive/protocol/answer-key hashes and preservation results;
15. extension/frontend/build results;
16. native docked-panel result or explicit non-execution;
17. all failures, warnings, skips, and limitations;
18. proof that no real approval, credential use, network inference, or paid call occurred;
19. local commit SHAs and final working-tree status;
20. explicit statement that nothing was pushed or merged unless separately authorized;
21. final status using only the permitted vocabulary;
22. recommendation for a new independent ALIVE-REVIEW-12 safety gate.

End the handoff with exactly one of:

```text
READY_FOR_INDEPENDENT_REVIEW
```

or:

```text
BLOCKED — <specific unresolved safety gate>
```

Never end with `READY_FOR_PAID_PILOT`.
