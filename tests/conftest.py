import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.models import Base

TOKEN = "test-token-for-alive-tests-123456789"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        alive_meta_api_key="",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        alive_api_token=TOKEN,
        alive_heartbeat_seconds=0.1,
        alive_workspace=tmp_path / "workspace",
    )


def _boot(settings):
    import asyncio

    from alive.db import Database

    async def schema():
        db = Database(settings.database_url)
        async with db.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await db.engine.dispose()

    asyncio.run(schema())


@pytest.fixture
def client(settings):
    # ARCH-01: the shared test client opts into the research harness so the
    # frozen ALIVE-03 experiment suite keeps exercising the full API. Default
    # production startup (create_app without flags) excludes it; see
    # test_arch_boundaries.py.
    _boot(settings)
    with TestClient(
        create_app(settings, include_experiments=True),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as c:
        yield c


@pytest.fixture
def bare_client(settings):
    """Production-only app: no experiment router, no research runner."""
    _boot(settings)
    with TestClient(
        create_app(settings, include_experiments=False),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as c:
        yield c
