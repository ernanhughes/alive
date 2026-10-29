# ALIVE-DOCKER-01 — Validation and Acceptance Report

Branch: `feat/alive-docker-01`
Base commit (origin/main): `83a8061ea1ce9e3acfd5f44427716c87e7b679d0`
(rebased from `b9978da` after PRs #47 and #49 merged; requalified from clean
volumes on the new base)
Final implementation commit: HEAD of `feat/alive-docker-01` at push time
(recorded in the draft PR description).
Toolchain: Docker 29.8.0, Docker Compose v5.5.1, Windows 11 + Docker Desktop.

## Launch command and browser URL

```
git clone https://github.com/ernanhughes/alive.git
cd alive
docker compose up --build -d
```

Browser: [http://localhost:8080](http://localhost:8080) (bound to loopback only).

## Actual container services

- `db` — `pgvector/pgvector:pg16`, healthy via `pg_isready`, named volume
  `alive-pgdata`, no published ports.
- `app` — multi-stage image (`node:24-slim` dashboard build + `python:3.13-slim`
  runtime, non-root `alive`), serves FastAPI + built React UI on one origin,
  named volume `alive-appdata`, healthy via stdlib `/api/v1/health` check.
- `e2e` (compose.e2e.yaml only) — same image with `entrypoint` overridden to
  `scripts/docker-e2e.py`; isolated `alive-e2e-*` volumes; never touches dev data.

## Database initialization

Fresh database: `alembic upgrade head` applied all six revisions on first start;
`/api/v1/capabilities` reports `backend: postgresql`, `available: true`,
`pgvector storage: true` (the `vector` extension installed on the pgvector
image; semantic *search* stays disabled without an embedding model, reported
honestly as `No embedding model configured`). Existing volumes are migrated, never
recreated; verified by restart test below.

## Genuine UI verified in a real browser

Yes. The container-served dashboard was driven in real Chrome: token entry,
`Backend connected` with zero console errors, live event stream counter
incrementing (same-origin WebSocket fix verified), Memory tab full-text search
for `Docker demo observation` returning `postgresql_fts` results with the seeded
fixture memory rendered. Screenshot: `docs/deployment/alive-docker-01-demo.jpg`.
The workshop default demo URL uses the container-loopback backend address because
managed-browser navigation executes server-side.

## Demonstration workflow executed

Idempotent seed (`ALIVE_DEMO_MODE=true`, default) created exactly one marker goal
(`Docker demo inquiry — Python 3.12 deprecation mirror`) plus one observation
ingested through the real `/api/v1/events` path and verified via
`postgresql_fts` search — all labeled fixture data, no inference. A genuine
interactive workflow (memory search) was completed by hand in the browser.

## E2E test results

`docker compose -f compose.e2e.yaml up --build --abort-on-container-exit
--exit-code-from e2e` → exit 0, `E2E OK: 6 groups passed`:
readiness, capabilities (postgresql + zeromq), frontend+fixtures (bundled UI,
`/demo`, all three `/demo-live-01/*` mirrors, unknown mirror 404),
goal-lifecycle (full transition chain + invalid-transition 409), evidence
workflow (ingest → fts retrieval → mock agent completion → event timeline),
failure-paths (401 unauthenticated, 404 unknown goal, vector-search 409 with
honest message). E2E used disposable `alive-e2e-*` volumes; dev data confirmed
unchanged afterwards (7 goals, exactly 1 marker goal).

## Regression results

- Host smoke test `scripts/docker-smoke-test.py`: 8/8 checks pass.
- New `tests/test_docker_config.py`: 7/7 pass.
- Full unit suite `pytest -q` on the rebased head: 562 passed, 7 skipped,
  1 xfailed, exit 0 (SQLite-based; PostgreSQL/Chrome/Pi acceptance covered
  separately by design).
- Dashboard production build (`tsc -b && vite build` inside Docker): pass.
- Playwright `dashboard/e2e/docker.spec.ts` against the composed app in real
  Chrome: 2/2 passed (production UI journey + offline fixtures).

## Outstanding failures and limitations

1. No managed Chrome in the slim runtime image: browser-session endpoints return
   honest 502 (`Browser operation failed; check Chrome and locator availability`);
   the demo and all tests use API-driven observation ingest instead.
2. Semantic/vector search returns 409 without a mounted embedding model; text
   search (`postgresql_fts`) is the supported Docker path.
3. No live Meta/Pi calls occur by default; both require explicit credentials.
   No paid inference was performed during this work.

## Paid inference / merge confirmation

No paid inference was performed or authorized. Nothing was merged; this work
targets a draft PR from the dedicated `feat/alive-docker-01` branch only.
No other workstreams were modified (worktree isolated from `origin/main`;
pre-existing untracked notebook files in the original checkout untouched).

## Acceptance gates

| Gate | Requirement | Result |
| ---- | ----------- | ------ |
| G1 | Clean image build succeeds | PASS |
| G2 | PostgreSQL initializes correctly | PASS |
| G3 | All migrations complete | PASS |
| G4 | Backend reaches healthy status | PASS |
| G5 | Actual ALIVE frontend loads on localhost:8080 | PASS |
| G6 | Demo workflow works without paid inference | PASS |
| G7 | Application data survives restart | PASS |
| G8 | E2E environment is isolated | PASS |
| G9 | Browser integration test passes | PASS (Playwright docker.spec.ts 2/2 in real Chrome + hand-driven UI journey) |
| G10 | Existing core test suite has no new regressions | PASS (562 passed, 7 skipped, 1 xfailed, on rebased head) |
| G11 | No secrets in images or commits | PASS (no provider keys in env, layers, or commits; dev-only placeholder token documented as local-only) |
| G12 | No unrelated source changes or branch interference | PASS |

Engineering verdict: **READY FOR INDEPENDENT REVIEW**.
