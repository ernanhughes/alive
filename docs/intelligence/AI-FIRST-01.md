# Ask ALIVE — AI-FIRST-01

The Bespoke dashboard now opens on **Ask ALIVE**. The owner configures the existing Meta
endpoint/model in ALIVE settings, approves a captured repository source, and confirms one
bounded session on the owner machine. Subsequent goals need one **Ask ALIVE** click each.
The interpreter selects a shipped procedure; approved repository analysis runs automatically
and returns its citation-bearing report. Other procedures and consequential actions receive
no additional authority.

If the model chooses shipped file inspection, ALIVE returns the exact captured file evidence
locally, without a second model call. A poor procedure choice is still reported as such in
evaluation; executing inspection does not turn it into semantic verification.

Previously, each interpretation needed prepare, CLI approval, refresh, start and compose,
followed by another prepare/CLI approval/start for analysis. Three analyzed goals needed six
CLI approvals. Now one standing consent covers six calls (normally three interpretation and
analysis pairs); each subsequent goal needs zero CLI approvals. The initial source approval
is still required. Cancellation and individual run receipts remain available.

## Owner-local demonstration

Review `SOURCE` and the three frozen, independently assigned expected procedure labels in
`scripts/live_bespoke_demo.py`. They contain two public toy arithmetic files, not ALIVE's
private workspace. With the configured credential and pinned Pi installation:

```powershell
uv run python -m scripts.live_bespoke_demo --output C:/Temp/alive-live-demo-new --approve-live --model meta/muse-spark-1.3-contributor --max-calls 6 --max-tokens 200000
```

Choose a new output directory. The command forces production Pi transport, creates a disposable
SQLite database and workspace, records one consent, submits three goals, then restarts the app
and checks retained reports/receipts without dispatching again. It never installs dependencies,
changes your normal database, or substitutes a scripted provider. The ledger records exact
model, endpoint, invocation and Pi request IDs, measured usage, latency, source identity,
responses, baseline choices, false choices and abstentions. Monetary cost is unknown.

For a live dashboard run, add `--setup-only`, serve that disposable database/workspace with
`ALIVE_MODEL_TRANSPORT=pi` and the same model, then run only:

Include the disposable server's exact browser origin in `ALIVE_ALLOWED_ORIGINS`; otherwise
the existing origin check correctly rejects browser POSTs before any model dispatch.

```powershell
# ALIVE_BASE_URL and ALIVE_API_TOKEN identify that disposable runtime.
$env:ALIVE_LIVE_LEDGER = 'C:/Temp/alive-live-demo-new/evidence-ledger.json'
cd dashboard
npx playwright test e2e/live-ai.spec.ts
```

That scenario submits the three real goals through the dashboard, checks receipts, reloads
history without another POST and captures desktop/mobile screenshots. Never point it at an
unapproved or normal working runtime.

Stop that disposable server, then verify restart without inference:

```powershell
uv run python -m scripts.live_bespoke_demo --output C:/Temp/alive-live-demo-new --history-only
```

## Authorization and retained evidence

Standing consent uses the existing append-only event records; no migration or provider client
was added. It pins the approved capture/scope/classification, model/endpoint, role contracts,
capabilities, workflow/recipe identities and Governor configuration. The variable input is
future owner goal text, bounded to 1,000 characters. Session expiry, call count and conservative
token reservations bound disclosure. Reservations remain charged after failed/ambiguous calls.
The existing Governor separately measures and charges actual usage.

`python -m alive.admission inspect-trust ID` reads the complete terms.
`trust ID --confirm-sha256 HASH` approves them once; `untrust ID` revokes them. The Pi dispatch
fence rechecks standing consent and the exact per-goal Grant, including late revocation.
Missing consent/provider, changed scope/model/endpoint and exhausted budgets fail visibly.

`enable_model` selects/probes the real provider while leaving autonomy paused. Explicit,
authorized owner workflows may infer while paused; ordinary autonomous reasoning still
requires running mode. Restart retains paused mode and the provider. History endpoints only
read retained rows; they never resume a model request.

Source-reference checks establish that citations match captured files. They do not establish
semantic truth or release readiness. Existing memory/search and experience persistence remain
available; this slice does not silently disclose unrelated memories to the provider.

## Focused verification

```text
uv run pytest -q -o addopts="" tests/test_live_admission.py
uv run pytest -q -o addopts="" tests/test_repository_analysis.py::test_owner_authorized_analysis_runs_end_to_end tests/test_intent_interpretation.py::test_a_goal_is_interpreted_and_recommended_without_executing_anything tests/test_owner_admission.py
npm --prefix dashboard test -- src/admission/live.test.tsx
npm --prefix dashboard run build
```

The explicit `addopts` override selects these integration tests despite the temporary fast-test
default. No workflow/CI configuration changed and no full backend suite was run.

Live results and code identity are recorded separately in the evidence ledger. A three-goal
toy demonstration establishes the live path; it is not broad AI-quality or ALIVE-release
qualification. Keep the PR draft for independent review.

## Recorded demonstration — 1 November 2026

Final implementation `5f69b7baab4d09c52f1a7a49433051b7dcb39533` was qualified from a clean
checkout in Chrome through the built dashboard and production Pi, using
`muse-spark-1.3-contributor` at `https://api.meta.ai/v1/chat/completions`.

- Three successive goals, one standing consent, three Ask clicks, zero further CLI approvals.
- Five actual provider requests; 9,640 measured tokens; summed invocation latency 28,349 ms.
- Two completed analysis reports identified the wrong divisor (2 instead of 3 for `[2,4]`).
  The unrelated poetry request received a model-backed explanation that no procedure fits.
- Restart retained all three exchanges and reports. Provider requests stayed **5 → 5**.
- Final three-goal comparison: live hybrid 3 correct / 0 false choices / 1 abstention;
  raw-goal deterministic selector 1 / 0 / 3; fixed analysis 2 / 1 / 0. Correct abstentions
  count as correct. The tiny label set was frozen before inference and reused for qualification.
- An earlier contributor browser run made one false choice (inspection for the arithmetic
  question). It is preserved alongside the successful final run, not discarded. Initial API
  qualification used `muse-spark-1.3`; both contributor runs used the requested cheaper model.
- Across all three retained runs: 14 calls, 27,528 measured tokens. No cost estimate.

The committed [evidence ledger](AI-FIRST-01-evidence.json) contains exact goal/source/invocation/
Pi-request receipts, response hashes, measured usage and model output, including the false
choice. [Desktop](validation/ai-first-01-1440.png) and
[mobile](validation/ai-first-01-390.png) screenshots show the real final run.

Offline checks: 15 standing-consent scenarios, 30 existing admission checks, five dashboard
tests, targeted Ruff/format checks and the production build passed. Only the single live
browser scenario ran; no full backend suite, other E2E specs, Docker or heavyweight CI changes.
