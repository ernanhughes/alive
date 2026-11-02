# ALIVE Docker deployment

One-command local deployment of the real ALIVE application (FastAPI backend +
built React dashboard + PostgreSQL/pgvector).

## Quick start

```powershell
./scripts/demo.ps1     # creates this checkout's token, then docker compose up -d --build
```

Open [http://localhost:8000](http://localhost:8000) and paste the token once. `scripts/init.ps1`
(run by `demo.ps1`) copies it to your clipboard and writes it to `.env` as `ALIVE_API_TOKEN`.
The token is **per checkout**: see [docs/DEMO-CREDENTIALS.md](../docs/DEMO-CREDENTIALS.md).

There is no shared default token. `docker compose up` on its own stops with a "Run
scripts/init.ps1 in this checkout" message when `.env` has no `ALIVE_API_TOKEN`; that is intended.

Without PowerShell: copy `.env.example` to `.env`, set `ALIVE_API_TOKEN` to a random value of at
least 24 visible ASCII characters, then run `docker compose up --build -d`. For example:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

The app is published on host port **8000** because that is the port the Chrome
extension is built for (its permissions, authorised pages and default backend,
and the server's page allow-list). Stop any dev backend on 8000 first.

## Local infrastructure defaults

The image installs the pinned 384-dimensional MiniLM ONNX model at
`/app/models/minilm` and enables semantic search, so the Infrastructure panel reports
**Semantic search: MiniLM · 384d** without a mounted model. The pinned Pi runtime is also in
the image; the Agents runner falls back to it when no `pi` executable is on `PATH`.

Compose probes an optional Ollama on the host at `http://host.docker.internal:11434`. If
Ollama is reachable and has a supported small chat model, ALIVE auto-configures Pi with
`ollama/<model>`; otherwise the panel and doctor report the exact missing piece. Ollama must
accept connections from Docker:

```powershell
# Restart Ollama with a non-loopback listener, then pull a small chat model.
$env:OLLAMA_HOST = "0.0.0.0:11434"
ollama serve
ollama pull qwen2.5:0.5b
```

Override detection with `ALIVE_OLLAMA_URL` and `ALIVE_OLLAMA_CHAT_MODEL`. To use a cloud Pi
provider inside the container, set `ALIVE_DOCKER_PI_PROVIDER` and `ALIVE_DOCKER_PI_MODEL`; host
`ALIVE_PI_*` values are deliberately not copied, so host-only credentials cannot leak in. Set
`ALIVE_EMBEDDING_ENABLED=false` for a text-only deployment. `mxbai-embed-large` is
1024-dimensional and is **not** compatible with the current `vector(384)` memory schema; the probe
reports it but does not select it.

## Evidence-lifecycle demo (fixture, no inference)

With the stack running, the pinned local mirrors are served at
`http://127.0.0.1:8000/demo-live-01/python-3.11.html`, `python-3.12.html` and
`synthetic-no-change.html`.

1. In Chrome open `chrome://extensions`, enable Developer mode, **Load unpacked**
   and choose this repository's `extension/` folder (the image does not contain it).
2. Open the extension side panel, set the token (default above), open the 3.11 mirror,
   review and save the excerpt, anchor the sentence, then open 3.12 and ask for the check.
3. The comparison runs through the deterministic `local_fixture_claim` provider, which
   compose enables only while `ALIVE_DEMO_MODE=true`. It is a **fixture result, not model
   reasoning and not source truth**. The paid Meta flags are not set.

Scripted check of the same lifecycle over HTTP (no Chrome needed):

```powershell
uv run python scripts/docker-lifecycle-check.py --phase run
docker compose restart app
uv run python scripts/docker-lifecycle-check.py --phase after-restart --goal-id <id printed by run>
```

With `ALIVE_DEMO_MODE=false` the fixture provider is refused
(`--phase expect-refused`).

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
$env:ALIVE_API_TOKEN = ((Get-Content .env | Select-String '^ALIVE_API_TOKEN=').Line -split '=', 2)[1]
uv run python scripts/docker-smoke-test.py --base-url http://localhost:8000
```

Isolated E2E (separate `alive-e2e-*` volumes, never touches dev data):

```powershell
docker compose -f compose.e2e.yaml up --build --abort-on-container-exit --exit-code-from e2e
docker compose -f compose.e2e.yaml down
```

Browser E2E against the composed app (Playwright, needs Chrome):

```powershell
$env:ALIVE_BASE_URL="http://localhost:8000"
$env:ALIVE_API_TOKEN = ((Get-Content .env | Select-String '^ALIVE_API_TOKEN=').Line -split '=', 2)[1]
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
- **Port 8000 occupied**: stop the conflicting process (often a dev backend), or set
  `ALIVE_HOST_PORT` (for example `ALIVE_HOST_PORT=8080`). The dashboard and API follow the
  override, but the Chrome extension is fixed to 8000, so the extension demo will not work.
- **App unhealthy / 503 degraded**: `docker compose logs app`; usually the
  database was unreachable (`DATABASE_URL` host `db`) or migrations are
  pending — the entrypoint runs `alembic upgrade head` automatically.
- **Database connection errors**: `docker compose logs db`; check
  `POSTGRES_*` values match `DATABASE_URL` credentials.
- **Frontend shows "Backend disconnected"**: the token in session storage must
  equal `ALIVE_API_TOKEN`; use the header `local` button to change it.
- **Managed-browser actions fail (502)**: expected in this image — no Chrome
  is bundled. API/demo/fixture workflows are unaffected.
- **Vector search 409**: the image should contain the pinned MiniLM model. Check
  `docker compose logs app` and `ALIVE_EMBEDDING_ENABLED`; text search
  (`postgresql_fts`) remains the fallback.
- **Ollama not detected**: the host listener must accept Docker connections
  (`OLLAMA_HOST=0.0.0.0:11434`), and `ALIVE_OLLAMA_URL` must point at it. Run
  `docker compose exec app python -m alive.ollama --url http://host.docker.internal:11434`
  for a read-only probe.
- **Pi says "Installed · model not configured"**: install a supported small Ollama chat model,
  or set `ALIVE_DOCKER_PI_PROVIDER` and `ALIVE_DOCKER_PI_MODEL` for a cloud provider whose
  credentials are present in the container. The pinned Pi runtime is already in the image;
  live model calls still need a provider.
- **Missing provider credentials**: live Meta/Pi calls need explicit keys and
  never run by default; the demo and tests use the deterministic mock runner.
