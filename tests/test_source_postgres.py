"""Source custody on PostgreSQL. Opt in with a DISPOSABLE, EMPTY database:

    docker run --rm -d --name alive-pg-check -p 55433:5432 -e POSTGRES_PASSWORD=check \
        -e POSTGRES_USER=check -e POSTGRES_DB=check pgvector/pgvector:pg16
    ALIVE_TEST_POSTGRES_URL=postgresql+asyncpg://check:check@127.0.0.1:55433/check \
        uv run pytest -q tests/test_source_postgres.py
"""

import asyncio
import os
import subprocess
import sys
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.kernel import Kernel
from alive.models import now
from alive.sources import custody
from alive.workflows.context import Refused
from tests.conftest import TOKEN
from tests.test_source_custody import OP, approved, captured, refused, repo_content
from tests.workflow_execution_helpers import call

URL = os.environ.get("ALIVE_TEST_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="needs ALIVE_TEST_POSTGRES_URL (disposable DB)")


def alembic(*args):
    env = os.environ | {"DATABASE_URL": URL}
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


async def asql(kernel, statement):
    async with kernel.db.sessions() as session:
        return (await session.execute(text(statement))).fetchall()


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


def test_custody_on_postgresql_including_a_cross_process_style_race(tmp_path):
    assert not sql("SELECT 1 FROM pg_tables WHERE schemaname = 'public'"), "database must be empty"
    alembic("upgrade", "head")
    assert alembic("heads").split() == ["0015", "(head)"]  # exactly one head

    with TestClient(app_for(tmp_path), headers={"Authorization": f"Bearer {TOKEN}"}) as client:

        async def go(k):
            capture = await captured(k)
            assert (await asql(k, "SELECT count(*) FROM source_captures"))[0][0] == 1
            # Timezone-aware expiry behaves the same as on SQLite.
            approval = await approved(k, capture, ttl=3600, request="pg-request-0001")
            assert await custody.resolve(k, approval["resources"], OP)

            # Two independent kernels (own lock, own connections), as the CLI and the app are.
            other_db = Database(URL)
            second = Kernel(other_db, None, k.settings)
            second.instance_id = k.instance_id
            try:
                terms = dict(
                    confirm_sha256=capture["content_sha256"],
                    operations=[OP],
                    scope={"all": True},
                    ttl_seconds=3600,
                    principal="owner-race",
                    request_id="pg-race-request-0002",
                )
                one, two = await asyncio.gather(
                    custody.approve(k, capture["id"], **terms),
                    custody.approve(second, capture["id"], **terms),
                )
                assert one["id"] == two["id"]  # the loser returned the winner's decision
                rows = await asql(
                    k, "SELECT count(*) FROM source_approvals WHERE idempotency_key IS NOT NULL"
                )
                assert rows[0][0] == 2  # the first approval and the raced one: never three
            finally:
                await other_db.engine.dispose()

            # Withdrawal and expiry are honoured by every reader of the database.
            await custody.withdraw(k, approval["id"], reason="withdrawn", principal="owner-race")
            with refused("source_withdrawn"):
                await custody.resolve(k, approval["resources"], OP)
            fresh = await approved(k, capture, ttl=60, request="pg-request-0003")
            async with k.db.sessions.begin() as session:  # expire it in the database itself
                await session.execute(
                    text("UPDATE source_approvals SET expires_at = :t WHERE id = :i"),
                    {"t": now() - timedelta(seconds=1), "i": fresh["id"]},
                )
            with refused("source_approval_expired"):
                await custody.resolve(k, fresh["resources"], OP)
            # Content altered underneath the application is detected on PostgreSQL too.
            await session_tamper(k, capture["id"])
            with pytest.raises(Refused, match="source_content_changed"):
                await custody.resolve(
                    k, (await approved(k, capture, request="pg-request-0004"))["resources"], OP
                )

        call(client, go)

    before = {
        t: sql(f"SELECT count(*) FROM {t}")[0][0]
        for t in ("events", "alive_instances", "source_captures", "source_approvals")
    }
    alembic("downgrade", "0012")
    assert not sql("SELECT 1 FROM pg_tables WHERE tablename LIKE 'source_%'")
    assert sql("SELECT count(*) FROM events")[0][0] == before["events"]  # older data untouched
    alembic("upgrade", "head")
    assert sql("SELECT count(*) FROM source_captures")[0][0] == 0  # downgrade discards custody
    assert alembic("heads").split() == ["0015", "(head)"]


async def session_tamper(kernel, capture_id):
    async with kernel.db.sessions.begin() as session:
        await session.execute(
            text("UPDATE source_captures SET content = CAST(:c AS jsonb) WHERE id = :i"),
            {"c": __import__("json").dumps(repo_content({"x.txt": "changed"})), "i": capture_id},
        )
