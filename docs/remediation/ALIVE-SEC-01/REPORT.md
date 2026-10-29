# ALIVE-SEC-01 — F-001 focused correction

Status: draft correction; **release remains NOT READY**. Stop after this focused PR and independent review. F-002, provider hardening, PR54/55 integration, PI-01B and combined release qualification are deliberately not implemented here.

Baseline: `1b6da07b856e497b3a44a9e1b9794e94adff55ab`.
Original independent audit: `codex/alive-audit-01` at `a918454`.
Reviewed implementation commit: **`6e312d9e146a6e668996f1ad73e5fbfd45e05d1f`**.

## Problem and correction

An existing empty/whitespace `.alive/token` file could supply an empty expected token. Missing HTTP credentials and a missing first WebSocket token also defaulted to empty, authorizing protected reads, writes and event history. The original audit reproduction fails on baseline again; [baseline receipt](receipts/baseline-audit-probe.txt). Newly added security regressions produced 21 failures and 5 passes on baseline; [receipt](receipts/baseline-security-tests.txt).

`prepare_local` now applies one token contract to configured and persisted tokens: at least 24 visible ASCII characters, without spaces/control characters or non-ASCII. Persisted LF/CRLF text-file endings remain compatible. Existing invalid files are rejected with a sanitized startup error and remain byte-for-byte unchanged; no automatic rotation occurs. Invalid UTF-8 decoder context is suppressed so startup tracebacks cannot disclose raw credential bytes.

First creation writes a unique private temporary file, flushes/fsyncs it, then publishes it with a non-overwriting hard link. Competing creators read and validate the winner. Failure before publication leaves no empty final token file; temporary files are cleaned up. On POSIX `mkstemp` uses mode0600 and a new `.alive` directory mode0700. On Windows the temporary file's inherited grants are removed and a single current-owner FullAccess DACL is applied **before secret bytes are written**, using a bounded `whoami` lookup and the Win32 `SetFileSecurityW` API. A filesystem unable to support secure publication fails closed rather than using an overwriting fallback.

HTTP and WebSocket consumers also independently reject absent/empty incoming credentials and an empty expected token. WebSocket authentication requires a string token and closes with1008 on refusal; no credentials are placed in URLs.

## Verification at the implementation above

| Check | Result | Evidence |
|---|---|---|
| Original F-001 audit probe, copied without assertion changes | **1 passed, 19 deselected** | [Fixed probe](receipts/fixed-audit-probe.txt) |
| Windows authentication regressions + existing runtime suite | **33 passed** | [Windows receipt](receipts/security-focused.txt) |
| Linux authentication regressions + existing runtime suite | **33 passed** in Docker | [Linux receipt](receipts/linux-focused.txt) |
| Lint / format of existing CI scope | Passed | [Lint](receipts/lint.txt), [format](receipts/format.txt) |
| Independent reviewer | See separately authored review | [Independent review](INDEPENDENT-REVIEW.md) |

The 27 new security cases cover invalid persisted bytes without rewriting them; configured-token validation; valid stored token/newline compatibility; actual denied HTTP reads/writes and WebSocket history; valid-token success; independent protocol denial with the loader deliberately bypassed; actual Windows private ACL/POSIX permissions; concurrent first creation; failure before publication; and credential-safe exception formatting.

The audit's F-001 assertion explicitly accepts refusing startup as a fail-closed result. The fixed corrupted-file path therefore refuses startup; the separate protocol tests independently prove 401/1008 and absence of unauthorized writes when the application starts. No existing assertion was weakened. The copied [probe](probes/audit_probe.py) is byte-identical to the original audit test source and runs only when explicitly selected; its other findings remain unfixed. Run from this checkout with its Python dependencies installed:

```powershell
uv run python -m pytest -q tests/test_authentication_tokens.py tests/test_runtime.py
uv run python -m pytest -q docs/remediation/ALIVE-SEC-01/probes/audit_probe.py -k empty_persisted_token
```

Linux used the baseline audit image's locked production dependencies, with the exact changed `alive/` and `tests/` mounted read-only and pytest9.1.1/pytest-asyncio1.4.1 added inside a disposable container. It is a focused cross-platform runtime check, not combined Docker demo qualification. Windows used the existing audit Python3.13 environment with this worktree on PYTHONPATH.

Full Linux/Windows GitHub CI status must be read at the final PR head; focused results do not substitute for that status. No combined release candidate is approved by this report.

## Limits and operator behavior

The legacy unversioned token format cannot identify arbitrary truncation that still leaves24 or more valid characters; that limitation also applies to the configured-token minimum-length contract. Below-minimum truncation is rejected, and an old client credential cannot match changed stored bytes. This fix does not invent a checksum format or rotate compatible existing tokens.

Existing valid token files are not rewritten or automatically re-permissioned. Operators with an invalid file must explicitly restore a valid credential or configure a valid `ALIVE_API_TOKEN`; the server will not repair it silently. Windows first-use creation requires the standard `whoami` utility, the Win32 security API and hard-link support. The change does not defend against a privileged/local attacker who controls the project directory or process environment.

No real provider credential was read or printed, and no paid inference was run. All frozen evaluation/archive material, the original audit commit/receipts and the owner's original checkout remain unchanged. This is F-001 remediation evidence only, not full-system assurance, human approval, or acceptance of unresolved P0/P1 risk.

## Post-merge CI correction (29 October 2026)

PR #56 merged at `94b0e9a` from reviewed head `626a3d1`, but its full Windows CI job was already failing at that head. The focused receipt's 33 passing Windows tests did not include the hosted-runner DACL behavior exercised by the full suite.

The failing assertion expected one access rule after `icacls /inheritance:r /grant:r`. The GitHub Windows runner's process default DACL carried four explicit ACEs (`LA`, `SY`, `BA`, `OW`), and `/grant:r` only replaces the named SID's grant; it does not remove the other explicit ACEs. The DACL was still protected and limited to the owner, Administrators and SYSTEM, so this was not an unprivileged disclosure, but it did not satisfy the documented single-owner rule.

The correction replaces the `icacls` mutation with `SetFileSecurityW` and an exact `D:P(A;;FA;;;SID)` descriptor. A regression now pre-populates extra explicit ACEs and proves they are removed. Focused authentication tests pass locally; the full hosted Windows/Linux CI result at the correction head is still required before this correction is treated as verified.
