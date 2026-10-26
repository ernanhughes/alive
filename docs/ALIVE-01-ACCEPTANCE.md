# ALIVE-01 — First Contact acceptance report

Qualified locally on **26 October 2026**, on feature branch `codex/alive-01`. Starting HEAD was `7db2621fa4806e9b1930e1239c7131c3bc7998cf`, with a clean tree. The implementation and qualification are saved as local commits; no push, merge, deployment or publication occurred. Run `git log -2 --oneline` and `git status --short` for the exact final revisions. The unrelated untracked `models.txt` is preserved outside the commits.

## Integration classification

| Integration | Classification | Actual evidence |
| --- | --- | --- |
| FastAPI + persistent ALIVE | VERIFIED LIVE | Local health/capabilities, stable UUID, heartbeat, suspension, accepted goal, forced process restart and recovery |
| PostgreSQL | VERIFIED LIVE | Server **16.8** on localhost:5432; migrations through **0002**; event/memory/goal/run persistence and PostgreSQL full-text retrieval |
| pgvector storage | VERIFIED LIVE | Extension present, nullable `vector(384)` column created, capability reports storage available |
| Semantic retrieval | BLOCKED | No configured embedding model; endpoint explicitly returns 409; no random embeddings |
| ZeroMQ | VERIFIED LIVE | Real loopback PUB/SUB, separate subscriber, identity/correlation-preserving receipt and reconnect tests; First Contact recorded **39** subscriber receipts before restart |
| React/Vite dashboard | VERIFIED LIVE | Real APIs and authenticated cursor-based WebSocket; Chrome E2E covers timeline, search, agent result, goals, navigation and denial errors |
| Managed stable Chrome | VERIFIED LIVE | Navigate, inspect, fill, click, screenshot, close; unauthorized destination/element denied; Chrome **155.0.8059.85** |
| Chrome extension | VERIFIED LIVE | Actual MV3 extension loaded in isolated stable Chrome; actual panel document connects; DOM change reaches PostgreSQL; private/hidden content omitted; stop/revoke removes observer and preview |
| Native docked side-panel presentation | IMPLEMENTED BUT NOT VERIFIED | Manifest and Side Panel API are configured; automation exercised its extension page, not the native docked panel/toolbar interaction or activeTab grant on a non-local site |
| Pi RPC | VERIFIED LIVE | Pi **1.4.0**, provider **opencode**, model **gpt-6-luna**; streamed progress, persisted completed result, follow-up goal; a newly created run also completed through dashboard controls |
| Deterministic agent/provider | VERIFIED WITH MOCK | Deterministic offline generation plus agent run/progress/result, subprocess fixtures for errors/timeouts/cancellation |
| Meta gateway adapter | IMPLEMENTED BUT NOT VERIFIED | Backend-only environment contract, usage/latency/error handling, structured decisions and buffered streaming fallback; no Meta configuration or live calls |
| Chrome built-in AI | NOT IMPLEMENTED | Future provider; not required for First Contact |
| GitHub Actions | IMPLEMENTED BUT NOT VERIFIED | Windows/Linux checks, frontend build/tests, PostgreSQL/pgvector First Contact using mock agent; remote workflow not run/published |

## Principal acceptance demonstration

Command actually executed successfully with final runtime/API behavior:

```powershell
uv run python -m scripts.first_contact --runner pi --existing-dashboard
```

The script owns backend startup/restart; Vite was already running. It migrated PostgreSQL, started ALIVE, launched managed Chrome, navigated to `/demo`, filled a permitted field, clicked the transmit control, inspected the changed visible text and captured a screenshot. It verified forbidden destinations and unpermitted clicks return 403. It then retrieved the derived memory using **PostgreSQL full-text search**, completed a **live Pi RPC** run, accepted a proposed follow-up goal, rendered the observation in the real dashboard, terminated/restarted the backend and checked identity, memory, accepted unfinished goal and exact event cursor replay.

Latest controlled evidence (from ignored `.alive/first-contact.json`):

| Item | Persisted identity |
| --- | --- |
| ALIVE instance | `c63edf59-5194-4ccd-b5c2-7e528be49d36` |
| Observation event | `e8ba0be6-b730-4337-ae42-a4df5de23c89` |
| Derived memory | `98f7ccc7-2402-4fc4-a3ca-d6a3d445b0c2` |
| Accepted unfinished goal | `2ef751f4-bdba-4916-8341-5d9d5b0bb771` |
| Completed live Pi run | `f6ccd13d-c4c8-4092-93b4-e876a619200a` |

Both final script assertions printed PASS: the browser/event/memory/agent path and continuity after restart. Screenshots and controlled logs are local `.alive` artifacts and remain untracked. The extension path was independently exercised by `uv run python -m scripts.extension_smoke`; the main demo's perception source is the managed-browser adapter.

## Automated verification

