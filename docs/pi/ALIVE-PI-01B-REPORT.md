# ALIVE-PI-01B — qualification report

Status: **draft PR. The first candidate (`b2208a8`) was independently reviewed and BLOCKED; this
version remediates that review and needs re-review.** Not merged. No paid inference was performed: every
provider call in every test and integration run below went to a scripted local server with a
throwaway credential.

| | |
| --- | --- |
| Branch | `feat/alive-pi-01b` |
| Base | `main` @ `ad34e40`, which includes PR #64 (the F-002 fix) |
| Branch point | `c0fe57e`, the F-002 fix commit (the local runs below were made on this base) |
| Code under test | the head SHA recorded in the PR description (this file is part of that head) |
| Platform of local runs | Windows 11 (Python 3.13, Node v25.8.2 locally; Node v24.22.2 in Docker), Docker 29.8.0 |

PI-01B was built on the F-002 fix because the Pi path must not be able to leave a `ModelInvocation`
permanently `reserved` (the audit gate for PI-01B). #64 merged while this PR was open, so the PR
targets `main`; the diff contains only PI-01B. The local test results were obtained at the branch
point; the merge commit `ad34e40` adds no code beyond `c0fe57e`, and CI re-runs the suite against it.

## A. Findings

1. **Cancellation is a three-way fact, not two.** Cancelling while a provider request is in flight
   is neither "cancelled" nor "failed": the provider may or may not have processed it. PI-01B keeps
   cognition's existing `cancelled` label for the no-dispatch case and records the in-flight case as
   run `UNKNOWN` / request `ambiguous` in its own tables (decision recorded with the owner).
2. **Pi prices an unpriced custom model at zero.** Pi's own usage/cost output cannot be used for
   accounting. ALIVE records only what its egress observed; cost is `null` ("unknown, not zero").
3. **`prompt` success is not completion.** Real Pi acknowledges a prompt and may answer
   `disposition: "handled"` (never settles). `agent_settled` is the only terminal event; `agent_end`
   is not final. The runner implements exactly that and fails typed otherwise.
4. **Restart already reconciles reservations** (F-002 work): a stale `reserved` invocation becomes
   `interrupted`, so a retry of the same reservation is refused at the gateway *and* by the unique
   `idempotency_key`. Two independent backstops against a double dispatch.
5. **Unconfirmed cancellation cleanup was invisible** in an early draft (the runner's result was lost
   when the task was cancelled). Found by a test; fixed by passing the result object in, so a
   cancelled run's receipt states whether the process tree was confirmed gone.
6. **Defences behind defences were untested** until mutation probing (see C): the gateway's re-checks
   of the runner's result (cleanup, stop reason, settled) and the offline/telemetry environment
   values had no test. Tests were added; all probes are now caught.

No blocker was found for starting PI-02. See G for what is *not* demonstrated.

## B. Implementation

New, all under `alive/pi/` unless noted: `states.py` (state machines), `models.py` + `migrations/versions/0007_pi_runs.py`
(`pi_runs`, `pi_provider_requests`, nothing else), `process.py` (process-tree supervision),
`runner.py` (pinned install, env/config isolation, RPC), `egress.py` (loopback metered endpoint),
`gateway.py` (`PiGateway`), `runtime.py` (lazy egress, recovery), `api.py` (read-only receipts).
Changed: `alive/model_gateway.py` (transport switch in `gateway_for`), `alive/app.py` (wiring),
`alive/config.py` (settings), `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`.
Added: `pi-runtime/` (pinned lockfile), `scripts/pi_integration.py`, `scripts/pi_image_smoke.py`,
`docs/pi/`. Pi events go to the existing `events` table (`source="pi"`). No workflow, capability or
research tables. Only `cognition.role` is migrated; `ALIVE_MODEL_TRANSPORT` defaults to `direct`.
Architecture: [ALIVE-PI-01B-ARCHITECTURE.md](ALIVE-PI-01B-ARCHITECTURE.md).

## C. Security evidence

