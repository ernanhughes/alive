from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url):
        self.engine = create_async_engine(url, pool_pre_ping=True)
        self.pg = self.engine.dialect.name == "postgresql"
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        if not self.pg:

            @event.listens_for(self.engine.sync_engine, "connect")
            def sqlite_pragmas(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA busy_timeout=5000")

    async def probe(self):
        async with self.engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            if self.pg:
                return bool(
                    await conn.scalar(
                        text("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname='vector')")
                    )
                )
        return False
