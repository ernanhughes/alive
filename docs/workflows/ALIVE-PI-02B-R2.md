# ALIVE-PI-02B-R2 remediation and qualification

The [ARCH-01 integration follow-up](ALIVE-PI-02B-R2-INTEGRATION.md) records the later
combined source and CI corrections. Counts below remain the initial R2 snapshot's
qualification; use the follow-up and final PR head for the next independent review.

PR #69 remains draft and unmerged. Reviewed R1 commit:
`b2d06caa59c411a87951afc76440a368717e8dfd`.
R2 implementation and executable qualification sources:
`a9ec88d1c247f2b692c47f388511660b479c82d5`.
Final review head is reported separately in the PR and delivery message; later changes
are qualification receipts and documentation. Date: 2026-10-30.

## Original reproductions

A new task-owned branch/worktree was created from the exact reviewed SHA. Another
detached task-owned scratch worktree ran the preserved reviewer probes before any
production changes. Its pytest plugin only redirected the evidence output directory;
the original probe file was unchanged. Eighteen selected probes passed, producing
observations that independently reproduce FAILED/CANCELLED artifacts with HTTP 200
and no run status, and an owner-granted extension context reaching COMPLETED without
an explicit provenance label. The same baseline kept actual dispatch-fence changes
at zero upstream calls and detected artifact substitution. These observation probes
do not turn the review's test gaps into claims of production authorization bypasses.

[Original review/probes](validation/pi02b-r2/r1-original) are copied byte-for-byte.
[Baseline reproductions](validation/pi02b-r2/reproduction-observations) and
[command output](validation/pi02b-r2/reproduction.txt) are separate. The original
review evidence directory and pre-existing worktrees were never modified. Raw audit
copies disable Git normalization/diff rendering to preserve their exact original
bytes, including whitespace. The receipt manifest checks that custody explicitly.

## F-01: historical artifact access conveys execution state

Authorized GET access still returns a retained, hash-checked artifact when its record
stage committed. It now includes `run_status`, `terminal_reason`, `stage_state`,
`stage_uncertainty`, `stage_validation` and `workflow_completed`. COMPLETED, FAILED,
CANCELLED and UNKNOWN are distinct; only the first sets `workflow_completed=true`.
An UNKNOWN run can have a completed record stage, but the response explicitly says
the run is UNKNOWN. Retrieval certifies neither workflow success nor semantic truth.
Uncommitted/missing/tampered artifacts still return 404. No write/start API was added.

Negative API tests inject cancellation or terminal settlement failure after artifact
commit, and a quiescent interrupted UNKNOWN outcome. They retain forensic access and
assert all state/validation fields, safe errors and released reservations. Existing
artifact content/hash/schema remain unchanged; additive read metadata preserves
historical artifacts, including legacy grants with no provenance field.

## F-02: source provenance is separate from approved use

The public event-ingestion schema permits only browser page-opened/DOM-changed events
with `extension` or `user` source. It cannot mint `workflow-owner` events or overwrite
an existing grant identity: duplicate ingestion is idempotent. Source strings from a
browser are transport labels, not authentication of page content.

A new executable grant must explicitly bind `context_provenance`: exact event source,
event type, custody class and `consent=exact_content_and_scope`, in addition to its
existing event ID, payload hash, owner, goal, inquiry and outbound scope. Eligible pairs:

| Source/type | Custody |
| --- | --- |
| controlled-laboratory / workflow.fixture.context | controlled_fixture |
| extension or user / browser.page_opened or browser.dom_changed | untrusted_browser |

Other pairs, missing labels and mismatches are refused. Revalidation at admission,
reservation and actual dispatch preserves that binding. A trusted owner can approve
exact captured browser material; it remains untrusted and semantically unverified.
The artifact read model records approved event ID/hash/classification alongside the
original retained source/type and explicitly says authorization is not source
authentication. No browser content can create owner consent. No public grant factory,
browser autonomy, broad context retrieval or evidence qualification is added.

Legacy grants remain parseable for authorized forensic reads but do not qualify for
new execution. Tests cover approved extension material, missing/forged provenance,
unsupported source, wrong goal, changed payload, withdrawal, and public attempts to
mint or overwrite grants. Separate dispatch tests preserve revocation protection.

## F-03: safeguards now have clause-level regression assertions

