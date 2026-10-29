# ALIVE-DOCKER-01 — Deployment Architecture Design

Base commit: `b9978da6bbededa88ad013952d2c165f85cc8cac` (`origin/main`).
Branch: `feat/alive-docker-01`. Status: design verified against the actual tree; no
assumptions about frameworks.

## A. Existing architecture (verified paths)

| Component | Implementation | Entry point |
| --- | --- | --- |
| Backend | FastAPI (`alive/app.py`, `create_app()` / `app`) | `uvicorn alive.app:app --host 127.0.0.1 --port 8000` |
| Frontend | React 19 + Vite 8 (`dashboard/`, `dashboard/src/main.tsx`) | dev `npm run dev` (5173); prod `npm run build` → `dashboard/dist` (gitignored, built in Docker) |
| Database | PostgreSQL via SQLAlchemy async + Alembic | `alembic upgrade head` (`alembic.ini`, `migrations/versions/0001..0006`) |
| pgvector | Optional `vector(384)` extension; `DO ... CREATE EXTENSION IF NOT EXISTS vector` with graceful fallback to JSONB (`migrations/versions/0001_foundation.py:129-145`); runtime probe in `alive/db.py:18-27` | `pgvector/pgvector:pg16` image |
| Event transport | In-process ZeroMQ PUB/SUB over loopback TCP (`alive/transport.py`); DB sequence cursor is the durable recovery source | no external broker |
| Managed browser | Playwright `chrome` channel + `extension/` (unpacked MV3 side panel); allowlisted by `ALIVE_BROWSER_ORIGINS` | not available in slim containers (see limitations) |
| Agent runner | `mock` (deterministic) or `pi` subprocess (`ALIVE_PI_COMMAND`) | default `mock`; no inference without explicit config |
| Inference | Meta Model API (`ALIVE_META_API_KEY`, default base `https://api.meta.ai/v1`, model `muse-spark-1.3`) | default `ALIVE_COGNITIVE_PROVIDER=mock`; no keys in images |
| Deterministic demo sources | Pinned local mirrors `fixtures/demo_live_01/*.html` + captures served by the backend itself at `/demo-live-01/{name}` (`alive/demo_live_01.py`); controlled habitat at `/demo` (`alive/demo.html`); synthetic claim fixtures (`alive/claim_fixtures.py`) | offline-capable, no network or inference |

## B. Runtime dependency graph

```
db (PostgreSQL+pgvector, healthy)
 └─► app (alembic upgrade head → seed marker check → uvicorn)
      ├─► serves /api/v1/* (health unauthenticated; everything else bearer token)
      ├─► serves /demo, /demo-live-01/* (unauthenticated fixture pages)
      └─► serves built dashboard dist/* + SPA fallback (same origin, no CORS)
```

Single application image serves both API and UI. No Redis/Celery/Kafka: the repo
uses none (ZeroMQ is an in-process loopback transport, `alive/transport.py:13-19`).
Two Compose services (`db`, `app`) are sufficient; workers, Pi and Chrome are
in-process or explicitly out of scope for the default offline demo.

Startup ordering is readiness-based, not sleep-based:
`app.depends_on.db.condition=service_healthy` (`pg_isready`),
entrypoint waits for TCP acceptance, runs migrations, then execs uvicorn;
Compose healthchecks poll `/api/v1/health` until `status == "ok"`.

## C. Database

- Supported version: PostgreSQL 16 (`pgvector/pgvector:pg16`, multi-arch).
- ORM/migrations: SQLAlchemy 2.0 async + Alembic; six revisions, idempotent
  `upgrade head` safe on existing volumes (never recreated, never downgraded).
- Extensions: `vector` attempted, absence tolerated (JSONB fallback + capability
  reporting at `/api/v1/capabilities`). Adding the extension later needs a new
  migration (documented in `docs/DEVELOPMENT.md`); Docker just ships an image
  where it is available.
- Persistence: named volumes `alive-pgdata` (Postgres) and `alive-appdata`
  (`/app/.alive`: generated token, agent workspace). Restart preserves both.

## D. Frontend and browser routing

