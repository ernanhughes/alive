from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from alive.app import create_app
from alive.config import Settings
from alive.models import Base

TOKEN = "test-token-for-alive-tests-123456789"
MANIFESTS_DIR = Path(__file__).resolve().parents[1] / "alive/capabilities/manifests"

# Fast default (1-min target): bare `pytest` runs only these files.
# Everything else under testpaths is auto-marked `slow` and skipped unless
# explicitly requested (`pytest -o addopts=""`, `-m "slow or not slow"`,
# or `python scripts/test_run.py --mode full|affected` which overrides addopts).
# Keep this list to proven-quick unit/config files only.
FAST_FILES = {
    "tests/test_transport.py",
    "tests/test_docker_config.py",
    "tests/test_ollama.py",
    "tests/test_test_select.py",
    "tests/test_arch_boundaries.py",
    "tests/test_workflows_spec.py",
    "tests/test_validation_workflows.py",
    "tests/test_meta_memory.py",
    "tests/test_capability_registry.py",
}


def pytest_collection_modifyitems(items):
    for item in items:
        path = item.nodeid.split("::")[0].replace("\\", "/")
        if (path.startswith("tests/") or path.startswith("alive/intelligence/tests/")) and (
            path not in FAST_FILES
        ):
            item.add_marker(pytest.mark.slow)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        _env_file=None,
        alive_meta_api_key="",
        database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db",
        alive_api_token=TOKEN,
        alive_heartbeat_seconds=0.1,
        alive_workspace=tmp_path / "workspace",
        alive_ollama_url="",
        alive_pi_provider="",
        alive_pi_model="",
    )


def _boot(settings, include_experiments=False):
    import asyncio

    if include_experiments:
        # Register frozen experiment tables for SQLite create_all. Test-only
        # import; production schema comes from alembic migrations, and
        # production code must not import alive.experiment (see ARCH-01).
        import alive.experiment.service  # noqa: F401

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
    # Construct the opt-in app first so its model tables are registered even
    # when an isolated suite has not imported any experiment modules yet.
    app = create_app(settings, include_experiments=True)
    _boot(settings)
    with TestClient(
        app,
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as c:
        yield c


@pytest.fixture
def bare_client(settings):
    """Production-only app: no experiment router, no research runner."""
    _boot(settings, include_experiments=False)
    with TestClient(
        create_app(settings, include_experiments=False),
        headers={"Authorization": f"Bearer {TOKEN}"},
    ) as c:
        yield c
