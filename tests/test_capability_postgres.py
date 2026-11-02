"""Migration 0011 on PostgreSQL with real rows. Opt in with a DISPOSABLE, EMPTY database:

    docker run --rm -d --name alive-pg-check -p 55433:5432 -e POSTGRES_PASSWORD=check \
        -e POSTGRES_USER=check -e POSTGRES_DB=check pgvector/pgvector:pg16
    ALIVE_TEST_POSTGRES_URL=postgresql+asyncpg://check:check@127.0.0.1:55433/check \
        uv run pytest -q tests/test_capability_postgres.py

The test refuses a database that already has tables. Downgrading 0011 discards the retained
capability bindings by design (the tables/columns are dropped); everything older must survive.
"""

import asyncio
import os
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from alive.app import create_app
from alive.config import Settings
from alive.workflows import store
from alive.workflows.examples import definition
from tests.conftest import TOKEN, database_env
from tests.workflow_execution_helpers import call, lifecycle, observation, prepare

URL = os.environ.get("ALIVE_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="needs ALIVE_TEST_POSTGRES_URL (disposable DB)")
TABLES = ("workflow_definitions", "workflow_runs", "workflow_stage_runs", "workflow_executions")


def alembic(*args):
    env = database_env(
        DATABASE_URL=URL, ALIVE_DB_TARGET="disposable:" + str(make_url(URL).database)
    )
    done = subprocess.run(
        [sys.executable, "-B", "-m", "alembic", *args], env=env, capture_output=True, text=True
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return done.stdout


def sql(statement):
    async def run():
        engine = create_async_engine(URL)
        try:
            async with engine.connect() as connection:
                return (await connection.execute(text(statement))).fetchall()
        finally:
            await engine.dispose()

    return asyncio.run(run())


def counts():
    return {t: sql(f"SELECT count(*) FROM {t}")[0][0] for t in TABLES}


def columns(table):
    rows = sql(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table}'")
    return {r[0] for r in rows}


def app_for(tmp_path):
    settings = Settings(
        _env_file=None,
        alive_meta_api_key="",
        database_url=URL,
        alive_api_token=TOKEN,
        alive_heartbeat_seconds=0.1,
        alive_workspace=tmp_path / "workspace",
    )
    return create_app(settings, include_experiments=True)


def test_0011_upgrade_downgrade_and_reupgrade_preserve_history(tmp_path):
    assert not sql("SELECT 1 FROM pg_tables WHERE schemaname = 'public'"), "database must be empty"
    alembic("upgrade", "head")
    assert alembic("heads").split() == ["0015", "(head)"]  # exactly one head

    with TestClient(app_for(tmp_path), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        prepare(client)
        observation(client)
        run, _ = call(
            client, lambda k: lifecycle(k, client.app.state.cognition, client.app.state.workflows)
        )
        assert run["status"] == "COMPLETED"
        before = call(client, store.get_stage_runs, run["id"])
        assert all(s["capability"]["version"] == "1.0.0" for s in before)
    original = counts()
    assert all(original.values()) and sql("SELECT count(*) FROM workflow_capability_bindings")[0][0]

    alembic("downgrade", "0010")
    assert counts() == original  # nothing older than 0011 is lost
    assert not sql("SELECT 1 FROM pg_tables WHERE tablename = 'workflow_capability_bindings'")
    assert "capability_snapshot" not in columns("workflow_executions")

    alembic("upgrade", "head")
    assert counts() == original
    assert {"capability_snapshot", "capability_snapshot_sha256"} <= columns("workflow_executions")
    assert sql("SELECT count(*) FROM workflow_capability_bindings")[0][0] == 0
    snapshots = sql(
        "SELECT capability_snapshot, capability_snapshot_sha256 FROM workflow_executions"
    )
    assert all(row[0] == {} and row[1] is None for row in snapshots)  # unlabelled, not invented

    with TestClient(app_for(tmp_path), headers={"Authorization": f"Bearer {TOKEN}"}) as client:
        after = client.get(f"/api/v1/workflow-runs/{run['id']}/stages")
        assert after.status_code == 200
        assert all("capability" not in s for s in after.json()["stages"])  # never attributed
        assert client.get(f"/api/v1/workflow-runs/{run['id']}/inspection").status_code == 200
        assert client.get(f"/api/v1/workflow-runs/{run['id']}/artifacts/record").status_code == 200
        # The definition now has no binding: it is genuine history, so re-registering the same
        # bytes adopts it under its original contract rather than demanding the modern one.
        call(client, store.register_definition, definition(model=False), status="active")
    bound = sql(
        "SELECT b.snapshot FROM workflow_capability_bindings b "
        "JOIN workflow_definitions d ON d.id = b.definition_id WHERE d.name = 'source-comparison'"
    )
    assert len(bound) == 1
    assert all(stage["legacy_contract"] for stage in bound[0][0]["stages"].values())
    # Startup also re-seeds the shipped definition, which is adopted the same way.
    assert sql("SELECT count(*) FROM workflow_capability_bindings")[0][0] == 2
    assert alembic("heads").split() == ["0015", "(head)"]