| Claim | Evidence |
| --- | --- |
| Provider credential never reaches Pi | Pi's only "key" is a run-scoped token; PI-01A ratchet tests (no new `MetaProvider`, no new credential read) pass unchanged; real-Pi hostile tests; receipts/events scanned for the key (`tests/test_pi_gateway.py`, `scripts/pi_integration.py`). |
| Pi inherits no environment | `tests/test_pi_runner.py` (env keys *and* `PI_*` values); mutation R1/R6/R7 caught. |
| Developer's own Pi config / `AGENTS.md` / API-key env can't leak in | Canary tests with fake Pi and with real Pi (`tests/test_pi_real.py`). |
| No tools, extensions, skills, MCP, sessions | Flags pinned and asserted byte-for-byte; mutations R2–R4 caught; hostile "run bash / read auth.json" prompt with real Pi → 0 tool events. |
| Pi cannot widen spend, swap model or change schema | Upstream request is built from the approved request; parity with the direct path asserted with real Pi; a Pi-side request for model `gpt-evil` is ignored (the provider still sees ALIVE's model, schema and token ceiling) and a prompt that is not the approved one is refused with zero dispatch (`tests/test_pi_egress.py`). |
| At most N provider requests, never retried | Slot reserved atomically under `k.lock`; `dispatched` persisted before upstream; real Pi makes exactly 1 request on 401/429/500 (retry disabled); extra Pi requests are `rejected`. |
| Egress is loopback-only, run-token-authenticated, single-run | Bind/auth/expiry tests in `tests/test_pi_egress.py`; token unregistered after the run. |
| Receipts are authenticated, read-only, secret-free | `tests/test_pi_gateway.py`: 401 without token, no start/cancel endpoint, no prompt text/credential in receipts or events. |
| Supply chain | Exact version, lockfile with `sha512` for all 121 packages, registry-only, `npm ci --ignore-scripts`, name/version verified before every run, bundle SHA-256 recorded. |

Mutation probing (a mutant = one deliberately broken safety branch; "caught" = a test fails):

* Egress (`alive/pi/egress.py`): 7/7 caught.
* Gateway/recovery (`alive/pi/gateway.py`, `runtime.py`): 12/12 caught after adding tests for M10 and
  M12 (both initially survived).
* Runner isolation (`alive/pi/runner.py`): 8/8 caught after adding the offline/telemetry value test
  (R6 and R7 initially survived).

## D. Lifecycle evidence

| Scenario | Result (test) |
| --- | --- |
| Cancel with Pi running, nothing dispatched | run `CANCELLED`, no requests, tree confirmed gone |
| Cancel during the provider call | run `UNKNOWN`, request `ambiguous`, tree confirmed gone, provider hit once (fake and real Pi) |
| Provider timeout after dispatch | request `ambiguous`, run `UNKNOWN`, never retried |
| Provider 401/429/500 / invalid body | typed existing category, request `failed`, run `FAILED`, never retried |
| Pi crash / handled / rejected / flood / malformed / no-settle | typed failure, no upstream call, tree cleaned, deadline enforced |
| Pi changes the text it was given | run `FAILED` (`invalid_response`); spend kept on the invocation |
| Restart with a `dispatched` request | request `ambiguous`, run `UNKNOWN`, nothing re-dispatched |
| Restart with an undispatched run | `CANCELLED` |
| Same reservation twice (also across restart) | second attempt refused; provider saw one call |

Accounting is the existing Governor path, unchanged: `PiGateway` returns the provider's usage on a
settled call and raises a typed `ProviderError` (carrying any usage that was actually spent) otherwise,
and cognition settles the reservation from that exactly as it does for the direct transport. PI-01B
does not re-test cognition's reservation arithmetic; it tests that the `ProviderError` contract
(category, usage, `response_received`) is what cognition expects, and the settled-path end-to-end run
above shows every invocation `validated`.

## E. Qualification

Exact commands, all from the repository root. `uv run` uses the locked environment.

| # | Check | Command | Platform | Result |
| --- | --- | --- | --- | --- |
| 1 | Lint + format | `uv run ruff check alive migrations scripts tests` and `ruff format --check …` | Windows | PASS |
| 2 | Full backend suite | `uv run pytest -q -rs` (includes PI-01A ratchet/golden, cognition budget/recovery, migrations, PI-01B) | Windows | PASS: 833 passed, 7 skipped, 1 xfailed (12m30s). The skips and the xfail are existing and unrelated (superseded ALIVE-14 R4 paths; one deliberately unimplemented notebook check) |
| 3 | PI-01B fake-Pi suites | `pytest tests/test_pi_state.py tests/test_pi_process.py tests/test_pi_runner.py tests/test_pi_egress.py tests/test_pi_gateway.py` | Windows | PASS (within #2) |
| 4 | Real pinned Pi vs scripted upstream | `uv run pytest tests/test_pi_real.py` | Windows | PASS (10/10, ran, not skipped) |
| 5 | Real-Pi cognition investigation | `uv run python -m scripts.pi_integration` | Windows | PASS (13/13) |
| 6 | Docker image build (pinned Node, locked Pi, `--ignore-scripts`) | `docker build -t alive-pi01b:pi .` | Docker Desktop | PASS |
| 7 | Real Pi inside the image, non-root (uid 10000) | `scripts/pi_image_smoke.py` (see its docstring) | Docker | PASS |
| 8 | Real-Pi cognition investigation inside the image | `scripts/pi_integration.py` via `docker run … --entrypoint python` | Docker | PASS (13/13) |
| 9 | Existing isolated Docker E2E (default transport) | `docker compose -p alive-pi01b-e2e -f compose.e2e.yaml up --build --abort-on-container-exit --exit-code-from e2e` | Docker | PASS (6 groups) |
| 10 | Mutation probes | scratch scripts, results in C | Windows | PASS (0 survivors) |
| 11 | Backend on **Linux** | CI `backend (ubuntu-latest)` | CI | PENDING CI (not run locally) |
| 12 | Backend on Windows | CI `backend (windows-latest)` | CI | PENDING CI |
| 13 | Dashboard, notebook, first-contact PostgreSQL jobs | CI | CI | PENDING CI |
| 14 | Chrome extension demo (ALIVE-DEMO-INTEGRATION-01) end-to-end | – | – | NOT RUN (default transport is unchanged; covered by CI `first-contact-postgresql` and `dashboard`) |
| 15 | Paid / real Meta provider call | – | – | NOT RUN (forbidden without separate authorization) |

Image size (measured with `docker image inspect`): baseline (`main` Dockerfile) **1.28 GB** →
with Pi **1.64 GB** (**+0.36 GB**). The new layers are the Node binary (127 MB) and the locked Pi
install (163 MB, 156 MB on disk); the rest of the difference was not attributed. Pi is built into
the image whether or not `ALIVE_MODEL_TRANSPORT=pi` is used. If that is unwanted, building without
the `pi-runtime` stage is a one-line change but would make `pi` transport unavailable in that image.

## F. Deviations from the specification

1. **"Outbound request body hash"** is the hash of the *approved structured request*, not of the
   wire bytes. The wire bytes are produced by the unchanged `MetaProvider`; byte-parity with the
   direct path is asserted by test instead.
2. **Upstream-observed model** is not available from `Generation`, so receipts show the requested
   upstream model and Pi's observed alias only. Capturing the provider's echoed model would need a
   change to the PI-01A seam; deferred.
3. **Cost** is `null` rather than a number (no ALIVE price table for this transport).
4. **`shielded()`** in `alive/pi/process.py` duplicates `complete_despite_cancel` from the F-002
   fix because #64 is not merged; they should be consolidated once it is.
5. **Docker "real Pi" test** is a script run against the built image (and a CI-run equivalent), not a
   compose service, because no Docker job exists in CI today. It uses real Pi, real Node, the real
   app and egress, a real HTTP scripted provider, and no mock of Pi.

## G. Remaining limitations (not demonstrated)

* **Linux containment is best-effort, not a sandbox.** The first candidate's confirmation was
  falsified by the review (a `setsid()` grandchild survived while `cleanup_confirmed` was true).
  It is now fixed, but a descendant that is both orphaned before cleanup and scrubs its own
  environment cannot be found without cgroups or a PID namespace (see the architecture notes).
* Real Pi was exercised only for the paths above. **Pi's behaviour on a protocol it was not tested
  with** (other versions, other providers, tool-calling models) is unknown; the pin is the control.
* Pi is built into the default image, adding ~0.36 GB.
* The locked tree contains `undici` 8.10.2, which `npm audit` flags (excessive-content-encoding DoS;
  custom-TLS-option loss). Exploitability here is **not established** (Pi talks only to ALIVE's
  loopback and uses no custom TLS callback) but it is a known dependency risk. An integrity hash is
  not a vulnerability scan.
* The run token is a local bearer: Pi, and any same-user process able to read the per-run temp
  directory or probe the loopback port, can use it for that one run's single slot.
* Event/stdout flood handling is bounded (frame size, retained-event caps) but was not stress-tested
  with a large stream of *valid* frames.
* Startup recovery runs only in the process that owns the database (kernel ownership); concurrent
  multi-backend crash behaviour was not exercised. The Pi runtime is module-global: one app per process.
* `--ignore-scripts` skips two dependency install scripts; Pi 1.4.0 was verified to run without them
  on this platform only.
* No real Meta provider was contacted. Real provider behaviour (streaming, rate limits, usage
  fields) is represented only by the scripted server and the existing `MetaProvider` tests.
* A crash between "provider replied" and "reply persisted" is recorded `ambiguous` by design even
  though the provider charged for it; the Governor keeps the conservative reservation.
* Scripted-provider success does not demonstrate security of the whole system or the quality of any
  reasoning.

## H. Draft PR

URL, base SHA and head SHA are in the PR description.

Independent review instructions — please review in this order, at the exact head SHA:

1. **Provider-dispatch control:** `alive/pi/egress.py` (`_admit`, the `dispatched` marker, the
   absence of any retry) and `alive/pi/gateway.py` (`structured`, `_conclude`). Try to cause two
   provider requests for one reservation.
2. **Process isolation:** `alive/pi/runner.py` (`build_env`, `FLAGS`, `models_config`) and
   `alive/pi/process.py`. Try to get anything from ALIVE's environment, the developer's Pi config or
   the filesystem into Pi.
3. **Cancellation liability:** `gateway.py` cancel path, `runtime.recover`, `states.py`. Try to find a
   cancel/crash/restart ordering that leaves a request `dispatched`, a run non-terminal, or a
   reservation `reserved`.
4. **Credential custody:** grep the diff for any new reads of provider credentials; run the PI-01A
   ratchet (`tests/test_model_gateway.py`).
5. Re-run: `uv run pytest -q`, `uv run python -m scripts.pi_integration`, and on Linux the same.

## I. Next milestone readiness

**GO for PI-02 planning, conditional on:** (a) PR #64 merged first, (b) CI green on Ubuntu and
Windows at the reviewed head SHA, and (c) the independent review finding no double-dispatch,
isolation-escape, or non-terminal-state defect. If CI shows a POSIX process-tree failure, **REVISE**
before PI-02. Nothing here authorizes starting PI-02 or any paid inference.

## Remediation of the independent review (R1)

The review of `b2208a8` (Codex, retained outside the repository) returned **BLOCKED** with two
blockers and five further findings. All were reproduced independently on this checkout before any
change, then fixed, each with a regression that fails on the old code:

| ID | Severity | Finding | Fix | Regression |
| --- | --- | --- | --- | --- |
| PIB-01 | BLOCKER | Linux cleanup confirmed while a `setsid()` grandchild lived | Membership by group+session+descendants+run tag; freeze, kill, poll; Windows child created suspended into the job | `tests/test_pi_process.py` (4 POSIX tests run in Docker as uid 10000; they fail on the old `process.py`) |
| PIB-03 | BLOCKER | An admitted HTTP handler dispatched after the run was `CANCELLED`; a request stayed `admitted` under a terminal run | Atomic `_dispatch` (run must be `RUNNING`); `_settle` rejects never-sent slots in the run-terminal transaction; recovery repairs pending rows under terminal runs | `tests/test_pi_lifecycle.py` |
| PIB-02 | HIGH | Cancel between durable transitions left the run `ADMITTED` | One lifecycle owner (own task) with idempotent `_abandon`/`_settle` from first durable write | `test_cancel_after_every_durable_transition_ends_terminal` (PREPARED/ADMITTED/STARTING) and 2 more |
| PIB-04 | HIGH | Recovery turned an already-`ambiguous` request's run into `CANCELLED` | Ambiguous rows count as possible dispatch; any live state → `UNKNOWN` | 56-combination recovery matrix test with invariants |
| PIB-05 | HIGH | `ALIVE_PI_MAX_PROVIDER_REQUESTS=2` allowed two dispatches under one reservation | Setting validated to exactly 1; gateway refuses anything else before any write | `test_the_provider_request_ceiling_cannot_be_raised_above_one` |
| PIB-06 | MEDIUM | Event redaction retained prompt text and a run token used as a key | Allowlist rebuild: unknown keys dropped, text hashed, labels checked, numbers by key, bounded; Pi-reported identity/usage reduced; retained-event cap | `tests/test_pi_runner.py` redaction tests |
| PIB-07 | MEDIUM | Env test derived its oracle from `build_env`, so an added proxy variable passed | Literal expected key set, hostile parent env, exact values | `test_build_env_is_exactly_the_written_out_allowlist` and the child-env test |

Also from the review: the pinned CLI bundle digest is now **enforced** (`ALIVE_PI_BUNDLE_SHA256`)
rather than only recorded; the "loads no Pi code" claim for the default transport was overstated and
is corrected above; the `undici` advisory and the same-user-process limits are recorded in G.

**Remediation evidence is in the PR description** (commands, platform, exact SHA). The review's own
reproductions remain the acceptance test: a re-reviewer should re-run them against the new head.
