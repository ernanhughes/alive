# ALIVE Docker deployment

One-command local deployment of the real ALIVE application (FastAPI backend +
built React dashboard + PostgreSQL/pgvector).

## Quick start

```powershell
Copy-Item .env.example .env   # optional; safe local defaults exist
docker compose up --build -d
```

Open [http://localhost:8080](http://localhost:8080). When prompted for the local
token, use your `ALIVE_API_TOKEN` value (or the compose default
`alive-dev-token-replace-for-local-use-000`, local use only).

## Operational commands

```powershell
docker compose up --build -d      # start (rebuilds after source changes)
docker compose ps                 # service status
docker compose logs -f app        # application logs (startup diagnosis)
docker compose logs -f db         # database logs
docker compose exec app alembic upgrade head   # run pending migrations
docker compose exec app alembic current        # show applied revisions
docker compose stop               # stop without removing anything
docker compose start              # start again (data preserved)
docker compose down               # stop and remove containers (volumes kept)
```

Demo fixtures: `ALIVE_DEMO_MODE=true` (default) seeds one idempotent marker
goal + observation into a **fresh** database after first start. Restarts never
duplicate it and never touch existing data. Set `ALIVE_DEMO_MODE=false` to
disable seeding.

Smoke test (host, needs `ALIVE_API_TOKEN` matching the app):

```powershell
$env:ALIVE_API_TOKEN="alive-dev-token-replace-for-local-use-000"
uv run python scripts/docker-smoke-test.py --base-url http://localhost:8080
```

Isolated E2E (separate `alive-e2e-*` volumes, never touches dev data):

```powershell
docker compose -f compose.e2e.yaml up --build --abort-on-container-exit --exit-code-from e2e
docker compose -f compose.e2e.yaml down
```

Browser E2E against the composed app (Playwright, needs Chrome):

```powershell
$env:ALIVE_BASE_URL="http://localhost:8080"
$env:ALIVE_API_TOKEN="alive-dev-token-replace-for-local-use-000"
cd dashboard; npx playwright test e2e/docker.spec.ts; cd ..
```

## Destructive commands

`docker compose down -v` **deletes all ALIVE data** (database + token volume).
Never use it as a routine stop command. Use `docker compose stop` / `down`
(without `-v`) to preserve data. The e2e file has its own volumes; removing
them only discards disposable test data.

## Troubleshooting

- **Docker unavailable**: install Docker Desktop (Windows) or Docker Engine +
  Compose v2 plugin (Linux); verify with `docker compose version`.
- **Port 8080 occupied**: stop the conflicting process, or map another host
  port by overriding `ports` for `app`.
- **App unhealthy / 503 degraded**: `docker compose logs app`; usually the
  database was unreachable (`DATABASE_URL` host `db`) or migrations are
  pending — the entrypoint runs `alembic upgrade head` automatically.
- **Database connection errors**: `docker compose logs db`; check
  `POSTGRES_*` values match `DATABASE_URL` credentials.
- **Frontend shows "Backend disconnected"**: the token in session storage must
  equal `ALIVE_API_TOKEN`; use the header `local` button to change it.
- **Managed-browser actions fail (502)**: expected in this image — no Chrome
  is bundled. API/demo/fixture workflows are unaffected.
- **Vector search 409**: expected without a mounted embedding model; text
  search (`postgresql_fts`) is the supported Docker path.
- **Missing provider credentials**: live Meta/Pi calls need explicit keys and
  never run by default; the demo and tests use the deterministic mock runner.
