# ALIVE-PI-01B — architecture notes

Scope: the existing `cognition.role` model operation can run through a real, pinned Pi agent
(`@earendil-works/pi-coding-agent` 1.4.0) instead of calling the provider directly. Nothing else is
migrated. The default transport is unchanged: it starts no Pi process or listener and never
imports `PiGateway` (the app module does import the Pi package, for the receipts router).

```
Cognition ─ ModelGateway ─┬─ DirectMetaGateway ─ MetaProvider ─ provider      ALIVE_MODEL_TRANSPORT=direct (default)
                          └─ PiGateway ─ PiRunner ─ Pi ─ ALIVE egress ─ DirectMetaGateway ─ MetaProvider ─ provider
                                                                                          ALIVE_MODEL_TRANSPORT=pi
```

Pi is a **transport that ALIVE supervises**, not an authority. It is never given the provider
credential, never chooses the model, the token limit or the schema, and never decides whether a call
is paid for.

## Components (all under `alive/pi/`)

| Module | Responsibility |
| --- | --- |
| `states.py` | The two monotonic state machines (run, provider request). Terminal states are final. |
| `models.py` | `pi_runs`, `pi_provider_requests` (migration `0007`). Unique `idempotency_key` per run, unique `(run_id, seq)` per request, nullable `usage_json` (unknown ≠ 0). |
| `process.py` | Process-tree supervision. Windows: child created suspended, placed in a Job Object (`KILL_ON_JOB_CLOSE`), then resumed; confirmed via `ActiveProcesses`. POSIX: membership = group/session + every descendant by parent pid + every process carrying the run's unique environment tag; members are frozen (`SIGSTOP`) until the set stops growing, then killed, then polled. `shielded()` for cancellation-proof cleanup. |
| `runner.py` | `PiRunner`: pinned-install verification (`locate_pi`), per-run temp config, explicit env allow-list, Pi RPC (strict LF JSONL, `agent_settled` is the only terminal), event redaction. |
| `egress.py` | The loopback, run-token-authenticated, metered model endpoint Pi talks to. |
| `gateway.py` | `PiGateway`: one run per Governor reservation, admission, classification, shielded settlement. |
| `runtime.py` | Process-wide runtime: lazy egress start, restart recovery. |
| `api.py` | Authenticated, **read-only** receipts under `/api/v1/pi/`. No start or cancel endpoint. |

`alive/model_gateway.py` gains only the transport switch in `gateway_for`; `alive/app.py` wires the
runtime and router.

## Request path and who decides what

1. **Admission (ALIVE).** `PiGateway.structured` requires an existing Governor reservation (a
   `reserved` `ModelInvocation`) as `req.correlation`. No reservation, no run. One reservation pays
   for exactly one provider request: `MAX_PROVIDER_REQUESTS = 1` is a constant, the setting is
   validated to 1 and the gateway refuses anything else before any durable write (`pi_config_invalid`). `idempotency_key =
   "<operation>:<reservation>"` is unique, so a reservation is never dispatched twice, even across a
   restart.
2. **Pi is started with nothing.** `--mode rpc --no-tools --no-extensions --no-skills
   --no-prompt-templates --no-context-files --no-session --no-mcp --no-approve --offline`, an empty
   per-run cwd, a per-run temp `PI_CODING_AGENT_DIR` (`HOME`/`USERPROFILE`/`TMP*` too), retry
   disabled in `settings.json`, and an environment built from scratch (`PI_*` plus `SYSTEMROOT` on
   Windows). Nothing is inherited from ALIVE's process.
3. **Pi's only model** is a custom provider `alive-egress`/`alive-approved` whose `baseUrl` is the
   loopback egress and whose "API key" is a run-scoped single-run token.
