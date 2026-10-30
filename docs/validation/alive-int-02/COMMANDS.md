# Qualification commands

Executed from `C:/Projects/alive-int-02-delivery` unless stated otherwise.
PowerShell `$py` is `C:/Projects/alive/.venv/Scripts/python.exe`;
`PYTHONDONTWRITEBYTECODE=1`. `.log` / JSON receipts accompany this file.

```powershell
git fetch origin main
git worktree add -b codex/alive-int-02-delivery C:/Projects/alive-int-02-delivery origin/main
git cherry-pick 72d9cb8b48f9917f1235cf72e79eeabe3ed12250 a2b20a3713458862bd6efd4f5305d7372188c86c

# In C:/Projects/alive-intelligence-01 before integration:
& $py -B -m pytest -q alive/intelligence/tests -p no:cacheprovider --confcutdir=alive/intelligence/tests
& $py -B -m pytest -q tests/test_model_gateway.py tests/test_learning.py tests/test_living.py tests/test_cognition.py -p no:cacheprovider --basetemp=alive/intelligence/.test-tmp -o tmp_path_retention_policy=failed
& $py -B -m alive.intelligence.example

# Final delivery source:
& $py -B -m pytest -q alive/intelligence/tests tests/test_intelligence_durable.py tests/test_intelligence_receipts.py tests/test_intelligence_migration.py -p no:cacheprovider
& $py -B -m pytest -q -p no:cacheprovider
& $py -B -m scripts.intelligence_mutations
& $py -B -m ruff check --no-cache alive migrations scripts tests
& $py -B -m ruff format --no-cache --check alive migrations scripts tests
npm.cmd ci --ignore-scripts --prefix pi-runtime
npm.cmd ci --ignore-scripts --prefix dashboard
& $py -B -m pytest -q tests/test_pi_real.py -p no:cacheprovider
& $py -B -m scripts.pi_integration
npm.cmd test --prefix dashboard
npm.cmd run build --prefix dashboard
node --test tests/extension-panel.test.cjs tests/extension-background.test.cjs tests/extension-capture.test.cjs tests/extension-live-background.test.cjs tests/extension-live-companion.test.cjs
docker build -t alive-int02-delivery:qualification .
```

Docker qualification used a new network `alive-int02-delivery-net` and a dedicated
`pgvector/pgvector:pg17` container named `alive-int02-delivery-db`. Its disposable
test user/database were `int02`; the test password was `int02-ephemeral-local`.
No existing database was used. The test API token was
`int02-delivery-ephemeral-test-token`, with empty `ALIVE_META_API_KEY`.

The following commands ran inside the final image with those explicit environment
settings and, for the harnesses, a read-only mount of the named script under
`/app/scripts/` (the normal image deliberately includes only its existing Docker
entrypoint scripts):

```sh
# Separate disposable databases: int02_workflows, int02_final, int02_migrations.
python -m scripts.workflows_check
python -m scripts.intelligence_check
alembic upgrade head
alembic downgrade 0008
alembic upgrade head
alembic current
```

The final app exposed loopback port 18040. Host smoke:

```powershell
& $py -B scripts/docker-smoke-test.py --base-url http://127.0.0.1:18040
docker restart alive-int02-delivery-final-app
```

Authenticated GETs of the exact state ID from `process-postgresql.json` were
asserted equal to the saved chain before restart and three times after it.
PostgreSQL counts before/after used:

```sql
SELECT (SELECT count(*) FROM intelligence_feedback),
       (SELECT count(*) FROM intelligence_learning_updates),
       (SELECT count(*) FROM intelligence_measurement_uses),
       (SELECT count(*) FROM model_invocations), (SELECT count(*) FROM pi_runs);
```

Linux ran in the **final image**, with root tests and isolated package tests mounted
read-only, and locked development dependencies installed only into that throwaway
container:

```sh
uv sync --locked --group dev
.venv/bin/python -B -m pytest -q -p no:cacheprovider alive/intelligence/tests tests/test_intelligence_durable.py tests/test_intelligence_receipts.py tests/test_intelligence_migration.py tests/test_pi_state.py tests/test_pi_gateway.py tests/test_pi_egress.py tests/test_pi_runner.py tests/test_pi_process.py tests/test_pi_lifecycle.py tests/test_pi_real.py
```

Owned app/database containers were stopped after qualification and retained for
inspection. Existing containers were not stopped. A separate temporary native
PostgreSQL 18 cluster also passed the earlier four-table lifecycle/migration run;
it was stopped and retained in ignored `.alive/int02-pgdata`. Final five-table
qualification uses the final Docker image/receipts above.