The reviewer mutation descriptions are read as static data, never executed as scripts.
`scripts.workflows_r2_mutations.py` copies the relevant source/tests into a temporary
scratch tree, runs each unchanged target, applies exactly one source mutation, then
restores it. Syntax/import/setup/teardown failures never count as kills. The original
eleven mutation probes are unchanged and were rerun separately.

[The full mutation matrix](validation/pi02b-r2/mutations.json) records the actual guard,
replacement, selected test, passing baseline and failed assertion. Results:

| Reviewed mutations | R2 result and protection |
| --- | --- |
| A1 stage claim | KILLED: even the current owner cannot repeat a completed stage |
| A2/A3 revoke/withdraw | KILLED: actual Pi dispatch makes zero upstream requests |
| A4 configuration | KILLED at the actual dispatch fence |
| A5/A6 uncertainty/cancel | KILLED by existing recovery/cancellation assertions |
| A7v/A8 result/artifact hash | KILLED: rebuilt event hash and artifact edits return 404 |
| A9 missing host guard | KILLED: real Pi with an absent callback fails closed |
| A10 pre-reservation model comparison | REDUNDANT for unauthorized dispatch: final B1 comparison independently enforces the same approved model |
| A11 Pi response linkage | KILLED by existing incomplete-receipt assertion |
| A12 dependency completion | KILLED: a real immutable graph's control dependency blocks a stage even without an output reference |
| A13 inquiry ownership | KILLED: existing snapshot/calls/live worker prevent transfer |
| A14 slot release | KILLED: a second admitted inquiry needs the released instance slot |
| A15 execution deadline | KILLED immediately before actual dispatch |
| B1–B5 model/context/reservation status/stage state/invocation link | Each KILLED separately at the actual dispatch fence |
| C1 owner-grant expiry (additional) | KILLED: expiry is checked independently of the execution deadline |

Thus the reviewed set has **19 kills and one documented redundant mutation**; the
additional expiry probe makes **20 kills, one redundant, 21 passing baselines**.
A10 is not counted as a kill. No additional production guard was weakened or removed
to manufacture a result. A1's public reachability remains restricted by run ownership;
its new test protects internal re-entry as defence in depth.

R1's first A7 deletion was invalid Python; R2 uses its documented A7v replacement.
The first B4 replay produced an invalid PENDING-to-UNKNOWN cleanup transition under
the intentionally corrupted database and was rejected as a teardown failure, not a
kill. The final B4 test substitutes a valid FAILED stage state, isolates the same
RUNNING requirement, observes the dispatch count, and cleans up normally. All final
results have relevant assertion failures and passing unchanged baselines.

## F-04/F-05: bounded errors and explicit validation meaning

Small phase boundaries distinguish `adapter_execution_failure`,
`output_validation_failure`, and `result_persistence_failure`. Existing bounded
authority refusal codes remain; a durable Pi rejection with
`workflow_authority_revoked` maps to `authority_refused` when linked to the stage.
Cancellation remains `cancelled`; possible effects retain UNKNOWN state and
`uncertainty=unknown_outcome`, independently of the initiating error category.
No exception text, credentials, SQL, prompt or filesystem path is exposed. Tests
inject private-looking exception messages and assert only fixed categories escape.

The legacy `validation_status` enum is retained for compatibility. Its sibling
`validation` object and artifact `stage_validation` explicitly separate contract,
structure, provided reference identity and semantic status. All semantic status is
conservatively `unverified`, with `independent_verification=false`; deterministic
comparison's artifact assessment still limits its result to controlled sources.
`workflow_completed` is separate again. Reference validation checks provided IDs;
uncited claims are permitted, explicitly labelled, and never promoted to truth.
A real Pi test supplies uncited claims and proves those distinctions in the artifact
and every stage API response. No semantic verifier or learning path was introduced.

## F-06–F-08: qualification and scope

R1's retained image hashes compared the Windows working tree to its image. As the
review correctly notes, that is Git-blob equality only after line-ending conversion
for nine files. That receipt is preserved unchanged. R2 disables `core.autocrlf`
when exporting Git for the final Docker build. Its new parity receipt separately
records Git-blob, image, working-tree and LF-normalized working-tree hashes; the
image equals the Git blobs byte-for-byte. The first R2 export inherited autocrlf;
its parity assertion failed, so it is not cited as exact-blob qualification. The
corrected LF image was rebuilt and the real-runtime/restart checks repeated.

