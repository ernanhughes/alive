# Development

## Environment

Backend: Python 3.13 and uv. Frontend: Node 24+ and npm. Main target: Windows, local PostgreSQL and installed stable Chrome. Docker is not required. Package versions are locked in `uv.lock` and `dashboard/package-lock.json`.

1. Run `uv sync --locked` from the repository root.
2. Run `npm ci` from `dashboard`.
3. Copy `.env.example` to ignored `.env` and configure your database and token.
4. Run `uv run alembic upgrade head`.

`DATABASE_URL` or `ALIVE_DSN` accepts `postgresql://` (normalized internally to asyncpg) or `postgresql+asyncpg://`. Never print or commit a real URL. The owner-supplied local credentials are stored only in `.env`. Existing environment variables take precedence over `.env`.

Without a database setting, the app uses `.alive/development.db` through SQLite. This is a labeled development substitute: no PostgreSQL full-text indexing or pgvector. Migrations are still required. If the selected database is unavailable or migrations are missing, health returns `degraded` and mutations return 503; the service does not silently switch databases.

## PostgreSQL provisioning

Use an administrator session only if the ALIVE database/role does not already exist:

```sql
CREATE ROLE alive LOGIN; -- assign a local password interactively with psql \password alive
CREATE DATABASE alive OWNER alive;
-- Connected specifically to alive, where the vector extension is installed locally:
CREATE EXTENSION IF NOT EXISTS vector;
```

Migrations attempt `CREATE EXTENSION IF NOT EXISTS vector`. If unavailable or unauthorized, vector storage is left nullable JSONB and capability discovery reports no pgvector. Adding the extension later requires a deliberate future migration to convert that fallback column. The runtime never creates unrelated roles or databases. Migration 0002 adds time/outbox indexes.

## Foreground startup

In one terminal:

```powershell
uv run uvicorn alive.app:app --host 127.0.0.1 --port 8000
```

In another:

```powershell
cd dashboard
npm run dev
```

Use Ctrl+C in each terminal to stop. `scripts/dev.ps1 -Install` installs locked dependencies, migrates and launches hidden backend/Vite processes. `scripts/stop.ps1` checks their recorded command lines before stopping them. It never stops PostgreSQL. Server process termination during development is recoverable; managed browser sessions should be closed from the dashboard first.

Read `.alive/token` locally if no token is configured. It is never returned by an unauthenticated API. The dashboard retains it only in session storage. Use the **local** header button to change it. Extension token storage is local extension storage; observation previews remain session-scoped.

Windows needs Tornado's selector bridge for pyzmq while retaining a Proactor event loop for Playwright/Pi subprocesses. The dependency is included; its informational runtime warning is expected. Do not switch the entire app to a Selector loop to silence it. Uvicorn is launched with one worker and without auto-reload.

## Pi

Install/configure Pi outside this repository; consult the installed `pi --help` and `pi auth check --provider PROVIDER --json --no-refresh`. Never use credential-printing commands in shared logs.

Set the JSON-array `ALIVE_PI_COMMAND` to an actual executable. On Windows use Node and the installed JavaScript launcher rather than a `.ps1` shell wrapper:

```dotenv
ALIVE_PI_COMMAND=["node","C:/Users/YOUR_NAME/.pi/agent/bin/pi-launcher.js"]
ALIVE_PI_PROVIDER=YOUR_PROVIDER
ALIVE_PI_MODEL=YOUR_MODEL
```

This machine completed a real run with Pi 1.4.0, provider `opencode`, model `gpt-6-luna`. Model catalog availability does not prove credential validity. The free model route returned a usage limit; the `opencode-go` route returned an upstream invalid-credential error. The working `opencode` route used existing environment credentials; none were copied into the repository.

## Browser and extension

Stable Chrome is used through Playwright's `chrome` channel. `ALIVE_HEADLESS=false` opens visible managed sessions. Allowed network origins default to `http://127.0.0.1:8000`; modify `ALIVE_BROWSER_ORIGINS` deliberately. Click/fill controls must opt in via `data-alive-allow`. Use `data-alive-private` to exclude a subtree from text perception.

Load `extension` unpacked in `chrome://extensions` and click its toolbar action. Configure backend and token in its side panel. Press **Authorise this page**, review its preview and **Send selected observation**. Automatic sending is off by default. **Stop & revoke** disconnects the observer, cancels its timer and clears local observation state. Full URL origins beyond the local backend rely on Chrome's temporary `activeTab` grant; no global host permissions are requested.

`uv run python -m scripts.extension_smoke` exercises the real extension in a disposable **stable Chrome** profile using Chrome's Extensions debugging API. The unsafe-extension-debugging flag is restricted to that isolated development profile; normal managed browsing never uses it. No security-policy bypass flags are used. The smoke test loads the actual panel document as an extension page; native toolbar/docked side-panel presentation still needs manual visual checking.

## Tests and First Contact

See root README commands. Unit tests create temporary SQLite databases; do not set them to a real user database. RPC subprocess fixtures verify framing, streaming, timeout, cancellation and cleanup. Real ZeroMQ tests use a separate subscriber and reconnect. The live acceptance script requires PostgreSQL and Chrome and records whether the runner is mock or Pi.

Run First Contact with the backend stopped. It starts its own backend (and Vite unless `--existing-dashboard`), closes its managed browser session, forcibly restarts its owned backend to verify crash continuity, and stops only its own processes. Evidence and logs stay ignored under `.alive`. It appends experience without resetting the database. For a clean dashboard, use a separately provisioned ALIVE development database rather than deleting existing experience.

## Meta gateway

Set `ALIVE_META_URL` to a complete compatible chat-completions endpoint, `ALIVE_META_MODEL` and `ALIVE_META_API_KEY` on the backend only. No live Meta inference was requested/executed without that configuration. API errors report HTTP status without echoing upstream response bodies or credentials.