Problem: `dashboard/src/api.ts` hardcodes `base = "http://127.0.0.1:8000"`,
correct for Vite-dev (5173 → 8000) but wrong when UI and API share one origin.
Fix (minimal, additive): `VITE_ALIVE_API_BASE` override → Vite-dev fallback →
same-origin (`""`). `fetch(base + "/api/v1" + path)` and
`base.replace("http","ws")` both work with `""` (same-origin fetch; `ws` derived
from `window.location`). `Cognition.tsx` uses `base + "/world/..."`, which
degrades correctly to `/world/...`.

The backend gains a guarded static mount: if `dashboard/dist` exists it serves
`/assets/*`, `/` and an SPA fallback that never shadows `/api/*`, `/demo*`,
`/docs`, `/openapi.json` or `/redoc`. API behaviour is otherwise untouched.
`ALIVE_ALLOWED_ORIGINS` defaults to the Vite ports; Compose overrides it with
the browser-facing origin `http://localhost:8080` (+ 127.0.0.1). Internal
hostname `db` never reaches browser JS: the browser only talks to
`http://localhost:8080`.

## E. Security review

| Variable | Required locally? | Sensitive? |
| --- | --- | --- |
| `DATABASE_URL` / `ALIVE_DSN` | yes (Compose provides `postgresql+asyncpg://alive:…@db:5432/alive`) | yes (password) — never baked into layers, only runtime env |
| `ALIVE_API_TOKEN` | yes (≥24 chars); generated to `.alive/token` if empty | yes - required; `scripts/init.ps1` writes one token to `.env` and `.alive/token` |
| `POSTGRES_DB/USER/PASSWORD` | yes (Compose defaults, overridable) | yes (password) |
| `ALIVE_ALLOWED_ORIGINS`, `ALIVE_BROWSER_ORIGINS` | yes (safe local defaults in Compose) | no |
| `ALIVE_META_API_KEY` / aliases, `ALIVE_META_URL/BASE_URL/MODEL`, `ALIVE_ROLE_MODELS` | only for live inference; empty by default | yes — never committed, never in images |
| `ALIVE_PI_COMMAND/PROVIDER/MODEL` | only for live Pi runs; default `mock` runner | credentials live outside the repo |
| `ALIVE_EMBEDDING_ENABLED/PATH`, `ALIVE_COGNITIVE_PROVIDER` | optional; defaults `false`/mock, no inference | no |
| `ALIVE_DEMO_MODE` | Docker-entrypoint only (`true` default); idempotent fixture seed, never wipes data | no |

No secrets are committed; `.dockerignore` excludes `.env`, `.alive/`, `node_modules/`,
`dist/`, caches and logs.

## F. File changes (this PR)

- `Dockerfile` (multi-stage: `node:24-slim` frontend build + `python:3.13-slim`
  runtime, `uv sync --locked`, non-root `alive`, stdlib healthcheck, exec-form entrypoint)
- `.dockerignore`, `compose.yaml` (db+app, `127.0.0.1:8080:8000`, named volumes,
  healthchecks), `compose.e2e.yaml` (isolated `alive-e2e-*` volumes + API + browser E2E)
- `docker/entrypoint.sh`, `docker/healthcheck.py`, `docker/README.md`
- `scripts/docker-smoke-test.py`, `scripts/docker-e2e.py`, `scripts/docker-demo-seed.py`
- `dashboard/e2e/docker.spec.ts` (production UI journey against the composed app)
- `tests/test_docker_config.py` (no-Docker config regression test)
- `alive/app.py`: guarded static serving of `dashboard/dist` (additive only)
- `dashboard/src/api.ts`: configurable base; `dashboard/src/main.tsx`: absolute demo-URL default
- `.env.example`: Docker section with real variables only
- `docs/deployment/ALIVE-DOCKER-01-design.md` (this file),
  `docs/deployment/ALIVE-DOCKER-01-test-report.md` (validation evidence)

## G. Known limitations (honest, not hidden)

1. Managed Chrome is unavailable in the slim runtime image: browser-session
   endpoints return honest `502` (`browser_operation` in `alive/app.py:417-431`);
   the demo journey therefore uses the `/demo` + `/demo-live-01/*` fixture pages
   through API-driven observation ingest, not live Chrome automation.
2. Semantic/vector search reports unavailable unless an embedding model is
   mounted; text search (`postgresql_fts`) is the supported Docker path.
3. Live Meta/Pi calls require explicit credentials and never run by default.
