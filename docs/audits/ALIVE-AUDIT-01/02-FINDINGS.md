# ALIVE-AUDIT-01 — Findings

All main findings below affect **`1b6da07b856e497b3a44a9e1b9794e94adff55ab`**. PR54 and PR55 descend from that baseline and do not correct F-001, F-002, F-004, or F-007. Severity is assigned within the commissioned rubric. No finding establishes compromise of the user's machine or leakage of real credentials.

| ID | Severity | Classification | Result |
|---|---|---|---|
| F-001 | P0 | CONFIRMED DEFECT | Empty persisted token disables HTTP and WebSocket authentication |
| F-002 | P1 | CONFIRMED DEFECT | Cancellation at reservation transaction exit leaves a terminal investigation with a `reserved` invocation |
| F-003 | P1 | CONFIRMED DEFECT | Main's default Docker stack cannot run the shipped evidence-lifecycle demo; draft PR54 addresses it |
| F-004 | P2 | CONFIRMED DEFECT | Malformed provider envelopes escape typed failure handling or return invalid `Generation` values |
| F-005 | P2 | CONFIRMED DEFECT | Main's dispatch ratchet misses aliased provider construction; PR55 addresses tested case |
| F-006 | P2 | CONFIRMED DEFECT | Selected gateway does not enforce request operation identity; PR55 addresses tested case |
| F-007 | P3 | CONFIRMED DEFECT | Explicit output cap zero is silently replaced with 1536 |

The eight red audit cases represent six defect groups: F-004 has three variants. F-003 has separate Docker reproduction evidence.

## F-001 — Persisted empty token fails authentication open

**Locations:** `alive/config.py:64–67`; HTTP consumer `alive/app.py:173–174`; WebSocket consumer `alive/app.py:494`.

**Cause:** Configured tokens are checked for a minimum length, but a token read from an existing `.alive/token` file is only stripped. An empty/whitespace file therefore produces `token == ""`. Missing HTTP credentials also produce `value == ""`; constant-time comparison of the two succeeds. The first WebSocket frame similarly defaults a missing token to empty.

**Reproduce:** `test_empty_persisted_token_never_allows_unauthenticated_access` creates an empty token file in a temporary working directory, uses no configured token, creates a fixture database, and starts the actual application. It submits requests without Authorization and sends `{}` as the WebSocket authentication frame. Run the audit command with `-k empty_persisted_token`.

**Expected:** Refuse startup or deny unauthenticated protected reads/writes and the WebSocket stream. **Observed:** GET `/api/v1/alive` **200**; POST `/api/v1/goals` **200**; WebSocket delivered a persisted event without a token. [Impact receipt](receipts/empty-token-impact.json), [regression output](receipts/adversarial.txt).

**Impact and scope:** Complete authentication bypass in the affected local runtime. Precondition: no nonempty configured `ALIVE_API_TOKEN` and an existing empty/whitespace token file. No remote file-write exploit is claimed. An interrupted non-atomic first token write is a plausible source of the file state, but that process-crash trigger was not independently induced. Compose's explicit nonempty default token does not exercise this path. P0 reflects the rubric's critical safety control failing open, not a claim that default Docker was anonymously exploitable.

**Minimal correction:** Validate persisted token length/content with the same fail-closed rule as configured tokens; independently require nonempty credentials in HTTP and WebSocket auth. Generate a token atomically, with restrictive permissions. Add empty/whitespace/truncated persisted-token regression cases. Do not silently rotate an existing invalid token without surfacing the condition to the owner.

## F-002 — Reservation cancellation gap explains a real failing invariant

**Locations:** `alive/cognition.py:684` reservation transaction through `:732`; handler begins `:735`; invocation cleanup `:760–776`; terminal cleanup `:1131` (`finish`) does not reconcile reserved invocations.

**Cause:** The durable ModelInvocation and usage reservation are written outside the `try` that settles cancellation. Cancellation while the reservation context exits can bypass the handler. `execute()` handles the timeout by making the investigation terminal, but `finish()` leaves its invocation status untouched.