4. **Egress (ALIVE).** For each request Pi makes: authenticate the token (hash lookup) → atomically
   reserve a request slot under `k.lock` (ceiling 1) → **atomically** check that the run is still
   `RUNNING` and persist `dispatched` before calling upstream (`_dispatch`; a cancelled or concluded
   run refuses, so no request can dispatch after the run lost authority) → build the upstream call **entirely from the
   approved request** (Pi's body is hashed and used only to check it is the prompt ALIVE sent) → call
   the existing `DirectMetaGateway` → persist the outcome → answer Pi with a streamed reply built
   from the settled text.
5. **Settlement (ALIVE).** The run settles from what was **durably recorded**, and Pi's own report is
   re-checked, never trusted: exactly one settled request, Pi settled and accepted the prompt, no tool
   events, `stopReason == stop`, Pi's final text equals the egress's record, process tree confirmed
   gone. Any failed check is a typed `ProviderError` and the Governor reservation is settled by the
   existing cognition code with the usage that was actually spent.

### Why Pi cannot widen spending, swap the model or touch the schema

The upstream request is a `StructuredRequest` that ALIVE built *before* Pi existed. The egress hands
it to `DirectMetaGateway` unchanged. Pi's body, `model`, `max_completion_tokens` and any tool or
format fields it adds are not read for any purpose except requiring `stream: true` and an equality
check on the user text.
`tests/test_pi_real.py` asserts parity: the provider sees the same body the direct path would send.

## State machines

```
run:      PREPARED → ADMITTED → STARTING → RUNNING → SETTLED | FAILED | CANCELLED | UNKNOWN
request:  admitted → dispatched → settled | failed | ambiguous        (rejected: refused before dispatch)
```

* `cancelled` is the existing label and is used only when **no provider request was in flight**.
* A cancel (or crash, or ALIVE restart) with a request `dispatched` is **`UNKNOWN`**, and the request
  is `ambiguous`. The distinction lives in PI-01B's own request records; cognition's existing
  `ModelInvocation` statuses are unchanged.
* `ambiguous` is never replayed. A timeout or network error after dispatch is `ambiguous`; the slot
  counter stops Pi asking again. Provider errors keep their existing categories (`authentication`,
  `rate_limit`, `server_error`, `invalid_response`, `timeout`, …).

## Cancellation and recovery

* The runner kills the **whole process tree** and confirms it is gone *before* a cancellation
  propagates (`shielded` cleanup). `cleanup_confirmed` is in the receipt; an unconfirmed tree fails
  the run (`pi_cleanup_unconfirmed`). See the limit under *Process containment* below.
* **One lifecycle owner.** From the first durable write, a single handler (`PiGateway._lifecycle`,
  run as its own task) owns the run. Any exit from it, error or a cancellation delivered at any
  `await`, goes through `_abandon` → `_settle`. A run is never left in a live state.
* **One settlement transaction.** `_settle` reconciles every request row (`dispatched` → `ambiguous`,
  never-sent `admitted` → `rejected`) and makes the run terminal in the same transaction that
  `_dispatch` serialises against, so none can be left `admitted`/`dispatched` under a terminal run.
* On startup `recover()` settles every non-terminal run **and repairs pending request rows even under
  an already-terminal run**: `dispatched` → `ambiguous`, `admitted` → `rejected`. A run with any
  `dispatched` **or already `ambiguous`** request → `UNKNOWN`; otherwise → `CANCELLED`. **Nothing is re-dispatched.** The
  existing cognition recovery has already moved the stale `reserved` reservation to `interrupted`, so
  a retry of the same reservation is refused (`pi_no_reservation`) and the DB uniqueness is a second
  backstop.

## Receipts (read-only, authenticated)

`GET /api/v1/pi/runs`, `/runs/{id}`, `/runs/{id}/events`. A receipt shows state and terminal reason,
Pi version + bundle SHA-256 + flags hash, requested upstream model vs Pi-observed alias, approved
request hashes, per-request state / HTTP status / usage / latency / error category, cleanup and
consistency facts, and cost. Cost is **`null` with a note** — ALIVE has no price table for this
transport, and Pi's own cost for an unpriced custom model is zero and is deliberately not used.
Receipts contain hashes, never prompt text, provider output, tokens or credentials.

## Pinned runtime and Docker

`pi-runtime/package.json` pins Pi to exactly `1.4.0`; `package-lock.json` hashes all 121 packages
(registry `sha512` integrity, all from `registry.npmjs.org`). `locate_pi` refuses any other
name/version before anything starts, and **enforces** the CLI bundle's SHA-256
(`ALIVE_PI_BUNDLE_SHA256`; identical on Windows and Linux), recording it on the run. The Dockerfile installs with
`npm ci --ignore-scripts` on a Node pinned by version **and** digest, copies the result next to the
app as the existing non-root `alive` user, and runs `cli.js --version` at build time so a broken
runtime fails the build. Treat a Pi version bump as a qualification event: change `package.json`,
the lockfile, `ALIVE_PI_PINNED_VERSION`, and re-run `tests/test_pi_real.py` and
`scripts/pi_integration.py`.

`--ignore-scripts` skips two dependency install scripts (`@google/genai`, `protobufjs`). Pi 1.4.0
starts and runs correctly without them, as tested.

## Configuration

| Setting | Default | Meaning |
| --- | --- | --- |
| `ALIVE_MODEL_TRANSPORT` | `direct` | `direct` or `pi`; anything else is a validation error. |
| `ALIVE_PI_NODE` / `ALIVE_PI_CLI` | auto | Override Node / Pi bundle paths. |
| `ALIVE_PI_RUNTIME_DIR` | `pi-runtime` | Where the locked install lives. |
| `ALIVE_PI_PINNED_VERSION` | `1.4.0` | Version `locate_pi` insists on. |
| `ALIVE_PI_BUNDLE_SHA256` | the 1.4.0 bundle digest | Bytes `locate_pi` insists on; empty disables the pin. |
| `ALIVE_PI_RUN_DEADLINE` | `120` | Seconds before a run is killed and failed. |
| `ALIVE_PI_MAX_PROVIDER_REQUESTS` | `1` | Validated to exactly 1 (one reservation, one provider request). |

## Process containment (what "cleanup confirmed" means)

* **Windows:** the child is created suspended, assigned to a Job Object, then resumed, so it never
  runs (or forks) outside the job. Confirmation reads the job's active-process count.
* **POSIX:** a process group is not containment, since a descendant can `setsid()` out of it. A run's
  members are the union of its group and session, every descendant by parent pid, and every process
  whose environment carries the run's unique `ALIVE_PI_RUN_TAG` (which finds a detached grandchild
  whose parent already exited). Cleanup freezes the members until the set stops growing (a stopped
  process cannot fork), kills them, and polls until no live member remains. Zombies are not alive.
* **Limit, stated rather than hidden:** without cgroups or a PID namespace, a descendant that is both
  orphaned before cleanup **and** scrubs its own environment cannot be found, and a process owned by
  another user cannot be signalled (cleanup then reports *unconfirmed*, which fails the run). This is
  process hygiene for a child that is not trying to escape. It is not an OS sandbox: the Node process
  runs as the same user, with ALIVE's filesystem and network access.

## Event retention

Pi's output is untrusted. A retained event is rebuilt from an allowlist: unknown keys are dropped (and
counted), free text is always hashed, protocol labels (`type`, `role`, `stopReason`, ...) survive only
if they are known values, numbers survive only under known keys, and depth/list length are bounded.
Pi's own reported identity and usage are reduced the same way. At most 200 events / 256 KiB are
persisted per run; the rest are counted (`events_dropped`).
