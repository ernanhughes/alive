# ALIVE environment: what it needs and where to look

Start here when something is wrong or before a demo:

```bash
uv run python scripts/alive_doctor.py
```

It is read-only. It lists **every** setting ALIVE knows (generated from `alive/config.py`, so it
cannot go stale), where each value came from, what is installed, and what is missing, with a
`fix:` line for each problem. Secrets are shown only as `set (N chars)`.

## How a setting gets its value

1. A variable in the **process environment** (your shell, system variables) wins.
2. Otherwise a variable in **`.env`** in the repository root.
3. Otherwise the default in `alive/config.py`.

A shell variable silently overrides `.env`; the doctor's `source` column shows which applied.
A few settings have more than one accepted name (`DATABASE_URL` or `ALIVE_DSN`;
`ALIVE_META_API_KEY`, `MODEL_API_KEY` or `META_API_KEY`). The first listed wins and the doctor warns
when several are set. A misspelt `ALIVE_*` name is **ignored without an error**; the doctor lists those.

## Two different "Pi"s

| | Used for | Configured by | Installed by |
| --- | --- | --- | --- |
| External Pi | The Agents runner | `ALIVE_PI_COMMAND`, `ALIVE_PI_PROVIDER`, `ALIVE_PI_MODEL` | You, outside the repo (see `docs/DEVELOPMENT.md`) |
| Pinned Pi | Governed model calls and workflows when `ALIVE_MODEL_TRANSPORT=pi`; the Pi test suites | `ALIVE_PI_RUNTIME_DIR`, `ALIVE_PI_NODE`, `ALIVE_PI_CLI`, pinned version and bundle hash | `npm ci --ignore-scripts --prefix pi-runtime` |

The pinned install is verified by version and SHA-256, and a different build is refused. By default
`ALIVE_MODEL_TRANSPORT=direct`, so the pinned Pi is never started.

## What Docker installs (see `Dockerfile`, `compose.yaml`)

In the image: pinned Node, the lockfile-pinned Pi (checked at build time), Python 3.13 with locked
dependencies (`uv sync --locked`), the built dashboard, the pinned 384-dimensional MiniLM model at
`/app/models/minilm` (semantic search enabled), `curl` and `postgresql-client`. The database is the
`pgvector/pgvector:pg16` image.

Not in the image: a browser (managed browser sessions need Chrome on the host), any external Pi
command, and Ollama. Compose probes a host Ollama at `http://host.docker.internal:11434` and
auto-configures the Pi agent with a small detected chat model. `mxbai-embed-large` is 1024-dimensional
and is not selected because the memory schema stores 384-dimensional vectors.

Compose passes only these to the app: `DATABASE_URL`, `ALIVE_API_TOKEN` (required),
`ALIVE_ALLOWED_ORIGINS`, `ALIVE_BROWSER_ORIGINS`, `ALIVE_COGNITIVE_PROVIDER`, `ALIVE_DEMO_MODE` (and the
demo flags tied to it), `ALIVE_EMBEDDING_ENABLED`, `ALIVE_EMBEDDING_PATH`, `ALIVE_OLLAMA_URL`,
`ALIVE_OLLAMA_CHAT_MODEL`, `ALIVE_PI_COMMAND` (the pinned fallback), `ALIVE_DOCKER_PI_PROVIDER`,
`ALIVE_DOCKER_PI_MODEL`, `ALIVE_META_API_KEY` and `ALIVE_META_MODEL`. Anything else you set locally
does **not** reach the container, which runs with the default for it. The doctor's *Docker parity*
section lists the differences. To pass one through, add it under `app.environment` in `compose.yaml`.

Docker uses `ALIVE_DOCKER_PI_PROVIDER` / `ALIVE_DOCKER_PI_MODEL` so a host-only Pi configuration
(and its credentials) is not copied into the container. Leave them empty to auto-detect a small
Ollama chat model; set them only when the container has the matching provider credentials.

## Where to look

| Symptom | Look at |
| --- | --- |
| Won't start, database errors | Doctor *Database*; `DATABASE_URL`/`ALIVE_DSN` source; `docker compose logs app` |
| `401` / "token required" | `ALIVE_API_TOKEN` vs `.alive/token`; run `scripts/init.ps1` |
| A setting seems ignored | Doctor *Unrecognised variables* and the `source` column |
| Works locally, differs in Docker | Doctor *Docker parity* |
| Pi failure in the Agents tab | `ALIVE_PI_COMMAND` and `Pi agent model` checks in the doctor |
| Pi failure in workflows or Pi tests | Pinned Pi check; run the `npm ci` line above |
| Pi says model not configured | `Pi agent model` in the doctor; set `ALIVE_PI_*` or start Ollama |
| Ollama not detected | `Ollama` in the doctor; host listener must accept Docker connections |
| Search is text-only | `ALIVE_EMBEDDING_ENABLED` and the model at `ALIVE_EMBEDDING_PATH` |
| Capability missing or unavailable | `uv run python -m alive.capabilities doctor` |
| Live model calls refused | `ALIVE_META_API_KEY`, `ALIVE_COGNITIVE_PROVIDER`; budgets are enforced by the Governor |
