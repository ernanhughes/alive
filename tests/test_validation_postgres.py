"""Opt-in deterministic workflow qualification on an explicitly disposable local PostgreSQL."""

import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.test_validation_workflows import (  # noqa: F401 (collect the same three real graphs)
    test_distinct_deterministic_workflows_run_and_replay_without_inference,
)

URL = os.environ.get("ALIVE_TEST_VALIDATION_POSTGRES_URL", "")
pytestmark = pytest.mark.skipif(not URL, reason="requires disposable PostgreSQL URL")


@pytest.fixture
def settings(settings):
    target = make_url(URL)
    assert target.host in {"127.0.0.1", "localhost"}
    assert target.database.startswith("alive_pi03c_disposable"), (
        "refuse to reset a non-test database"
    )

    async def reset():
        engine = create_async_engine(URL)
        try:
            async with engine.begin() as connection:
                await connection.execute(text("DROP SCHEMA public CASCADE"))
                await connection.execute(text("CREATE SCHEMA public"))
                await connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        finally:
            await engine.dispose()

    asyncio.run(reset())
    settings.database_url = URL
    return settings
