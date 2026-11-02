import asyncio
import sys

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

from alive.config import Settings
from alive.db_target import DatabaseTargetError, migration_database_url
from alive.models import Base


def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    # Resolve and refuse BEFORE creating an engine. A conflicting inherited DSN must
    # never reach a database connection or apply a migration.
    try:
        url = migration_database_url(Settings())
    except DatabaseTargetError as error:
        print(f"database target refused: {error}", file=sys.stderr)
        raise SystemExit(1) from None

    engine = create_async_engine(url)
    async with engine.connect() as connection:
        await connection.run_sync(run)
    await engine.dispose()


asyncio.run(online())