- **12 backend tests passed**, none skipped. Temporary SQLite CRUD, duplicate event handling, causal/correlation preservation, memory retrieval, goal transition enforcement, scheduler heartbeat/suspension, stable identity/restart continuity, duplicate owner denial, security/degraded operation, WebSocket cursor replay, migrations/repeated upgrade, deterministic provider, real ZeroMQ subscriber/reconnect, Pi RPC fixtures for streaming/error/timeout/cancellation and cleanup.
- **4 frontend Vitest tests passed**, none skipped: authenticated API writes/errors and bounded event ordering/deduplication.
- **Chrome Playwright E2E passed with mock and live Pi selections.** It tracks the new run's returned ID, rather than accidentally inspecting an old completed run. It covers real timeline, memory search, goal creation, browser operations, permission denial and overview rendering.
- **Production frontend build passed** with TypeScript and Vite **8.3.5**. `npm audit` reported **0 vulnerabilities** at qualification time.
- **Ruff check and format check passed** for backend, migrations, scripts and tests.
- **Stable Chrome extension smoke passed**, including a real DOM mutation, PostgreSQL persistence, private/hidden-text exclusion and observer revocation. The connection initialization race discovered during testing was fixed by disabling credential inputs until saved settings finish loading.
- **PowerShell start/stop/restart scripts passed locally**; health returned `ok` after both starts. No PostgreSQL service/database outside ALIVE was modified.

Expected warnings: pyzmq registers Tornado's additional selector thread on Windows Proactor loops; Starlette emits a TestClient/httpx deprecation warning. Neither was hidden or counted as a failure. Live PostgreSQL behavior was checked by First Contact, not inferred from the SQLite suite. Live Pi behavior was checked separately from the controlled RPC fixtures.

## Implemented files and behavior

- `alive/`: configuration, Pydantic event/request/response schemas, SQLAlchemy persistence, event outbox/PUB-SUB, persistent kernel, deterministic drives, FastAPI/OpenAPI/authentication, Pi/mock runners, provider contracts, managed-browser policy/operations and controlled demo HTML.
- `migrations/`: frozen explicit schema migration 0001 and event time/outbox indexes 0002; PostgreSQL JSONB, generated `tsvector`/GIN and optional pgvector setup.
- `dashboard/`: React/TypeScript observatory with overview, real timeline, memory search/provenance, live agent console/history, browser controls/screenshots, runtime drives and goal transitions; lockfile, unit and browser tests.
- `extension/`: MV3 manifest, service worker, side-panel document/script and coalescing MutationObserver. Manual preview/send, explicit auto-send, connection status and revocation.
- `scripts/`: PowerShell developer startup/stop, reproducible First Contact with restart, real stable-Chrome extension smoke.
- `tests/`: runtime/security/recovery, migration, real transport and supervised RPC/provider tests.
- Repository configuration: `pyproject.toml`, `uv.lock`, `alembic.ini`, safe `.env.example`, updated `.gitignore`, CI workflow, README, contributing/security guidance and architecture/development/provenance/acceptance documents. The original Apache license was retained unchanged.

API/provider credentials, `.env`, generated tokens, logs, screenshots, browser profiles, installed dependencies and build output are ignored. They were not staged or committed. The owner-supplied local database secret is deliberately omitted from this report. Existing configured environment credentials supplied Pi access; no provider key was copied into ALIVE source.

## Run again

```powershell
uv sync --locked
cd dashboard
npm ci
cd ..
uv run alembic upgrade head
./scripts/dev.ps1
# Open http://127.0.0.1:5173 and supply the locally stored token.
uv run python -m scripts.extension_smoke
# To run the owned restart demonstration, stop development processes first:
./scripts/stop.ps1
uv run python -m scripts.first_contact --runner pi
# Leave the normal local app running afterward:
./scripts/dev.ps1
```

Current local URLs: dashboard `http://127.0.0.1:5173`, API/OpenAPI `http://127.0.0.1:8000/docs`, health `http://127.0.0.1:8000/api/v1/health`, controlled habitat `http://127.0.0.1:8000/demo`. These are local development servers, not a deployment. See DEVELOPMENT for configuring Pi's Windows executable, database environment, tokens and extension loading.

## Limitations and ALIVE-02

The native docked side panel, arbitrary-site activeTab authorization, remote CI and live Meta API remain unverified. Semantic search and actual vision are unavailable. The Meta adapter assumes an explicitly configured compatible chat-completions gateway; native server-side streaming is not advertised. There is no learning algorithm, distributed scheduler, multi-user authorization, database-encrypted secrets, vector model, automated migration-on-startup or automatic execution of proposed goals. Browser controls deliberately require explicit origin/element permission; screenshots are limited to the demonstration path. Dashboard browse lists are capped at 100 and the timeline retains 300 recent events; history remains in PostgreSQL. Tests append controlled demonstration experience to the local database.

For ALIVE-02: add bounded attention/goal evaluation to the cognitive heartbeat, a reviewable action approval/execution policy and measurable novelty/outcome experiments. Qualify the native side panel on a non-local controlled site. Configure one real Meta model and one explicit embedding model with provenance and usage budgets. Keep First Contact as the regression gate before extending autonomous behavior.
