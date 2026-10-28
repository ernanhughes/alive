"""Run the isolated, zero-spend ALIVE-DEMO-LIVE-01 backend (no migrations).

Usage: uv run python scripts/demo_live_01.py --port 8000
Connect the existing unpacked extension using the token file printed at startup.
"""

import argparse
import asyncio
import os
import secrets
from pathlib import Path

from alive.app import create_app
from alive.config import Settings
from alive.db import Database
from alive.models import Base


def environment(directory, port):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    token_file = directory / "token"
    if not token_file.exists():
        token_file.write_text(secrets.token_urlsafe(40), encoding="utf-8")
    token = token_file.read_text(encoding="utf-8").strip()
    backend = f"http://127.0.0.1:{port}"
    names = ["python-3.11.html", "python-3.12.html", "synthetic-no-change.html"]
    env = os.environ | {
        "DATABASE_URL": f"sqlite+aiosqlite:///{(directory / 'demo.db').as_posix()}",
        "ALIVE_API_TOKEN": token,
        "ALIVE_WORKSPACE": str(directory / "workspace"),
        "ALIVE_META_API_KEY": "",
        "MODEL_API_KEY": "",
        "META_API_KEY": "",
        "ALIVE_META_BASE_URL": "http://127.0.0.1:1",
        "ALIVE_CLAIM_META_ENABLED": "false",
        "ALIVE_RESEARCH_META_ENABLED": "false",
        "ALIVE_RELATIONSHIP_ALLOW_TEST_PROVIDERS": "true",
        "ALIVE_NATIVE_TEST_PAGES": ",".join(backend + "/demo-live-01/" + name for name in names),
        "ALIVE_EMBEDDING_ENABLED": "false",
        "ALIVE_COGNITIVE_PROVIDER": "mock",
    }
    return env, token


async def prepare_schema(url):
    database = Database(url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await database.engine.dispose()


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--directory", default=".alive/demo-live-01")
    args = parser.parse_args()
    env, _ = environment(args.directory, args.port)
    os.environ.update(env)
    settings = Settings(_env_file=None)
    asyncio.run(prepare_schema(settings.database_url))
    print("Local fixture demonstration only. Paid inference is disabled.")
    print("Connect using token file:", Path(args.directory).resolve() / "token")
    uvicorn.run(create_app(settings), host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()
