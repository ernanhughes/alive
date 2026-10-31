# L1 Stage A R2 — destination binding and transport security

Decision requested: **independent re-review; do not merge automatically.** Level 1 remains
unqualified pending that review, final-head CI and the outstanding owner retention decisions.
No PI-03C, L2 or L3 implementation is included.

## Baselines and preservation

Reviewed PR #83 head: `e3a28b1fb0bb3c15e0cb38b4f9d8c222443e36c5`.
R2 executable code and frozen mutation baseline:
`aa6c328cdc2e5f72ac515c68aabba5916d495206`. Later delivery edits concern comments,
documentation, receipts and an extra assertion proving the poisoned gateway was constructed.
The exact delivered SHA and current CI are on PR #83.

Work continues on `codex/l1-qualification` in `C:/Projects/alive-l1-qualification`.
The clean primary checkout and the independent reviewer's detached worktree at
`C:/Projects/alive-review83` were preserved. Its untracked `tests/review_probe_pr83.py` was
read and adapted into permanent regressions; the original was not changed. No paid inference
or sensitive source material was used. All source/provider/proxy/TLS fixtures are synthetic.

## Root causes and reproductions

1. **Substituted snapshot.** Live settings were the dispatch fence's authority input, while the
   provider used an earlier independent settings snapshot. Briefly setting the override to
   `https://attacker.example/v1/chat/completions` only during gateway construction, then restoring
   settings, passed the fence and sent the request to that URL. The reviewer's P1 probe failed
   before R2 with the actual captured attacker URL. After R2 it proves the evil snapshot was
   constructed, then observes **zero outbound requests**. The supported approved endpoint still
   succeeds through real admission, Pi, validation and report generation.
2. **Ambient routing and CA trust.** HTTPX trusted environment proxies and certificate variables.
   A real local proxy listener received CONNECT under `HTTPS_PROXY` before the fix (uppercase
   and lowercase reproductions). The same socket-based assertions pass after R2. No test makes
   a request to a live provider or public network endpoint.
3. **URL differential during integration.** A copied reviewer URL probe exposed a leading-space
   URL accepted by `urlsplit` but treated as relative by HTTPX. This failed closed at transport,
   but should not be reviewable as an HTTPS destination. Admission now rejects whitespace and
   control characters. The preserved URL probes call the production validator rather than a
   copied formula; malformed/userinfo/query/fragment/port cases remain covered.

## Authorization-to-network contract

`workflows.context.model_claim` first uses the existing owner authorization validator, including
admission/source custody. For a typed analysis stage it then reads the immutable admission row
and produces `ApprovedModelDestination(admission_id, review_sha256, endpoint)`. This frozen
context is never derived from model output or a public request field.

Cognition stores that identity in the reserved `ModelInvocation.input_json` and passes it in
the frozen `StructuredRequest`. Pi preparation requires the request's destination to equal the
reserved identity. The existing WorkflowRunner dispatch fence additionally binds the persisted
identity to the exact immutable admission review. No independent gateway authorization path
or grant-minting mechanism is introduced.

The existing DirectMetaGateway forwards the typed context to MetaProvider. Immediately before
the network send, MetaProvider checks both its pinned effective endpoint and the actual built
HTTPX request URL against the approved endpoint. It sends that same checked request object,
using a local URL value rather than re-reading mutable settings. HTTPX canonicalization is
applied equally to the constructed request and approved URL; the initial pinned comparison
also requires the exact configured endpoint string. Mismatches raise the bounded, fatal
`destination_mismatch` provider category before any network send. They are not retried.

The upstream model client explicitly uses `trust_env=False` and `follow_redirects=False`.
The credential-bearing discovery client also disables ambient environment trust. There is no
synchronous model HTTP client or second inference client. The shared generate/decide/structured
paths retain the same `_request` transport. Existing explicit scripted transports remain
supported; no deployment proxy or CA feature is added. TLS verification is not disabled.

New admitted invocations bind the destination in their Pi approved-request hash. Requests
without an admission destination retain the old hash shape, so historical non-admission
identities and L1-01's no-inference behavior are preserved. No migration, executor, capability,
permission, security allowlist expansion, owner-grant widening or retention change is included.

## Tests and qualification

| Check | Result and limits |
| --- | --- |
| Initial analysis/reviewer/unit/environment/reservation group | 127 passed, one leading-space URL probe failed; validator corrected, affected reviewer/unsafe-URL group then 37 passed |
| Actual pinned/built-request destination plus invocation-context replacement probes | 11 passed; no outbound requests on four identity replacements |
| Persisted destination versus immutable review at dispatch | Passed; changing the retained review digest before the fence is refused |
| Stronger poisoned-snapshot construction assertion | Passed after the final test refinement |
| Model transport environment/TLS probes | Eight cases pass in the initial group: local proxy listeners, ignored invalid ambient CA paths, default rejection of a self-signed TLS server, explicit synthetic SSL context succeeds |
| Owner admission, ModelGateway, Pi gateway/egress, workflow authority/transactions, source custody, Bespoke | 203 passed; one real-Pi transaction case failed without the installed runtime path; that case and all workflow execution/fence probes pass with the explicit installed path (31 passed) |
| Real pinned Pi with scripted provider | 3 passed: full Chrome admission/report/reload journey, restored-settings snapshot attack and retained-event canary confidentiality |
| PostgreSQL | Source-custody/race/migration check and capability upgrade/downgrade/history check each passed on separate disposable databases; 7 analysis/destination/fence scenarios passed on a third disposable database |
| Dashboard | 112 tests passed; production build passed |
| Docker | Image built with Pi 1.4.0; disposable PostgreSQL migrated; 8 smoke checks and 6 HTTP journey groups passed |
| Changed-file Ruff / format / diff checks | Passed; final documentation-only validation uses diff checks |
| Full backend and Windows/Linux qualification on delivered head | CI pending, not duplicated locally or extrapolated from the focused checks |

