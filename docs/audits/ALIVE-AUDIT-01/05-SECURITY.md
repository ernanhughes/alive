# ALIVE-AUDIT-01 — Security and data integrity

## Assessment

**Release-blocking authentication failure confirmed (F-001, P0).** An empty persisted token permits unauthenticated API reads, writes and WebSocket history access. This was reproduced only in a temporary fixture runtime. It is conditional on an invalid local token file and no configured nonempty token; it is not a demonstrated remote compromise or a statement that the explicitly token-configured Docker stacks were anonymously accessible.

The reviewed application has meaningful fail-closed controls, but a green test suite does not establish end-to-end security. No paid inference, real secret, owner database, or external exploitation was used. This is not a penetration-test certification or proof that no other vulnerability exists.

## Contracts and evidence

| Boundary | Observed protection / limitation | Audit outcome |
|---|---|---|
| HTTP authentication | Constant-time bearer comparison; readiness dependency protects API routers | Explicit bad bearer401 passes. Persisted empty token bypass confirmed; F-001 |
| WebSocket | First-frame authentication keeps tokens out of URL/access logs; allowed Origin enforced | Empty persisted token accepts `{}` and delivers event; F-001 |
| Local single-user ownership | `SECURITY.md` expressly defines one owner/local runtime; no multi-user ACL contract | Absence of tenant ACLs is intended. Exposing this service publicly is outside stated deployment contract |
| CORS / browser origins | Exact dashboard origins; HTTP auth separately permits `chrome-extension://` origins, still requiring token | Hostile ordinary Origin403 independently observed. Allowing extension schemes is not authentication by itself |
| Managed browser | Exact URL origin; deny credential-bearing URLs; route subrequests; no downloads/service workers; private DOM exclusions; explicit element operation permission | Source reviewed. Redirect/DNS/symlink/OS sandbox assurance is not exhaustive |
| Extension control messages | Sender extension ID and extension-page URL checks; observed tab and exact URL binding; allowed backend set | Source inspected and Node tests; unchanged native side panel against PR54 passed |
| Capture/source review | SHA of reviewed text; exact URL grant; capture-v2 entry bounds; pinned mirror identification | Independent hash mismatch403; changed snapshot remains changed; mutation removing hash guard killed |
| Goal / source identity | Current/historical memory/goal binding; exact hashes/anchors/revisions before request | Existing negative tests pass; selected revalidation paths reviewed. This is consistency inside owner DB trust, not independent source authenticity |
| Source withdrawal | Delete projection/vectors; same-transaction dependent consent/analysis/connection invalidation and scrubbing; active-source filtering on reads | Two-source isolation probe; real Chrome withdrawal + PostgreSQL + restart passed |
| Prompt injection | Page/memory inputs labelled untrusted; schemas/reference/quote validation; Governor owns permissions; class C action unsupported | Existing adversarial suites pass. No real-model jailbreak campaign performed; prompt wording alone is not a control proof |
| Paid inference | Explicit caller consent and budgets; reserve before dispatch; Meta disabled by default in audited stacks | Zero real inference. Provider-boundary cap0 default and request-operation defects exist; no public spend bypass demonstrated |
| Recovery / campaigns | No inference replay after restart; durable fatal campaign block, approval/index checks, conservative settlement | Full test baseline passes; selected ALIVE-14 paths inspected. Cognition reservation-window defect F-002 remains |
| Subprocess execution | Pi command is configured by owner, launched as argument vector with tools/context/MCP disabled; output fields restricted | No arbitrary model-generated shell-command path found in reviewed source. Real Pi invocation NOT EXECUTED |
| Filesystem | Static SPA path resolution checks containment; fixed mirror filename manifest; archive exporter bounds source under `.alive` | Selected path checks inspected. Exhaustive symlink/path/platform attack matrix NOT EXECUTED |
| Docker defaults | Host port loopback; PostgreSQL not published by audit compose; app runs nonroot; `.alive` directory700; explicit dev tokens/passwords | Defaults are public development values, not secret credentials. They do not qualify as strong deployment credentials. No public deployment tested |
| Logs / model input privacy | Provider errors categorized; database errors redacted; managed capture excludes private fields; visible content still may be sensitive | No real credentials collected or printed. Regex redaction is not a secret vault or general guarantee; authorized inputs can still contain sensitive text |

## Reported credential scanner

Tracked Python source contains a matching `walk(tree, None)` in the **model-construction ratchet**, `tests/test_model_gateway.py:450`. It is correctly nested under the per-file loop at main. The independent multi-file test puts the only rogue in the first file and a clean file last; it is detected. An import alias is missed for a different causal reason (F-005).

No repository credential scanner matching the reported indentation defect was found. Export utilities such as `scripts/archive11.py` apply simple credential-marker checks per exported text; that is not the reported AST scanner. The external scanner's source/commit/input/output remain **UNVERIFIED**, and no claim that it is safe is made.

## ALIVE-specific evidence integrity

The inspected evidence qualifier returns semantic abstention even when hashes/quotes are internally consistent. The claim validator uses exact bounded quotes, negation/qualification checks, subject entries and mirror identity; accepted relationship output is still labelled an unverified interpretation. Real Chrome displayed “Deterministic local demonstration · $0 inference” and “No external model was called”; the screenshot was visually inspected. No model output was relabelled as independent truth in the tested flow.

Changed source captures retain distinct identity/hash. Withdrawal removes active dependent findings and the tested restart does not resurrect them. These observations apply to the chosen fixtures and paths; they are not proof of correctness for all arbitrary text, source changes or concurrent transactions.

Eval02 sealed custody currently sets signature verification unavailable and refuses qualified progression. That is **INTENDED FAIL-CLOSED BEHAVIOR**. A passing structural evaluation must not be presented as independently qualified evaluation. Tests for substituted keys, outputs and trust roots ran in the full baseline; no frozen evidence was altered.

## Required next security work

1. Correct persisted-token validation and independent nonempty credential checks before any release (F-001).
2. Reconcile durable cancellation/settlement ownership (F-002), preserving uncertain-spend liability.
3. Harden provider envelope validation and gateway identity, and independently review PR55's static-analysis scope.
4. Perform a separate independent review of every remaining runtime and operational path, especially crash/commit windows, mutable consent/usage records, ownership lease loss, cancellation during settlement, symlinks and DNS/redirect boundaries. These are coverage gaps, not confirmed exploits.

No P0/P1 risk acceptance was supplied, and this audit does not accept those issues on the owner's behalf.
