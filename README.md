# ALIVE

**Adaptive Living Intelligence** — a persistent local runtime that perceives browser observations, remembers experience, proposes goals and survives restarts.

ALIVE-01 is a working vertical slice: FastAPI + PostgreSQL/pgvector + ZeroMQ + React dashboard + managed Chrome + Manifest V3 extension + Pi RPC. Deterministic policies drive curiosity, coherence and commitment. They do not require recurring model calls or claim to be reinforcement learning.

## Run on Windows

Prerequisites: Python 3.13, uv, Node 24+ (tested with 25.8.2), PostgreSQL and stable Chrome.

```powershell
uv sync --locked
Copy-Item .env.example .env
# Edit .env locally: set DATABASE_URL (or ALIVE_DSN) and a strong ALIVE_API_TOKEN.
# If ALIVE_API_TOKEN is omitted, ALIVE generates an ignored .alive/token file.
uv run alembic upgrade head
cd dashboard
npm ci
cd ..
./scripts/dev.ps1
```

Open the [dashboard](http://127.0.0.1:5173) and enter your local token. The [API documentation](http://127.0.0.1:8000/docs) describes the interface. The [controlled habitat](http://127.0.0.1:8000/demo) contains explicitly permitted interaction controls.

Stop the development processes with `./scripts/stop.ps1`. For foreground processes, use the separate commands in [development instructions](docs/DEVELOPMENT.md).

## First Contact

Stop the backend first. This demonstration owns its backend processes, restarts them and **adds** test experience to your existing ALIVE database. It never drops or resets it.

```powershell
uv run python -m scripts.first_contact --runner mock
# With local Pi credentials/model configured:
uv run python -m scripts.first_contact --runner pi
```

It launches managed Chrome, changes the habitat, verifies PostgreSQL full-text retrieval, ZeroMQ delivery, dashboard rendering and agent completion, accepts a follow-up goal, restarts the backend and checks continuity. Evidence stays in ignored `.alive/first-contact.json` and `.alive/first-contact.png`.

Use `--existing-dashboard` when Vite is already running. See [acceptance evidence and limitations](docs/ALIVE-01-ACCEPTANCE.md).

## Chrome extension

Open `chrome://extensions`, enable Developer mode, select **Load unpacked**, and choose the repository's `extension` directory. Click the ALIVE toolbar icon to open its side panel. Configure the backend and local token, then click **Authorise this page**. Review and send an observation, or explicitly enable automatic sending. **Stop & revoke** disconnects the observer and clears its selected observation.

The extension uses `activeTab`, scripting, storage and the Side Panel API, with host permissions limited to the local backend. It excludes form values, hidden text and marked private subtrees. Arbitrary webpage observation requires a fresh toolbar grant; the test habitat is already covered by the narrow backend host grant.

## Verification

```powershell
uv run ruff check alive migrations scripts tests
uv run ruff format --check alive migrations scripts tests
uv run pytest -q
cd dashboard
npm test
npm run build
# With backend and dashboard running:
npm run test:e2e
cd ..
uv run python -m scripts.extension_smoke
```

The default unit suite uses temporary SQLite databases, labels substring search correctly and exercises real loopback ZeroMQ. PostgreSQL, Chrome, Pi and dashboard acceptance are verified separately; a mocked test is never treated as proof of live integration.

Read [architecture](docs/ARCHITECTURE.md), [development](docs/DEVELOPMENT.md), [security](SECURITY.md) and [provenance](docs/HACKATHON_PROVENANCE.md). Apache-2.0; the repository's original license is preserved.