The original three-worker fixture uses three independent pools/locks in **one OS
process**, under one real host lease. It is not a distributed worker test. New
PostgreSQL qualification launches genuine independent application processes:
a contender is refused by the production database lease, then a fresh successor
owns the lease and replays/executes the completed identities without new effect or
learning records. The same checks run inside Docker and are added to PostgreSQL CI.
Concurrent run/stage claims by multiple active host processes on one database remain
NOT_RUN: the production lease intentionally disallows that topology. No lease was
disabled, borrowed or faked. This is host exclusion/handover evidence, not a claim
of distributed stage execution. Such workers remain outside PI-02B.

Baseline provider-construction and Pi-reference tests are unchanged by R2. The full
source ratchet still forbids new MetaProvider construction sites; the workflow
boundary only allows Pi receipt model imports, not Pi/provider executors. The Pi FK
test requires an actual existing receipt. Both remain in the regression selections.
No migration, dependency lock, Pi architecture, Intelligence learner or policy changes.

## Commands and results

Use the locked environment (`uv sync --locked`, pinned Pi npm installation). Windows
commands used `C:/Projects/alive/.venv/Scripts/python.exe`; no paid credentials.

| Command/check | Result |
| --- | --- |
| Original SHA selected review probes with evidence redirect | 18 passed |
| Four new R2 suites | 38 passed, 38 warnings |
| Original eleven mutation probes | 11 baseline PASS, 11 assertion KILLED |
| R2 source-mutation replay | 21 baseline PASS, 20 KILLED, A10 redundant |
| Full backend `python -B -m pytest -q -p no:cacheprovider` | 1,200 passed, 12 skipped, 1 xfailed, 945 warnings; 972.90 seconds |
| Linux R2/transaction/FK/ratchet/migration selection | 107 passed; initial R2 image, same source modulo CRLF |
| Final LF Docker image, R2/transaction tests | 40 passed |
| Windows workflow API/FK/migration selection | 90 passed, 86 warnings |
| `python -B -m scripts.workflows_execute_check` SQLite | PASS, two graphs, real Pi/scripted provider, one request |
| Same, PostgreSQL `--database-url <disposable> --process-probe` | PASS, lease exclusion and successor replay |
| Same, final LF Docker image / PostgreSQL | PASS, real pinned Pi plus genuine process lease/replay |
| PostgreSQL upgrade/downgrade 0009, 0008 and base, each re-upgraded | PASS, final 0010 |
| Docker smoke / API E2E / actual restart | 8 checks / 6 groups / 6 unchanged response bodies and zero new effects |
| Ruff check / format | PASS, 294 files including qualification utility |
| Remote CI on final review head | PENDING; reported separately from local results |

Receipts are under [validation/pi02b-r2](validation/pi02b-r2). The full run collected
before the added uncited-claim test and the B4 test-fixture adjustment; the final
38-test selection covers both. Production source was unchanged after the full run
started. The Python interpreter retains inherited Windows ZeroMQ/subprocess cleanup
warnings; see logs. Early harness errors (Event lookup used its audit ID as the
primary key, then a missing test import) were corrected; those runs are not passes.
The first Docker smoke call raced startup and failed transport; readiness/E2E and
the subsequent smoke passed. These failures did not motivate production changes.

Final LF image:
`sha256:896322bdef57971449d5acc2bf238d5ddc2e9feacb2c73c97bef668bdba540b8`.
The initial Linux 107-test selection used image `0a51e38d...` before correcting the
archive export. Its production source is identical after LF normalization. A fresh
focused R2/transaction selection on the final LF image is recorded separately.
Only task-owned Docker containers were stopped after qualification.

Main advanced during R2 to `4088671ece35566c21056199042189405ccc78b0`
(ARCH-01 merge). R2 preserves the reviewed PR baseline, not an untested rebased
snapshot. A read-only `git merge-tree --write-tree HEAD origin/main` check reported
a clean merge; no merge commit or owner-worktree changes were made. Integration CI
on the eventual PR head is separate from these local branch qualifications.

No paid inference, live Chrome interaction, new dashboard UI, general memory/evidence
adapter, automatic retry/resume, Bespoke router or policy promotion was attempted.
Reference identity checks do not establish semantic truth. Unknown cost stays null.
Existing process containment, cancellation cooperation and quiescent-recovery limits
remain. Stop for another independent review; do not merge #69 or start PI-02C.