Existing Windows Proactor/ZeroMQ selector warnings remain. Initial failed attempts are described
above rather than hidden or turned into passes. No timeout, production security allowlist,
skip or assertion was relaxed to make verification faster. The browser harness configures only
its own disposable loopback origin, with the normal production origin check still in force.

The browser harness starts the real app on the existing fixture's event loop with lifespan
already owned by the fixture. Owner confirmation is local/trusted; Chrome then authenticates,
inspects the endpoint disclosure, starts the approved workflow, awaits its real completion
response, reads the generated report and reloads history without a second provider call.
Only upstream inference is scripted. There are no test HTTP approval routes or mocked browser
API responses. Reproduce after building the dashboard and installing the pinned Pi:

```powershell
$env:ALIVE_TEST_ANALYSIS_BROWSER='1'
$env:ALIVE_TEST_REAL_PI='1'
$env:ALIVE_PI_RUNTIME_DIR='<existing pinned Pi directory>'
python -m pytest -q tests/test_analysis_browser.py
```

The browser journey is explicitly opt-in; a skipped default run is not browser qualification.
The TLS fixture's public certificate/private key are solely for a loopback server, never a
production credential or system trust-store installation.

Docker smoke image:
`sha256:fc92243b2f84bcbc48d2cd99ed1534da179968b1782dc403362be3106be1a677`.

## Isolated mutation follow-up

[Receipts and losslessly compressed logs](validation/l1-stage-a-r2/) pin the immutable code
baseline and exact command for each of the ten selected affected mutants. This is a targeted R2
campaign, not a claim to have replayed all historical mutants on the delivered head.

| Mutant | Outcome | Behavioral evidence |
| --- | --- | --- |
| M10b | Survived, equivalent | Disclosure approval is immutable and required at preparation; inspect-operation resolution still catches withdrawal/expiry |
| M16 | Killed | A real live inquiry without a workflow claim must receive the typed-stage refusal; arbitrary crashes no longer stand in for the expected refusal |
| M21 | Killed | A fabricated file must return `unknown_file`; a runtime exception is explicitly classified as a broken response contract and fails that behavioral assertion |
| M29 | Killed | Snapshot removal breaks the original post-fence pinning behavior; the new request check still protects destination safety |
| M30 | Survived, redundant | Removing the pinned-string check alone still leaves the constructed-request check blocking the unapproved destination |
| M31 | Killed | A substituted built HTTP request must not reach the scripted transport |
| M32 | Killed | A local proxy listener observes CONNECT when environment trust is deliberately restored |
| M33 | Killed | Dropping invocation destination authority must refuse at Pi preparation |
| M34 | Killed | Altered persisted review identity must refuse at the existing dispatch fence |
| C04 | Killed | Removing both destination comparisons lets the wrong destination reach transport, violating the no-dispatch assertion |

Totals: **8 behavioral kills, 1 equivalent survivor, 1 redundant survivor, 0 invalid**.
All deliberate edits occur in a fresh archive copy. Production worktrees remain unmutated;
the previous Stage A campaign/invalid attempts remain as historical evidence, superseded only
where R2 provides the stronger probe. No upstream production protection was removed for tests.

## Independent-review handoff and remaining boundaries

Please re-review the owner-review-to-HTTP-request boundary independently, particularly
`model_claim`, Cognition reservation, Pi preparation, WorkflowRunner's dispatch fence and
MetaProvider's built-request checks. Attack restoration around snapshot construction, missing
or forged admission identity, modification after request construction, environment proxies,
environment CA trust, redirects, cancellation and unknown outcomes. Verify a normal approved
endpoint control and the historical/no-inference paths. Preserve the reviewer's original probe
file for comparison; no independent acceptance is claimed by this implementation.

This is application-level destination enforcement, not DNS/IP pinning, an operating-system
network sandbox, provider identity attestation or a remote-provider retention guarantee.
Explicit future deployment proxies/custom CAs require separate reviewed disclosure and policy.

Qualification remains restricted to synthetic/non-sensitive or deliberately public sources.
Captures, prompts, responses and reports may remain locally stored in clear text. Source
withdrawal prevents new use; it does not erase history. Owner retention/deletion decisions
remain open. Do not advance to dependent intelligence stages until the corrected boundary and
necessary qualification contracts have independent acceptance.
