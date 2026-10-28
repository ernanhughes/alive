**ALIVE-REVIEW-12 — R5 Paid-Pilot Safety Qualification**

Reviewer: Codex, reviewing the pre-existing R5 commits from a separate clean checkout. This is not a Claude review. Date: 28 October 2026, Europe/London.

**Engineering integrity: FAIL.**

**Stage 1 safe to offer for explicit owner approval: NOT READY.**

**Full two-stage campaign: NOT READY.**

The four original REVIEW-11 scenarios now have passing corrected-outcome regressions. Independent adversarial probes nevertheless found four remaining blocker categories: missing durable fatal-stop enforcement, cancellation settlement rollback/unsafe stage-2 recovery, unenforced next-call ordering, and divergent displayed versus enforced manifests. No paid approval proposal is supplied.

1. **Repository and provenance.**

   Published the existing `codex/alive-14-r5-approval-integrity` branch and opened [draft PR #26](https://github.com/ernanhughes/alive/pull/26). Both commits were preserved unchanged:

   - `ef26935ab346c0e0e916a1d83c84c706f58d3be5` — implementation, regressions and evidence.
   - `49a602b9eb9cc0a15cdc100ecd63e81d33a9e7b0` — records the local implementation commit.

   Current remote main remains `8ae71b967fe92ae43ca8baa24d382b74d5435044`, the branch's merge base. There is no divergence requiring a rebase. The PR is draft, open and unmerged; GitHub reports it mergeable. The reviewed checkout is `C:/Projects/alive-review-12` at the exact published head, with no tracked changes. No additional source commit was made. Some archived R5 documents incorrectly label `ac11be8` as the R4 merge; actual ancestry establishes `8ae71b9` as the baseline.

   Frozen protocol v3 and answer key are byte-identical to main. Their canonical hashes remain `85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b` and `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`.

2. **The four original failure reproductions.**

   The existing R5 suites were independently rerun: **34 passed**. They reproduce the corrected safe outcomes for:

   | REVIEW-11 failure | R5 reproduced outcome |
   | --- | --- |
   | Revocation after call 1 permits call 2 | Runner stops with one dispatch after server revocation |
   | Local question/hash edits change approved dispatch | Local task mutations and server-bound changed question are rejected |
   | Stage 1 accepts caps 3 or 18 | Backend rejects both, and rejects premature stage 2 |
   | Raw timeout continues | Raw timeout and a real asynchronous sleep exceeding `asyncio.timeout` stop after one dispatch with conservative liability |

   Existing ordinary 2+16 execution, active/revoked approval pointers, low caps, quotation rejection, missing outputs, revised ratings and archive regressions also pass. This confirms these particular sequences; it does not establish the stronger claim that all equivalent failures are impossible.

3. **New independent adversarial findings — four P1 blocker categories.**

   **B1: A durable fatal provider error does not prohibit subsequent backend dispatch, and ordinary runner crash recovery can continue.**

   `test_backend_dispatches_after_fatal_error` uses a valid two-call synthetic approval. Index 0 settles with `ProviderError(authentication, 401)` and a durable `campaign_fatal=true` record. The same authenticated API then accepts index 1 and calls the stub again: two provider attempts in an all-401 sequence.

   `test_runner_crash_recovery_continues_after_fatal` demonstrates this through the ordinary runner rather than just a custom caller. It simulates process exit after index 0's fatal settlement commits but before the HTTP result is journalled locally. On normal restart, the runner recovers the failed attempt, appends it to outputs, then dispatches index 1 and reaches `staged`. No local campaign-content edit or new approval is needed.

   Cause: `alive/experiment_approval.py:534` loads campaign attempts only for duplicate-index checking; it does not reject a campaign with a previous fatal attempt. `scripts/alive14r5_experiment.py:1199` recovers prior attempts and continues without honouring the recovered fatal flag.

   Smallest correction: enforce an uncleared durable fatal/blocked state from the server ledger at every experiment reservation/final dispatch, regardless of local phase or output files. Apply the same check when recovering attempts. A distinct owner-authorised recovery, if supported later, must be explicit; ordinary restart must not clear it.

   **B2: Cancellation rolls back settlement; recovery then permits stage 2 after an ambiguous dispatch.**

   `test_cancellation_rolls_back_settlement_and_allows_stage_two` settles index 0 successfully, then raises `asyncio.CancelledError` from the provider-bound stub for index 1. After propagation, index 1 is still `reserved`, has no charged-token settlement, and has no fatal flag. This is because `alive/research_relationships.py:1166` re-raises cancellation inside the settlement transaction; SQLAlchemy rolls that transaction back.

   The probe invokes restart recovery. Index 1 becomes `interrupted` and retains a positive full conservative liability, but `initialize` at line 1586 does not mark the unknown completion campaign-fatal. `stage_one_eligible_locked` at `alive/experiment_approval.py:334` accepts two non-reserved rows if one validated and neither has a fatal flag. The authenticated server therefore creates stage-2 approval, and the probe actually dispatches index 2. The ambiguous index 1 is not replayed, but the campaign incorrectly continues beyond it.

   Smallest correction: commit cancellation settlement before re-raising, outside the transaction context. Recovery must record unknown completion/possibly-started interruption as a durable fatal blocker. Stage-2 eligibility must require explicitly allowed settled outcomes and reject ambiguous/interrupted dispatches, not merely `status != reserved`.

   **B3: The backend checks index identity/range, but not that it is the next call.**

   `test_server_dispatches_second_cell_first` sends a correctly bound index-1/B request under the valid stage-1 approval before any index-0/A attempt. It reaches the provider-bound stub, which receives historical evidence. The server accepts it as validated. Thus the immutable order is stored and individual index labels are checked, but runtime progression through that order is not enforced.

   Cause: `alive/experiment_approval.py:527` verifies the task/condition at the supplied index and line 534 checks duplicates. It does not require all earlier indices to have eligible terminal attempts or reject another outstanding attempt.

   Smallest correction: atomically derive the next eligible index from durable attempts when reserving/dispatching. Refuse skipped, reversed or concurrent progression, and apply the fatal/ambiguity checks from B1/B2 before allowing any successor.

   **B4: The native-display manifest can disagree with the digest-bound content actually dispatched.**

   `test_registration_accepts_display_manifest_divergence` registers a fresh campaign with unchanged canonical `content`, but a different first question in the separate `manifest`. It keeps the objects independent in the JSON request. Registration succeeds. A simulated stage-1 approval is then created, and index 0 dispatches. The captured provider-bound question equals `content.tasks[0].question` and differs from `manifest.tasks[0].question`.

   Cause: `alive/experiment_approval.py:96` validates canonical `content`, but does not require the displayed `manifest` to represent that same content. `extension/panel.js:397` renders `campaignView.manifest`; dispatch validation uses `campaign.data.content` for task fields. An opaque digest alongside a conflicting display does not let the owner inspect the actual authorised content.

   Smallest correction: expose and render one canonical authoritative content object, with derived stage/accounting metadata. If the duplicate manifest is retained, require exact equality of its overlapping content with the canonical object before registration or approval. Derive dispatch audit hashes from that same object.

4. **Revocation and concurrency assessment.**

   Independent `test_revocation_queued_before_final_marker_blocks_dispatch` pauses the guard, queues authenticated revocation on the shared kernel lock, then releases the guard. Revocation commits before the final dispatch transaction. The attempt settles with a fatal permission error, zero provider calls and zero liability. This supports the documented linearisation rule for the tested single-process backend.

   Independent `test_supersession_before_marker_blocks_dispatch` authorises a cell, creates a new current stage-1 approval before any attempt, then tries the old consent. It is refused at final dispatch with zero calls and zero liability. Existing tests also refuse revoked stage-2 approval after restart. The review does not claim exhaustive multi-process/database-instance race coverage. The remaining fatal/recovery findings are not revocation-order failures.

5. **Immutable content binding.**

   Independent mutation probes intercept payload construction before the server boundary and verify zero provider-bound stub calls when changing research question, current excerpt, historical evidence insertion, URL, source hash, goal, instructions, schema, provider or model. Run identity, unknown approval identity, mismatched stage and mismatched index/condition are also rejected. Existing suite tests separately cover changed historical source content in local state.

   These are useful positive results: recalculating local hashes no longer makes a changed task eligible under the honest registered content. They do not resolve B4's inconsistent registration/display. A valid different-campaign approval substitution was not separately exhaustively exercised; the backend's campaign/run comparisons were inspected, and invalid run/approval identities were tested. Arbitrary local database writes are outside the owner-channel trust boundary.

6. **Stage and approval enforcement.**

   Server stage-1 caps of 3 and 18 are rejected; indices are restricted to 0–1. Stage 2 requires a separate current approval and is limited to 2–17. One stage-1 attempt is insufficient; normal two-terminal/one-validated eligibility and 2+16 continuation pass. Attestation and server-side approval pointer checks remain covered.

   Eligibility is nevertheless unsafe for the cancellation/restart outcome in B2, and ordering within the permitted index range fails in B3. A stage cap is not a guarantee about which call executes next. Neither a locally edited progress cache nor a recovered fatal record should restore dispatch eligibility.

7. **Timeout and settlement safety.**

   Reproduced raw timeout and real asynchronous timeout expiry through the R5 suite; both stop the normal runner after one attempt. Authentication/401, access denied/403, unsupported schema, quota, rate limit and server errors have passing stop-after-one regressions. Evidence/quotation rejection remains a permitted per-cell outcome in the full mixed-output run.

   Positive conservative liability and no replay of the same cell are verified for the tested failures. However, B1 shows a fatal result is not a durable campaign-wide barrier, and B2 shows cancellation is not durably finalised as claimed. A broad independent campaign test for every ambiguous-settlement category was not repeated after these blockers were established. Recovery must forbid further dispatch as well as duplicate replay.

8. **Budget accounting and digest.**

   Independent fresh preparations reproduce the normal pinned-model accounting. Two synthetic databases have distinct snapshot UUIDs and the same digest; changing a source excerpt changes the canonical digest. Real-mode preview creates no owner approval and performs no inference.

   | Scope | Calls | Reserved tokens | Conservative liability |
   | --- | ---: | ---: | ---: |
   | Stage 1 | 2 | 10,345 | $0.043967 |
   | Full | 18 | 92,148 | $0.391635 |
   | Hard protocol ceiling | 18 | — | $0.45 |

   Recalculated liability as the sum of each call's reservation rounded upward at $4.25/M: `sum((tokens * 17 + 3) // 4)` micro-USD. Synthetic model/provider strings are longer, so their preview reservation is $0.393090; it must not be confused with the real model's budget.

   Pure validation tests independently verify effective limits of $0.40 when runtime is lower than owner, $0.39 when owner is lower than runtime, and $0.45 when owner/runtime are both $5. These tests create no real approval. The separate $5 project budget does not authorise increasing the frozen campaign cap. [Meta's pricing documentation](https://dev.meta.ai/docs/pricing-rate-limits), checked during this review session, lists Standard input/cached-input/output rates of $1.25/$0.15/$4.25 per million; the pinned model remains `muse-spark-1.3` without the Contributor suffix.

   These baseline calculations and normal-runner guards are not an exhaustive proof for arbitrary malicious campaign registrations or multiple independent backend processes. The new consent and recovery blockers must be fixed before any spend is offered.

9. **Native Chrome evidence.**

   Reviewed archived native JSON, the stage-1 screenshot and the native harness. The archive reports genuine docked Chrome 156, early stage-2 rejection, stage-1 approval/revocation/reapproval, later stage-2 approval and archived read-only results after restart. The stage-1 screenshot visibly includes the prior stage-2 rejection and an active two-call synthetic approval. Its manifest disclosure is collapsed in that image; the JSON reports manifest display during the journey.

   Browser actions are explicitly separated from CLI/backend actions: the 2+16 execution, rating, reveal, analysis and archive were runner-driven. No paid-provider qualification is claimed.

   The native evidence records `source_commit=8ae71b9`, and its screenshot says verified local runtime `8ae71b9`, although R5 was then uncommitted work on that base. This is a provenance limitation: it does not by itself identify the exact tested source tree at `49a602b`. Archive hashes preserve the evidence but are not a source-tree attestation. No fresh native run was claimed here; after backend blockers were reproduced, no extension installation, UI approval or further native execution was attempted.

10. **Tests, skipped replacements, archives and CI.**

   - `backend-suite.txt`: **243 passed, 6 skipped**, 346 Windows ZMQ event-loop warnings, 234.29 seconds.
   - `r5-suite.txt`: **34 passed**, 191 warnings, 105.49 seconds.
   - `independent-probes-final.txt`: **6 passed**, 29 warnings, 17.63 seconds.
   - `extra-probes.txt`: **15 passed**, 6 deselected, 63 warnings, 34.23 seconds.
   - `refined-probes.txt`: **2 passed**, 20 deselected, 11 warnings, 8.84 seconds; strengthens the display-manifest probe by capturing the actual dispatched question and adds supersession.

   There are **22 distinct independent probe cases** in `test_review12.py`; the manifest case was rerun after strengthening it. Observation probes deliberately assert the unsafe outcome to preserve reproducible negative evidence. Their passing status is not a safety pass. Earlier development output remains available and is superseded by the final/refined logs above.

   The six historical skips are four test functions comprising six parameterised cases, not six unrelated safety requirements:

   | Skipped R4 coverage | R5 replacement |
   | --- | --- |
   | fatal 401/schema/quota (3 cases) | `test_alive14r5.py::test_campaign_fatal_provider_failure_stops_after_one`, plus broader safety-category tests |
   | attestation/effective cap | same-named R5 test; low owner cap is now refused by server |
   | file-only/revoked server approval | same-named R5 test |
   | missing output/revised rating archive | same-named R5 test, now run over strict 2+16 stages |

   The normal R4 staged test itself is not skipped. Replacement coverage is equivalent or stronger for those specific assertions, but it omits the new cancellation, crash-after-fatal, next-index and dual-manifest scenarios. Those omissions explain why the existing suite can pass with these blockers.

   `archive-protocol.txt`: R1/R2/R3/R4/R5 verified respectively **18/16/30/32/36** listed payloads with no unlisted files. Earlier R1–R4 archive directories have no diff from main. Protocol and answer-key files are byte-identical to main.

   [PR Actions run 40660354699](https://github.com/ernanhughes/alive/actions/runs/40660354699) completed successfully at `49a602b`. CI includes backend tests on Windows/Linux, lint/format, dashboard/extension/build and PostgreSQL first-contact tests. Its archive verification steps currently stop at R4; add an explicit R5 archive check. CI does not run this external independent harness or a genuine R5 native journey.

11. **Exact blockers, minimal corrections and reproduction.**

   Required work is limited to B1–B4: durable server-enforced fatal-stop/order progression; cancellation commit before propagation plus fail-closed ambiguous recovery/stage eligibility; one canonical manifest for display, approval and dispatch. Add adversarial regressions for these exact sequences and the R5 archive check. Correct stale baseline/source provenance when producing new native evidence. Preserve protocol v3, answer key, prior archives and all negative evidence. Do not approve or execute Meta, merge the PR, or broaden the research protocol.

   Application source remains unchanged. All new review artifacts, databases, journals and evidence are outside the source checkout at `C:/Projects/alive-review-12-evidence`. Reproduce from PowerShell with the isolated checkout as current directory:

   ```powershell
   $env:PYTHONPATH='C:\Projects\alive-review-12'
   & C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q tests/test_alive14r5.py tests/test_alive14r5_safety.py
   & C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q
   & C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q -s C:\Projects\alive-review-12-evidence\test_review12.py --basetemp=C:\Projects\alive-review-12-evidence\fresh-reproduction
   & C:\Projects\alive\.venv\Scripts\python.exe -c "from scripts.verify_archive import verify; [verify('archives/'+x) for x in ['ALIVE-14-R1','ALIVE-14-R2','ALIVE-14-R3','ALIVE-14-R4','ALIVE-14-R5']]"
   & C:\Projects\alive\.venv\Scripts\python.exe scripts/verify_alive14r3_protocol.py
   ```

   Use a fresh `--basetemp` target when reproducing; retain existing evidence directories. The independent harness removes the Meta key and forbids `MetaProvider._request`; all execution probes are synthetic. Existing repository unit tests use isolated fake-credential/transport fixtures for real-labelled paths; none approve or execute the operational pilot.

   Final decisions remain **FAIL / NOT READY / NOT READY**. Publication is complete; the paid pilot remains blocked. No real owner approval, Meta inference, application modification or merge was performed.
