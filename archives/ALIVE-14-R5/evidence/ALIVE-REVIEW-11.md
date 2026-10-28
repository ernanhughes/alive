**ALIVE-REVIEW-11 — R4 Paid-Pilot Safety Gate**

Independent reviewer: Codex. Date: 28 October 2026 (Europe/London).
Scope: merged R4, isolated checkout, stub inference, frozen protocol v3. This review did not modify application code, merge or publish anything, approve the operational Meta pilot, or execute Meta inference. Disposable test databases contain simulated approval records needed to test the approval mechanism; these are not owner authorisation for the real pilot.

**A. Engineering integrity: FAIL.**

**B. Stage 1 safe to offer for explicit owner approval: NOT READY.**

**C. Eighteen-call campaign safe to run in two stages: NOT READY.**

The reported R4 fixes are substantial and the existing tests pass. Four independently reproduced gaps nevertheless defeat the required approval or fail-fast guarantees. No paid approval proposal is provided.

1. **Repository and archive state — verified, with CI qualification stated precisely.**

   [PR #25](https://github.com/ernanhughes/alive/pull/25) is merged. Its merge commit is `8ae71b967fe92ae43ca8baa24d382b74d5435044`; source head is `689f192621709a925bba0c3e44f399c99e629b0e`. `git ls-remote origin refs/heads/main` returned that merge commit during this review. The shared workspace was at `0809f37` with unrelated changes; review used the clean detached checkout at `C:/Projects/alive-review-11`.

   The [final-head Actions run](https://github.com/ernanhughes/alive/actions/runs/40611998859) succeeded: Windows backend, Ubuntu backend, dashboard, and PostgreSQL first-contact jobs all passed. This independently verifies four jobs on the final source head; it does not independently establish eight distinct checks on the merge commit. The merge commit's legacy combined-status endpoint returned no status entries.

   There is no diff in `alive`, `scripts`, `tests`, or `extension` between the reported qualification implementation `4bdefea1bb0eb198d06db2b0518d6f13d1f7d6ad` and the reviewed merge. The merge adds extension-pack documentation/data beyond the PR head, without changing those implementation directories. Thus the archived backend/native qualification corresponds to the reviewed implementation, although archived documents still describe the PR as draft.

   Archive verification passed for R1/R2/R3/R4: respectively 18/16/30/32 payloads, no unlisted files. Earlier R1–R3 archive directories have no diff from R4's baseline `ac11be8`. Frozen protocol hash: `85fe891cee31bf93d178c4cba2102642b8f4b5e666a0ee426186d5735eb5a71b`. Sealed answer-key hash: `255e706dd569634d1710a50831f65a6dd6eb7dabc5ee56e1cd763b382554b43d`. Both verified.

2. **Revocation — grant correction passes; campaign approval revocation fails during execution (P1).**

   Existing regressions reproduce active grant → restart suspension → `revoked_restart` → explicit owner revoke → permanent `revoked`; restoration is refused and outbound preview is blocked. Concurrent revocation/recovery, expiry, second restart, final source revalidation and withdrawal regressions passed in the full backend suite. Source withdrawal is refused while a transmission is already in flight, then effective after settlement; it cannot retract data already dispatched.

   Independent probe `test_revoked_campaign_continues_dispatch` approves a two-call synthetic stage and revokes its **campaign approval through the authenticated server endpoint after call 1 settles, before the runner requests call 2**. The server reports `revoked`; the runner nevertheless dispatches call 2 and finishes the stage. This is distinct from the corrected grant revocation bug.

   Cause: `scripts/alive14r4_experiment.py:929` fetches approval once before execution. The per-cell loop at line 1039 and the final dispatch path in `alive/research_relationships.py:713` do not revalidate that campaign approval.

   Smallest correction: bind the campaign approval identity to each experiment dispatch and check its active, non-superseded state in the backend immediately before committing dispatch, under the same ordering/lock used for revocation. Reject subsequent calls after revocation; retain settlement of any call already sent.

3. **Fatal provider errors — categorical failures pass; unwrapped timeout fails (P1).**

   Independent synthetic campaign probes injected `ProviderError` for authentication/401, access denied/403, unsupported schema/400, quota/402, rate limit/429, timeout, and ambiguous settlement. Each dispatched exactly once, retained a failed/missing output with positive conservative token liability, marked the campaign blocked, and refused an ordinary restart execution. The all-401 result is exactly one attempted call. Existing dispatch-marker regressions also distinguish never-dispatched zero liability from ambiguous full-reservation liability.

   `test_unwrapped_timeout_fails_to_stop` injects Python `TimeoutError`, the exception type also produced by the enclosing `asyncio.timeout(cfg.wall_seconds)`. Both calls in an approved two-call stage are attempted. Each record has `error_category=TimeoutError` and `campaign_fatal=false`. Provider HTTP timeouts wrapped in `ProviderError` are handled correctly; the surrounding wall-clock timeout is not.

   Cause: `alive/research_relationships.py:914` defaults `campaign_fatal` to false for exceptions without that attribute.

   Smallest correction: normalise wall-clock timeout, cancellation and unexpected/ambiguous dispatch errors to fatal categories. Allow continuation only for the explicitly documented per-cell evidence/schema-output failures. Add a test that actually expires the wall-clock context around an awaiting stub provider.

4. **Staged execution — normal 2 + 16 lifecycle passes; server stage binding fails (P1).**

   Independent `test_staged_order_budget_digest_and_revisions` uses separate synthetic server approvals for cap 2 and cumulative cap 18. The first execution makes two calls; another execution under the same approval makes no additional calls. Separate stage-2 approval permits the remaining sixteen. All 18 attempt IDs are distinct, frozen task/A-B order is preserved, outputs survive backend restarts, 27 blind ratings persist, commitment verification succeeds and archive retrieval works. The first stage leaves sixteen undispatched cells.

   `test_stage_one_accepts_full_campaign_cap` submits `stage=1, call_cap=18` against a campaign whose registered stage-1 cap is two. The backend creates an active stage-1 approval for eighteen calls. Native UI normally sends two, but the authenticated API does not enforce that stage definition. The runner also accepts full-cap stage-1 synthetic approval.

   Cause: `alive/experiment_approval.py:131` compares caps only with campaign-wide limits; line 164 records the supplied stage without checking its registered limits.

   Smallest correction: validate the stage against its registered call/token/dollar limits on the server, and validate stage-2 eligibility against durable stage-1 progress and technical outcome. Enforce the same stage identity during dispatch. Do not rely on the selector UI to enforce this contract.

5. **Approval security — file-only forgery is rejected, but approved content binding can be bypassed (P1).**

   Existing regressions reject a forged approval pointer with `human_approval=true`, a missing server approval, revoked approval at startup, absent real attestation, and insufficient approved/runtime USD caps. Independent probes reject an invalid bearer (401), a placeholder `approved_by` request field (422), and an earlier superseded approval pointer. Approval provenance denotes possession of the authenticated owner channel plus a claimed attestation; it does not verify human presence.

   Independent `test_local_question_and_hash_edits_bypass_digest` approves a synthetic campaign, changes the first dispatched task's research question in local `state.json`, obtains ordinary fresh preview hashes for that changed question, and updates the local state/approval hash maps. It changes neither the registered campaign nor its server approval/digest. Execution dispatches the changed question successfully under the original server approval. The test captures the actual stub input to establish that the changed request was dispatched.

   Cause: `approval_from_server` at `scripts/alive14r4_experiment.py:562` constructs the payload map from local state. `validate_execution_approval` at line 847 compares local maps with local maps. `execute` checks the server digest string against the local string, but does not reconstruct the dispatch content from the immutable server manifest and compare its digest with the approved one.

   Smallest correction: derive the dispatch identity and allowed payloads from the server's immutable campaign manifest; recompute canonical content identity from the actual task/source/question/instructions/schema/provider/model. Compare it to the server approval and enforce run/protocol identity server-side. Treat local JSON as a pointer and progress cache only. This correction must cover changed excerpts as well as the demonstrated changed question; a digest-generation function alone is insufficient.

6. **Budget, stable digest and model — baseline calculation verified; enforcement qualification limited by finding 5.**

   Two equivalent fresh synthetic preparations had different snapshot UUIDs and the same campaign digest. Editing a source excerpt in the canonical campaign content changed its digest. A real-mode preparation with no approval and no inference reproduced:

   | Scope | Calls | Reserved tokens | Conservative liability |
   | --- | ---: | ---: | ---: |
   | Stage 1 | 2 | 10,345 | $0.043967 |
   | Full campaign | 18 | 92,148 | $0.391635 |
   | Protocol ceiling | 18 | — | $0.45 |

   Cost is the sum of each call's reservation rounded upward at $4.25/M, the highest pinned token rate. Per-call rounding explains why rounding the aggregate token count once produces a slightly different number. The remaining worst-case reservation after stage 1 is 81,803 tokens / $0.347668; headroom under the full ceiling is $0.058365. Actual remaining dollar allowance must use the durable settled/conservative ledger, not simply assume the first two calls cost their maximum.

   Code and cap regressions verify `min(protocol ceiling, approved max_usd, runtime cap)` on the normal real runner path. `check_spend` guards each reservation. This does not cure the editable-content approval bypass.

   The pinned model is `muse-spark-1.3`, Standard mode, with no Contributor suffix. [Meta's current pricing documentation](https://dev.meta.ai/docs/pricing-rate-limits) confirms $1.25/M input, $0.15/M cached input, $4.25/M output and distinct Standard/Contributor data-use terms. No account credit or real structured-output compatibility was verified.

7. **Blinding and scoring — exercised successfully within the tested routes.**

   The existing mixed-failure/revised-rating regression passed. An additional full 18-call synthetic run injected a valid abstention, rejected/missing output and misleading answer; three revised ratings produced 30 rows for 27 distinct output identities. Reveal, analysis and archive succeeded. Even an explicitly positive rating on the missing placeholder did not make it supported-useful. Misleading counts were present separately for A/B/C.

   Collecting-state blind views omit condition/attempt/provider metadata. Tested paired settled/authorised events contain only their neutral mode/settlement flags. The relationships status route redacts payload/source metadata during collection, but still exposes attempt IDs/statuses; this audit did not demonstrate a condition join from that route alone. These checks are not a proof against every possible timing, text-content or cross-route inference. Local database/file access is outside the blinded UI boundary.

   The scripted abstention exercises contract/scoring plumbing; semantic correctness and usefulness remain human judgements. The misleading synthetic answer intentionally demonstrates why exact quotation validation is not truth validation.

8. **Native approval evidence — archived correspondence verified; fresh docked-panel qualification incomplete.**

   Reviewed `archives/ALIVE-14-R4/evidence/native-r4-approval.png`, `native-synthetic.json`, and `extension/panel.js:381`. The panel source displays provider/model, digest, full manifest, stage limits, tokens/dollars through the manifest, and attestation; it submits the selected stage via the authenticated backend. The archived native evidence reports a two-call synthetic stage approval, synthetic rating provenance, four synthetic note calls, zero paid calls and restart/read-only checks. The source comparison in item 1 establishes implementation correspondence.

   The current genuine Chrome window was inspected using the computer-use skill; no ALIVE docked approval panel was open. No extension installation or native approval was performed. Consequently this review does **not** claim a fresh independent native-panel pass. In particular, the existing native evidence cannot override the reproduced backend enforcement failures.

9. **Remaining limitations and required next action.**

   Apply only the four targeted corrections above, then rerun the failed gate scenarios, affected regression tests and a genuine docked synthetic approval journey. Preserve protocol v3 and its answer key. Recheck direct source mutation, cross-campaign/run pointers, revocation/supersession during dispatch, and timeout cancellation at the actual await boundary. Broader crash windows and exhaustive cross-route unblinding were not independently proven safe here.

   No real connectivity, balance, provider settlement reconciliation, human usefulness, semantic truth or cryptographic human-presence verification is established. These limitations must remain explicit. This audit supplies no real campaign approval manifest for owner sign-off because critical checks failed.

10. **Exact reproduction references and validation.**

   Application checkout: `C:/Projects/alive-review-11` at `8ae71b9`, tracked tree clean. All new audit files are outside the source checkout in `C:/Projects/alive-review-11-evidence`.

   - Full backend: `backend-suite.txt` — **215 passed**, 197 Windows ZMQ event-loop warnings, 166.15 seconds.
   - Independent harness: `test_review11.py`.
   - `independent-probes-final.txt` — **14 passed** in 58.80 seconds.
   - `extra-probes.txt` — **2 passed**, 14 deselected, in 11.38 seconds (mixed scoring and superseded/authentication controls).
   - The observation probes deliberately assert the reproduced unsafe outcomes; their passing status is evidence of the findings, not a passing safety gate. Earlier development logs remain present and are superseded by these final logs.
   - Synthetic databases, output journals and archives remain under `tmp-final` and `tmp-extra`. The unapproved real preview remains under `tmp-final/test_fresh_database_digest_and0/fresh-runs`.

   Reproduce from PowerShell in the isolated checkout (use a fresh `--basetemp` directory):

   ```powershell
   $env:PYTHONPATH='C:\Projects\alive-review-11'
   & C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q
   & C:\Projects\alive\.venv\Scripts\python.exe -m pytest -q -s C:\Projects\alive-review-11-evidence\test_review11.py --basetemp=C:\Projects\alive-review-11-evidence\fresh-reproduction
   & C:\Projects\alive\.venv\Scripts\python.exe -c "from scripts.verify_archive import verify; [verify('archives/'+x) for x in ['ALIVE-14-R1','ALIVE-14-R2','ALIVE-14-R3','ALIVE-14-R4']]"
   & C:\Projects\alive\.venv\Scripts\python.exe scripts/verify_alive14r3_protocol.py
   git diff 4bdefea1bb0eb198d06db2b0518d6f13d1f7d6ad HEAD -- alive scripts tests extension
   git diff ac11be81115f397a9bad9f5c630a74ee22bdc3d2 HEAD -- archives/ALIVE-14-R1 archives/ALIVE-14-R2 archives/ALIVE-14-R3
   ```

   Focused baseline references: `tests/test_alive14r4.py` (revocation, staged execution, fatal errors, approval caps, dispatch ambiguity, missing output and revisions); `tests/test_research_memory.py` (withdrawal, final dispatch, blinding, evidence contracts); `scripts/verify_archive.py`; `scripts/verify_alive14r3_protocol.py`.