**Reproduce:** `test_timeout_in_durable_reservation_exit_settles_invocation` widens the scheduling window with an audit-only async context wrapper. It lets the real reservation commit, delays context exit, and allows the real one-second timeout to cancel the task before provider dispatch. It does not edit production data, alter the intended state transition, or call an external provider. Run with `-k timeout_in_durable`.

**Expected:** FAILED investigation with cancelled/otherwise explicitly settled invocation, no ongoing `reserved` record. **Observed:** FAILED investigation and invocation still `reserved`. Conservative token accounting remains; this probe does **not** establish undercharging or a paid call. The provider stub is never entered.

**Independent CI evidence:** [Run 40882738081](https://github.com/ernanhughes/alive/actions/runs/40882738081), same commit, Ubuntu job, failed `tests/test_recovery_budgets.py:137` with precisely `reserved != cancelled`; 618 passed, one failed. Windows job was cancelled, not passed. [Original failure log](receipts/ci-failed.txt). The original focused test and full suite both passed locally on Windows. The deterministic probe establishes a production cancellation gap; it does not prove which exact scheduler/driver event occurred in the historical Linux run.

**Impact:** Incorrect durable lifecycle status and misleading active-role reporting after terminal failure; a release-critical recovery assertion genuinely failed. Restart later marks stale invocations interrupted, which is not a substitute for correct timeout settlement.

**Minimal correction:** Put the durable reservation boundary inside explicit cancellation/reconciliation ownership; settle reservations on every terminal path, including cancellation during commit and cancellation during settlement. Preserve pessimistic charging for uncertain external dispatch. Add controlled barriers around precommit/postcommit/predispatch/postresponse settlement, rather than relaxing the timing assertion.

## F-003 — Main Docker demo is disconnected from shipped extension/fixture mode

**Locations:** `compose.yaml:30–39` (host 8080; no relationship fixture flag); `extension/config.js:1` (backend 8000); `extension/manifest.json:7` (host permissions); `alive/web_experience.py:41` (`PAGES` at 8000); `alive/research_relationships.py:328` (fixture provider gate).

**Reproduce:** Build/start main with fresh volumes. The isolated audit stack uses an explicit host-port override to 18081 to avoid the owner's already-running 8080 service; that override is recorded and does not fix the fixture gate. Run PR54's read-only-source HTTP lifecycle driver against main with `--base-url http://127.0.0.1:18081 --phase run` and the fake audit token.

**Expected:** The advertised default composed demo supports the shipped extension and deterministic lifecycle. **Observed:** The driver gets **403 `Claim fixture provider is disabled`** on outbound preview. [Receipt](receipts/main-lifecycle-negative.txt). Separately, the pinned main compose/extension values prove default port disagreement. Main's general smoke/E2E groups pass because they do not test this entire lifecycle.

**Impact:** Primary cold-start demo fails on current main, even though health/dashboard/ordinary API smoke pass. No security gate should simply be removed: refusal with test providers off is intended. The defect is deployment configuration failing to opt the explicitly local demo into its fixture contract.

**Minimal correction:** Review PR54's port alignment and demo-mode-bound fixture enablement. The pinned PR54 was independently exercised through HTTP and real unchanged Chrome extension, including restart and demo-mode-off 403. It remains an unmerged candidate, not release qualification of main. Arbitrary `ALIVE_HOST_PORT` overrides still do not move shipped extension allowlists; that limitation is documented in PR54.

## F-004 — Provider envelope validation is incomplete

**Locations:** `alive/providers.py:154–171`.

**Reproduce:** `test_malformed_response_is_typed_provider_failure`, three HTTPX MockTransport HTTP-200 bodies:

1. `{"choices": []}` → raw **IndexError** (not caught by the typed provider error handler).
2. First choice with `message.content = null` → returns successful `Generation(text=None)`.
3. First choice with content as a list → returns successful `Generation(text=list)`.

**Expected:** `ProviderError("invalid_response", response_received=True)` before returning a Generation. **Observed:** exception leakage or malformed success value. [Receipt](receipts/adversarial.txt). By contrast, a `finish_reason="length"` response correctly raises `output_truncated`.

**Impact:** Callers lose the promised error taxonomy; malformed transport output can be represented as provider success. Reviewed structured callers subsequently run schema parsing and generally fail closed. These tests do not establish acceptance of an invalid claim, execution of an action, or corrupted evidence. Provider-agnostic/multiple content-block support would need an explicit contract; silently returning a list under a string annotation is insufficient.

**Minimal correction:** Explicitly validate the envelope, nonempty choices, message shape and string content; normalize only documented provider structures. Validate usage shape separately and preserve response/usage liability on all malformed response paths. Add negative response-envelope tests at the real transport boundary.

## F-005 — Direct-dispatch scanner misses import aliases

**Location:** `tests/test_model_gateway.py:422`, name equality against literal `MetaProvider`.

**Reproduce:** Put `from alive.providers import MetaProvider as Alias` and `Alias(s).structured(...)` in `a_alias.py`, with clean `z_clean.py` after it. `check_allowlist(find_meta_constructions(tmp_path))` returns **[]**. The same first-file construction using the literal name is detected, proving the file loop itself works. See `test_alias_construction_is_detected` and `test_first_file_direct_construction_is_detected`.

**Expected:** Reject new direct construction regardless of import alias. **Observed:** Ratchet accepts the alias. No production alias bypass or unauthorized paid inference was found in this baseline; this is a defective release guard, not an observed runtime exploit.

**Minimal correction:** Resolve imports/assignments and fail closed on unsupported dynamic provider usage; add multi-file/alias/subclass/transport tests. PR55's own 32 tests pass, and all three independent scanner/operation probes pass on its exact head. [Independent PR55 receipt](receipts/pr55-independent.txt). Broader static analysis soundness is still not proven.

## F-006 — Gateway operation identity is unchecked at dispatch

**Location:** `alive/model_gateway.py:42–52`; factory checks its input at `:56`, but the returned gateway does not check `req.operation`.

**Reproduce:** Give the gateway for the cognition role a StructuredRequest whose operation is `audit.unauthorized` and a MockTransport. It dispatches successfully. `test_unknown_request_operation_refused` fails on main and passes on PR55.

**Expected:** Operation/request mismatch refused before transport. **Observed:** Request operation is ignored by main's gateway. Current production caller uses `cognition.role` correctly, so there is no demonstrated untrusted caller able to choose arbitrary gateway requests through the public API.

**Minimal correction:** Bind the gateway to the factory-selected operation and verify equality before dispatch, as PR55 proposes. Preserve admission/accounting in the caller; an operation string alone is not authorization.

## F-007 — Zero output cap is silently defaulted

**Location:** `alive/providers.py:104` (`max_output or settings.alive_meta_max_output`).

**Reproduce:** `StructuredRequest(max_output=0, ...)` via MockTransport produces `max_completion_tokens: 1536`. `test_zero_output_limit_is_not_silently_replaced` records the divergence.

**Expected:** Reject an invalid explicit zero before dispatch, or preserve it if supported; do not silently increase the caller's cap. **Observed:** Explicit zero becomes default 1536.

**Impact:** Internal interface edge case. Current cognition configuration enforces `output_tokens >= 256`; no public zero-budget bypass or spend violation was demonstrated. No inference was purchased.

**Minimal correction:** Use an explicit `is None` default and validate the accepted positive range at the request boundary. Document empty model/correlation behavior as well; production correlation IDs are ASCII UUIDs.

## Claims not promoted to defects

* **ENVIRONMENTAL OR EXTERNAL ISSUE / UNVERIFIED:** Contributor reports of dropped tool-call arguments. ALIVE's structured provider does not expose a general model-tool argument executor; Pi tools are disabled. No external contributor trace was supplied. Nested sentinel payloads survive ALIVE's tested transport boundaries.
* **UNVERIFIED:** Reported credential scanner with `walk(tree, None)` outside a loop. No credential-scanner implementation matching that report was located in tracked source. The matching ALIVE model-construction scanner has correct indentation and passes an independent first-file/last-clean-file probe.
* **INTENDED BEHAVIOR:** Evidence qualifier abstains on semantic truth; missing signature backend refuses qualified evaluation progression; class C actions remain unsupported; revoked grants cannot silently reactivate. These are safety contracts, not missing functionality defects.
* **COVERAGE GAP:** Exhaustive semantic review and mutation testing across every module/path are incomplete. See coverage matrix and test-integrity report. No claim of zero additional P0/P1 issues is justified.
