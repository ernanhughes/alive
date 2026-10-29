# ALIVE-SEC-01 — Independent focused review

Review date: 29 October 2026. Reviewer: a separate Codex review agent from the remediation implementer. This is engineering review evidence, not human approval to merge or release.

## Exact reviewed code

**Code commit:** `6e312d9e146a6e668996f1ad73e5fbfd45e05d1f`.

**Baseline:** `1b6da07b856e497b3a44a9e1b9794e94adff55ab`.

I inspected the complete production diff in `alive/config.py` and `alive/app.py` and the new `tests/test_authentication_tokens.py`. After the code commit was created, I checked the exact committed diff and confirmed that the working copies of these three files had no differences from that commit. Their committed changes match the code reviewed and tested below. Later documentation-only commits do not change this code identity.

Scope is F-001 only: fail-closed local credential loading, atomic first publication, file permissions, HTTP authentication, WebSocket authentication, and valid-token compatibility. F-002 and other audit findings are not corrected or accepted by this review.

## Findings and disposition

**No remaining actionable F-001 finding identified in this reviewed change.**

The shared validator rejects empty, short, non-ASCII, whitespace-containing and control-containing credential values, without printing their content. An invalid existing token is refused without rewriting it. Persisted LF/CRLF text-file endings remain compatible. Explicit configured credentials use the same format/minimum-length contract.

First publication writes a private temporary file, flushes and fsyncs its complete content, then publishes by a non-overwriting hard link. A concurrent winner is loaded and validated rather than replaced. Failure before publication does not create an empty token at the public path. POSIX temporary creation uses mode0600; Windows removes inherited grants and gives the current user's SID FullAccess before writing credential content. Windows identity/ACL subprocesses have bounded timeouts.

The HTTP consumer rejects missing credentials and an empty expected token before comparison. The WebSocket consumer separately requires a nonempty string credential and nonempty expected token; malformed initial frame shapes are refused. Thus token-loader refusal and protocol authentication are independently defended.

During review I raised the risk of exposing decoder exception context through a chained startup exception. The implementer suppressed that context and added a formatted-traceback regression. I independently checked the resulting behavior. I also identified two Windows ACL test harness issues: Windows PowerShell module autoload failure and the assumption that `icacls /save` always emits a UTF-16 BOM. The implementer corrected the harness while retaining its protected-DACL/single-FullAccess-ACE assertions. These were test-environment assumptions, not evidence of a production ACL bypass.

## Checks executed by this reviewer

All commands used `C:/Projects/alive-audit-01/.venv/Scripts/python.exe` with `PYTHONPATH=C:/Projects/alive-sec-01`, from the remediation worktree. No real credentials, paid models or owner database were used.

| Independent check | Observed result |
|---|---|
| Unchanged copied original audit probe: `-m pytest -q docs/remediation/ALIVE-SEC-01/probes/audit_probe.py -k empty_persisted_token --tb=short` | **1 passed, 19 deselected**. Startup refusal satisfies the original probe without weakening its essential assertion. The source audit package was not run in place by this reviewer. |
| New security suite during review, before final ACL test encoding correction | 26 passed, one failure caused by decoding BOM-less UTF-16LE ACL output. This failed attempt was reported rather than treated as a pass. |
| Final targeted rerun of `test_first_creation_is_stable_and_private`, `test_corrupt_token_bytes_never_enter_startup_traceback`, and `test_concurrent_first_creation_never_publishes_partial_or_replaces_winner` | **3 passed**. Actual Windows protected-DACL assertions, exception-context suppression and no-clobber concurrency assertions passed. |
| Additional independently constructed temporary-directory check: 32 first-use calls through 16 threads | Every call returned the same complete token; persisted value matched; no `.token-*` temporary files remained. No token value was printed. |
| Replace that temporary credential with whitespace, then call the real loader | ValueError; the invalid file's bytes remained unchanged. |
| `git diff --check` | Passed. |
| Compare the three reviewed code/test files against exact commit `6e312d9e146a6e668996f1ad73e5fbfd45e05d1f` | No differences. |

## Results supplied by the implementer

The implementer supplied the focused Windows receipt reporting **33 passed** for the new security and existing runtime tests. The implementer also supplied [the Linux Docker focused receipt](receipts/linux-focused.txt), which I read: **33 passed in 13.24s**. I did **not** independently execute that Linux run, so it is additional implementer evidence rather than my own runtime observation.

## Limits and release status

* This review does not establish full-system security or completion of ALIVE-AUDIT-01's outstanding semantic assurance.
* I independently exercised the Windows runtime; POSIX runtime/mode assertions rely on the implementer's Linux receipt and subsequent CI. Hosted Linux/Windows CI results must be assessed separately at the final candidate SHA.
* A legacy unversioned token that is shortened but still contains at least24 valid visible ASCII characters cannot be recognized as truncated from the stored string alone. Format/minimum-length corruption is detected; an old client credential no longer matches a changed stored token. Detecting arbitrary valid-looking truncation would require a separately designed storage format or integrity mechanism and is not claimed by this fix.
* No arbitrary-filesystem-attacker, symlink/DNS or whole-machine security qualification was performed. The existing single-owner local-runtime threat boundary still applies.
* No F-002 lifecycle/charging changes, combined PR54/55 candidate qualification, real-model inference or release approval is included.

Keep the corrective PR in draft pending the required independent human approval and CI assessment. The overall release remains **NOT READY** because the other blockers and verification gaps remain unresolved.
